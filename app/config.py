"""Strongly typed environment configuration for TaskFlow."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name, str(default)).strip().lower()
    return value in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


@dataclass(frozen=True, slots=True)
class Settings:
    app_name: str
    version: str
    git_sha: str
    environment: str
    database_url: str
    log_level: str
    auto_create_schema: bool
    failure_rate: float
    port: int
    otel_service_name: str
    host: str = "127.0.0.1"
    forwarded_allow_ips: str = "127.0.0.1"

    @classmethod
    def from_env(cls) -> Settings:
        environment = os.getenv("APP_ENVIRONMENT", "local").strip().lower() or "local"
        failure_rate = max(0.0, min(1.0, _env_float("APP_FAILURE_RATE", 0.0)))
        # Failure injection is a canary-drill aid and can never be enabled in prod.
        if environment == "prod":
            failure_rate = 0.0
        try:
            port = int(os.getenv("PORT", "8080"))
        except ValueError:
            port = 8080
        # Containers set HOST explicitly; the safe direct-run default is loopback only.
        host = os.getenv("HOST", "127.0.0.1").strip() or "127.0.0.1"
        forwarded_allow_ips = (
            os.getenv("FORWARDED_ALLOW_IPS", "127.0.0.1").strip() or "127.0.0.1"
        )
        return cls(
            app_name=os.getenv("APP_NAME", "TaskFlow"),
            version=os.getenv("APP_VERSION", "1.0.0"),
            git_sha=os.getenv("APP_GIT_SHA", "unknown")[:12],
            environment=environment,
            database_url=os.getenv("DATABASE_URL", "sqlite:///./.cache/taskflow.db"),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
            auto_create_schema=_env_bool("AUTO_CREATE_SCHEMA", True),
            failure_rate=failure_rate,
            port=port,
            otel_service_name=os.getenv("OTEL_SERVICE_NAME", "taskflow"),
            host=host,
            forwarded_allow_ips=forwarded_allow_ips,
        )

    @property
    def is_production(self) -> bool:
        return self.environment in {"prod", "production"}
