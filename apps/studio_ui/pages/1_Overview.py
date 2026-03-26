from __future__ import annotations

from datetime import date, timedelta

import streamlit as st

from apps.studio_ui.client import (
    ApiError,
    build_date_filters,
    compute_overview_metrics,
    fetch_all_calls,
)

st.title("Overview")

today = date.today()
default_start = today - timedelta(days=6)

selected_range = st.date_input(
    "Date range",
    value=(default_start, today),
)

filters = build_date_filters(selected_range)

try:
    items, _total = fetch_all_calls(filters=filters)
except ApiError as exc:
    st.error(f"Failed to fetch calls: {exc}")
    st.stop()

metrics = compute_overview_metrics(items)

col1, col2, col3 = st.columns(3)
col4, col5, col6 = st.columns(3)

col1.metric("Calls", f"{int(metrics['calls_count'])}")
col2.metric("Error rate", f"{metrics['error_rate_pct']:.2f}%")
col3.metric("P50 latency", f"{metrics['p50_latency_ms']:.2f} ms")
col4.metric("P95 latency", f"{metrics['p95_latency_ms']:.2f} ms")
col5.metric("Total tokens", f"{int(metrics['total_tokens'])}")
col6.metric("Total cost", f"${metrics['total_cost_usd']:.6f}")

if not items:
    st.info("No calls found for the selected date range.")
