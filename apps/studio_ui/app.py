from __future__ import annotations

import streamlit as st

from apps.studio_ui.client import get_trace_api_url

st.set_page_config(page_title="LLM Trace + Cost Studio", layout="wide")

st.title("LLM Trace + Cost Studio")
st.caption(f"Trace API URL: `{get_trace_api_url()}`")
st.write(
    "Use the sidebar to navigate: **Overview**, **Calls List**, and **Call Detail**."
)
