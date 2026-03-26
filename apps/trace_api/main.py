from __future__ import annotations

import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException, Query

from apps.trace_api.db.sqlite import get_llm_call, init_db, insert_llm_call, list_llm_calls
from shared.cost import estimate_cost_usd
from shared.redaction import redact_llm_call_payload
from shared.schemas import LLMCallIngest, LLMCallIngestResponse, LLMCallStored


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _db_path() -> str:
    return os.getenv("TRACE_DB_PATH", "./trace.db")


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI):
        init_db(_db_path())
        yield

    app = FastAPI(title="LLM Trace API", lifespan=lifespan)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/ingest/llm_call", response_model=LLMCallIngestResponse)
    def ingest_llm_call(payload: LLMCallIngest) -> LLMCallIngestResponse:
        redacted_payload = redact_llm_call_payload(payload, _env_bool("REDACT_TEXT", default=False))
        cost_usd = estimate_cost_usd(
            provider=redacted_payload.provider,
            model=redacted_payload.model,
            tokens_in=redacted_payload.tokens_in,
            tokens_out=redacted_payload.tokens_out,
        )

        ts_server = datetime.now(timezone.utc)
        call = LLMCallStored(
            id=str(uuid.uuid4()),
            ts_server=ts_server,
            cost_usd=cost_usd,
            **redacted_payload.model_dump(),
        )
        insert_llm_call(call)

        return LLMCallIngestResponse(
            id=call.id,
            ts_server=call.ts_server,
            cost_usd=call.cost_usd,
            stored=call,
        )

    @app.get("/calls")
    def list_calls(
        from_ts: datetime | None = Query(default=None),
        to_ts: datetime | None = Query(default=None),
        model: str | None = Query(default=None),
        status: str | None = Query(default=None),
        app_id: str | None = Query(default=None),
        session_id: str | None = Query(default=None),
        limit: int = Query(default=100, ge=1, le=200),
        offset: int = Query(default=0, ge=0),
    ) -> dict[str, Any]:
        filters: dict[str, Any] = {}
        if from_ts is not None:
            filters["ts_server_from"] = from_ts
        if to_ts is not None:
            filters["ts_server_to"] = to_ts
        if model is not None:
            filters["model"] = model
        if status is not None:
            filters["status"] = status
        if app_id is not None:
            filters["app_id"] = app_id
        if session_id is not None:
            filters["session_id"] = session_id

        items, total = list_llm_calls(filters=filters, limit=limit, offset=offset)
        # Avoid returning a `spans: null` field for list endpoints — exclude None fields
        items_serialized = [item.model_dump(exclude_none=True) for item in items]
        return {"total": total, "items": items_serialized}

    @app.get("/calls/{id}", response_model=LLMCallStored)
    def get_call(id: str) -> LLMCallStored:
        result = get_llm_call(id)
        if result is None:
            raise HTTPException(status_code=404, detail="call not found")

        call, spans = result
        # `get_llm_call` already populates `spans` when requested; return the stored model directly
        return call

    return app


app = create_app()
