from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import build_api_router
from app.config import Settings
from app.dependencies import build_dependencies
from app.telemetry.logging import configure_logging


def create_app() -> FastAPI:
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


app = create_app()
