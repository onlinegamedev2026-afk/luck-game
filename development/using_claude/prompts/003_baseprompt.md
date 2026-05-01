Backend Scalability
	Can be solved locally: mostly yes
	Required modifications:
		Run FastAPI with a production-like server setup, such as Gunicorn with Uvicorn workers.
		Stop keeping important state inside one Python process.
		Make the app safe to run with multiple app containers.
		Add /health, /ready, and /metrics-style endpoints.
		Add structured logging for requests, errors, wallet actions, bet placement, settlement, and background jobs.
		Add graceful shutdown handling so game cycles, DB connections, and WebSockets close cleanly.
	Local Docker test:
		Run 2 or 3 app containers behind Nginx.
		Confirm login, dashboard, game pages, betting, WebSockets, and wallet actions still work when traffic goes to different containers.


Database Connection Scalability
	Can be solved locally: yes for architecture, partially for real capacity
	Required modifications:
		Stop opening unlimited direct PostgreSQL connections per request.
		Add PgBouncer between the app and PostgreSQL.
		Change DATABASE_URL so app containers connect to PgBouncer, not directly to PostgreSQL.
		Use proper transaction boundaries.
		Avoid autocommit=True for wallet/game money transactions.
		Add database indexes for frequent queries:
			bets by session_id
			bets by player_id/status
			game sessions by status/game_key
			accounts by username/role
			wallet transactions by wallet and timestamp
		Add migration tooling instead of creating/updating schema on startup.
	Local Docker test:
		App container -> PgBouncer -> PostgreSQL.
		Verify PostgreSQL connection count stays controlled when many requests run.
		

Redis / Cache / Realtime State Usage
	Can be solved locally: yes
	Move these from memory to Redis:
		CAPTCHA store
		Login OTP store
		Child email OTP store
		Admin password OTP store
		OTP rate limit counters
		Game phase
		Current game session IDs
		Cards dealt
		Winner state
		Phase end timestamps
		Distributed locks
		WebSocket broadcast events
	Use Redis TTLs for temporary data:
		CAPTCHA: 10 minutes
		OTP: 30 minutes
		Rate-limit windows: 30 minutes
		Game runtime keys: expire after session completion plus buffer time
	Required modifications:
		Create a Redis service/helper module.
		Replace global dictionaries in main.py.
		Replace class-level game runtime dictionaries in GameOrchestrator.
		Use Redis locks for game cycle ownership and settlement protection.
		Store game session state in Redis and persist final results in PostgreSQL.
	
WebSocket Scalability
	Can be solved locally: partially yes
		Required modifications:
		Keep local WebSocket connections in each app container, but broadcast through Redis Pub/Sub.
		When one app container emits a game event, publish it to Redis.
		All app containers subscribe to Redis and forward events to their own connected WebSocket clients.
		Add reconnect behavior on frontend.
		Add ping/pong or heartbeat logic.
		Add backpressure handling so slow clients do not block all broadcasts.
		Do not depend on one Python process knowing all sockets.
	Local Docker test:
		Run multiple app containers.
		Open browser sessions connected to different containers.
		Place a bet or wait for game event.
		Confirm all users receive the same event.
		
Background Job / Game Cycle Handling
	Can be solved locally: yes
	Current issue: game cycles start inside the web app process. That is unsafe with multiple workers.
	Required modifications:
		Remove automatic game cycle startup from FastAPI app startup.
		Create a separate game scheduler container.
		Only the scheduler should open betting, close betting, run rounds, settle bets, and finish cycles.
		Use Redis distributed locks so only one scheduler owns each game cycle.
		Use Celery worker for normal background jobs like email.
		Optionally use Celery Beat for scheduled tasks, but for game loops a dedicated scheduler container may be clearer.
		Add idempotency checks so settlement cannot run twice for the same session.
	Recommended local containers:
		app
		game_scheduler
		celery_worker
		optionally celery_beat if you later move periodic tasks there
		
