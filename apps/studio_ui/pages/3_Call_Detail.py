from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from apps.studio_ui.client import ApiError, NotFoundError, get_call

st.title("Call Detail")

query_call_id = st.query_params.get("call_id", "")
if isinstance(query_call_id, list):
    default_call_id = query_call_id[0] if query_call_id else ""
else:
    default_call_id = str(query_call_id)

call_id = st.text_input("Call ID", value=default_call_id)

if not call_id:
    st.info("Enter a call ID or select a row from Calls List.")
    st.stop()

try:
    call = get_call(call_id)
except NotFoundError:
    st.error("Call not found (404).")
    st.stop()
except ApiError as exc:
    st.error(f"Failed to fetch call detail: {exc}")
    st.stop()

st.subheader("Call Payload")
st.json(call)

spans = call.get("spans") or []
if spans:
    st.subheader("Spans Timing Breakdown")
    total_latency = float(call.get("latency_ms", 0.0) or 0.0)
    rows = []
    for span in spans:
        latency = span.get("latency_ms")
        latency_value = float(latency) if latency is not None else 0.0
        pct_of_call = (latency_value / total_latency * 100.0) if total_latency > 0 else 0.0
        rows.append(
            {
                "name": span.get("name"),
                "latency_ms": latency,
                "pct_of_call_latency": round(pct_of_call, 2),
                "metadata": json.dumps(span.get("metadata"), default=str),
            }
        )

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)
else:
    st.info("No spans available for this call.")

st.download_button(
    label="Export JSON",
    data=json.dumps(call, indent=2, default=str),
    file_name=f"llm_call_{call_id}.json",
    mime="application/json",
)
