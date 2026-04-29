import asyncio
import csv
import hashlib
import io
import secrets
import time
from decimal import Decimal
from urllib.parse import urlencode

from fastapi import Depends, FastAPI, Form, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from core.config import settings
from core.database import connect, init_db
from core.security import read_session, sign_session
from models.schemas import Actor
from realtime.manager import manager
from services.auth_service import AuthService
from services.game_orchestrator import GameOrchestrator
from services.hierarchy_service import HierarchyService, is_valid_email
from services.wallet_service import WalletService
from tasks.celery_app import send_email_job
from utils.identity import generate_account_id, generate_password

app = FastAPI(title="Luck Game")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")
CAPTCHA_STORE: dict[str, tuple[int, float]] = {}
OTP_STORE: dict[str, tuple[str, str, str, float]] = {}
CHILD_EMAIL_OTP_STORE: dict[str, dict[str, str | float | bool]] = {}
CHILD_EMAIL_OTP_RATE: dict[str, list[float]] = {}
OTP_TTL_SECONDS = 30 * 60
OTP_SEND_COOLDOWN_SECONDS = 60
OTP_SEND_WINDOW_SECONDS = 30 * 60
OTP_SEND_MAX_PER_WINDOW = 5


def back_to(path: str, *, error: str | None = None, notice: str | None = None) -> RedirectResponse:
    params = {}
    if error:
        params["error"] = error
    if notice:
        params["notice"] = notice
    target = path if not params else f"{path}?{urlencode(params)}"
    return RedirectResponse(target, status_code=303)


def make_captcha() -> dict[str, str]:
    left = secrets.randbelow(8) + 2
    right = secrets.randbelow(8) + 2
    token = secrets.token_urlsafe(24)
    CAPTCHA_STORE[token] = (left + right, time.time() + 600)
    return {"token": token, "question": f"{left} + {right}"}


def verify_captcha(token: str, answer: str) -> bool:
    expected = CAPTCHA_STORE.pop(token, None)
    if not expected or expected[1] < time.time():
        return False
    try:
        return int(answer.strip()) == expected[0]
    except ValueError:
        return False


