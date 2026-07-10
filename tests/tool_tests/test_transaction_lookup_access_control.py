import pytest

from app.repository.contracts import StoreLocation
from app.repository.processed_store import ProcessedStore
from app.errors import AccessDeniedError
from app.security.auth_context import AuthContext
from app.tools.registry import ToolInvocation, ToolRegistry


def test_tool_registry_scopes_transactions_to_allowed_accounts(processed_test_assets) -> None:
    store = ProcessedStore(StoreLocation(mode="local", local_root=processed_test_assets["processed_root"]))
    registry = ToolRegistry(store=store)

    result = registry.invoke(
        ToolInvocation(name="transaction_lookup", arguments={"limit": 5}),
        auth_context=AuthContext(
            user_id="user-123",
            tenant_id="tenant-001",
            roles=("customer",),
            account_ids=("acc-001",),
        ),
    )

    account_ids = {record["account_id"] for record in result.payload["records"]}
    assert account_ids == {"acc-001"}


def test_tool_registry_rejects_disallowed_account_scope(processed_test_assets) -> None:
    store = ProcessedStore(StoreLocation(mode="local", local_root=processed_test_assets["processed_root"]))
    registry = ToolRegistry(store=store)

    with pytest.raises(AccessDeniedError):
        registry.invoke(
            ToolInvocation(name="transaction_lookup", arguments={"account_ids": ("acc-002",)}),
            auth_context=AuthContext(
                user_id="user-123",
                tenant_id="tenant-001",
                roles=("customer",),
                account_ids=("acc-001",),
            ),
        )
