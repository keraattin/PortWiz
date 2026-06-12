"""PortWiz control plane application entry point."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .api import api_router
from .api.routes.health import router as health_router
from .core.config import get_settings
from .seed import seed_first_admin

logging.basicConfig(level=logging.INFO)
settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Migrations are applied by the container entrypoint (alembic upgrade head)
    # before the app boots; here we only seed idempotent data.
    await seed_first_admin()
    yield


app = FastAPI(
    title=settings.app_name,
    version=__version__,
    description="Audit-ready, AI-assisted port & service change monitoring.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health endpoints live at the root for container probes.
app.include_router(health_router)
# Versioned API.
app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/", tags=["meta"])
async def root() -> dict[str, str]:
    return {"name": settings.app_name, "version": __version__}
