# Installation and deployment

PortWiz has two kinds of moving parts:

- **The control plane** runs on one host: the API, a Celery worker and beat
  (background jobs and schedules), the web UI, a PostgreSQL/TimescaleDB database,
  and a Valkey (Redis-compatible) broker.
- **Scan agents** run one per network segment. Each agent polls the control
  plane for jobs, scans its segment, and reports results back. Agents are
  deployed separately from the control plane so they can sit inside each network.

You can run everything with **Docker** (recommended, the least moving parts) or
**natively** without Docker. This guide covers both, component by component.

> **Database requirement:** PortWiz needs PostgreSQL with the **TimescaleDB**
> extension (observations are stored in a hypertable). A stock `postgres` image
> or install will fail the migrations. The Docker images use
> `timescale/timescaledb`; for a native database, install the TimescaleDB
> extension on your PostgreSQL.

---

## System requirements

Sizing is driven by how much you monitor (number of hosts and open ports, how
often you scan, and how long you keep history) and whether you run **local AI**.
The tiers below are for the **whole control plane on one host** (database,
broker, API, worker, beat, and web), **without** local AI.

| Resource | Minimum | Recommended | Comfortable |
|---|---|---|---|
| Hosts monitored | up to ~500 | ~500 to 5,000 | 5,000+ |
| CPU | 2 vCPU | 4 vCPU | 8+ vCPU |
| RAM | 4 GB | 8 GB | 16 GB+ |
| Disk (SSD) | 20 GB | 100 GB | 200 GB+ |

- **Scan agents** are separate and tiny: about **1 vCPU and 0.5 to 1 GB RAM**
  each. Scanning is network-bound, not CPU-bound, so an agent runs comfortably on
  a small VM or container. Deploy one per network segment.
- **Local AI (Ollama)** is the main extra memory (and optionally GPU) driver. Add
  roughly **4 to 8 GB RAM** for a small (about 3B-parameter) model, more for
  larger ones; a GPU is optional but much faster. If you use a cloud provider
  (Claude or any OpenAI-compatible API) or no AI, you do not need this.
- **Disk** grows mainly from the observations table (hosts x open ports x scan
  frequency x retention). Use SSD, and tune how long raw observations are kept
  with `retention_observation_days` (or the Settings UI). Back up the database
  volume for durability.
- These are practical guidelines, not hard limits. Start at Recommended if
  unsure; scale CPU/RAM/disk up as your estate and scan frequency grow.

---

## Option A: Docker (recommended)

Requires Docker and Docker Compose. All compose files live in `deploy/`.

### Development

```bash
cd deploy
cp .env.example .env          # fill in secrets
docker compose up --build
```

This starts the database, broker, API, worker, beat, web, and a dev mail sink.

- API: `http://localhost:8000` (interactive docs at `/docs` in non-production)
- Web UI: `http://localhost:5173`
- Mail sink (Mailpit): `http://localhost:8025`

The first admin user is seeded from the `PORTWIZ_FIRST_ADMIN_*` values in `.env`.

### Production

The production compose file runs a hardened, single-origin stack: containers run
as a non-root user, the API, database, and broker are never published to the
host, and one nginx service serves the built UI and reverse-proxies `/api` and
`/health` (so there is no cross-origin traffic).

```bash
cd deploy
cp .env.prod.example .env.prod    # set strong secrets, DB password, admin, SMTP
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
```

- Web UI: `http://localhost:8080` (change `WEB_PORT` in `.env.prod`)

