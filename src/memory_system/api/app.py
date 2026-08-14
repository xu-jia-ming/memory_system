"""FastAPI application factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from memory_system.api.error_handlers import register_error_handlers
from memory_system.api.middleware import AccessLogMetricsMiddleware, RequestIdMiddleware
from memory_system.api.routes import (
    health,
    internal_metrics,
    memory_extraction_admin,
    memory_message,
    memory_retrieval,
    memory_session,
)
from memory_system.infrastructure.llm import FakeLlmClient
from memory_system.infrastructure.llm.protocol import LLMClient
from memory_system.infrastructure.runtime import AppState, create_app_state, shutdown_app_state
from memory_system.observability.logging import configure_logging
from memory_system.settings.models import Settings, get_settings


@asynccontextmanager
async def _production_lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    state = await create_app_state(settings)
    app.state.app_state = state
    try:
        yield
    finally:
        await shutdown_app_state(state)


def create_app(
    settings: Settings | None = None,
    *,
    app_state: AppState | None = None,
    llm_client: LLMClient | None = None,
) -> FastAPI:
    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings, service_name="memory-api")

    if app_state is not None:

        @asynccontextmanager
        async def lifespan(app: FastAPI) -> AsyncIterator[None]:
            app.state.app_state = app_state
            yield

    else:
        lifespan = _production_lifespan

    app = FastAPI(
        title="Memory System API",
        lifespan=lifespan,
    )
    app.state.settings = resolved_settings
    app.state.llm_client = llm_client or FakeLlmClient()

    app.add_middleware(AccessLogMetricsMiddleware)
    app.add_middleware(RequestIdMiddleware)

    register_error_handlers(app)
    app.include_router(health.router)
    app.include_router(internal_metrics.router)
    app.include_router(memory_session.router)
    app.include_router(memory_message.router)
    app.include_router(memory_extraction_admin.router)
    app.include_router(memory_retrieval.router)

    return app
