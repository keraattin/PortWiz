"""Demo data seeding for local exploration.

Populates a realistic set of agents (in every health state), plus supporting
inventory, scans, changes and tasks so the UI has content to show. Idempotent:
it is a no-op once the demo VLAN exists.

Run against a running stack:
    docker exec portwiz-api-1 python -m portwiz_api.seed_demo
"""

from __future__ import annotations

import asyncio
import datetime as dt
import logging

from sqlalchemy import select

from .core.db import async_session_maker
from .core.security import generate_agent_token, hash_agent_token
from .models.agent import Agent
from .models.asset import VLAN, Asset, Criticality
from .models.change import ChangeEvent
from .models.scan import (
    Observation,
    ScanProfile,
    ScanRun,
    ScanRunStatus,
    ScanSource,
    ScanType,
)
from .models.task import Task, TaskStatus
from .models.user import User

logger = logging.getLogger("portwiz.seed_demo")

_MARKER_VLAN = "Corporate LAN"


def _agent(name: str, **kwargs) -> Agent:
    # Every agent needs a unique token hash even though the plaintext is thrown
    # away; the demo agents authenticate with tokens nobody holds.
    return Agent(name=name, token_hash=hash_agent_token(generate_agent_token()), **kwargs)


async def seed_demo(session_maker=None) -> None:
    """Seed demo data. ``session_maker`` defaults to the app engine; tests pass
    their own so the seed can run against the in-memory database."""
    maker = session_maker or async_session_maker
    now = dt.datetime.now(tz=dt.timezone.utc)

    def ago(**kw) -> dt.datetime:
        return now - dt.timedelta(**kw)

    async with maker() as session:
        exists = (
            await session.execute(select(VLAN).where(VLAN.name == _MARKER_VLAN))
        ).scalar_one_or_none()
        if exists is not None:
            logger.info("Demo data already present; skipping.")
            return

        admin = (await session.execute(select(User).limit(1))).scalar_one_or_none()
        admin_id = admin.id if admin else None

        # --- Agents (one per health state) ---
        agents = [
            _agent(
                "edge-scanner-01",
                segment="vlan10-corp",
                enabled=True,
                last_seen_at=ago(seconds=8),
                version="0.18.0",
                platform="linux/amd64",
                last_ip="10.10.0.12",
                token_rotated_at=ago(days=3),
            ),
            _agent(
                "edge-scanner-02",
                segment="vlan20-servers",
                enabled=True,
                last_seen_at=ago(seconds=45),
                version="0.18.0",
                platform="linux/arm64",
                last_ip="10.20.0.5",
            ),
            _agent(
                "dmz-probe",
                segment="dmz",
                enabled=True,
                last_seen_at=ago(minutes=25),
                version="0.17.0",
                platform="linux/amd64",
                last_ip="192.168.50.3",
            ),
            _agent(
                "branch-office-scanner",
                segment="vlan30-branch",
                enabled=True,
                last_seen_at=ago(hours=5),
                version="0.17.0",
                platform="linux/amd64",
                last_ip="172.16.4.9",
            ),
            _agent("lab-agent", segment=None, enabled=True, last_seen_at=None),
            _agent(
                "legacy-scanner",
                segment="vlan99",
                enabled=False,
                last_seen_at=ago(days=2),
                version="0.16.0",
                platform="linux/386",
                last_ip="10.99.0.2",
            ),
        ]
        session.add_all(agents)

        # --- Inventory: VLANs + assets ---
        corp = VLAN(name=_MARKER_VLAN, vlan_tag=10, description="Head-office user network")
        servers = VLAN(name="Server Segment", vlan_tag=20, description="Internal server farm")
        dmz = VLAN(name="Perimeter DMZ", vlan_tag=50, description="Internet-facing services")
        session.add_all([corp, servers, dmz])
        await session.flush()

        C = Criticality
        assets = [
            Asset(ip="10.10.0.12", hostname="hr-portal", vlan_id=corp.id, criticality=C.high),
            Asset(
                ip="10.20.0.5", hostname="db-primary", vlan_id=servers.id, criticality=C.critical
            ),
            Asset(ip="10.20.0.6", hostname="app-server-1", vlan_id=servers.id, criticality=C.high),
            Asset(ip="192.168.50.3", hostname="public-web", vlan_id=dmz.id, criticality=C.medium),
            Asset(
                ip="10.10.0.40",
                hostname="workstation-42",
                vlan_id=corp.id,
                criticality=Criticality.low,
                discovered=True,
            ),
        ]
        session.add_all(assets)

        # --- Scan profiles ---
        corp_profile = ScanProfile(
            name="Corporate weekly",
            targets=["10.10.0.0/24"],
            ports="top-1000",
            scan_type=ScanType.connect,
            service_detection=True,
            rate_limit_pps=1000,
            scan_source=ScanSource.internal_unauthenticated,
            segment="vlan10-corp",
            cron="0 2 * * 1",
            enabled=True,
            created_by=admin_id,
        )
        dmz_profile = ScanProfile(
            name="DMZ daily",
            targets=["192.168.50.0/24"],
            ports="1-1024",
            scan_type=ScanType.connect,
            service_detection=True,
            rate_limit_pps=500,
            scan_source=ScanSource.external_asv,
            segment="dmz",
            cron="0 3 * * *",
            enabled=True,
            created_by=admin_id,
        )
        session.add_all([corp_profile, dmz_profile])
        await session.flush()

        # --- Scan runs (completed / failed / pending) ---
        done_corp = ScanRun(
            scan_profile_id=corp_profile.id,
            agent_id="edge-scanner-01",
            status=ScanRunStatus.completed,
            scan_source=ScanSource.internal_unauthenticated,
            started_at=ago(hours=2),
            finished_at=ago(hours=2) + dt.timedelta(minutes=4),
            attempts=1,
        )
        done_dmz = ScanRun(
            scan_profile_id=dmz_profile.id,
            agent_id="dmz-probe",
            status=ScanRunStatus.completed,
            scan_source=ScanSource.external_asv,
            started_at=ago(days=1),
            finished_at=ago(days=1) + dt.timedelta(minutes=6),
            attempts=1,
        )
        failed = ScanRun(
            scan_profile_id=dmz_profile.id,
            agent_id="dmz-probe",
            status=ScanRunStatus.failed,
            scan_source=ScanSource.external_asv,
            started_at=ago(hours=6),
            finished_at=ago(hours=6) + dt.timedelta(minutes=30),
            attempts=3,
            error="Agent did not return results after 3 attempts",
        )
        pending = ScanRun(
            scan_profile_id=corp_profile.id,
            status=ScanRunStatus.pending,
            scan_source=ScanSource.internal_unauthenticated,
        )
        session.add_all([done_corp, done_dmz, failed, pending])
        await session.flush()

        # --- Observations for the completed corporate run ---
        obs_ts = done_corp.finished_at or now
        observations = [
            ("10.10.0.12", 22, "ssh", "OpenSSH 9.6"),
            ("10.10.0.12", 443, "https", "nginx/1.25.4"),
            ("10.20.0.5", 5432, "postgresql", "PostgreSQL 16.2"),
            ("10.20.0.6", 8080, "http", "Apache Tomcat 10.1"),
        ]
        session.add_all(
            Observation(
                ts=obs_ts,
                scan_run_id=done_corp.id,
                ip=ip,
                port=port,
                protocol="tcp",
                state="open",
                service=service,
                version=version,
            )
            for ip, port, service, version in observations
        )

        # --- Change events ---
        changes = [
            ChangeEvent(
                scan_profile_id=corp_profile.id,
                scan_run_id=done_corp.id,
                asset_id=assets[2].id,
                ip="10.20.0.6",
                port=8080,
                protocol="tcp",
                change_type="opened",
                before={"state": "closed"},
                after={"state": "open", "service": "http", "version": "Apache Tomcat 10.1"},
                severity="high",
                status="open",
                detected_at=ago(hours=3),
            ),
            ChangeEvent(
                scan_profile_id=corp_profile.id,
                scan_run_id=done_corp.id,
                asset_id=assets[0].id,
                ip="10.10.0.12",
                port=443,
                protocol="tcp",
                change_type="service_changed",
                before={"service": "https", "version": "nginx/1.24.0"},
                after={"service": "https", "version": "nginx/1.25.4"},
                severity="medium",
                status="acknowledged",
                detected_at=ago(days=1),
            ),
            ChangeEvent(
                scan_profile_id=dmz_profile.id,
                scan_run_id=done_dmz.id,
                asset_id=assets[3].id,
                ip="192.168.50.3",
                port=21,
                protocol="tcp",
                change_type="closed",
                before={"state": "open", "service": "ftp"},
                after={"state": "closed"},
                severity="medium",
                status="resolved",
                detected_at=ago(days=2),
            ),
            ChangeEvent(
                scan_profile_id=corp_profile.id,
                scan_run_id=done_corp.id,
                asset_id=assets[1].id,
                ip="10.20.0.5",
                port=5432,
                protocol="tcp",
                change_type="version_changed",
                before={"version": "PostgreSQL 15.6"},
                after={"version": "PostgreSQL 16.2"},
                severity="low",
                status="open",
                detected_at=ago(hours=5),
            ),
        ]
        session.add_all(changes)
        await session.flush()

        # --- Tasks linked to the two open-ish changes ---
        session.add_all(
            [
                Task(
                    title="Investigate new port 8080 on app-server-1",
                    description=(
                        "Tomcat appeared on 10.20.0.6:8080. Confirm it is an approved deployment."
                    ),
                    status=TaskStatus.open,
                    change_event_id=changes[0].id,
                    assignee_id=admin_id,
                    created_by=admin_id,
                ),
                Task(
                    title="Review TLS service change on hr-portal",
                    description=(
                        "nginx upgraded 1.24.0 -> 1.25.4 on 10.10.0.12:443. "
                        "Verify the change ticket."
                    ),
                    status=TaskStatus.in_progress,
                    change_event_id=changes[1].id,
                    assignee_id=admin_id,
                    created_by=admin_id,
                ),
            ]
        )

        await session.commit()
        logger.info("Demo data seeded: %d agents, 3 VLANs, %d assets.", len(agents), len(assets))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # Demo data (hardcoded agents/assets/scans) is a local-exploration tool and
    # must never populate a real deployment.
    from .core.config import get_settings

    if get_settings().environment == "production":
        raise SystemExit(
            "Refusing to seed demo data in a production environment; "
            "this tool is for local exploration only."
        )
    asyncio.run(seed_demo())
