"""Ingest payload is bounded so a compromised agent token can't drive huge
memory/DB writes or push megabyte banners."""

from __future__ import annotations

import datetime as dt
import uuid

import pytest
from pydantic import ValidationError

from portwiz_api.schemas.scan import HostIn, PortIn, ScanResultIn


def _port(p: int = 80) -> dict:
    return {"port": p, "protocol": "tcp", "state": "open"}


def _result(hosts: list) -> None:
    ScanResultIn(
        version=1,
        job_id=uuid.uuid4(),
        scan_run_id=uuid.uuid4(),
        agent_id="a",
        started_at=dt.datetime.now(dt.timezone.utc),
        finished_at=dt.datetime.now(dt.timezone.utc),
        hosts=hosts,
    )


def test_banner_length_capped() -> None:
    with pytest.raises(ValidationError):
        PortIn(port=80, protocol="tcp", state="open", banner="x" * 8193)


def test_hostname_length_capped() -> None:
    with pytest.raises(ValidationError):
        HostIn(ip="10.0.0.1", hostname="h" * 254, ports=[])


def test_ports_per_host_capped() -> None:
    with pytest.raises(ValidationError):
        HostIn(ip="10.0.0.1", ports=[_port(1) for _ in range(65537)])


def test_hosts_per_ingest_capped() -> None:
    with pytest.raises(ValidationError):
        _result([{"ip": "10.0.0.1", "ports": []} for _ in range(65537)])


def test_reasonable_payload_ok() -> None:
    _result([{"ip": "10.0.0.1", "ports": [_port(80), _port(443)]}])
