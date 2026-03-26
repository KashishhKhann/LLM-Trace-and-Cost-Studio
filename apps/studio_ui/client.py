from __future__ import annotations

import json
import os
from datetime import date, datetime, time, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

DEFAULT_TRACE_API_URL = "http://localhost:8000"


class ApiError(RuntimeError):
    pass


class NotFoundError(ApiError):
    pass


def get_trace_api_url() -> str:
    return os.getenv("TRACE_API_URL", DEFAULT_TRACE_API_URL).rstrip("/")


def get_call(call_id: str) -> dict[str, Any]:
    return _get_json(f"/calls/{call_id}")


def fetch_all_calls(
    filters: dict[str, Any] | None = None,
    *,
    limit: int = 200,
) -> tuple[list[dict[str, Any]], int]:
    if limit <= 0:
        raise ValueError("limit must be > 0")

    all_items: list[dict[str, Any]] = []
    offset = 0
    total = 0

    while True:
        page = _get_json(
            "/calls",
            params={
                **(filters or {}),
                "limit": limit,
                "offset": offset,
            },
        )

        items = page.get("items", [])
        total = int(page.get("total", len(items)))
        all_items.extend(items)
        offset += len(items)

        if not items or offset >= total:
            break

    return all_items, total


def build_date_filters(date_range: Any) -> dict[str, str]:
    normalized = _normalize_date_range(date_range)
    if normalized is None:
        return {}

    start_date, end_date = normalized
    from_ts = datetime.combine(start_date, time.min, tzinfo=timezone.utc).isoformat()
    to_ts = datetime.combine(end_date, time.max, tzinfo=timezone.utc).isoformat()
    return {"from_ts": from_ts, "to_ts": to_ts}


def compute_overview_metrics(items: list[dict[str, Any]]) -> dict[str, float]:
    count = len(items)
    errors = sum(
        1
        for item in items
        if str(item.get("status", "")).lower() not in {"ok", "success"}
    )
    latencies = [float(item.get("latency_ms", 0.0)) for item in items]
    total_tokens = sum(
        int(item.get("tokens_in", 0)) + int(item.get("tokens_out", 0))
        for item in items
    )
    total_cost = sum(float(item.get("cost_usd", 0.0)) for item in items)

    return {
        "calls_count": float(count),
        "error_rate_pct": (errors / count * 100.0) if count else 0.0,
        "p50_latency_ms": _percentile(latencies, 0.50),
        "p95_latency_ms": _percentile(latencies, 0.95),
        "total_tokens": float(total_tokens),
        "total_cost_usd": total_cost,
    }


def _normalize_date_range(value: Any) -> tuple[date, date] | None:
    if value is None:
        return None

    if isinstance(value, date):
        return value, value

    if isinstance(value, (list, tuple)) and len(value) == 2:
        start_date = value[0]
        end_date = value[1]
        if isinstance(start_date, date) and isinstance(end_date, date):
            if start_date <= end_date:
                return start_date, end_date
            return end_date, start_date
    return None


def _percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0

    ordered = sorted(values)
    index = (len(ordered) - 1) * q
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)

    if lower == upper:
        return ordered[lower]

    lower_value = ordered[lower]
    upper_value = ordered[upper]
    return lower_value + (upper_value - lower_value) * (index - lower)


def _get_json(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    query_string = ""
    if params:
        clean_params = {
            key: value
            for key, value in params.items()
            if value is not None and value != ""
        }
        query_string = urlencode(clean_params)

    url = f"{get_trace_api_url()}{path}"
    if query_string:
        url = f"{url}?{query_string}"

    request = Request(url=url, method="GET")

    try:
        with urlopen(request, timeout=10) as response:
            body = response.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        if exc.code == 404:
            raise NotFoundError(detail or "Not found") from exc
        raise ApiError(f"{exc.code} {exc.reason}: {detail}") from exc
    except URLError as exc:
        raise ApiError(f"Could not reach Trace API at {get_trace_api_url()}: {exc.reason}") from exc

    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise ApiError("Trace API returned invalid JSON") from exc
