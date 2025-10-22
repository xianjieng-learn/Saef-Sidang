# app_core/io_csv.py
from __future__ import annotations
import os, shutil, tempfile
from pathlib import Path
import pandas as pd
import streamlit as st

# Fallback reader with encoding tries
def _read_csv_raw(path: Path) -> pd.DataFrame:
    if not path.exists(): return pd.DataFrame()
    for enc in ("utf-8-sig", "utf-8", "cp1252"):
        try:
            return pd.read_csv(path, encoding=enc)
        except Exception:
            continue
    return pd.read_csv(path)

def _atomic_write_csv(df: pd.DataFrame, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile('w', delete=False, encoding="utf-8-sig", newline='') as tmp:
        df.to_csv(tmp.name, index=False, encoding="utf-8-sig")
        tmp.flush()
        os.fsync(tmp.fileno())
    shutil.move(tmp.name, path.as_posix())

@st.cache_data(show_spinner=False)
def _read_csv_cached(path_str: str, mtime: float) -> pd.DataFrame:
    p = Path(path_str)
    return _read_csv_raw(p)

def read_csv(path: Path) -> pd.DataFrame:
    mtime = path.stat().st_mtime if path.exists() else 0.0
    return _read_csv_cached(path.as_posix(), mtime)

def write_csv(df: pd.DataFrame, path: Path):
    _atomic_write_csv(df, path)
