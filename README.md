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
  VLAN/segment; `naabu` + `nmap-service-probes`.
- 🤖 **Provider-agnostic AI**: fingerprints unknown services and a natural-language
  assistant. Local model (Ollama) by default, Claude optional; data never leaves
  the network.
- 🔗 **Workflow integrations**: in-app tasks, email, Jira (bidirectional).
  Phase 2: Slack/Teams, AD/SSO.

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

> Requires: Docker + Docker Compose.

```bash
cd deploy
cp .env.example .env        # fill in secrets
docker compose up --build
```

- API:        http://localhost:8000  (docs: `/docs`)
- Web UI:     http://localhost:5173
- MailHog:    http://localhost:8025  (outgoing email)

The first admin user is seeded from the `PORTWIZ_FIRST_ADMIN_*` values in `.env`.

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

- **Phase 1 (MVP):** asset/VLAN/IP management → scanning → flapping-aware diff →
  audit + evidence export → task/Jira/email + scheduling → AI v0.
- **Phase 2:** compliance cadence templates, agent fleet, Keycloak
  (AD/LDAP/SSO), Slack/Teams, SIEM/WORM forwarding.
- **Phase 3:** MCP/RAG AI assistant, local-only mode, Kubernetes/Helm, passive
  discovery correlation.

## License

[Apache-2.0](./LICENSE). Third-party component notices: [`NOTICES.txt`](./NOTICES.txt).
