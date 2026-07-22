<div align="center">

# PortWiz

**Open-source, AI-assisted port & service change monitoring and compliance platform**

_Not just a port scanner. It produces audit-ready **evidence of change**._

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](./LICENSE)

</div>

---

## What is PortWiz?

PCI-DSS, ISO 27001, SOC 2, HIPAA and NIST audits require **periodic monitoring of
open ports/services and detection of changes** on network assets. PortWiz covers
that requirement and takes it a step further:

- 🔁 **Flapping-aware change detection**: a confirmation-based diff engine that
  separates real changes from network noise. No false positives.
- 🔒 **Immutable (hash-chained) audit log**: who scanned/approved/exported what
  and when. Tamper-evident evidence for auditors.
- 📦 **One-click evidence package**: scan report + change diff + linked
  task/approval + audit-log slice → signed JSON/PDF.
- 🛰️ **Distributed scan agents**: a lightweight Go agent placed in each
  VLAN/segment; `naabu` + `nmap-service-probes`. Runs are routed per segment, and
  a run an agent claims but never finishes is automatically requeued.
- 🗂️ **Inventory at scale**: manage assets and VLANs by hand, bulk-import from
  CSV/Excel, or sync bidirectionally with NetBox (IPAM): pull hosts and VLANs in,
  and write scan-discovered hosts back. Hosts found during a scan are auto-added as
  assets; each carries owner, criticality, and data-sensitivity for scoping.
- 🛡️ **CVE enrichment**: match a discovered service and version against known CVEs
  from NVD (online), or, for **air-gapped** installs, an imported NVD feed served
  entirely offline. Findings are stored per asset and port, with an optional
  AI-written brief. See [docs/offline-cve.md](./docs/offline-cve.md).
- 🤖 **Provider-agnostic AI**: refines weak service fingerprints during scans, plus
  an agentic assistant that proposes actions for you to confirm. Local model
  (Ollama) by default, with Claude or any OpenAI-compatible provider optional; data
  never leaves the network.
- 🔗 **Workflow integrations**: in-app tasks, and notifications via email, Slack,
  and Microsoft Teams with per-channel rules (minimum severity, scan-profile
  scope) and immediate or digested delivery with quiet hours. Plus Jira (Cloud or
  Server/Data Center, bidirectional) with configurable project, issue type,
  assignee and labels. A settings page tests each connection. Phase 2: AD/SSO.
- 🌍 **Built for non-experts**: a collapsible left sidebar, light/dark themes, six
  UI languages, searchable/filterable/paginated tables, and scan setup that picks
  targets from your inventory and schedules by plain-language period (no cron).

## Architecture

```
┌──────────────┐    ScanJob (HTTPS)    ┌──────────────────┐
│  React UI    │◀───────┐              │  Scan Agent (Go) │  per-VLAN
│ (dashboard,  │        │   ┌─────────▶│  naabu + probes  │
│  diff, evid.)│        │   │ ScanResult└──────────────────┘
└──────┬───────┘        │   │ (HTTPS)
       │ REST           │   │
┌──────▼─────────────────▼──┴────────────────────────────┐
│  FastAPI Control Plane                                  │
│  auth/RBAC · scheduler · change-detection · audit ·     │
│  evidence · fingerprint · integrations(jira/email)      │
└──────┬──────────────┬───────────────┬──────────────────┘
       │              │               │
┌──────▼─────┐  ┌─────▼──────┐  ┌─────▼───────────────┐
│ PostgreSQL │  │  Celery +  │  │  AI layer           │
│ +TimescaleDB│ │  Valkey    │  │  Ollama / Claude    │
└────────────┘  └────────────┘  └─────────────────────┘
```

## Quick start (development)

> Requires: Docker + Docker Compose. For a full component-by-component install
> guide (Docker **and** without Docker), see [docs/installation.md](docs/installation.md).

```bash
cd deploy
cp .env.example .env        # fill in secrets
docker compose up --build
```

- API:        http://localhost:8000  (docs: `/docs`)
- Web UI:     http://localhost:5173
- MailHog:    http://localhost:8025  (outgoing email)

The first admin user is seeded from the `PORTWIZ_FIRST_ADMIN_*` values in `.env`.

For production, set `PORTWIZ_ENCRYPTION_KEY` (see `.env.example` for the one-line
generator) to encrypt stored integration secrets (API keys, tokens, and the SMTP
password) at rest. Keep the key stable: rotating or losing it makes existing
secrets unreadable.

## Production deployment

A separate compose file runs the hardened, single-origin stack. Containers run
as a non-root user, the API/DB/broker are never published to the host, and one
nginx service serves the built SPA and reverse-proxies `/api` and `/health`
(no CORS).

```bash
cd deploy
cp .env.prod.example .env.prod   # set strong secrets, DB password, admin, SMTP
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
```

