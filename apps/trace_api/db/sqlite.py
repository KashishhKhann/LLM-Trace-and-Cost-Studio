from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from shared.schemas import LLMCallIngestSpan, LLMCallStored

_DB_PATH: str | None = None
_INIT_LOCK = threading.Lock()


def init_db(db_path: str) -> None:
    # Guard init to avoid race condition if called concurrently
    global _DB_PATH
    with _INIT_LOCK:
        if _DB_PATH == db_path:
            return
        _DB_PATH = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        with _connect() as conn:
        conn.executescript(
            """
            PRAGMA foreign_keys = ON;

            CREATE TABLE IF NOT EXISTS llm_calls (
                id TEXT PRIMARY KEY,
                ts_server TEXT NOT NULL,
                ts_client TEXT,
                app_id TEXT NOT NULL,
                env TEXT NOT NULL,
                session_id TEXT NOT NULL,
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                operation TEXT,
                route TEXT,
                tokens_in INTEGER NOT NULL,
                tokens_out INTEGER NOT NULL,
                latency_ms INTEGER NOT NULL,
                cost_usd REAL NOT NULL,
                status TEXT NOT NULL,
                error_type TEXT,
                prompt_preview TEXT,
                response_preview TEXT,
                metadata_json TEXT
            );

            CREATE TABLE IF NOT EXISTS spans (
                id TEXT PRIMARY KEY,
                call_id TEXT NOT NULL,
                name TEXT NOT NULL,
                start_ts TEXT,
                end_ts TEXT,
                meta_json TEXT,
                FOREIGN KEY (call_id) REFERENCES llm_calls(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_llm_calls_ts_server ON llm_calls(ts_server);
            CREATE INDEX IF NOT EXISTS idx_llm_calls_model ON llm_calls(model);
            CREATE INDEX IF NOT EXISTS idx_llm_calls_status ON llm_calls(status);
            CREATE INDEX IF NOT EXISTS idx_llm_calls_session_id ON llm_calls(session_id);
            """
        )


def insert_llm_call(call: LLMCallStored) -> str:
    call_id = call.id or str(uuid.uuid4())
    metadata_json = _dumps_json(call.metadata)
    error_type = call.metadata.get("error_type") if isinstance(call.metadata, dict) else None

    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO llm_calls (
                id, ts_server, ts_client, app_id, env, session_id, provider, model,
                operation, route, tokens_in, tokens_out, latency_ms, cost_usd, status,
                error_type, prompt_preview, response_preview, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                call_id,
                call.ts_server.isoformat(),
                call.ts_client.isoformat() if call.ts_client else None,
                call.app_id,
                call.env,
                call.session_id,
                call.provider,
                call.model,
                call.operation,
                call.route,
                call.tokens_in,
                call.tokens_out,
                call.latency_ms,
                call.cost_usd,
                call.status,
                error_type,
                call.prompt_preview,
                call.response_preview,
                metadata_json,
            ),
        )

        for span in call.spans or []:
            span_meta = dict(span.metadata or {})
            if span.latency_ms is not None:
                span_meta["__latency_ms"] = span.latency_ms

            conn.execute(
                """
                INSERT INTO spans (id, call_id, name, start_ts, end_ts, meta_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    call_id,
                    span.name,
                    None,
                    None,
                    _dumps_json(span_meta),
                ),
            )

    return call_id


def list_llm_calls(
    filters: dict[str, Any] | None = None, limit: int = 100, offset: int = 0
) -> tuple[list[LLMCallStored], int]:
    if limit < 0:
        raise ValueError("limit must be >= 0")
    if offset < 0:
        raise ValueError("offset must be >= 0")

    where_sql, params = _build_where_clause(filters or {})

    with _connect() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM llm_calls {where_sql}",
            params,
        ).fetchone()[0]

        rows = conn.execute(
            f"""
            SELECT id, ts_server, ts_client, app_id, env, session_id, provider, model,
                   operation, route, tokens_in, tokens_out, latency_ms, cost_usd,
                   status, error_type, prompt_preview, response_preview, metadata_json
            FROM llm_calls
            {where_sql}
            ORDER BY ts_server DESC
            LIMIT ? OFFSET ?
            """,
            [*params, limit, offset],
        ).fetchall()

    items = [_row_to_call(row, include_spans=False) for row in rows]
    return items, int(total)


def get_llm_call(call_id: str) -> tuple[LLMCallStored, list[LLMCallIngestSpan]] | None:
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT id, ts_server, ts_client, app_id, env, session_id, provider, model,
                   operation, route, tokens_in, tokens_out, latency_ms, cost_usd,
                   status, error_type, prompt_preview, response_preview, metadata_json
            FROM llm_calls
            WHERE id = ?
            """,
            (call_id,),
        ).fetchone()

        if row is None:
            return None

        span_rows = conn.execute(
            """
            SELECT name, start_ts, end_ts, meta_json
            FROM spans
            WHERE call_id = ?
            ORDER BY rowid ASC
            """,
            (call_id,),
        ).fetchall()

    spans = [_row_to_span(row) for row in span_rows]
    call = _row_to_call(row, include_spans=True, spans=spans)
    return call, spans


