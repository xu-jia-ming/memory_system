"""Request-scoped context variables for observability."""

from __future__ import annotations

from contextvars import ContextVar

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
user_id_var: ContextVar[str | None] = ContextVar("user_id", default=None)
session_id_var: ContextVar[str | None] = ContextVar("session_id", default=None)


def set_request_id(request_id: str) -> None:
    request_id_var.set(request_id)


def get_request_id() -> str | None:
    return request_id_var.get()


def clear_request_context() -> None:
    request_id_var.set(None)
    user_id_var.set(None)
    session_id_var.set(None)
