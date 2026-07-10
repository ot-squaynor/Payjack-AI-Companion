from __future__ import annotations

from dataclasses import dataclass

from app.config import Settings


@dataclass(frozen=True, slots=True)
class SelectedModel:
    model_id: str
    reason: str


def select_model(*, route: str, settings: Settings) -> SelectedModel:
    return SelectedModel(
        model_id=settings.bedrock_model_id,
        reason=f"default_model_for_{route}",
    )
