# Luck Game Webapp

Generated from the local prompts, draw.io flow, Tin Patti engine, and synced game template.

## Run locally

```powershell
cd using_chatgpt
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Open `http://127.0.0.1:8000`.

Default admin login:

- Username: `admin`
- Password: `admin123`

## Notes

- SQLite is the default local database so the app starts quickly.
- The settings file includes PostgreSQL, Redis, and Celery URLs for the production stack requested in the prompts.
- Wallet movement is ledger-only: no UI route overwrites balances directly.
- Admin can create/delete immediate agents. Agents can create/delete immediate agents and users.
- Deleting an agent removes its entire subtree, matching the draw.io and prompt rules.

## Docker With Local PostgreSQL

This Compose setup runs the FastAPI app, Redis, and Celery in Docker. PostgreSQL is expected to be installed locally on your machine, not inside Docker.

```powershell
cd using_chatgpt
copy .env.docker.example .env
docker compose up --build
```

Use this database URL format in `.env`:

```text
DATABASE_URL=postgresql://luck_user:luck_password@host.docker.internal:5432/luck_game
```

Then open `http://127.0.0.1:8000`.
