# PortWiz Scan Agent

A lightweight Go binary deployed **per VLAN/segment**. It executes `ScanJob`
orders from the control plane and returns `ScanResult` over JSON-over-HTTPS
(see `packages/contracts`).

## Status

- **M0 (current):** heartbeat-only stub that proves control-plane connectivity.
- **M2:** embed [`naabu`](https://github.com/projectdiscovery/naabu) as a library
  for port discovery, add `nmap-service-probes` matching for service/version
  detection, agent enrollment (token + `agent_id`), and result reporting.

## Run locally

```bash
go run ./cmd/agent
```

Environment:

| Variable | Default | Purpose |
|---|---|---|
| `PORTWIZ_API_URL` | `http://localhost:8000` | Control plane base URL |
| `PORTWIZ_AGENT_ID` | `agent-local` | Agent identity (assigned at enrollment in M2) |
| `PORTWIZ_AGENT_TOKEN` | (none) | Bearer token used to authenticate to the control plane (M2) |

## Notes

- SYN scans require `CAP_NET_RAW`; the container must be granted it
  (`cap_add: ["NET_RAW"]`) or fall back to CONNECT scans.
- Rate limiting defaults to an IDS-friendly 1000 pps for internal networks.