def otp_hash(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


def queue_email(to_address: str | None, subject: str, body: str) -> dict:
    if not to_address:
        return {"sent": False, "error": "Missing recipient email address."}
    try:
        send_email_job.apply_async(args=[to_address, subject, body])
        return {"sent": True, "queued": True, "to": to_address}
    except Exception:
        return send_email_job(to_address, subject, body)


@app.on_event("startup")
def startup() -> None:
    init_db()


def db():
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


def current_actor(request: Request, conn=Depends(db)) -> Actor:
    session = read_session(request.cookies.get("luck_session"))
    if not session:
        raise HTTPException(status_code=401)
    actor = AuthService(conn).get_actor(session[0])
    if not actor:
        raise HTTPException(status_code=401)
    if actor.status != "ACTIVE":
        active_game = GameOrchestrator(conn).active_game_for_player(actor)
        if not active_game or not (request.url.path.startswith("/games") or request.url.path == "/api/me"):
            raise HTTPException(status_code=401)
    return actor


@app.get("/", response_class=HTMLResponse)
def index(request: Request, error: str = "", notice: str = ""):
    return templates.TemplateResponse(
        "login.html",
        {"request": request, "captcha": make_captcha(), "error": error, "notice": notice},
    )


@app.post("/login")
def login(
    request: Request,
    role: str = Form(...),
    username: str = Form(...),
    password: str = Form(...),
    captcha_token: str = Form(...),
    captcha_answer: str = Form(...),
    conn=Depends(db),
):
    if not verify_captcha(captcha_token, captcha_answer):
        return back_to("/", error="Captcha validation failed.")
    auth = AuthService(conn)
    actor = auth.verify_credentials(username, password, role)
    if not actor:
        if auth.credential_failure_reason(username, password, role) == "inactive":
            return back_to("/", error="Currently you are inactive please contact your agent")
        return back_to("/", error="Invalid login details.")
    if role in {"ADMIN", "AGENT"}:
        if not actor.email:
            return back_to("/", error="This account does not have an email for OTP login.")
        code = f"{secrets.randbelow(900000) + 100000}"
        otp_token = secrets.token_urlsafe(32)
        OTP_STORE[otp_token] = (actor.id, actor.role, otp_hash(code), time.time() + OTP_TTL_SECONDS)
        delivery = queue_email(actor.email, "Luck Game login OTP", f"Your Luck Game login OTP is {code}. It expires in 30 minutes.")
        return templates.TemplateResponse(
            "otp.html",
            {
                "request": request,
                "otp_token": otp_token,
                "role": role,
                "username": username,
                "error": "",
                "delivery": delivery,
                "dev_otp": code if not settings.smtp_host else "",
            },
        )
    token = AuthService(conn).login(username, password, role)
    redirect = RedirectResponse("/dashboard", status_code=303)
    redirect.set_cookie("luck_session", token, httponly=True, samesite="lax")
    return redirect


@app.post("/login/otp")
def login_otp(otp_token: str = Form(...), otp_code: str = Form(...), conn=Depends(db)):
    pending = OTP_STORE.pop(otp_token, None)
    if not pending or pending[3] < time.time() or not secrets.compare_digest(pending[2], otp_hash(otp_code.strip())):
        return back_to("/", error="OTP validation failed.")
    actor = AuthService(conn).get_actor(pending[0])
    if not actor or actor.role != pending[1] or actor.status != "ACTIVE":
        return back_to("/", error="Account is not active.")
    redirect = RedirectResponse("/dashboard", status_code=303)
    redirect.set_cookie("luck_session", sign_session(actor.id, actor.role), httponly=True, samesite="lax")
    return redirect


@app.post("/logout")
def logout():
    redirect = RedirectResponse("/", status_code=303)
    redirect.delete_cookie("luck_session")
    return redirect


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(
    request: Request,
    q: str = "",
    role_filter: str = "ALL",
    page: int = 1,
    error: str = "",
    notice: str = "",
    actor: Actor = Depends(current_actor),
    conn=Depends(db),
):
    children, child_total = HierarchyService(conn).list_children_page(actor, q, role_filter, page, 20)
    txs = WalletService(conn).transactions_for_actor(actor)[:20]
    page = max(page, 1)
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "actor": actor,
            "children": children,
            "transactions": txs,
            "q": q,
            "role_filter": role_filter if role_filter in {"ALL", "USER", "AGENT"} else "ALL",
            "page": page,
            "child_total": child_total,
            "has_prev": page > 1,
            "has_next": page * 20 < child_total,
            "error": error,
            "notice": notice,
        },
    )


@app.post("/children")
def create_child(
    username: str = Form(...),
    display_name: str = Form(...),
    email: str = Form(""),
    role: str = Form(...),
    password: str = Form(...),
    email_otp_token: str = Form(""),
    actor: Actor = Depends(current_actor),
    conn=Depends(db),
):
    try:
        if role == "AGENT":
            _require_verified_child_email(actor, email, email_otp_token)
        HierarchyService(conn).create_child(actor, username, display_name, email, role, password)
        if email_otp_token:
            CHILD_EMAIL_OTP_STORE.pop(email_otp_token, None)
        return back_to("/dashboard", notice="Account created successfully.")
    except (PermissionError, ValueError) as exc:
        return back_to("/dashboard", error=str(exc))


def _require_verified_child_email(actor: Actor, email: str, token: str) -> None:
    pending = CHILD_EMAIL_OTP_STORE.get(token)
    if (
        not pending
        or pending["expires_at"] < time.time()
        or pending["creator_id"] != actor.id
        or pending["email"] != email.strip()
        or not pending["verified"]
    ):
        raise ValueError("Verify the agent email with OTP before generating credentials.")


def _check_otp_send_rate(key: str) -> int:
    now = time.time()
    attempts = [stamp for stamp in CHILD_EMAIL_OTP_RATE.get(key, []) if stamp > now - OTP_SEND_WINDOW_SECONDS]
    if attempts and now - attempts[-1] < OTP_SEND_COOLDOWN_SECONDS:
        return int(OTP_SEND_COOLDOWN_SECONDS - (now - attempts[-1])) + 1
    if len(attempts) >= OTP_SEND_MAX_PER_WINDOW:
        return int(OTP_SEND_WINDOW_SECONDS - (now - attempts[0])) + 1
    attempts.append(now)
    CHILD_EMAIL_OTP_RATE[key] = attempts
    return 0


