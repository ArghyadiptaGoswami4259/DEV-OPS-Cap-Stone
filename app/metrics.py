"""Custom Prometheus metrics with bounded route cardinality."""

from __future__ import annotations

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, Info, generate_latest

REQUESTS = Counter(
    "taskflow_http_requests_total",
    "Total HTTP requests handled by TaskFlow.",
    ["method", "route", "status"],
)
LATENCY = Histogram(
    "taskflow_http_request_duration_seconds",
    "HTTP request latency in seconds.",
    ["method", "route"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)
IN_FLIGHT = Gauge("taskflow_http_requests_in_flight", "Requests currently in flight.")
READY = Gauge("taskflow_ready", "Whether the service's dependencies are ready (1 or 0).")
TASK_OPERATIONS = Counter(
    "taskflow_task_operations_total",
    "Task mutations by operation.",
    ["operation"],
)
BUILD_INFO = Info("taskflow_build", "Build metadata for the running TaskFlow instance.")


def set_build_info(version: str, commit: str, environment: str) -> None:
    BUILD_INFO.info({"version": version, "commit": commit, "environment": environment})


def set_ready(ready: bool) -> None:
    READY.set(1 if ready else 0)


def render_metrics() -> tuple[bytes, str]:
    return generate_latest(), CONTENT_TYPE_LATEST
