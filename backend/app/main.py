# app/main.py
# 2026-04-02
"""Purpose: Construct the Payjack FastAPI application with local env bootstrapping."""

from __future__ import annotations

##BRICK 1: Imports and local env bootstrap
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import build_api_router
from app.config import Settings
from app.dependencies import build_dependencies
from app.env import load_local_env
from app.telemetry.logging import configure_logging


##BRICK 2: Application factory
def create_app() -> FastAPI:
    """Create the configured FastAPI application instance."""

    load_local_env()
    settings = Settings.from_env()
    configure_logging(settings.log_level)

    app = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.dependencies = build_dependencies(settings)
    app.include_router(build_api_router())
    return app


##BRICK 3: ASGI application export
app = create_app()