@app.post("/children/email-otp/send")
def send_child_email_otp(request: Request, email: str = Form(...), role: str = Form("AGENT"), actor: Actor = Depends(current_actor)):
    email = email.strip()
    if not HierarchyService.can_create(actor, role):
        raise HTTPException(status_code=403)
    if role != "AGENT":
        return JSONResponse({"required": False, "verified": True})
    if not is_valid_email(email):
        raise HTTPException(status_code=400, detail="Enter a valid agent email first.")
    retry_after = _check_otp_send_rate(f"{actor.id}:{email}:{request.client.host if request.client else 'unknown'}")
    if retry_after:
        raise HTTPException(status_code=429, detail=f"Please wait {retry_after} seconds before requesting another OTP.")
    code = f"{secrets.randbelow(900000) + 100000}"
    token = secrets.token_urlsafe(32)
    CHILD_EMAIL_OTP_STORE[token] = {
        "creator_id": actor.id,
        "email": email,
        "code_hash": otp_hash(code),
        "expires_at": time.time() + OTP_TTL_SECONDS,
        "verified": False,
    }
    delivery = queue_email(
        email,
        "Luck Game agent email verification OTP",
        f"Your Luck Game agent email verification OTP is {code}. It expires in 30 minutes.",
    )
    return JSONResponse(
        {
            "required": True,
            "token": token,
            "delivery": delivery,
            "dev_otp": code if not settings.smtp_host else "",
        }
    )


@app.post("/children/email-otp/verify")
def verify_child_email_otp(
    email: str = Form(...),
    otp_token: str = Form(...),
    otp_code: str = Form(...),
    actor: Actor = Depends(current_actor),
):
    pending = CHILD_EMAIL_OTP_STORE.get(otp_token)
    if (
        not pending
        or pending["expires_at"] < time.time()
        or pending["creator_id"] != actor.id
        or pending["email"] != email.strip()
        or not secrets.compare_digest(str(pending["code_hash"]), otp_hash(otp_code.strip()))
    ):
        raise HTTPException(status_code=400, detail="OTP validation failed.")
    pending["verified"] = True
    return JSONResponse({"verified": True})


@app.get("/credentials/generate")
def generate_credentials(
    display_name: str,
    role: str = "AGENT",
    email: str = "",
    email_otp_token: str = "",
    actor: Actor = Depends(current_actor),
):
    if actor.role == "USER":
        raise HTTPException(status_code=403)
    if not HierarchyService.can_create(actor, role):
        raise HTTPException(status_code=403)
    if role == "AGENT":
        if not is_valid_email(email):
            raise HTTPException(status_code=400, detail="Enter a valid agent email first.")
        try:
            _require_verified_child_email(actor, email, email_otp_token)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
    return JSONResponse({"username": generate_account_id(display_name), "password": generate_password()})


@app.post("/wallet/admin/adjust")
def adjust_admin_money(
    direction: str = Form(...),
    amount: Decimal = Form(...),
    actor: Actor = Depends(current_actor),
    conn=Depends(db),
):
    try:
        WalletService(conn).adjust_admin_balance(actor, amount, direction)
        return back_to("/dashboard", notice="Admin balance updated successfully.")
    except (PermissionError, ValueError) as exc:
        return back_to("/dashboard", error=str(exc))


@app.post("/children/{child_id}/status")
def set_status(child_id: str, status: str = Form(...), actor: Actor = Depends(current_actor), conn=Depends(db)):
    try:
        HierarchyService(conn).set_status(actor, child_id, status)
        return back_to("/dashboard", notice="Status updated successfully.")
    except (PermissionError, ValueError) as exc:
        return back_to("/dashboard", error=str(exc))


