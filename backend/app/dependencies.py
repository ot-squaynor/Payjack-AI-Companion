# app/dependencies.py
# 2026-04-02
"""Purpose: Assemble the runtime dependency graph for the Payjack backend."""

from __future__ import annotations

##BRICK 1: Imports and dependency container contract
from dataclasses import dataclass

from app.config import Settings
from app.llm.autoregressive.bedrock_client import build_generation_client
from app.memory.session_memory import InMemorySessionMemoryStore
from app.orchestrator.workflow_engine import WorkflowEngine
from app.rag.retriever import build_retriever
from app.repository.contracts import StoreLocation
from app.repository.processed_store import ProcessedStore
from app.tools.registry import ToolRegistry


@dataclass(slots=True)
class AppDependencies:
    settings: Settings
    processed_store: ProcessedStore
    tool_registry: ToolRegistry
    llm_client: object
    retriever: object | None
    session_memory: InMemorySessionMemoryStore
    workflow_engine: WorkflowEngine


##BRICK 2: Dependency graph construction
def build_dependencies(settings: Settings | None = None) -> AppDependencies:
    resolved_settings = settings or Settings.from_env()
    store = ProcessedStore(
        StoreLocation(
            mode=resolved_settings.processed_store_mode,
            local_root=resolved_settings.processed_local_root,
            s3_bucket=resolved_settings.processed_s3_bucket,
            s3_prefix=resolved_settings.processed_s3_prefix,
        )
    )
    tool_registry = ToolRegistry(store=store)
    retriever = build_retriever(resolved_settings)
    llm_client = build_generation_client(resolved_settings)
    session_memory = InMemorySessionMemoryStore()
    workflow_engine = WorkflowEngine(
        settings=resolved_settings,
        tool_registry=tool_registry,
        llm_client=llm_client,
        retriever=retriever,
        session_memory=session_memory,
    )
    return AppDependencies(
        settings=resolved_settings,
        processed_store=store,
        tool_registry=tool_registry,
        llm_client=llm_client,
        retriever=retriever,
        session_memory=session_memory,
        workflow_engine=workflow_engine,
    )