def _connect() -> sqlite3.Connection:
    if _DB_PATH is None:
        raise RuntimeError("Database is not initialized. Call init_db(db_path) first.")

    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _build_where_clause(filters: dict[str, Any]) -> tuple[str, list[Any]]:
    clauses: list[str] = []
    params: list[Any] = []

    simple_filters = {
        "app_id",
        "env",
        "session_id",
        "provider",
        "model",
        "operation",
        "route",
        "status",
    }

    for key in simple_filters:
        value = filters.get(key)
        if value is None:
            continue
        clauses.append(f"{key} = ?")
        params.append(value)

    ts_server_from = filters.get("ts_server_from")
    if ts_server_from is not None:
        clauses.append("ts_server >= ?")
        params.append(_normalize_ts(ts_server_from))

    ts_server_to = filters.get("ts_server_to")
    if ts_server_to is not None:
        clauses.append("ts_server <= ?")
        params.append(_normalize_ts(ts_server_to))

    if not clauses:
        return "", params
    return "WHERE " + " AND ".join(clauses), params


def _normalize_ts(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _loads_json(raw: str | None) -> dict[str, Any] | None:
    if raw is None:
        return None
    parsed = json.loads(raw)
    if isinstance(parsed, dict):
        return parsed
    return None


def _dumps_json(value: dict[str, Any] | None) -> str | None:
    if value is None:
        return None
    return json.dumps(value)


def _row_to_span(row: sqlite3.Row) -> LLMCallIngestSpan:
    metadata = _loads_json(row["meta_json"]) or {}
    latency_ms = metadata.pop("__latency_ms", None)
    return LLMCallIngestSpan(
        name=row["name"],
        latency_ms=latency_ms,
        metadata=metadata or None,
    )


def _row_to_call(
    row: sqlite3.Row,
    include_spans: bool,
    spans: list[LLMCallIngestSpan] | None = None,
) -> LLMCallStored:
    metadata = _loads_json(row["metadata_json"])
    if row["error_type"] is not None:
        metadata = dict(metadata or {})
        metadata.setdefault("error_type", row["error_type"])

    return LLMCallStored(
        id=row["id"],
        ts_server=datetime.fromisoformat(row["ts_server"]),
        ts_client=datetime.fromisoformat(row["ts_client"]) if row["ts_client"] else None,
        app_id=row["app_id"],
        env=row["env"],
        session_id=row["session_id"],
        provider=row["provider"],
        model=row["model"],
        operation=row["operation"],
        route=row["route"],
        tokens_in=row["tokens_in"],
        tokens_out=row["tokens_out"],
        latency_ms=row["latency_ms"],
        cost_usd=float(row["cost_usd"]),
        status=row["status"],
        prompt_preview=row["prompt_preview"],
        response_preview=row["response_preview"],
        metadata=metadata,
        spans=spans if include_spans else None,
    )
