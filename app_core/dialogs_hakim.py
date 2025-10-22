from __future__ import annotations
import streamlit as st
import pandas as pd
from typing import Any, Dict, Tuple
from app_core.data_io import save_table

_DLG_KEY = "_dlg_hakim"

def _state() -> Dict[str, Any]:
    return st.session_state.setdefault(_DLG_KEY, {})

def open_hakim_dialog(name: str, title: str = "", payload: Dict[str, Any] | None = None) -> None:
    st.session_state[_DLG_KEY] = {"name": name, "title": title or "", "payload": payload or {}}

def _close() -> None:
    st.session_state.pop(_DLG_KEY, None)

def _current() -> Tuple[str | None, str, Dict[str, Any]]:
    s = _state()
    return s.get("name"), s.get("title", ""), s.get("payload", {})

def _header(title: str) -> None:
    st.markdown(f"""<div style="padding:8px 12px; border:1px solid #e6e6e6; border-bottom:none; border-radius:12px 12px 0 0; background:#fafafa;">
            <h4 style="margin:0; font-weight:700;">{title}</h4></div>""", unsafe_allow_html=True)

def _box():
    return st.container(border=True)

def _ensure(df: pd.DataFrame, col: str, default: Any = "") -> None:
    if col not in df.columns:
        df[col] = default

def _add_form(hakim_df: pd.DataFrame) -> None:
    _ensure(hakim_df, "alias", "")
    _header("Tambah Hakim")
    with _box():
        with st.form("hakim_add", clear_on_submit=False):
            nama = st.text_input("Nama", "")
            hari = st.selectbox("Hari Sidang", ["Senin", "Selasa", "Rabu", "Kamis"], index=0)
            aktif = st.selectbox("Aktif", ["YA", "TIDAK"], index=0)
            max_hari = st.number_input("Max/Hari", min_value=0, step=1, value=0)
            catatan = st.text_area("Catatan", "")
            alias = st.text_area("Alias", "", placeholder="Pisahkan dengan koma, titik koma, atau baris baru.\nContoh: Syahrani; Syakrani; Syachrani",
                                  help="Dipakai untuk pencocokan nama rekap (tanpa gelar).")
            c1, c2 = st.columns(2)
            ok = c1.form_submit_button("Simpan")
            cancel = c2.form_submit_button("Batal")
        if cancel:
            _close(); st.rerun()
        if ok:
            row = {
                "nama": (nama or "").strip(),
                "hari_sidang": (hari or "").strip(),
                "aktif": (aktif or "").strip(),
                "max_per_hari": int(max_hari or 0),
                "catatan": (catatan or "").strip(),
                "alias": (alias or "").strip(),
            }
            out = pd.DataFrame([row])
            save_table(pd.concat([hakim_df, out], ignore_index=True), "hakim")
            st.success(f"Hakim '{row['nama'] or '(tanpa nama)'}' ditambahkan.")
            _close(); st.rerun()

def _valid(i: int, n: int) -> bool: return 0 <= i < n

def _edit_form(hakim_df: pd.DataFrame, payload: Dict[str, Any], title: str) -> None:
    _ensure(hakim_df, "alias", "")
    idx = int(payload.get("index", -1))
    if not _valid(idx, len(hakim_df)):
        st.error("Index hakim tidak valid."); return
    row = hakim_df.iloc[idx]
    _header(title or "Edit Hakim")
    with _box():
        with st.form("hakim_edit", clear_on_submit=False):
            nama = st.text_input("Nama", str(row.get("nama","")))
            opsi = ["Senin","Selasa","Rabu","Kamis"]
            hval = str(row.get("hari_sidang","Senin")); hidx = opsi.index(hval) if hval in opsi else 0
            hari = st.selectbox("Hari Sidang", opsi, index=hidx)
            aktif = st.selectbox("Aktif", ["YA","TIDAK"], index=0 if str(row.get("aktif","YA")).upper()!="TIDAK" else 1)
            max_hari = st.number_input("Max/Hari", min_value=0, step=1, value=int(row.get("max_per_hari",0) or 0))
            catatan = st.text_area("Catatan", str(row.get("catatan","")))
            alias = st.text_area("Alias", str(row.get("alias","")),
                                 placeholder="Pisahkan dengan koma, titik koma, atau baris baru.\nContoh: Syahrani; Syakrani; Syachrani")
            c1, c2, c3 = st.columns(3)
            ok = c1.form_submit_button("Simpan Perubahan")
            delete = c2.form_submit_button("Hapus")
            cancel = c3.form_submit_button("Batal")
        if cancel:
            _close(); st.rerun()
        if delete:
            save_table(hakim_df.drop(hakim_df.index[idx]).reset_index(drop=True), "hakim")
            st.warning(f"Hakim '{row.get('nama','(tanpa nama)')}' dihapus.")
            _close(); st.rerun()
        if ok:
            hakim_df.at[idx, "nama"] = (nama or "").strip()
            hakim_df.at[idx, "hari_sidang"] = (hari or "").strip()
            hakim_df.at[idx, "aktif"] = (aktif or "").strip()
            hakim_df.at[idx, "max_per_hari"] = int(max_hari or 0)
            hakim_df.at[idx, "catatan"] = (catatan or "").strip()
            hakim_df.at[idx, "alias"] = (alias or "").strip()
            save_table(hakim_df, "hakim")
            st.success(f"Perubahan untuk '{nama or '(tanpa nama)'}' disimpan.")
            _close(); st.rerun()

def render_hakim_dialog(hakim_df: pd.DataFrame, **_kwargs) -> None:
    name, title, payload = _current()
    if not name: return
    if name == "add_hakim": _add_form(hakim_df)
    elif name == "edit_hakim": _edit_form(hakim_df, payload, title)
    else:
        _header(title or "Dialog")
        with _box():
            st.info(f"Dialog '{name}' belum diimplementasikan.")
            if st.button("Tutup"): _close(); st.rerun()