Game Transaction Safety
	Can be solved locally: yes
	Required modifications:
		Use PostgreSQL row-level locks for wallet rows during bet placement.
		Replace the current read-calculate-update flow with locked transactions.
		During bet placement:
			start transaction
			lock player wallet row
			lock system pool wallet row
			verify active game session
			verify betting phase
			verify balance
			insert wallet transaction
			update player wallet
			update pool wallet
			insert bet
			update session totals
			commit
		Use NUMERIC(18,3) or similar for money columns instead of storing balances as text.
		Do not use float math for game totals.
		Add unique/idempotency keys for bet placement if the frontend retries.
		Add tests for double-click bet submission and concurrent bets.
		
Wallet Transaction Safety
	Can be solved locally: yes
	Required modifications:
		Add row-level locking in LedgerService.transfer.
		Lock both wallets in a stable order to reduce deadlocks.
		Use SELECT ... FOR UPDATE.
		Keep wallet update, transaction insert, and balance check inside the same DB transaction.
		Use idempotency keys for operations that may retry.
		Use database constraints where possible.
		Use optimistic version checks only if deliberately designed; right now version increments but does not protect anything.
		Add audit logs for all money movement.
		Prevent deleting wallet transaction history for real-money audit safety. Current delete logic removes transaction records when deleting accounts; this should be changed before production-like testing.
	
Security Fixes Required Before Scaling
	Can be solved locally: yes
	Required modifications:
		Remove default production secrets.
		Rotate the SMTP credential that appears in .env.example.
		Never commit real credentials.
		Add CSRF protection to all form POST routes.
		Add secure cookie settings:
			httponly=True
			samesite="lax" or stricter where possible
			secure=True when HTTPS is enabled
		Add environment-based config:
			local dev
			local production-like Docker
			real production later
		Add rate limiting for:
			login
			OTP send
			OTP verify
			password update
			bet placement
			credential generation
		Move rate limiting counters to Redis.
		Disable showing dev_otp except in explicit local development mode.
		Add trusted host checks.
		Add request size limits in Nginx.
		Add security headers through Nginx or FastAPI middleware.
		
Missing Docker / Local Production-Like Containers
		Can be solved locally: yes
		Recommended containers:
			nginx: reverse proxy and WebSocket proxy
			app: FastAPI application, multiple replicas if possible
			postgres: local PostgreSQL
			pgbouncer: database connection pooler
			redis: cache, temporary state, locks, Pub/Sub, Celery broker
			celery_worker: email/background jobs
			game_scheduler: single-owner game cycle runner
			prometheus: optional metrics collection
			grafana: optional dashboard
			loki or another log collector: optional local logging
Nginx / Reverse Proxy
	Can be solved locally: yes
	Required modifications:
		Add Nginx container.
		Route HTTP traffic to app containers.
		Route WebSocket paths:
			/ws/games/...
			/ws/game
		Preserve upgrade headers for WebSockets.
		Serve or proxy static files.
		Add request timeout settings suitable for WebSockets.
		Add basic rate limits for sensitive endpoints.
		Add body size limits.
		Add security headers.
		For local testing, HTTP is enough. HTTPS can be added later with local self-signed certs only if needed.
		
Step-By-Step Local Preparation Plan
	Create a local production-like Docker Compose setup.
	Add PostgreSQL container and stop using SQLite for serious testing.
	Add PgBouncer and route app DB traffic through it.
	Fix PostgreSQL transaction handling.
	Fix wallet transfer locking.
	Fix game bet placement locking.
	Convert money columns from text-style handling to proper numeric handling.
	Move OTP/CAPTCHA/rate-limit state to Redis.
	Move game runtime state to Redis.
	Add Redis locks for game cycle and settlement ownership.
	Move game cycle execution out of the web app into a scheduler container.
	Add Redis Pub/Sub for WebSocket broadcasts.
	Run multiple app containers behind Nginx.
	Add CSRF protection and secure cookie config.
	Add health checks for app, PostgreSQL, Redis, PgBouncer, Celery, and scheduler.
	Add logging and basic monitoring.
	Run local load tests with small numbers first.
	Increase local test load gradually and watch logs, DB locks, Redis, and CPU.
	
