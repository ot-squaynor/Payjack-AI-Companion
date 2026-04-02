from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request


router = APIRouter(tags=["health"])


@router.get("/health")
async def health(request: Request) -> dict[str, object]:
    dependencies = request.app.state.dependencies
    return {
        "status": "ok",
        "app": dependencies.settings.app_name,
        "environment": dependencies.settings.app_env,
    }


@router.get("/ready")
async def ready(request: Request) -> dict[str, object]:
    dependencies = request.app.state.dependencies
    repository_health = dependencies.processed_store.healthcheck()
    if not repository_health.ready:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "not_ready",
                "detail": repository_health.detail,
            },
        )

    return {
        "status": "ready",
        "dataset_version": repository_health.dataset_version,
        "artifact_count": repository_health.artifact_count,
    }
