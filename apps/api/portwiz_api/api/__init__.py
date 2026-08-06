"""API v1 router aggregation."""

from fastapi import APIRouter

from .routes import (
    agents,
    ai,
    audit,
    auth,
    certificates,
    changes,
    compliance,
    cve,
    evidence,
    ingest,
    ports,
    settings,
    stats,
    suppressions,
    tasks,
    update,
    users,
)
from .routes.inventory import assets_router, ip_ranges_router, vlans_router
from .routes.scans import profiles_router, runs_router

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(vlans_router)
api_router.include_router(ip_ranges_router)
api_router.include_router(assets_router)
api_router.include_router(agents.router)
api_router.include_router(ingest.router)
api_router.include_router(profiles_router)
api_router.include_router(runs_router)
api_router.include_router(changes.router)
api_router.include_router(ports.router)
api_router.include_router(certificates.router)
api_router.include_router(suppressions.router)
api_router.include_router(audit.router)
api_router.include_router(evidence.router)
api_router.include_router(tasks.router)
api_router.include_router(ai.router)
api_router.include_router(settings.router)
api_router.include_router(stats.router)
api_router.include_router(compliance.router)
api_router.include_router(cve.router)
api_router.include_router(update.router)

__all__ = ["api_router"]
