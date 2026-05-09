# Production Deployment Checklist

This folder ships as a **local Docker testing** environment.
Every item below must be done before traffic hits the server.

---

## 1. .env — critical values to replace

### Security keys
Generate both values fresh — never reuse the dev values:
```
python -c "import secrets; print(secrets.token_hex(32))"
```
```
SECRET_KEY=<new 64-char hex>
CSRF_SECRET=<new 64-char hex>
```

### Cookie security
Must be `true` when running behind HTTPS:
```
COOKIE_SECURE=true
```

### Admin credentials
Change all three before the first `docker compose up`:
```
ADMIN_USERNAME=<strong unique username>
ADMIN_PASSWORD=<16+ char strong password>
ADMIN_EMAIL_ID=<real admin email>
```

---

## 2. .env — database

### Point pgbouncer at your managed PostgreSQL
```
DB_HOST=<your-managed-db-hostname>     # e.g. db-postgresql-xxx.ondigitalocean.com
DB_PORT=25060                           # DigitalOcean; use 5432 for AWS RDS / Supabase
DB_USER=<db_username>
DB_PASSWORD=<strong db password>
DB_NAME=luck_game_prod
SERVER_TLS_SSLMODE=require              # must be require for managed DBs
```

### Scale the connection pools to match your DB plan
```
DB_POOL_MIN=2
DB_POOL_MAX=20
PGBOUNCER_MAX_CLIENT_CONN=500
PGBOUNCER_DEFAULT_POOL_SIZE=30
```
Rule of thumb: `DEFAULT_POOL_SIZE` × number of web replicas ≤ max connections
your DB plan allows. DigitalOcean Basic plan allows ~25; Production plans allow 100+.

---

## 3. .env — Redis

Replace the local Redis container with a managed service
(Redis Cloud, Upstash, ElastiCache, or DigitalOcean Managed Redis):
```
REDIS_URL=rediss://<user>:<password>@<host>:<port>/0
CELERY_BROKER_URL=rediss://<user>:<password>@<host>:<port>/1
CELERY_RESULT_BACKEND=rediss://<user>:<password>@<host>:<port>/2
```
Note the `rediss://` scheme (TLS) for managed providers.

---

## 4. docker-compose.yml — remove the local postgres service

The `postgres` service is only for local testing.
In production, delete the entire `postgres:` block and the `postgres_data:` volume,
then set `DB_HOST` in `.env` to your managed PostgreSQL hostname.

Also remove the `depends_on: postgres` entry from the `pgbouncer:` service block.

---

## 5. docker-compose.yml — web app scaling

Change `container_name` (fixed names conflict with replicas) and set replica count:
```yaml
web:
  # remove container_name — it clashes when replicas > 1
  deploy:
    replicas: 2          # increase for more throughput
  environment:
    APP_ENV: production
    COOKIE_SECURE: "true"
```

---

## 6. docker-compose.yml — Celery worker scaling

For high email volume, increase email worker concurrency:
```yaml
celery_worker:
  command: celery -A tasks.celery_app.celery_app worker -Q celery --loglevel=info --concurrency=8
  environment:
    APP_ENV: production
```

The `celery_cleanup_worker` should stay at `--concurrency=1`
(cleanup tasks must run sequentially).

---

## 7. docker-compose.yml — all APP_ENV values

Change every service from `APP_ENV: development` → `APP_ENV: production`:
Services to update: `web`, `celery_worker`, `celery_beat`,
`celery_cleanup_worker`, `game_scheduler`.

---

## 8. nginx — add HTTPS / SSL termination

### Option A: terminate TLS at the load balancer (recommended)
Use DigitalOcean Load Balancer, AWS ALB, or Cloudflare in front of nginx.
nginx only listens on port 80 internally; the LB handles the certificate.
Add `X-Forwarded-Proto` checking in nginx if needed.

