from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from shared.schemas import LLMCallIngest


def _valid_ingest_payload() -> dict:
    return {
        "app_id": "app-1",
        "env": "dev",
        "session_id": "sess-1",
        "provider": "openai",
        "model": "gpt-4o-mini",
        "tokens_in": 10,
        "tokens_out": 15,
        "latency_ms": 120,
        "status": "ok",
        "ts_client": datetime.now(timezone.utc).isoformat(),
    }


def test_llm_call_ingest_accepts_required_fields() -> None:
    payload = _valid_ingest_payload()
    model = LLMCallIngest(**payload)
    assert model.app_id == payload["app_id"]
    assert model.tokens_in == payload["tokens_in"]
    assert model.ts_client is not None


@pytest.mark.parametrize(
    "missing_field",
    [
        "app_id",
        "env",
        "session_id",
        "provider",
        "model",
        "tokens_in",
        "tokens_out",
        "latency_ms",
        "status",
    ],
)
def test_llm_call_ingest_missing_required_field_fails(missing_field: str) -> None:
    payload = _valid_ingest_payload()
    payload.pop(missing_field)

    with pytest.raises(ValidationError):
        LLMCallIngest(**payload)
