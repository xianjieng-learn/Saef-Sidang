# app_core/dialogs_js.py
from __future__ import annotations

import streamlit as st
import pandas as pd
from typing import Any, Dict
from app_core.data_io import save_table

_DLG_KEY = "_dlg_js"

def _state():
    return st.session_state.setdefault(_DLG_KEY, {})

def open_js_dialog(name: str, title: str = "", payload: Dict[str, Any] | None = None) -> None:
    st.session_state[_DLG_KEY] = {"name": name, "title": title or "", "payload": payload or {}}

def _close():
    st.session_state.pop(_DLG_KEY, None)

def _current():
    s = _state()
    return s.get("name"), s.get("title",""), s.get("payload",{})

def _header(t: str):
    st.markdown(
        f"""
        <div style="padding:8px 12px; border:1px solid #e6e6e6; border-bottom:none;
        border-radius:12px 12px 0 0; background:#fafafa;">
        <h4 style="margin:0; font-weight:700;">{t}</h4></div>
        """,
        unsafe_allow_html=True,
    )

def _box():
    return st.container(border=True)

def _ensure(df: pd.DataFrame, col: str, default: Any = ""):
    if col not in df.columns:
        df[col] = default

# ====== Form Tambah JS ======
def _add_form(js_df: pd.DataFrame)->None:
    _ensure(js_df,"nama","")
    _ensure(js_df,"catatan","")
    _ensure(js_df,"alias","")

    _header("Tambah Jurusita (JS)")
    with _box():
        with st.form("js_add"):
            nama = st.text_input("Nama","")
            alias = st.text_area(
                "Alias",
                "",
                placeholder="Pisahkan dengan koma, titik koma, atau baris baru.\nContoh: Budi; Budiman; Budianto",
                help="Dipakai untuk pencocokan nama di rekap (tanpa gelar).",
            )
            catatan = st.text_area("Catatan","")
            c1,c2=st.columns(2)
            ok=c1.form_submit_button("Simpan")
            cancel=c2.form_submit_button("Batal")
    if cancel: _close(); st.rerun()
    if ok:
        row={"nama":nama.strip(),"alias":alias.strip(),"catatan":catatan.strip()}
        save_table(pd.concat([js_df,pd.DataFrame([row])], ignore_index=True), "js")
        st.success(f"JS '{row['nama'] or '(tanpa nama)'}' ditambahkan.")
        _close(); st.rerun()

# ====== Form Edit JS ======
def _edit_form(js_df: pd.DataFrame, payload: Dict[str,Any], title:str)->None:
    _ensure(js_df,"nama","")
    _ensure(js_df,"catatan","")
    _ensure(js_df,"alias","")

    idx=int(payload.get("index",-1))
    if not (0<=idx<len(js_df)):
        st.error("Index JS tidak valid."); return
    row=js_df.iloc[idx]

    _header(title or "Edit JS")
    with _box():
        with st.form("js_edit"):
            nama=st.text_input("Nama",str(row.get("nama","")))
            alias=st.text_area(
                "Alias",
                str(row.get("alias","")),
                placeholder="Pisahkan dengan koma, titik koma, atau baris baru.\nContoh: Budi; Budiman; Budianto",
                help="Dipakai untuk pencocokan nama di rekap (tanpa gelar).",
            )
            catatan=st.text_area("Catatan",str(row.get("catatan","")))
            c1,c2,c3=st.columns(3)
            ok=c1.form_submit_button("Simpan Perubahan")
            delete=c2.form_submit_button("Hapus")
            cancel=c3.form_submit_button("Batal")
    if cancel: _close(); st.rerun()
    if delete:
        save_table(js_df.drop(js_df.index[idx]).reset_index(drop=True), "js")
        st.warning(f"JS '{row.get('nama','(tanpa nama)')}' dihapus.")
        _close(); st.rerun()
    if ok:
        js_df.at[idx,"nama"]=nama.strip()
        js_df.at[idx,"alias"]=alias.strip()
        js_df.at[idx,"catatan"]=catatan.strip()
        save_table(js_df,"js")
        st.success(f"Perubahan untuk '{nama or '(tanpa nama)'}' disimpan.")
        _close(); st.rerun()

# ====== Render Dialog ======
def render_js_dialog(js_df: pd.DataFrame, **_kwargs)->None:
    name,title,payload=_current()
    if not name: return
    if name=="add_js": _add_form(js_df)
    elif name=="edit_js": _edit_form(js_df,payload,title)
    else:
        _header(title or "Dialog")
        with _box():
            st.info(f"Dialog '{name}' belum diimplementasikan.")
            if st.button("Tutup"): _close(); st.rerun()