### Option B: terminate TLS on nginx directly
Replace `nginx/nginx.conf` with an HTTPS config:
```nginx
server {
    listen 443 ssl;
    server_name yourdomain.com;

    ssl_certificate     /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_ciphers         HIGH:!aNULL:!MD5;

    # ... rest of location blocks unchanged ...
}

# Redirect HTTP → HTTPS
server {
    listen 80;
    server_name yourdomain.com;
    return 301 https://$host$request_uri;
}
```
Mount the certificate with a volume in `nginx:` service:
```yaml
volumes:
  - /etc/letsencrypt:/etc/letsencrypt:ro
ports:
  - "80:80"
  - "443:443"
```

---

## 9. nginx — add `server_name`

Replace the wildcard `server_name _;` with your actual domain:
```nginx
server_name yourdomain.com www.yourdomain.com;
```

---

## 10. nginx — tighten Content Security Policy

Add a `Content-Security-Policy` header once you know your exact asset origins.
The current config omits it intentionally to avoid blocking dev tooling.

---

## 11. pgbouncer — SSL to managed PostgreSQL

`SERVER_TLS_SSLMODE=require` is set by step 2 above.
Some managed providers (e.g. DigitalOcean) also require a CA certificate.
If your provider requires it, add to `pgbouncer/entrypoint.sh`:
```sh
server_tls_ca_file = /etc/ssl/certs/ca-certificates.crt
```
And mount the cert in the pgbouncer service:
```yaml
volumes:
  - /path/to/ca.crt:/etc/ssl/certs/server-ca.crt:ro
```

---

## 12. Secrets management

Never put production secrets in `.env` files committed to git.

Recommended approaches:
- **Docker Swarm secrets**: `docker secret create`
- **GitHub Actions**: store as repository secrets, inject at deploy time
- **HashiCorp Vault** or **AWS Secrets Manager**: fetch at runtime
- At minimum: keep the production `.env` only on the server, outside the repo

---

## 13. Logging and monitoring

The app writes structured logs to stdout.
In production, pipe them to a log aggregator:
```yaml
web:
  logging:
    driver: "json-file"
    options:
      max-size: "50m"
      max-file: "5"
```
Or use `--log-driver=loki` / `--log-driver=awslogs` for central aggregation.

Add an uptime monitor (Better Uptime, UptimeRobot) on the `/health` endpoint.

---

## 14. Database backups

Enable automated daily backups on your managed PostgreSQL provider.
Also run a periodic `pg_dump` and store it off-site.
The archive tables (`bets_archive`, `game_sessions_archive`,
`wallet_transactions_archive`) are included in the normal backup — no extra steps needed.

---

## 15. Celery Beat — single-instance constraint

Only ONE `celery_beat` container must ever run.
If you scale the stack with replicas, do NOT add `deploy.replicas` to `celery_beat`.
Multiple beat processes will fire duplicate scheduled tasks.

---

## 16. Game timing — production values

Review these for your live traffic:
```
BETTING_WINDOW_SECONDS=40         # how long players can bet each round
GAME_INITIATION_SECONDS=10        # pause before cards are dealt
AFTER_GAME_COOLDOWN_SECONDS=10    # result display time
CARD_DRAWING_DELAY_SECONDS=3      # delay between each card reveal
```

---

## Quick checklist before go-live

- [ ] All secrets in `.env` replaced with production values
- [ ] `COOKIE_SECURE=true`
- [ ] `SERVER_TLS_SSLMODE=require`
- [ ] `APP_ENV=production` in every service
- [ ] Local `postgres` service removed from compose; `DB_HOST` points at managed DB
- [ ] Redis URLs point at managed Redis with TLS (`rediss://`)
- [ ] Nginx `server_name` set to real domain
- [ ] HTTPS configured (LB or nginx)
- [ ] Celery Beat has exactly one running instance
- [ ] DB connection pool sizes reviewed against DB plan limits
- [ ] Automated database backups enabled
- [ ] Uptime monitor on `/health`
- [ ] Log aggregation configured
