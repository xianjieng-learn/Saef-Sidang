# app_core/ss.py
from __future__ import annotations
import pandas as pd
import streamlit as st

def set_df(name: str, df: pd.DataFrame) -> None:
    """Save a DataFrame copy into st.session_state[name]."""
    if isinstance(df, pd.DataFrame):
        st.session_state[name] = df.copy()

def get_df(name: str, fallback: pd.DataFrame | None = None) -> pd.DataFrame | None:
    """Get DataFrame from st.session_state[name] if present, else fallback."""
    df = st.session_state.get(name)
    if isinstance(df, pd.DataFrame) and not df.empty:
        return df.copy()
    return fallback
