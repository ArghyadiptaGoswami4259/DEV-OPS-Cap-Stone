from __future__ import annotations

import re

from fastapi.testclient import TestClient


def test_root_ui_exposes_release_identity(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "TaskFlow" in response.text
    assert "1.0.0-test" in response.text
    assert "/api/v1/tasks" in response.text


def test_health_and_correlation_headers(client: TestClient) -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["commit"] == "testcommit"
    assert re.fullmatch(r"[0-9a-f]{16}", response.headers["x-request-id"])
    assert re.fullmatch(r"[0-9a-f]{32}", response.headers["x-trace-id"])
    assert response.headers["traceparent"].startswith("00-")
    assert response.headers["x-content-type-options"] == "nosniff"


def test_w3c_trace_context_is_reused(client: TestClient) -> None:
    trace_id = "a" * 32
    parent = f"00-{trace_id}-{'b' * 16}-01"
    response = client.get("/healthz", headers={"traceparent": parent})
    assert response.headers["x-trace-id"] == trace_id
    assert response.headers["traceparent"].startswith(f"00-{trace_id}-")


def test_readiness_checks_database(client: TestClient) -> None:
    response = client.get("/readyz")
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "database": "ok"}


def test_metrics_expose_build_info_and_request_counters(client: TestClient) -> None:
    client.get("/api/v1/tasks")
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "taskflow_build_info" in response.text
    expected = (
        'taskflow_http_requests_total{method="GET",route="/api/v1/tasks",status="200"}'
    )
    assert expected in response.text
    assert "taskflow_ready 1.0" in response.text


def test_task_crud_lifecycle(client: TestClient) -> None:
    created = client.post(
        "/api/v1/tasks",
        json={"title": "  Verify canary analysis  ", "description": "Check error budget"},
    )
    assert created.status_code == 201
    task = created.json()
    assert task["title"] == "Verify canary analysis"
    assert task["status"] == "todo"

    listed = client.get("/api/v1/tasks", params={"status": "todo"})
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["id"] == task["id"]

    fetched = client.get(f"/api/v1/tasks/{task['id']}")
    assert fetched.status_code == 200

    updated = client.patch(
        f"/api/v1/tasks/{task['id']}",
        json={"status": "done", "description": "Analysis passed"},
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "done"

    deleted = client.delete(f"/api/v1/tasks/{task['id']}")
    assert deleted.status_code == 204
    assert client.get(f"/api/v1/tasks/{task['id']}").status_code == 404


def test_validation_and_unknown_fields_are_rejected(client: TestClient) -> None:
    assert client.post("/api/v1/tasks", json={"title": "   "}).status_code == 422
    assert client.post("/api/v1/tasks", json={"title": "x", "admin": True}).status_code == 422
    invalid_status = client.post(
        "/api/v1/tasks",
        json={"title": "x", "status": "archived"},
    )
    assert invalid_status.status_code == 422


def test_unknown_task_returns_clean_404(client: TestClient) -> None:
    response = client.get("/api/v1/tasks/does-not-exist")
    assert response.status_code == 404
    assert response.json() == {"detail": "Task not found"}


def test_info_endpoint(client: TestClient) -> None:
    response = client.get("/api/v1/info")
    assert response.status_code == 200
    assert response.json()["otel_service_name"] == "taskflow-test"


def test_canary_failure_injection(app_factory) -> None:
    application = app_factory(environment="staging", failure_rate=1.0)
    with TestClient(application) as client:
        response = client.get("/api/v1/tasks")
        assert response.status_code == 503
        assert response.json()["detail"] == "Injected canary failure"


def test_production_security_posture(app_factory) -> None:
    application = app_factory(environment="prod", failure_rate=1.0)
    with TestClient(application) as client:
        response = client.get("/healthz", headers={"x-forwarded-proto": "https"})
        assert response.status_code == 200
        assert response.headers["strict-transport-security"].startswith("max-age=")
        assert response.headers["x-frame-options"] == "DENY"
        assert client.get("/docs").status_code == 404
        assert client.get("/api/v1/tasks").status_code == 200
