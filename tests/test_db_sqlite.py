from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from apps.trace_api.db.sqlite import get_llm_call, init_db, insert_llm_call, list_llm_calls
from shared.schemas import LLMCallIngestSpan, LLMCallStored


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "trace.db"
    init_db(str(path))
    return path


def _build_call(
    call_id: str,
    ts_server: datetime,
    model: str = "gpt-4o-mini",
    status: str = "ok",
    session_id: str = "session-1",
    spans: list[LLMCallIngestSpan] | None = None,
) -> LLMCallStored:
    return LLMCallStored(
        id=call_id,
        ts_server=ts_server,
        ts_client=ts_server,
        app_id="app-1",
        env="dev",
        session_id=session_id,
        provider="openai",
        model=model,
        operation="chat_completion",
        route="/v1/chat/completions",
        tokens_in=100,
        tokens_out=200,
        latency_ms=350,
        cost_usd=0.1234,
        status=status,
        prompt_preview="hello",
        response_preview="world",
        metadata={"tenant": "none"},
        spans=spans,
    )


def test_init_db_creates_tables_and_indexes(db_path: Path) -> None:
    with sqlite3.connect(db_path) as conn:
        objects = {
            (row[0], row[1])
            for row in conn.execute(
                """
                SELECT type, name
                FROM sqlite_master
                WHERE name IN (
                    'llm_calls',
                    'spans',
                    'idx_llm_calls_ts_server',
                    'idx_llm_calls_model',
                    'idx_llm_calls_status',
                    'idx_llm_calls_session_id'
                )
                """
            ).fetchall()
        }

    assert ("table", "llm_calls") in objects
    assert ("table", "spans") in objects
    assert ("index", "idx_llm_calls_ts_server") in objects
    assert ("index", "idx_llm_calls_model") in objects
    assert ("index", "idx_llm_calls_status") in objects
    assert ("index", "idx_llm_calls_session_id") in objects


def test_insert_and_get_llm_call_with_spans(db_path: Path) -> None:
    ts_server = datetime.now(timezone.utc)
    call = _build_call(
        call_id="call-1",
        ts_server=ts_server,
        spans=[
            LLMCallIngestSpan(name="span-a", latency_ms=15, metadata={"phase": "encode"}),
            LLMCallIngestSpan(name="span-b", latency_ms=20, metadata={"phase": "decode"}),
        ],
    )

    inserted_id = insert_llm_call(call)
    assert inserted_id == "call-1"

    loaded = get_llm_call("call-1")
    assert loaded is not None
    stored, spans = loaded

    assert stored.id == call.id
    assert stored.model == call.model
    assert stored.status == call.status
    assert stored.metadata == call.metadata
    assert len(spans) == 2
    assert spans[0].name == "span-a"
    assert spans[0].latency_ms == 15
    assert spans[0].metadata == {"phase": "encode"}
    assert spans[1].name == "span-b"
    assert spans[1].latency_ms == 20
    assert spans[1].metadata == {"phase": "decode"}


def test_list_llm_calls_filters_and_pagination(db_path: Path) -> None:
    base = datetime.now(timezone.utc)
    call_1 = _build_call(call_id="call-1", ts_server=base, model="model-a", status="ok")
    call_2 = _build_call(
        call_id="call-2",
        ts_server=base + timedelta(seconds=1),
        model="model-b",
        status="error",
        session_id="session-2",
    )

    insert_llm_call(call_1)
    insert_llm_call(call_2)

    all_items, total = list_llm_calls(filters={}, limit=10, offset=0)
    assert total == 2
    assert len(all_items) == 2
    assert all_items[0].id == "call-2"
    assert all_items[1].id == "call-1"

    filtered_items, filtered_total = list_llm_calls(
        filters={"model": "model-b"},
        limit=10,
        offset=0,
    )
    assert filtered_total == 1
    assert len(filtered_items) == 1
    assert filtered_items[0].id == "call-2"

    paged_items, paged_total = list_llm_calls(filters={}, limit=1, offset=1)
    assert paged_total == 2
    assert len(paged_items) == 1
    assert paged_items[0].id == "call-1"


def test_get_llm_call_missing_returns_none(db_path: Path) -> None:
    assert get_llm_call("missing-id") is None
