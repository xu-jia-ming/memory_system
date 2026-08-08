"""FastAPI dependencies for settings, auth, and request context."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, Request

from memory_system.api.errors import AppError
from memory_system.infrastructure.security.api_key import ApiKeyRole, verify_api_key
from memory_system.settings.models import Settings, get_settings


def get_settings_dep() -> Settings:
    return get_settings()


def get_request_id(request: Request) -> str:
    request_id = getattr(request.state, "request_id", None)
    if not isinstance(request_id, str) or not request_id:
        raise AppError(
            code="internal_error",
            message="Request ID missing",
            status_code=503,
        )
    return request_id


def _resolve_api_key_role(api_key: str | None, settings: Settings) -> ApiKeyRole | None:
    if verify_api_key(api_key, settings.memory_admin_api_key):
        return ApiKeyRole.ADMIN
    if verify_api_key(api_key, settings.memory_api_key):
        return ApiKeyRole.MEMORY
    return None


async def require_memory_api_key(
    settings: Annotated[Settings, Depends(get_settings_dep)],
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> ApiKeyRole:
    role = _resolve_api_key_role(x_api_key, settings)
    if role is None:
        raise AppError(
            code="invalid_api_key",
            message="Invalid API key",
            status_code=401,
        )
    return role


async def require_admin_api_key(
    settings: Annotated[Settings, Depends(get_settings_dep)],
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> ApiKeyRole:
    if verify_api_key(x_api_key, settings.memory_admin_api_key):
        return ApiKeyRole.ADMIN
    if verify_api_key(x_api_key, settings.memory_api_key):
        # Engineering freeze (DEV-005): valid memory key on admin route => 403 forbidden.
        # Spec §3.21 forbids distinguishing missing vs invalid keys (401 invalid_api_key).
        raise AppError(
            code="forbidden",
            message="Forbidden",
            status_code=403,
        )
    raise AppError(
        code="invalid_api_key",
        message="Invalid API key",
        status_code=401,
    )
