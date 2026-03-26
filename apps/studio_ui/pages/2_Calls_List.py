from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from apps.studio_ui.client import ApiError, build_date_filters, fetch_all_calls

st.title("Calls List")

today = date.today()
default_start = today - timedelta(days=6)

col1, col2 = st.columns(2)
with col1:
    selected_range = st.date_input("Date range", value=(default_start, today))
with col2:
    status = st.selectbox("Status", options=["", "ok", "error"])

col3, col4 = st.columns(2)
with col3:
    model = st.text_input("Model")
with col4:
    session_id = st.text_input("Session ID")

filters = build_date_filters(selected_range)
if model:
    filters["model"] = model
if status:
    filters["status"] = status
if session_id:
    filters["session_id"] = session_id

try:
    items, total = fetch_all_calls(filters=filters)
except ApiError as exc:
    st.error(f"Failed to fetch calls: {exc}")
    st.stop()

st.caption(f"Total matched calls: {total}")

if not items:
    st.info("No calls found for the selected filters.")
    st.stop()

rows = [
    {
        "id": item.get("id"),
        "ts_server": item.get("ts_server"),
        "app_id": item.get("app_id"),
        "session_id": item.get("session_id"),
        "model": item.get("model"),
        "status": item.get("status"),
        "latency_ms": item.get("latency_ms"),
        "tokens_in": item.get("tokens_in"),
        "tokens_out": item.get("tokens_out"),
        "cost_usd": item.get("cost_usd"),
    }
    for item in items
]
df = pd.DataFrame(rows)

selected_id: str | None = None
try:
    event = st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
    )
    selected_rows = event.selection.rows if event else []
    if selected_rows:
        selected_id = str(df.iloc[selected_rows[0]]["id"])
except TypeError:
    st.dataframe(df, use_container_width=True, hide_index=True)

if selected_id is None:
    selectable_ids = [""] + [str(value) for value in df["id"].tolist()]
    selected_id = st.selectbox("Select call ID", options=selectable_ids)
    if selected_id == "":
        selected_id = None

if selected_id and st.button("Open Selected Call"):
    st.query_params["call_id"] = selected_id
    st.switch_page("pages/3_Call_Detail.py")
