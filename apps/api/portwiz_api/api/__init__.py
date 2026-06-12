"""API v1 router aggregation."""

from fastapi import APIRouter

from .routes import auth, users
from .routes.inventory import assets_router, ip_ranges_router, vlans_router

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(vlans_router)
api_router.include_router(ip_ranges_router)
api_router.include_router(assets_router)

__all__ = ["api_router"]
