import asyncio
import csv
import io
from decimal import Decimal
from urllib.parse import urlencode

from fastapi import Depends, FastAPI, Form, HTTPException, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from core.database import connect, init_db
from core.security import read_session
from models.schemas import Actor
from realtime.manager import manager
from services.auth_service import AuthService
from services.game_orchestrator import GameOrchestrator
from services.hierarchy_service import HierarchyService
from services.wallet_service import WalletService

app = FastAPI(title="Luck Game")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


def back_to(path: str, *, error: str | None = None, notice: str | None = None) -> RedirectResponse:
    params = {}
    if error:
        params["error"] = error
    if notice:
        params["notice"] = notice
    target = path if not params else f"{path}?{urlencode(params)}"
    return RedirectResponse(target, status_code=303)


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
    if not actor or actor.status != "ACTIVE":
        raise HTTPException(status_code=401)
    return actor


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login")
def login(response: Response, role: str = Form(...), username: str = Form(...), password: str = Form(...), conn=Depends(db)):
    token = AuthService(conn).login(username, password, role)
    if not token:
        return RedirectResponse("/?error=1", status_code=303)
    redirect = RedirectResponse("/dashboard", status_code=303)
    redirect.set_cookie("luck_session", token, httponly=True, samesite="lax")
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
    error: str = "",
    notice: str = "",
    actor: Actor = Depends(current_actor),
    conn=Depends(db),
):
    children = HierarchyService(conn).list_children(actor, q)
    txs = WalletService(conn).transactions_for_actor(actor)[:20]
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "actor": actor,
            "children": children,
            "transactions": txs,
            "q": q,
            "error": error,
            "notice": notice,
        },
    )


@app.post("/children")
def create_child(
    username: str = Form(...),
    display_name: str = Form(...),
    role: str = Form(...),
    password: str = Form(...),
    actor: Actor = Depends(current_actor),
    conn=Depends(db),
):
    try:
        HierarchyService(conn).create_child(actor, username, display_name, role, password)
        return back_to("/dashboard", notice="Account created successfully.")
    except (PermissionError, ValueError) as exc:
        return back_to("/dashboard", error=str(exc))


@app.post("/children/{child_id}/status")
def set_status(child_id: str, status: str = Form(...), actor: Actor = Depends(current_actor), conn=Depends(db)):
    try:
        HierarchyService(conn).set_status(actor, child_id, status)
        return back_to("/dashboard", notice="Status updated successfully.")
    except (PermissionError, ValueError) as exc:
        return back_to("/dashboard", error=str(exc))


@app.post("/children/{child_id}/delete")
def delete_child(child_id: str, actor: Actor = Depends(current_actor), conn=Depends(db)):
    try:
        HierarchyService(conn).delete_child_subtree(actor, child_id)
        return back_to("/dashboard", notice="Account subtree removed successfully.")
    except (PermissionError, ValueError) as exc:
        return back_to("/dashboard", error=str(exc))


@app.post("/wallet/{child_id}/add")
def add_money(child_id: str, amount: Decimal = Form(...), actor: Actor = Depends(current_actor), conn=Depends(db)):
    try:
        WalletService(conn).add_money(actor, child_id, amount)
        return back_to("/dashboard", notice="Money added successfully.")
    except (PermissionError, ValueError) as exc:
        return back_to("/dashboard", error=str(exc))


@app.post("/wallet/{child_id}/deduct")
def deduct_money(child_id: str, amount: Decimal = Form(...), actor: Actor = Depends(current_actor), conn=Depends(db)):
    try:
        WalletService(conn).deduct_money(actor, child_id, amount)
        return back_to("/dashboard", notice="Money deducted successfully.")
    except (PermissionError, ValueError) as exc:
        return back_to("/dashboard", error=str(exc))


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
def game(request: Request, error: str = "", notice: str = "", actor: Actor = Depends(current_actor)):
    return templates.TemplateResponse(
        "game.html",
        {"request": request, "actor": actor, "error": error, "notice": notice},
    )


@app.post("/game/betting/open")
async def open_betting(actor: Actor = Depends(current_actor), conn=Depends(db)):
    try:
        await GameOrchestrator(conn).open_betting()
        return back_to("/game", notice="Betting opened successfully.")
    except ValueError as exc:
        return back_to("/game", error=str(exc))


@app.post("/game/bet")
async def bet(side: str = Form(...), amount: Decimal = Form(...), actor: Actor = Depends(current_actor), conn=Depends(db)):
    try:
        await GameOrchestrator(conn).place_bet(actor, side, amount)
        return back_to("/game", notice="Bet placed successfully.")
    except (PermissionError, ValueError) as exc:
        return back_to("/game", error=str(exc))


@app.post("/game/start")
async def start_game(actor: Actor = Depends(current_actor), conn=Depends(db)):
    if GameOrchestrator(conn).current_state()["in_progress"]:
        return back_to("/game", error="A Tin Patti round is already running.")

    async def run_with_own_connection():
        own_conn = connect()
        try:
            await GameOrchestrator(own_conn).run_round()
        finally:
            own_conn.close()

    asyncio.create_task(run_with_own_connection())
    return back_to("/game", notice="Round started.")


@app.websocket("/ws/game")
async def game_ws(websocket: WebSocket):
    await manager.connect(websocket)
    conn = connect()
    try:
        await websocket.send_json({"event": "server_state", "data": GameOrchestrator(conn).current_state()})
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    finally:
        conn.close()
