# app_core/dialogs_js_ghoib.py
from __future__ import annotations

import streamlit as st
import pandas as pd
from typing import Any, Dict
from app_core.data_io import save_table

_DLG_KEY = "_dlg_js_ghoib"

def _state(): return st.session_state.setdefault(_DLG_KEY, {})
def open_js_ghoib_dialog(name: str, title: str = "", payload: Dict[str, Any] | None = None) -> None:
    st.session_state[_DLG_KEY] = {"name": name, "title": title or "", "payload": payload or {}}
def _close(): st.session_state.pop(_DLG_KEY, None)
def _current(): s=_state(); return s.get("name"), s.get("title",""), s.get("payload",{})

def _header(t): 
    st.markdown(f"""<div style="padding:8px 12px; border:1px solid #e6e6e6; border-bottom:none; 
    border-radius:12px 12px 0 0; background:#fafafa;"><h4 style="margin:0; font-weight:700;">{t}</h4></div>""", unsafe_allow_html=True)
def _box(): return st.container(border=True)
def _ensure(df: pd.DataFrame, col: str, default: Any = ""): 
    if col not in df.columns: df[col]=default

# ====== Form Tambah JS Ghoib ======
def _add_form(jsg_df: pd.DataFrame) -> None:
    _ensure(jsg_df, "nama", ""); _ensure(jsg_df, "total_ghoib", 0); _ensure(jsg_df, "catatan", "")
    _header("Tambah JS Ghoib")
    with _box():
        with st.form("jsg_add"):
            nama = st.text_input("Nama", "")
            total_ghoib = st.number_input("Total Ghoib", min_value=0, step=1, value=0)
            catatan = st.text_area("Catatan", "")
            c1, c2 = st.columns(2)
            ok = c1.form_submit_button("Simpan")
            cancel = c2.form_submit_button("Batal")
    if cancel: _close(); st.rerun()
    if ok:
        row = {"nama": nama.strip(), "total_ghoib": int(total_ghoib or 0), "catatan": catatan.strip()}
        save_table(pd.concat([jsg_df, pd.DataFrame([row])], ignore_index=True), "js_ghoib")
        st.success(f"JS Ghoib '{row['nama'] or '(tanpa nama)'}' ditambahkan.")
        _close(); st.rerun()

# ====== Form Edit JS Ghoib ======
def _edit_form(jsg_df: pd.DataFrame, payload: Dict[str, Any], title: str) -> None:
    _ensure(jsg_df, "nama", ""); _ensure(jsg_df, "total_ghoib", 0); _ensure(jsg_df, "catatan", "")
    idx = int(payload.get("index", -1))
    if not (0 <= idx < len(jsg_df)): st.error("Index JS Ghoib tidak valid."); return
    row = jsg_df.iloc[idx]
    _header(title or "Edit JS Ghoib")
    with _box():
        with st.form("jsg_edit"):
            nama = st.text_input("Nama", str(row.get("nama","")))
            total_ghoib = st.number_input("Total Ghoib", min_value=0, step=1, value=int(row.get("total_ghoib",0) or 0))
            catatan = st.text_area("Catatan", str(row.get("catatan","")))
            c1, c2, c3 = st.columns(3)
            ok = c1.form_submit_button("Simpan Perubahan")
            delete = c2.form_submit_button("Hapus")
            cancel = c3.form_submit_button("Batal")
    if cancel: _close(); st.rerun()
    if delete:
        save_table(jsg_df.drop(jsg_df.index[idx]).reset_index(drop=True), "js_ghoib")
        st.warning(f"JS Ghoib '{row.get('nama','(tanpa nama)')}' dihapus.")
        _close(); st.rerun()
    if ok:
        jsg_df.at[idx, "nama"] = nama.strip()
        jsg_df.at[idx, "total_ghoib"] = int(total_ghoib or 0)
        jsg_df.at[idx, "catatan"] = catatan.strip()
        save_table(jsg_df, "js_ghoib")
        st.success(f"Perubahan untuk '{nama or '(tanpa nama)'}' disimpan.")
        _close(); st.rerun()

# ====== Render Dialog ======
def render_js_ghoib_dialog(js_ghoib_df: pd.DataFrame, **_kwargs) -> None:
    name, title, payload = _current()
    if not name: return
    if name == "add_js_ghoib": _add_form(js_ghoib_df)
    elif name == "edit_js_ghoib": _edit_form(js_ghoib_df, payload, title)
    else:
        _header(title or "Dialog")
        with _box():
            st.info(f"Dialog '{name}' belum diimplementasikan.")
            if st.button("Tutup"): _close(); st.rerun()
