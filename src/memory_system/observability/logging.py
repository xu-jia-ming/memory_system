"""Structured JSON logging configuration."""

from __future__ import annotations

import logging
from typing import Any, cast

import structlog

from memory_system.observability.request_context import (
    _LOG_CONTEXT_FIELDS,
    get_request_id,
)
from memory_system.settings.models import Settings

DEFAULT_SERVICE_NAME = "memory-api"
_configured_service_name = DEFAULT_SERVICE_NAME


def _add_service_context(
    _logger: logging.Logger,
    _method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    event_dict.setdefault("service_name", _configured_service_name)
    request_id = get_request_id()
    if request_id is not None:
        event_dict.setdefault("request_id", request_id)
    for field_name, context_var in _LOG_CONTEXT_FIELDS.items():
        value = context_var.get()
        if value is not None:
            event_dict.setdefault(field_name, value)
    return event_dict


def configure_logging(settings: Settings, *, service_name: str = DEFAULT_SERVICE_NAME) -> None:
    """Configure structlog JSON logging with spec minimum fields."""
    global _configured_service_name
    _configured_service_name = service_name
    structlog.configure(
        processors=cast(
            Any,
            [
                structlog.contextvars.merge_contextvars,
                _add_service_context,
                structlog.processors.add_log_level,
                structlog.processors.TimeStamper(fmt="iso", utc=True),
                structlog.processors.JSONRenderer(),
            ],
        ),
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=False,
    )
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(environment=settings.app_env)