- Web UI: http://localhost:8080  (change `WEB_PORT` in `.env.prod`)

The API applies database migrations on boot before it turns healthy; the worker
and beat services wait for that. Notes:

- **TLS:** the web service listens on plain HTTP. Put your own TLS terminator
  (reverse proxy, load balancer, or nginx with certificates) in front of it
  before exposing PortWiz to a real network: agents send their bearer token to
  the API, so that traffic must be encrypted.
- **Secrets:** set `PORTWIZ_SECRET_KEY` and `PORTWIZ_ENCRYPTION_KEY` to fresh
  random values, and use a strong `POSTGRES_PASSWORD` (kept in sync with
  `PORTWIZ_DATABASE_URL`).
- **Agents** are deployed per network segment, not by this compose file. Enroll
  an agent in the UI and use the guided deploy panel, which gives you a one-time
  `docker build` and a ready-to-run `docker run` command. The agent image is
  either built from `apps/agent` (the panel's build command) or pulled from GHCR
  once the `agent-image` workflow has published it
  (`ghcr.io/<your-org>/portwiz-agent`); make that package public to pull without
  authentication.
- **Local AI (optional):** add `--profile ai` to start Ollama and set
  `PORTWIZ_AI_PROVIDER=ollama`.

## Running without Docker (native)

You can run each component directly on the host instead of in containers. A
practical middle ground is to run just the database and broker with Docker
(`cd deploy && docker compose up db valkey`) and the app components natively.

> The database must be PostgreSQL **with the TimescaleDB extension** (observations
> use a hypertable); a stock `postgres` fails the migrations.

Point the shared settings at localhost (`PORTWIZ_DATABASE_URL=postgresql+asyncpg://portwiz:portwiz@localhost:5432/portwiz`,
`PORTWIZ_CELERY_BROKER_URL=redis://localhost:6379/0`,
`PORTWIZ_CELERY_RESULT_BACKEND=redis://localhost:6379/1`, plus a
`PORTWIZ_SECRET_KEY` and the `PORTWIZ_FIRST_ADMIN_*` values), then:

```bash
# API (Python 3.11+), from apps/api:
python -m venv .venv && . .venv/bin/activate     # PowerShell: .venv\Scripts\Activate.ps1
pip install -e .
alembic upgrade head
uvicorn portwiz_api.main:app --host 0.0.0.0 --port 8000

# Worker and beat (from apps/api, same env):
celery -A portwiz_api.workers.celery_app.celery_app worker --loglevel=info
celery -A portwiz_api.workers.celery_app.celery_app beat --loglevel=info --schedule=./celerybeat-schedule

# Web (Node 22), from apps/web:
npm ci
VITE_API_BASE_URL=http://localhost:8000 npm run dev -- --host 0.0.0.0   # or: VITE_API_BASE_URL="" npm run build

# Scan agent (Go 1.23), from apps/agent; enroll in the UI first to get a token:
go build -trimpath -o portwiz-agent ./cmd/agent
PORTWIZ_API_URL=http://localhost:8000 PORTWIZ_AGENT_TOKEN=<token> ./portwiz-agent run
```

See **[docs/installation.md](docs/installation.md)** for the full component-by-component
guide (Docker and native), the environment-variable reference, and agent deployment.

## Repository layout

| Path | Contents |
|---|---|
| `apps/api` | FastAPI control plane (Python 3.11+) |
| `apps/web` | React + TypeScript + Tailwind (Vite) |
| `apps/agent` | Go scan agent (naabu + service-probes) |
| `packages/contracts` | Shared agent ↔ control-plane JSON schemas |
| `deploy` | docker-compose (Phase 2: helm) |
| `docs` | architecture & development notes |

## Roadmap

- **Phase 1 (MVP), done:** asset/VLAN/IP management → scanning → flapping-aware
  diff → audit + evidence export → task/Jira/email + scheduling → AI v0, plus a
  live dashboard, role-based UI, and admin pages (users, agents, settings).
- **Phase 2, in progress:** ✅ bulk CSV/Excel import (assets + VLANs),
  ✅ bidirectional NetBox/IPAM sync, ✅ Jira Cloud & Server/Data Center,
  ✅ per-segment agent routing + stale-run requeue + fleet coverage view,
  ✅ compliance cadence templates, ✅ CVE enrichment (online NVD + offline feed),
  ✅ in-app update check with one-click apply, ✅ integration connection tests,
  ✅ Slack/Teams notifications with per-channel rules, digests and quiet hours,
  ✅ localized (six-language) themeable UI. Next: Keycloak (AD/LDAP/SSO),
  SIEM/WORM forwarding.
- **Phase 3:** MCP/RAG AI assistant, local-only mode, Kubernetes/Helm, passive
  discovery correlation.

## License

[Apache-2.0](./LICENSE). Third-party component notices: [`NOTICES.txt`](./NOTICES.txt).
