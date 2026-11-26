from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.db import Database
from app.main import create_app


def settings_for(tmp_path: Path, **overrides: object) -> Settings:
    values: dict[str, object] = {
        "app_name": "TaskFlow Test",
        "version": "1.0.0-test",
        "git_sha": "testcommit",
        "environment": "test",
        "database_url": f"sqlite:///{tmp_path / 'taskflow.db'}",
        "log_level": "WARNING",
        "auto_create_schema": True,
        "failure_rate": 0.0,
        "port": 8080,
        "otel_service_name": "taskflow-test",
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


@pytest.fixture
def app_factory(tmp_path: Path):
    counter = 0

    def factory(**overrides: object):
        nonlocal counter
        counter += 1
        settings = settings_for(tmp_path, **overrides)
        settings = replace(
            settings,
            database_url=f"sqlite:///{tmp_path / f'taskflow-{counter}.db'}",
        )
        return create_app(settings, Database(settings))

    return factory


@pytest.fixture
def client(app_factory) -> Iterator[TestClient]:
    application = app_factory()
    with TestClient(application) as test_client:
        yield test_client
