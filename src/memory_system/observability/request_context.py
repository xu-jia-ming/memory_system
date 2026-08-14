"""Request-scoped context variables for observability."""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
user_id_var: ContextVar[str | None] = ContextVar("user_id", default=None)
session_id_var: ContextVar[str | None] = ContextVar("session_id", default=None)
task_run_id_var: ContextVar[str | None] = ContextVar("task_run_id", default=None)
archive_id_var: ContextVar[str | None] = ContextVar("archive_id", default=None)
task_id_var: ContextVar[str | None] = ContextVar("task_id", default=None)

_LOG_CONTEXT_FIELDS: dict[str, ContextVar[str | None]] = {
    "user_id": user_id_var,
    "session_id": session_id_var,
    "task_run_id": task_run_id_var,
    "archive_id": archive_id_var,
    "task_id": task_id_var,
}


def set_request_id(request_id: str) -> None:
    request_id_var.set(request_id)


def get_request_id() -> str | None:
    return request_id_var.get()


def set_task_run_id(task_run_id: str) -> None:
    task_run_id_var.set(task_run_id)


def get_task_run_id() -> str | None:
    return task_run_id_var.get()


def bind_log_context(**kwargs: Any) -> None:
    """Bind allowed log context fields for the current async/task scope."""
    for key, value in kwargs.items():
        if key not in _LOG_CONTEXT_FIELDS:
            continue
        if value is None:
            continue
        _LOG_CONTEXT_FIELDS[key].set(str(value))


def clear_task_context() -> None:
    """Clear worker task-scoped context between records/runs."""
    task_run_id_var.set(None)
    archive_id_var.set(None)
    task_id_var.set(None)
    user_id_var.set(None)
    session_id_var.set(None)


def clear_request_context() -> None:
    request_id_var.set(None)
    user_id_var.set(None)
    session_id_var.set(None)
    task_run_id_var.set(None)
    archive_id_var.set(None)
    task_id_var.set(None)
