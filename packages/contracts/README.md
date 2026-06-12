# PortWiz Contracts

The **language-agnostic** contract between the scan agent and the control plane.
The Go agent and the Python control plane both conform to these JSON schemas.
A schema change is a breaking change affecting both sides; bump the `version`
field accordingly.

- `scan_job.schema.json` — the scan order sent from the control plane to an agent.
- `scan_result.schema.json` — the scan result returned from an agent to the center.

## Transport

`ScanResult` is POSTed by the agent to the control plane over **JSON-over-HTTPS**
(`Authorization: Bearer <agent-token>`). gRPC is intentionally not used (protobuf
CVE-2025-4565, untrusted scan input). All timestamps are RFC 3339 / UTC; the
center normalizes against `received_at` to avoid clock-skew phantom diffs.
