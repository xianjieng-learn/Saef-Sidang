# app_core/dialogs_libur.py
from __future__ import annotations

import streamlit as st
import pandas as pd
from typing import Any, Dict
from app_core.data_io import save_table

_DLG_KEY = "_dlg_libur"

def _state(): return st.session_state.setdefault(_DLG_KEY, {})
def open_libur_dialog(name: str, title: str = "", payload: Dict[str, Any] | None = None) -> None:
    st.session_state[_DLG_KEY] = {"name": name, "title": title or "", "payload": payload or {}}
def _close(): st.session_state.pop(_DLG_KEY, None)
def _current(): s=_state(); return s.get("name"), s.get("title",""), s.get("payload",{})

def _header(t): 
    st.markdown(f"""<div style="padding:8px 12px; border:1px solid #e6e6e6; border-bottom:none; 
    border-radius:12px 12px 0 0; background:#fafafa;"><h4 style="margin:0; font-weight:700;">{t}</h4></div>""", unsafe_allow_html=True)
def _box(): return st.container(border=True)
def _ensure(df: pd.DataFrame, col: str, default: Any = ""): 
    if col not in df.columns: df[col]=default

# ====== Form Tambah Libur ======
def _add_form(libur_df: pd.DataFrame)->None:
    _ensure(libur_df,"tanggal",""); _ensure(libur_df,"keterangan","")
    _header("Tambah Tanggal Libur")
    with _box():
        with st.form("libur_add"):
            tanggal = st.date_input("Tanggal")
            keterangan = st.text_input("Keterangan","")
            c1,c2=st.columns(2)
            ok=c1.form_submit_button("Simpan"); cancel=c2.form_submit_button("Batal")
    if cancel: _close(); st.rerun()
    if ok:
        row={"tanggal": str(tanggal), "keterangan": keterangan.strip()}
        save_table(pd.concat([libur_df,pd.DataFrame([row])], ignore_index=True), "libur")
        st.success(f"Libur {row['tanggal']} ditambahkan.")
        _close(); st.rerun()

# ====== Form Edit Libur ======
def _edit_form(libur_df: pd.DataFrame, payload: Dict[str,Any], title:str)->None:
    _ensure(libur_df,"tanggal",""); _ensure(libur_df,"keterangan","")
    idx=int(payload.get("index",-1))
    if not (0<=idx<len(libur_df)): st.error("Index libur tidak valid."); return
    row=libur_df.iloc[idx]
    _header(title or "Edit Tanggal Libur")
    with _box():
        with st.form("libur_edit"):
            try:
                default_date = pd.to_datetime(str(row.get("tanggal",""))).date()
            except Exception:
                default_date = pd.Timestamp.today().date()
            tanggal = st.date_input("Tanggal", value=default_date)
            keterangan = st.text_input("Keterangan", str(row.get("keterangan","")))
            c1,c2,c3=st.columns(3)
            ok=c1.form_submit_button("Simpan Perubahan")
            delete=c2.form_submit_button("Hapus")
            cancel=c3.form_submit_button("Batal")
    if cancel: _close(); st.rerun()
    if delete:
        save_table(libur_df.drop(libur_df.index[idx]).reset_index(drop=True), "libur")
        st.warning(f"Tanggal libur {row.get('tanggal','')} dihapus.")
        _close(); st.rerun()
    if ok:
        libur_df.at[idx,"tanggal"]=str(tanggal)
        libur_df.at[idx,"keterangan"]=keterangan.strip()
        save_table(libur_df,"libur")
        st.success("Perubahan disimpan.")
        _close(); st.rerun()

# ====== Render Dialog ======
def render_libur_dialog(libur_df: pd.DataFrame, **_kwargs)->None:
    name,title,payload=_current()
    if not name: return
    if name=="add_libur": _add_form(libur_df)
    elif name=="edit_libur": _edit_form(libur_df,payload,title)
    else:
        _header(title or "Dialog")
        with _box():
            st.info(f"Dialog '{name}' belum diimplementasikan.")
            if st.button("Tutup"): _close(); st.rerun()
