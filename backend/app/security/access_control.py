from __future__ import annotations

from app.errors import AccessDeniedError
from app.security.auth_context import AuthContext


def resolve_account_scope(
    *,
    requested_account_ids: tuple[str, ...],
    auth_context: AuthContext,
) -> tuple[str, ...]:
    allowed_account_ids = tuple(
        account_id.strip()
        for account_id in auth_context.account_ids
        if account_id.strip()
    )

    if not allowed_account_ids:
        return requested_account_ids

    if not requested_account_ids:
        return allowed_account_ids

    scoped_account_ids = tuple(
        account_id for account_id in requested_account_ids if account_id in allowed_account_ids
    )
    if not scoped_account_ids:
        raise AccessDeniedError(
            "The request does not have access to the requested account scope.",
            detail=f"user_id={auth_context.user_id}",
        )
    return scoped_account_ids
