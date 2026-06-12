"""API v1 router aggregation."""

from fastapi import APIRouter

from .routes import auth, users

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)

__all__ = ["api_router"]
