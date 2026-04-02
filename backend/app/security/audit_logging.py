from __future__ import annotations

import json
import logging
from typing import Any

from app.security.auth_context import AuthContext


logger = logging.getLogger(__name__)


def log_audit_event(
    *,
    event_type: str,
    request_id: str,
    auth_context: AuthContext,
    payload: dict[str, Any],
) -> None:
    logger.info(
        "audit_event %s",
        json.dumps(
            {
                "event_type": event_type,
                "request_id": request_id,
                "user_id": auth_context.user_id,
                "tenant_id": auth_context.tenant_id,
                "roles": list(auth_context.roles),
                "payload": payload,
            },
            sort_keys=True,
            default=str,
        ),
    )
