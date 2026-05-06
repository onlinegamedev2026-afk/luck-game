# Luck Game Production Deployment

This folder is a production-oriented copy of `using_claude_v4`.

The Docker app server runs:

- Nginx as the only public container on port `80`
- FastAPI web app behind Nginx
- PgBouncer as the database connection pooler
- Redis inside Docker
- Celery worker
- One game scheduler container

PostgreSQL is expected to run outside this server as a managed database, for example DigitalOcean Managed PostgreSQL.

## What Changed For Production

The app containers now connect to:

```text
pgbouncer:5432
```

PgBouncer connects to the remote managed database from `.env`:

```env
DB_HOST=private-db-postgresql-blr1-12345-do-user-1234567-0.b.db.ondigitalocean.com
DB_PORT=25060
```

PgBouncer also enables TLS to the database by default:

```env
SERVER_TLS_SSLMODE=require
```

This is needed for providers such as DigitalOcean Managed PostgreSQL.

## Required Server Setup

1. Create one app server for Docker.

2. Create one managed PostgreSQL database.

3. In the managed DB firewall, allow only the app server public IP.

4. Point your domain to the app server public IP:

```text
game.example.com -> APP_SERVER_PUBLIC_IP
```

5. Open these ports on the app server:

```text
80/tcp
443/tcp
```

6. Do not expose PostgreSQL publicly to everyone.

7. Keep Redis private inside Docker Compose.

## Environment File

On the production server:

```bash
cp .env.production.example .env
```

Then edit `.env` and replace every `change-me` value.

Minimum important values:

```env
APP_ENV=production
COOKIE_SECURE=true
SECRET_KEY=strong-random-value
CSRF_SECRET=strong-random-value

DB_HOST=your-managed-postgres-host
DB_PORT=25060
DB_NAME=your-db-name
DB_USER=your-db-user
DB_PASSWORD=your-db-password

ADMIN_PASSWORD=strong-admin-password
```

Generate secrets with:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

## HTTPS

The included Nginx config currently listens on port `80`.

For production, use one of these:

- Put Cloudflare, DigitalOcean Load Balancer, or another HTTPS proxy in front.
- Add Certbot and HTTPS directly to Nginx.
- Replace Nginx with Caddy or Traefik for automatic HTTPS.

After HTTPS is active, keep:

```env
COOKIE_SECURE=true
```

If you test temporarily over plain HTTP, set `COOKIE_SECURE=false`, but change it back before real users log in.

## Deploy

From this folder on the production app server:

```bash
docker compose up --build -d
```

Check containers:

```bash
docker compose ps
```

Check logs:

```bash
docker compose logs --tail=120 web
docker compose logs --tail=80 pgbouncer
docker compose logs --tail=80 celery_worker
docker compose logs --tail=80 game_scheduler
```

Health check:

```text
http://YOUR_DOMAIN/health
```

After HTTPS:

```text
https://YOUR_DOMAIN/health
```

## Capacity Starting Point

For around 500 initial users, this folder starts with conservative DB pooling:

```env
DB_POOL_MIN=1
DB_POOL_MAX=5
PGBOUNCER_MAX_CLIENT_CONN=500
PGBOUNCER_DEFAULT_POOL_SIZE=30
```

Monitor:

- CPU and memory on the app server
- managed DB CPU and connection count
- PgBouncer logs
- web logs
- websocket count
- slow requests and slow SQL queries

Increase only after observing real usage.

## Important Notes

- The app initializes database tables automatically on startup.
- Keep only one `game_scheduler` container running.
- Do not run multiple scheduler replicas unless the scheduler code is changed for leader election.
- If the managed DB provider uses a different port, update `DB_PORT`.
- If the managed DB does not require TLS, set `SERVER_TLS_SSLMODE=prefer` or `disable`, but `require` is recommended for production.
- Keep `.env` private and never commit real credentials.
