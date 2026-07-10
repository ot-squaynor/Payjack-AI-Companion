from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True, slots=True)
class AuthContext:
    user_id: str
    tenant_id: str
    roles: tuple[str, ...] = ()
    account_ids: tuple[str, ...] = ()

    @classmethod
    def from_headers(cls, headers: Mapping[str, str]) -> "AuthContext":
        user_id = headers.get("x-payjack-user-id", "dev-user").strip() or "dev-user"
        tenant_id = headers.get("x-payjack-tenant-id", "dev-tenant").strip() or "dev-tenant"
        roles_header = headers.get("x-payjack-roles", "")
        accounts_header = headers.get("x-payjack-account-ids", "")
        roles = tuple(role.strip() for role in roles_header.split(",") if role.strip())
        account_ids = tuple(
            account_id.strip()
            for account_id in accounts_header.split(",")
            if account_id.strip()
        )
        return cls(
            user_id=user_id,
            tenant_id=tenant_id,
            roles=roles,
            account_ids=account_ids,
        )
