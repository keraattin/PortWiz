# PortWiz Scan Agent

A lightweight Go binary deployed **per VLAN/segment**. It pulls `ScanJob` orders
from the control plane, scans locally, and returns `ScanResult` over
JSON-over-HTTPS (see `packages/contracts`).

## Scanning engine

The default `Scanner` is a dependency-free **TCP connect scanner** (pure Go).
When `nmap` is present, an optional `nmap -sV` pass enriches each open port with
service, product, and version (the hybrid engine decision). The agent image
ships with nmap installed.

The `Scanner` interface is intentionally small so a `naabu`-based
implementation (SYN scans, higher throughput) can be swapped in behind it for
larger deployments without touching the rest of the agent.

## Modes

```bash
# Poll-and-scan loop (default): heartbeat, poll for jobs, scan, report.
portwiz-agent run

# One-shot scan that reports against an existing scan run (handy for testing).
portwiz-agent scan \
  --run-id <scan-run-uuid> \
  --targets 10.0.0.0/24,10.1.0.5 \
  --ports 1-1000 \
  --api http://localhost:8000 \
  --token <agent-token>
```

## Configuration

| Variable | Default | Purpose |
| - | - | - |
| `PORTWIZ_API_URL` | `http://localhost:8000` | Control plane base URL (use an `https://` URL in production) |
| `PORTWIZ_AGENT_TOKEN` | (none) | Bearer token issued at enrollment |
| `PORTWIZ_AGENT_ID` | `agent-local` | Agent identity label |
| `PORTWIZ_POLL_SECONDS` | `15` | Seconds between heartbeat + job polls |

## Tests

```bash
go test ./...
```

The scanner is tested hermetically against a loopback listener; no privileges
or network access are required.

## Notes

- The connect scanner is unprivileged. A future naabu/SYN backend needs
  `CAP_NET_RAW` (`cap_add: ["NET_RAW"]` on the container).
- Rate limiting defaults to an IDS-friendly 1000 pps for internal networks.
