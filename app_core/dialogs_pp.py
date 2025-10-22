# app_core/dialogs_pp.py
from __future__ import annotations

import streamlit as st
import pandas as pd
from typing import Any, Dict
from app_core.data_io import save_table

# state khusus PP
_DLG_KEY = "_dlg_pp"


def _state():
    return st.session_state.setdefault(_DLG_KEY, {})


def open_pp_dialog(name: str, title: str = "", payload: Dict[str, Any] | None = None) -> None:
    """Buka dialog PP"""
    st.session_state[_DLG_KEY] = {
        "name": name,
        "title": title or "",
        "payload": payload or {},
    }


def _close():
    st.session_state.pop(_DLG_KEY, None)


def _current():
    s = _state()
    return s.get("name"), s.get("title", ""), s.get("payload", {})


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


# ====== Form Tambah PP ======
def _add_form(pp_df: pd.DataFrame) -> None:
    _ensure(pp_df, "nama", "")
    _ensure(pp_df, "aktif", "YA")
    _ensure(pp_df, "catatan", "")
    _ensure(pp_df, "alias", "")  # <-- kolom baru

    _header("Tambah Panitera Pengganti (PP)")
    with _box():
        with st.form("pp_add"):
            nama = st.text_input("Nama", "")
            aktif = st.selectbox("Aktif", ["YA", "TIDAK"], index=0)
            catatan = st.text_area("Catatan", "")
            alias = st.text_area(
                "Alias",
                "",
                placeholder="Pisahkan dengan koma, titik koma, atau baris baru.\nContoh: Rini; Rini A; Riniati",
                help="Dipakai untuk pencocokan nama di rekap (tanpa gelar).",
            )
            c1, c2 = st.columns(2)
            ok = c1.form_submit_button("Simpan")
            cancel = c2.form_submit_button("Batal")

    if cancel:
        _close()
        st.rerun()
    if ok:
        row = {
            "nama": (nama or "").strip(),
            "aktif": (aktif or "").strip(),
            "catatan": (catatan or "").strip(),
            "alias": (alias or "").strip(),
        }
        save_table(pd.concat([pp_df, pd.DataFrame([row])], ignore_index=True), "pp")
        st.success(f"PP '{row['nama'] or '(tanpa nama)'}' ditambahkan.")
        _close()
        st.rerun()


# ====== Form Edit PP ======
def _edit_form(pp_df: pd.DataFrame, payload: Dict[str, Any], title: str) -> None:
    _ensure(pp_df, "nama", "")
    _ensure(pp_df, "aktif", "YA")
    _ensure(pp_df, "catatan", "")
    _ensure(pp_df, "alias", "")  # <-- kolom baru

    idx = int(payload.get("index", -1))
    if not (0 <= idx < len(pp_df)):
        st.error("Index PP tidak valid.")
        return

    row = pp_df.iloc[idx]

    _header(title or "Edit PP")
    with _box():
        with st.form("pp_edit"):
            nama = st.text_input("Nama", str(row.get("nama", "")))
            aktif = st.selectbox(
                "Aktif",
                ["YA", "TIDAK"],
                index=0 if str(row.get("aktif", "YA")).upper() != "TIDAK" else 1,
            )
            catatan = st.text_area("Catatan", str(row.get("catatan", "")))
            alias = st.text_area(
                "Alias",
                str(row.get("alias", "")),
                placeholder="Pisahkan dengan koma, titik koma, atau baris baru.\nContoh: Rini; Rini A; Riniati",
                help="Dipakai untuk pencocokan nama di rekap (tanpa gelar).",
            )
            c1, c2, c3 = st.columns(3)
            ok = c1.form_submit_button("Simpan Perubahan")
            delete = c2.form_submit_button("Hapus")
            cancel = c3.form_submit_button("Batal")

    if cancel:
        _close()
        st.rerun()
    if delete:
        save_table(pp_df.drop(pp_df.index[idx]).reset_index(drop=True), "pp")
        st.warning(f"PP '{row.get('nama','(tanpa nama)')}' dihapus.")
        _close()
        st.rerun()
    if ok:
        pp_df.at[idx, "nama"] = (nama or "").strip()
        pp_df.at[idx, "aktif"] = (aktif or "").strip()
        pp_df.at[idx, "catatan"] = (catatan or "").strip()
        pp_df.at[idx, "alias"] = (alias or "").strip()
        save_table(pp_df, "pp")
        st.success(f"Perubahan untuk '{nama or '(tanpa nama)'}' disimpan.")
        _close()
        st.rerun()


# ====== Render Dialog ======
def render_pp_dialog(pp_df: pd.DataFrame, **_kwargs) -> None:
    name, title, payload = _current()
    if not name:
        return
    if name == "add_pp":
        _add_form(pp_df)
    elif name == "edit_pp":
        _edit_form(pp_df, payload, title)
    else:
        _header(title or "Dialog")
        with _box():
            st.info(f"Dialog '{name}' belum diimplementasikan.")
            if st.button("Tutup"):
                _close()
                st.rerun()
