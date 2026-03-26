from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class LLMCallIngestSpan(BaseModel):
    name: str
    latency_ms: int | None = Field(default=None, ge=0)
    metadata: dict[str, Any] | None = None


class LLMCallIngest(BaseModel):
    app_id: str
    env: str
    session_id: str
    provider: str
    model: str
    tokens_in: int = Field(ge=0)
    tokens_out: int = Field(ge=0)
    latency_ms: int = Field(ge=0)
    status: str

    operation: str | None = None
    route: str | None = None
    ts_client: datetime | None = None
    prompt_preview: str | None = None
    response_preview: str | None = None
    metadata: dict[str, Any] | None = None
    spans: list[LLMCallIngestSpan] | None = None


class LLMCallStored(LLMCallIngest):
    id: str
    ts_server: datetime
    cost_usd: float = Field(ge=0.0)


class LLMCallIngestResponse(BaseModel):
    id: str
    ts_server: datetime
    cost_usd: float = Field(ge=0.0)
    stored: LLMCallStored