Required Docker-Level Modifications
	FastAPI app container:
		Run production-like command.
		Use env vars only.
		Connect to PgBouncer.
		Connect to Redis.
		Do not start game cycles on app startup.
		Add health check.
	PostgreSQL container:
		Persistent volume.
		Proper username/password/database.
		Health check using pg_isready.
		Init scripts or migrations.
		Use PostgreSQL for all local production-like tests.
	Redis container:
		Persistent volume if needed.
		Health check using redis-cli ping.
		Separate logical DBs or key prefixes for:
			cache/temp state
			Celery broker
			Celery result backend
			Pub/Sub/locks
	Celery worker container:
		Same image as app.
		Command runs Celery worker.
		Depends on Redis and PostgreSQL/PgBouncer.
		Health/log checks.
		Handles email and async jobs.
	Game scheduler container:
		Same image as app.
		Runs only game cycle scheduler.
		Uses Redis lock to become owner.
		Writes game results to PostgreSQL.
		Publishes realtime events through Redis.
	PgBouncer container:
		Sits between app/scheduler/workers and PostgreSQL.
		Limits database connections.
		Uses transaction pooling or session pooling depending on transaction needs.
		App DATABASE_URL points to PgBouncer.
	Nginx container:
		Receives browser traffic.
		Proxies to app containers.
		Supports WebSocket upgrade headers.
		Can serve static files or proxy them.
		Adds rate limits and request limits.
	Docker networks:
		One internal backend network for app, DB, Redis, PgBouncer, Celery.
		Only Nginx exposed to host.
		PostgreSQL/Redis should not be exposed publicly except maybe local debugging.
	Docker volumes:
		PostgreSQL data volume.
		Redis data volume if persistence is enabled.
		Optional logs volume.
	Health checks:
		App: /health
		PostgreSQL: pg_isready
		Redis: redis-cli ping
		PgBouncer: simple connection check
		Celery: inspect ping or process health
		Scheduler: heartbeat key in Redis
		Nginx: HTTP check
	Environment variables:
		APP_ENV=local-prod
		SECRET_KEY
		DATABASE_URL
		REDIS_URL
		CELERY_BROKER_URL
		CELERY_RESULT_BACKEND
		COOKIE_SECURE
		CSRF_SECRET
		SMTP_*
		GAME_SCHEDULER_ENABLED
		RATE_LIMIT_ENABLED
		LOG_LEVEL
		
"
Recommended Local Docker Architecture

Browser talks to:

Browser -> Nginx -> FastAPI app containers

FastAPI app talks to:

FastAPI app -> PgBouncer -> PostgreSQL

FastAPI app also talks to:

FastAPI app -> Redis

WebSocket flow:

Browser WebSocket -> Nginx -> one FastAPI app container

Realtime broadcast flow:

Game scheduler/app -> Redis Pub/Sub -> all FastAPI app containers -> connected WebSocket users

Background jobs:

FastAPI app -> Redis/Celery broker -> Celery worker

Game cycle:

Game scheduler -> Redis lock/state -> PostgreSQL transactions -> Redis Pub/Sub -> FastAPI WebSocket containers

Database flow:

app / celery / scheduler -> PgBouncer -> PostgreSQL
"
"
Exact Implementation Order

Step 1: Switch local serious testing to PostgreSQL only.

Step 2: Fix money schema and transaction handling.

Step 3: Fix wallet row locking using PostgreSQL transactions.

Step 4: Fix game bet locking and settlement idempotency.

Step 5: Add PgBouncer and route app DB traffic through it.

Step 6: Move OTP, CAPTCHA, and rate-limit state to Redis.

Step 7: Move game runtime state to Redis.

Step 8: Add Redis distributed locks for game cycle ownership.

Step 9: Move game cycles into a dedicated scheduler container.

Step 10: Add Redis Pub/Sub for WebSocket broadcasting.

Step 11: Run multiple app containers behind Nginx.

Step 12: Add CSRF protection.

Step 13: Add secure cookie and environment-based security config.

Step 14: Add rate limiting through Redis and/or Nginx.

Step 15: Add health check endpoints and Docker health checks.

Step 16: Add structured logging and error handling.

Step 17: Add local monitoring containers if needed.

Step 18: Run local load tests and fix bottlenecks found.
"