The API applies database migrations on boot before it becomes healthy; the worker
and beat wait for that. Put your own TLS terminator in front of the web port
before exposing PortWiz to a real network (see [TLS](#tls-and-exposure)).

### Optional services

- **Local AI (Ollama):** add `--profile ai` and set `PORTWIZ_AI_PROVIDER=ollama`.
  Pull a model after start, e.g. `docker exec portwiz-ollama-1 ollama pull qwen2.5:3b`.
- **One-click updates (prod):** add `--profile updater` and set
  `PORTWIZ_UPDATE_APPLY_ENABLED=true` (needs registry images).

---

## Option B: without Docker (native)

Run each component directly on the host. A practical middle ground is to run the
**database and broker with Docker** (they are the fiddly parts) and the app
components natively:

```bash
cd deploy
docker compose up db valkey       # just the infra
```

If you prefer fully native, install PostgreSQL **with the TimescaleDB
extension** and Valkey (or Redis) yourself, create the `portwiz` database, and
point the URLs below at them.

Prerequisites for the app components: **Python 3.11 or 3.12**, **Node 22**, and
**Go 1.23** (only for building the agent).

### Shared configuration

The API, worker, and beat read the same settings (all prefixed `PORTWIZ_`). They
auto-load a `.env` file in the working directory, or you can export them. For
native runs, point hostnames at `localhost` instead of the compose service names:

```bash
PORTWIZ_DATABASE_URL=postgresql+asyncpg://portwiz:portwiz@localhost:5432/portwiz
PORTWIZ_CELERY_BROKER_URL=redis://localhost:6379/0
PORTWIZ_CELERY_RESULT_BACKEND=redis://localhost:6379/1
PORTWIZ_SECRET_KEY=change-me            # openssl rand -hex 32
PORTWIZ_FIRST_ADMIN_EMAIL=admin@example.com
PORTWIZ_FIRST_ADMIN_PASSWORD=choose-a-strong-password
```

See [Environment variables](#environment-variables) for the full list.

### API

From `apps/api`:

```bash
python -m venv .venv
. .venv/bin/activate            # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -e .                # add ".[dev]" for tests and linting
alembic upgrade head            # create/upgrade the schema (needs the DB reachable)
uvicorn portwiz_api.main:app --host 0.0.0.0 --port 8000   # add --reload for dev
```

The API serves on port 8000 under the `/api/v1` prefix, with a health check at
`GET /health`.

### Worker and beat

The background worker and the scheduler run from the same `apps/api` project and
environment, with the broker reachable. In two more terminals:

```bash
# Worker (runs scans, CVE re-checks, notification digests):
celery -A portwiz_api.workers.celery_app.celery_app worker --loglevel=info

# Beat (fires the schedules: due scans, CVE re-checks, notification flush):
celery -A portwiz_api.workers.celery_app.celery_app beat --loglevel=info --schedule=./celerybeat-schedule
```

### Web

From `apps/web`. The UI finds the API through `VITE_API_BASE_URL`.

```bash
npm ci

# Development server on http://localhost:5173, talking to the API directly:
VITE_API_BASE_URL=http://localhost:8000 npm run dev -- --host 0.0.0.0

# Production build (outputs to dist/):
VITE_API_BASE_URL="" npm run build
```

For dev, the browser calls the API origin directly, so the API must allow it:
keep `PORTWIZ_CORS_ORIGINS` including `http://localhost:5173` (the default).

For a production build, an empty `VITE_API_BASE_URL` makes the UI use relative
`/api` and `/health` URLs. Serve the `dist/` folder from any static web server or
reverse proxy that also proxies `/api` and `/health` to the API (this is exactly
what the bundled nginx image does).

### Scan agent

From `apps/agent` (needs Go 1.23; optionally install `nmap` for `-sV` service
detection):

```bash
go mod download
CGO_ENABLED=0 go build -trimpath -o portwiz-agent ./cmd/agent

# Poll-and-scan loop (normal mode). Enroll an agent in the UI first to get a token:
PORTWIZ_API_URL=http://localhost:8000 PORTWIZ_AGENT_TOKEN=<token> ./portwiz-agent run
```

Agent environment variables:

| Variable | Default | Purpose |
|---|---|---|
| `PORTWIZ_API_URL` | `http://localhost:8000` | Control-plane base URL |
| `PORTWIZ_AGENT_TOKEN` | (none) | Bearer token from enrollment |
| `PORTWIZ_AGENT_ID` | `agent-local` | Agent identity label |
| `PORTWIZ_POLL_SECONDS` | `15` | Poll interval (the server config can override it) |

For a one-shot test scan without enrolling:

```bash
./portwiz-agent scan --run-id <uuid> --targets 10.0.0.0/24 --ports 1-1000 \
  --api http://localhost:8000 --token <token>
```

---

## Deploying scan agents (per segment)

Agents live in each network segment, not in the control-plane compose file. The
usual flow is:

1. In the UI, go to **Agents** and enroll an agent for the segment. You get a
   one-time bearer token.
2. Use the guided deploy panel, which gives you a ready-to-run **Docker** command,
   or run the native binary above.

With Docker, the agent image is either built from `apps/agent` or pulled from the
container registry once the `agent-image` workflow has published it
(`ghcr.io/<your-org>/portwiz-agent`). A typical run:

```bash
docker run -d --name portwiz-agent --restart unless-stopped \
  -e PORTWIZ_API_URL=https://portwiz.example.com \
  -e PORTWIZ_AGENT_TOKEN=<token> \
  ghcr.io/<your-org>/portwiz-agent
```

The agent needs network reach to the control plane and to the hosts it scans.
Give it the token once; rotate it from the UI if it leaks.

---

## Environment variables

The `deploy/.env.example` (dev) and `deploy/.env.prod.example` (prod) files are
the source of truth and are commented. The essentials:

| Variable | Purpose | Required |
|---|---|---|
| `PORTWIZ_DATABASE_URL` | asyncpg URL, e.g. `postgresql+asyncpg://user:pass@host:5432/portwiz` | Yes |
| `PORTWIZ_CELERY_BROKER_URL` | Broker, e.g. `redis://host:6379/0` | Yes |
| `PORTWIZ_CELERY_RESULT_BACKEND` | Results, e.g. `redis://host:6379/1` | Yes |
| `PORTWIZ_SECRET_KEY` | Signing key for sessions/JWT (`openssl rand -hex 32`) | Yes |
| `PORTWIZ_ENCRYPTION_KEY` | Fernet key encrypting stored integration secrets at rest | Recommended (required in production) |
| `PORTWIZ_ENVIRONMENT` | `development` or `production` | Yes |
| `PORTWIZ_CORS_ORIGINS` | JSON array of allowed browser origins (dev split-origin) | Dev only |
| `PORTWIZ_FIRST_ADMIN_EMAIL` / `_PASSWORD` | Seed the first admin on an empty database | Recommended |
| `VITE_API_BASE_URL` | Web build/runtime API base URL | Web only |
| `PORTWIZ_SMTP_*` | SMTP host/port/from/credentials for email notifications | Optional |
| `POSTGRES_USER` / `_PASSWORD` / `_DB` | Database credentials (compose only) | With Docker |

In `PORTWIZ_ENVIRONMENT=production`, startup hard-fails if `PORTWIZ_SECRET_KEY`,
`PORTWIZ_ENCRYPTION_KEY`, the seeded admin password, or the database password are
left at their placeholder/dev-default values. This is intentional: it stops a
production deploy from booting with known-weak secrets.

---

## TLS and exposure

The web service listens on plain HTTP. On a trusted internal network this is fine
and keeps deployment simple. Before exposing PortWiz to an untrusted network, put
your own TLS terminator (a reverse proxy, load balancer, or nginx with
certificates) in front of the web port: agents send their bearer token to the
API, so that traffic must be encrypted in transit.

## Notes

- **Migrations** run automatically when the API container boots. Running natively,
  run `alembic upgrade head` yourself before starting the API.
- The dev mail sink service is named `mailhog` in compose but runs Mailpit.
- The database and broker are the only stateful services; back up the Postgres
  volume for durability.
