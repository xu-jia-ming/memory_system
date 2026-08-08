"""Prometheus metrics registration and helpers."""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path_template", "status"],
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "path_template", "status"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

COMPRESSION_TOTAL = Counter(
    "compression_total",
    "Compression operations",
    ["status"],
)

EXTRACTION_TASKS_TOTAL = Counter(
    "extraction_tasks_total",
    "Extraction tasks",
    ["status"],
)

EXTRACTION_TASK_DURATION_SECONDS = Histogram(
    "extraction_task_duration_seconds",
    "Extraction task duration in seconds",
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0),
)

RETRIEVAL_REQUESTS_TOTAL = Counter(
    "retrieval_requests_total",
    "Retrieval requests",
    ["mode", "status"],
)

RETRIEVAL_DURATION_SECONDS = Histogram(
    "retrieval_duration_seconds",
    "Retrieval duration in seconds",
    ["mode"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 15.0),
)

CONSOLIDATION_RUNS_TOTAL = Counter(
    "consolidation_runs_total",
    "Consolidation runs",
    ["status"],
)

KAFKA_CONSUMER_LAG = Gauge(
    "kafka_consumer_lag",
    "Kafka consumer lag",
)

ALL_METRICS = (
    HTTP_REQUESTS_TOTAL,
    HTTP_REQUEST_DURATION_SECONDS,
    COMPRESSION_TOTAL,
    EXTRACTION_TASKS_TOTAL,
    EXTRACTION_TASK_DURATION_SECONDS,
    RETRIEVAL_REQUESTS_TOTAL,
    RETRIEVAL_DURATION_SECONDS,
    KAFKA_CONSUMER_LAG,
    CONSOLIDATION_RUNS_TOTAL,
)


def observe_http_request(
    *,
    method: str,
    path_template: str,
    status: str,
    duration_seconds: float,
) -> None:
    labels = {
        "method": method,
        "path_template": path_template,
        "status": status,
    }
    HTTP_REQUESTS_TOTAL.labels(**labels).inc()
    HTTP_REQUEST_DURATION_SECONDS.labels(**labels).observe(duration_seconds)
