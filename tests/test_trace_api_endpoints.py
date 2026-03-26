from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from apps.trace_api.main import create_app


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    db_path = tmp_path / "trace_api.sqlite3"
    monkeypatch.setenv("TRACE_DB_PATH", str(db_path))
    monkeypatch.setenv("REDACT_TEXT", "false")

    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


def _ingest_payload(status: str = "ok", model: str = "gpt-4o-mini") -> dict:
    return {
        "app_id": "studio",
        "env": "dev",
        "session_id": "session-1",
        "provider": "openai",
        "model": model,
        "tokens_in": 1000,
        "tokens_out": 2000,
        "latency_ms": 123,
        "status": status,
        "operation": "chat",
        "route": "/chat",
        "prompt_preview": "hello",
        "response_preview": "world",
        "metadata": {"k": "v"},
        "spans": [{"name": "provider_call", "latency_ms": 50, "metadata": {"phase": "llm"}}],
    }


def test_ingest_happy_path(client: TestClient) -> None:
    response = client.post("/ingest/llm_call", json=_ingest_payload())
    assert response.status_code == 200

    body = response.json()
    assert body["id"]
    assert body["ts_server"]
    assert body["stored"]["id"] == body["id"]
    assert body["stored"]["model"] == "gpt-4o-mini"
    assert body["cost_usd"] == 0.00135
    assert body["stored"]["cost_usd"] == 0.00135


def test_list_filtering_by_status_and_model(client: TestClient) -> None:
    first = _ingest_payload(status="ok", model="gpt-4o-mini")
    second = _ingest_payload(status="error", model="gpt-4.1-mini")

    assert client.post("/ingest/llm_call", json=first).status_code == 200
    assert client.post("/ingest/llm_call", json=second).status_code == 200

    response = client.get("/calls", params={"status": "error", "model": "gpt-4.1-mini"})
    assert response.status_code == 200

    body = response.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1
    assert body["items"][0]["status"] == "error"
    assert body["items"][0]["model"] == "gpt-4.1-mini"


def test_detail_404(client: TestClient) -> None:
    response = client.get("/calls/not-found")
    assert response.status_code == 404
