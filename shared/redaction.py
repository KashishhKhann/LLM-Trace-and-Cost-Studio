from __future__ import annotations

from shared.schemas import LLMCallIngest

REDACTED_TEXT = "[REDACTED]"


def redact_text(value: str | None, enabled: bool) -> str | None:
    if not enabled or value is None:
        return value
    return REDACTED_TEXT


def redact_llm_call_payload(payload: LLMCallIngest, enabled: bool) -> LLMCallIngest:
    if not enabled:
        return payload

    return payload.model_copy(
        update={
            "prompt_preview": redact_text(payload.prompt_preview, True),
            "response_preview": redact_text(payload.response_preview, True),
        }
    )
