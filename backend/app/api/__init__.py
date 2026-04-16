# app/api/__init__.py
# 2026-04-02
"""Purpose: Build the top-level API router for Payjack runtime endpoints."""

##BRICK 1: Router composition
from fastapi import APIRouter

from app.api.routes_chat import router as chat_router
from app.api.routes_health import router as health_router


def build_api_router() -> APIRouter:
    router = APIRouter()
    router.include_router(health_router)
    router.include_router(chat_router)
    router.include_router(health_router, prefix="/api")
    router.include_router(chat_router, prefix="/api")
    return router

print("API router initialized with health and chat routes.")