@app.post("/children/status")
def set_status_from_form(
    child_id: str = Form(...),
    status: str = Form(...),
    actor: Actor = Depends(current_actor),
    conn=Depends(db),
):
    return set_status(child_id, status, actor, conn)


@app.post("/password/update")
def update_password(
    old_password: str = Form(...),
    new_password: str = Form(...),
    actor: Actor = Depends(current_actor),
    conn=Depends(db),
):
    if actor.role == "ADMIN":
        return back_to("/dashboard", error="Admin password cannot be changed from this page.")
    try:
        HierarchyService(conn).update_password(actor, old_password, new_password)
        return back_to("/dashboard", notice="Password updated successfully.")
    except ValueError as exc:
        return back_to("/dashboard", error=str(exc))


@app.post("/children/regenerate-password")
def regenerate_child_password(child_id: str = Form(...), actor: Actor = Depends(current_actor), conn=Depends(db)):
    try:
        new_password = HierarchyService(conn).regenerate_child_password(actor, child_id)
        return back_to("/dashboard", notice=f"New password for {child_id}: {new_password}")
    except (PermissionError, ValueError) as exc:
        return back_to("/dashboard", error=str(exc))


@app.post("/children/{child_id}/delete")
def delete_child(child_id: str, actor: Actor = Depends(current_actor), conn=Depends(db)):
    try:
        HierarchyService(conn).delete_child_subtree(actor, child_id)
        return back_to("/dashboard", notice="Account subtree removed successfully.")
    except (PermissionError, ValueError) as exc:
        return back_to("/dashboard", error=str(exc))


@app.post("/children/delete")
def delete_child_from_form(child_id: str = Form(...), actor: Actor = Depends(current_actor), conn=Depends(db)):
    return delete_child(child_id, actor, conn)


@app.post("/wallet/{child_id}/add")
def add_money(child_id: str, amount: Decimal = Form(...), actor: Actor = Depends(current_actor), conn=Depends(db)):
    try:
        WalletService(conn).add_money(actor, child_id, amount)
        return back_to("/dashboard", notice="Money added successfully.")
    except (PermissionError, ValueError) as exc:
        return back_to("/dashboard", error=str(exc))


@app.post("/wallet/add")
def add_money_from_form(
    child_id: str = Form(...),
    amount: Decimal = Form(...),
    actor: Actor = Depends(current_actor),
    conn=Depends(db),
):
    return add_money(child_id, amount, actor, conn)


@app.post("/wallet/{child_id}/deduct")
def deduct_money(child_id: str, amount: Decimal = Form(...), actor: Actor = Depends(current_actor), conn=Depends(db)):
    try:
        WalletService(conn).deduct_money(actor, child_id, amount)
        return back_to("/dashboard", notice="Money deducted successfully.")
    except (PermissionError, ValueError) as exc:
        return back_to("/dashboard", error=str(exc))


@app.post("/wallet/deduct")
def deduct_money_from_form(
    child_id: str = Form(...),
    amount: Decimal = Form(...),
    actor: Actor = Depends(current_actor),
    conn=Depends(db),
):
    return deduct_money(child_id, amount, actor, conn)


@app.get("/download/transactions")
def download_transactions(actor: Actor = Depends(current_actor), conn=Depends(db)):
    rows = WalletService(conn).transactions_for_actor(actor)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["created_at", "type", "amount", "net_amount", "from_wallet", "to_wallet", "status"])
    for row in rows:
        writer.writerow([row["created_at"], row["transaction_type"], row["amount"], row["net_amount"], row["from_wallet_id"], row["to_wallet_id"], row["status"]])
    output.seek(0)
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=transactions.csv"})


@app.get("/download/children")
def download_children(actor: Actor = Depends(current_actor), conn=Depends(db)):
    children = HierarchyService(conn).list_children(actor)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "username", "display_name", "role", "status", "balance"])
    for child in children:
        writer.writerow([child.id, child.username, child.display_name, child.role, child.status, f"{child.balance:.3f}"])
    output.seek(0)
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=children.csv"})


