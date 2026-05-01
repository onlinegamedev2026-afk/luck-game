# The Base Prompt

Codex will start reading from this prompt

- Codex will ignore the prompt where `status` is **Done**
- Codex will focus on the prompts where `status` is **Ongoing**


---
## prompt - 005 
`status` : **Done**
```
1. parent folder (using_claude) contains a web application made by you

```
```

Target folder:
    parent folder (using_claude)

Query:
    First, please check the complete web application inside the target folder.

    I want to deploy this application, so please analyze whether the current application is scalable enough to handle at most 20,000 concurrent users.

    Please check the following clearly:
    1. Backend scalability
    2. Database scalability
    3. Redis / cache / realtime state usage
    4. WebSocket scalability, if used
    5. Background job handling
    6. Game transaction safety
    7. Wallet transaction safety
    8. Any bottlenecks in the current code
    9. Any security issues before deployment
    10. Any missing production-level configuration

    After checking the application, please suggest which server or cloud provider would be better for this project.

    Important:
    - The application will mostly be used in India.
    - Preferably suggest a server location suitable for Eastern India users.
    - I am new to deployment, so explain everything in a beginner-friendly way.

    Also explain:
    1. What steps are required before deployment?
    2. What things must be fixed before going live?
    3. What server size/specification should I start with?
    4. Should I use VPS, dedicated server, or cloud server?
    5. Should I use Docker in production?
    6. Should I use Nginx?
    7. Should I use SSL/HTTPS?
    8. Should PostgreSQL and Redis be on the same server or separate servers?
    9. How should I take database backups?
    10. How should I monitor the server?

    Please also explain Cloudflare:
    - Can I use Cloudflare with this application?
    - What benefits will Cloudflare give me?
    - Is Cloudflare like a VPN, or is it different?
    - Should I use Cloudflare DNS, SSL, caching, DDoS protection, or WAF?
    - What Cloudflare settings are safe for this type of real-money/game wallet application?

    Finally, give me a clear deployment roadmap:
    1. Things to check before deployment
    2. Code changes needed before deployment
    3. Server setup steps
    4. Database setup steps
    5. Redis setup steps
    6. Environment variable setup
    7. Domain and Cloudflare setup
    8. SSL/HTTPS setup
    9. Running the application
    10. Testing after deployment
    11. Monitoring after going live

    Please explain in detail but in simple and clear language.
    Do not directly change the code unless I ask.
    First analyze the project and give me the deployment/scalability report.
 
```
---
---
## prompt - 006 
`status` : **Ongoing**
```

Target folder:
    parent folder (using_claude)

Reference files:
    - 002_baseprompt.md
    - 002_005_op.md

Query:
    Please read the previous scalability report first.

    For now, ignore the full deployment section, hosting provider section, Cloudflare setup section, and production launch roadmap.

    I only want to know whether the "Main Scalability Problems" mentioned in the previous report can be solved now in my local system using local Docker.

    Important:
    - Do not directly change any code.
    - Do not modify files.
    - Only give me a complete detailed modification list.
    - Explain in simple beginner-friendly language.
    - Assume I want to prepare the application locally before real deployment.

    Please focus only on these main scalability problems:
    1. Backend scalability
    2. Database connection scalability
    3. Redis/cache/realtime state usage
    4. WebSocket scalability
    5. Background job/game cycle handling
    6. Game transaction safety
    7. Wallet transaction safety
    8. Security fixes that are required before scaling
    9. Missing Docker/local production-like containers
    10. Missing Nginx/reverse proxy configuration

    Please answer the following clearly:

    1. Can these scalability problems be solved locally using Docker?
       - Which problems can be fully solved locally?
       - Which problems can only be partially tested locally?
       - Which problems need real server/load testing later?

    2. Give me a step-by-step local preparation plan.

    3. List all required code-level modifications.
       Include detailed changes needed for:
       - Database connection pooling
       - PostgreSQL transaction safety
       - Wallet row locking
       - Game bet locking
       - Redis-based OTP/CAPTCHA/session-like temporary state
       - Redis-based game runtime state
       - Redis Pub/Sub or similar WebSocket broadcasting
       - Single-owner game scheduler/worker
       - Celery/background task improvements
       - CSRF protection
       - Secure cookie configuration
       - Rate limiting
       - Logging and error handling
       - Health check endpoints
       - Any required config/env changes

    4. List all required Docker-level modifications.
       Include detailed changes needed for:
       - FastAPI app container
       - PostgreSQL container
       - Redis container
       - Celery worker container
       - Celery beat or scheduler container, if needed
       - PgBouncer container, if needed
       - Nginx container, if needed
       - Docker networks
       - Docker volumes
       - Health checks
       - Environment variables
       - Local production-like docker-compose setup

    5. Tell me if I missed any required container.
       Specifically check whether I need:
       - Nginx
       - PgBouncer
       - Redis
       - Celery worker
       - Celery beat / scheduler
       - PostgreSQL
       - App container
       - Monitoring/logging container
       - Any other useful local container

    6. Give me the recommended local Docker architecture.
       Explain which container talks to which container.

    7. Give me the recommended order of implementation.
       Example:
       Step 1: Fix DB transaction safety
       Step 2: Add connection pooling/PgBouncer
       Step 3: Move in-memory state to Redis
       etc.

    8. Mention clearly what should NOT be done locally yet.
       For example:
       - Do not focus on cloud provider now
       - Do not focus on real domain now
       - Do not focus on Cloudflare now
       - Do not focus on SSL certificates yet unless needed for local testing

    Final output format:
    - First give a short answer: yes/no/partially
    - Then give a detailed checklist
    - Then give the local Docker architecture
    - Then give the exact implementation order
    - Do not write code unless absolutely necessary
    - Do not edit files directly
```
---
---