@app.get("/game", response_class=HTMLResponse)
@app.get("/games", response_class=HTMLResponse)
def games(request: Request, error: str = "", notice: str = "", actor: Actor = Depends(current_actor), conn=Depends(db)):
    active = GameOrchestrator(conn).active_game_for_player(actor)
    return templates.TemplateResponse(
        "games.html",
        {
            "request": request,
            "actor": actor,
            "games": GameOrchestrator.available_games(),
            "active_game": active,
            "error": error,
            "notice": notice,
        },
    )


@app.get("/games/{game_key}", response_class=HTMLResponse)
def game_console(
    game_key: str,
    request: Request,
    error: str = "",
    notice: str = "",
    actor: Actor = Depends(current_actor),
    conn=Depends(db),
):
    try:
        orchestrator = GameOrchestrator(conn, game_key)
    except ValueError:
        raise HTTPException(status_code=404)
    active = orchestrator.active_game_for_player(actor)
    if active and active["game_key"] != game_key:
        return back_to("/games", error=f"You already have an active {active['title']} round.")
    template = "andar_bahar.html" if game_key == "andar-bahar" else "tin_patti.html"
    return templates.TemplateResponse(
        template,
        {
            "request": request,
            "actor": actor,
            "game": {"key": game_key, "title": orchestrator.definition["title"]},
            "error": error,
            "notice": notice,
        },
    )


@app.get("/api/me")
def api_me(actor: Actor = Depends(current_actor), conn=Depends(db)):
    refreshed = AuthService(conn).get_actor(actor.id)
    if not refreshed:
        raise HTTPException(status_code=401)
    active = GameOrchestrator(conn).active_game_for_player(refreshed)
    return JSONResponse(
        {
            "id": refreshed.username,
            "display_name": refreshed.display_name,
            "role": refreshed.role,
            "balance": f"{refreshed.balance:.3f}",
            "active_game": active,
        }
    )


@app.post("/games/{game_key}/betting/open")
async def open_betting(game_key: str, actor: Actor = Depends(current_actor), conn=Depends(db)):
    if actor.status != "ACTIVE":
        return back_to(f"/games/{game_key}", error="Currently you are inactive please contact your agent")
    try:
        await GameOrchestrator(conn, game_key).open_betting()
        return back_to(f"/games/{game_key}", notice="Betting opened successfully.")
    except ValueError as exc:
        return back_to(f"/games/{game_key}", error=str(exc))


@app.post("/games/{game_key}/bet")
async def bet(game_key: str, side: str = Form(...), amount: Decimal = Form(...), actor: Actor = Depends(current_actor), conn=Depends(db)):
    if actor.status != "ACTIVE":
        return back_to(f"/games/{game_key}", error="Currently you are inactive please contact your agent")
    try:
        await GameOrchestrator(conn, game_key).place_bet(actor, side, amount)
        return back_to(f"/games/{game_key}", notice="Bet placed successfully.")
    except (PermissionError, ValueError) as exc:
        return back_to(f"/games/{game_key}", error=str(exc))


@app.post("/games/{game_key}/start")
async def start_game(game_key: str, actor: Actor = Depends(current_actor), conn=Depends(db)):
    if actor.status != "ACTIVE":
        return back_to(f"/games/{game_key}", error="Currently you are inactive please contact your agent")
    try:
        orchestrator = GameOrchestrator(conn, game_key)
    except ValueError:
        raise HTTPException(status_code=404)
    if orchestrator.current_state()["in_progress"]:
        return back_to(f"/games/{game_key}", error=f"A {orchestrator.definition['title']} round is already running.")

    async def run_with_own_connection():
        own_conn = connect()
        try:
            await GameOrchestrator(own_conn, game_key).run_round()
        finally:
            own_conn.close()

    asyncio.create_task(run_with_own_connection())
    return back_to(f"/games/{game_key}", notice="Round started.")


@app.websocket("/ws/games/{game_key}")
async def game_ws(game_key: str, websocket: WebSocket):
    await manager.connect(websocket)
    conn = connect()
    try:
        await websocket.send_json({"event": "server_state", "data": GameOrchestrator(conn, game_key).current_state()})
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    finally:
        conn.close()


@app.websocket("/ws/game")
async def legacy_game_ws(websocket: WebSocket):
    await game_ws("tin-patti", websocket)
