# pages/3b_🧑‍💼_Data_PP.py  (CSV-only)
from __future__ import annotations
import re
import math
from pathlib import Path
from typing import List, Tuple

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Data: PP (CSV-only)", layout="wide")
st.header("🧑‍💼 Data Panitera Pengganti (PP) — CSV-only")

DATA_DIR = Path("data")
PP_CSV = DATA_DIR / "pp_df.csv"

# ===================== Utilities =====================
def _is_active_value(v) -> bool:
    s = re.sub(r"[^A-Z0-9]+", "", str(v).replace("\ufeff","").strip().upper())
    if s in {"1","YA","Y","TRUE","T","AKTIF","ON"}: return True
    if s in {"0","TIDAK","TDK","NO","N","FALSE","F","NONAKTIF","OFF","NONE","NAN",""}: return False
    try: return float(s) != 0.0
    except Exception: return False

def _safe_int(v) -> int:
    try:
        if pd.isna(v): return 0
    except Exception: pass
    try: return int(v)
    except Exception:
        try: return int(float(str(v).strip()))
        except Exception: return 0

def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists(): return pd.DataFrame()
    for enc in ["utf-8-sig","utf-8","cp1252"]:
        try:
            return pd.read_csv(path, encoding=enc)
        except Exception:
            continue
    return pd.read_csv(path)

def _write_csv(df: pd.DataFrame, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8-sig")

# ===================== Loader PP (CSV) =====================
BASE_COLS = ["id","nama","aktif","catatan","alias"]

def _ensure_pp_cols(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    # normalisasi nama kolom umum
    ren = {}
    for c in out.columns:
        k = re.sub(r"\s+", " ", str(c).replace("\ufeff","").strip().lower())
        if k == "id": new="id"
        elif k in {"nama","name","nama pp","pp"}: new="nama"
        elif k in {"aktif","status","active","is active"}: new="aktif"
        elif k in {"catatan","keterangan","note","notes"}: new="catatan"
        elif k in {"alias","a.k.a","aka"}: new="alias"
        else: new=c
        ren[c]=new
    out = out.rename(columns=ren)

    for c in BASE_COLS:
        if c not in out.columns:
            out[c] = 0 if c in {"id","aktif"} else ""

    # tipe data
    out["id"] = pd.to_numeric(out["id"], errors="coerce").fillna(0).astype(int)
    out["aktif"] = out["aktif"].apply(_is_active_value).astype(int)
    for c in ["nama","catatan","alias"]:
        out[c] = out[c].astype(str).fillna("").map(lambda s: s.strip())

    # drop baris kosong nama
    out = out[out["nama"] != ""].copy()

    # urut kolom
    out = out[BASE_COLS]
    return out.reset_index(drop=True)

def _load_pp_csv() -> pd.DataFrame:
    df = _read_csv(PP_CSV)
    if df.empty:
        df = pd.DataFrame(columns=BASE_COLS)
        _write_csv(df, PP_CSV)
    return _ensure_pp_cols(df)

def _save_pp_csv(df: pd.DataFrame):
    _write_csv(_ensure_pp_cols(df), PP_CSV)
    st.toast("pp_df.csv tersimpan ✅", icon="✅")

def _next_id(df: pd.DataFrame) -> int:
    if "id" not in df.columns or df.empty: return 1
    mx = pd.to_numeric(df["id"], errors="coerce").fillna(0).astype(int).max()
    return int(mx) + 1

# ===================== CSV CRUD (id, upsert, delete) =====================
def upsert_pp_by_nama_csv(df: pd.DataFrame, nama: str, aktif: int, catatan: str, alias: str) -> Tuple[pd.DataFrame, str]:
    """Upsert by nama (case-insensitive, trimming)."""
    work = _ensure_pp_cols(df)
    nm = str(nama or "").strip()
    if not nm: return work, "skipped"

    mask = work["nama"].str.lower() == nm.lower()
    if not mask.any():
        new_row = {"id": _next_id(work), "nama": nm, "aktif": int(aktif), "catatan": catatan.strip(), "alias": alias.strip()}
        work = pd.concat([work, pd.DataFrame([new_row])], ignore_index=True)
        return work, "inserted"
    else:
        work.loc[mask, ["nama","aktif","catatan","alias"]] = [nm, int(aktif), catatan.strip(), alias.strip()]
        return work, "updated"

def update_pp_by_id_csv(df: pd.DataFrame, row_id: int, nama: str, aktif: int, catatan: str, alias: str) -> pd.DataFrame:
    work = _ensure_pp_cols(df)
    mask = work["id"] == int(row_id)
    if mask.any():
        work.loc[mask, ["nama","aktif","catatan","alias"]] = [nama.strip(), int(aktif), catatan.strip(), alias.strip()]
    return work

def delete_pp_by_id_csv(df: pd.DataFrame, row_id: int) -> pd.DataFrame:
    work = _ensure_pp_cols(df)
    work = work[work["id"] != int(row_id)].reset_index(drop=True)
    return work

# ===================== Dialog (Tambah/Edit/Hapus) =====================
if "pp_dialog" not in st.session_state:
    st.session_state["pp_dialog"] = {"open": False, "mode": "", "title": "", "payload": {}}

def open_pp_dialog(mode: str, title: str, payload: dict | None = None):
    st.session_state["pp_dialog"] = {"open": True, "mode": mode, "title": title, "payload": payload or {}}

def render_pp_dialog(current_df: pd.DataFrame):
    dlg = st.session_state.get("pp_dialog", {"open": False})
    if not dlg.get("open"): return
    mode = dlg.get("mode"); title = dlg.get("title", ""); payload = dlg.get("payload", {}) or {}

    with st.form("pp_dialog_form"):
        if mode == "edit_pp" and not current_df.empty:
            i = int(payload.get("index", 0))
            row = current_df.reset_index(drop=True).iloc[i]
            row_id = _safe_int(row.get("id"))
            nama_init = str(row.get("nama",""))
            aktif_init = _is_active_value(row.get("aktif", 1))
            cat_init = str(row.get("catatan",""))
            alias_init = str(row.get("alias",""))
        else:
            row_id = None
            nama_init = ""; aktif_init = True; cat_init = ""; alias_init = ""

        st.subheader(title or ("Edit PP" if row_id else "Tambah PP"))
        nama  = st.text_input("Nama", value=nama_init)
        aktif = st.checkbox("Aktif", value=aktif_init)
        alias = st.text_area("Alias", value=alias_init, height=70, help="Pisahkan dengan ; atau baris baru (opsional)")
        catatan = st.text_area("Catatan", value=cat_init, height=70)

        c1, c2, c3 = st.columns([1,1,1])
        with c1: sbtn = st.form_submit_button("💾 Simpan", width="stretch")
        with c2: cbtn = st.form_submit_button("Batal", width="stretch")
        with c3: dbtn = st.form_submit_button("🗑️ Hapus", width="stretch") if (mode=="edit_pp" and row_id) else None

        if sbtn:
            if not nama.strip():
                st.error("Nama wajib diisi.")
            else:
                df = _load_pp_csv()
                if mode == "edit_pp" and row_id:
                    df = update_pp_by_id_csv(df, row_id, nama, 1 if aktif else 0, catatan, alias)
                else:
                    df, _ = upsert_pp_by_nama_csv(df, nama, 1 if aktif else 0, catatan, alias)
                _save_pp_csv(df)
                st.session_state["pp_dialog"]["open"] = False
                st.success("Tersimpan ✅"); st.rerun()

        if dbtn and (mode=="edit_pp" and row_id):
            df = _load_pp_csv()
            df = delete_pp_by_id_csv(df, row_id)
            _save_pp_csv(df)
            st.session_state["pp_dialog"]["open"] = False
            st.success("Dihapus 🗑️"); st.rerun()

        if cbtn and not sbtn and not dbtn:
            st.session_state["pp_dialog"]["open"] = False
            st.info("Dibatalkan."); st.rerun()

# ===================== Toolbar =====================
topL, topR = st.columns([1,1])
with topR:
    if st.button("➕ Tambah PP", width="stretch"):
        open_pp_dialog("add_pp", "Tambah PP")

# ===================== IMPORT CSV → CSV (gabung) =====================
with st.expander("📥 Import CSV → pp_df.csv (gabung by nama)", expanded=False):
    st.write("Unggah CSV dengan kolom minimal **nama**. Kolom opsional: aktif, catatan, alias.")
    up = st.file_uploader("Pilih CSV", type=["csv"], key="pp_csv_up")

    df_src = pd.DataFrame()
    if up is not None:
        for enc in ["utf-8-sig","utf-8","cp1252"]:
            try:
                up.seek(0); df_src = pd.read_csv(up, encoding=enc); break
            except Exception: continue
        if df_src.empty:
            up.seek(0); df_src = pd.read_csv(up)

    if not df_src.empty:
        # Standar kolom
        ren = {}
        for c in df_src.columns:
            k = re.sub(r"\s+"," ", str(c).replace("\ufeff","").strip().lower())
            if   k in {"nama","name","nama pp","pp"}: new="nama"
            elif k in {"aktif","status","active"}: new="aktif"
            elif k in {"catatan","keterangan","note","notes"}: new="catatan"
            elif k in {"alias","a.k.a","aka"}: new="alias"
            elif k == "id": new="id"
            else: new=c
            ren[c]=new
        df_src = df_src.rename(columns=ren)
        keep = [c for c in ["id","nama","aktif","catatan","alias"] if c in df_src.columns]
        df_src = df_src[keep]
        if "aktif" in df_src.columns:
            df_src["aktif"] = df_src["aktif"].apply(lambda v: 1 if _is_active_value(v) else 0)
        else:
            df_src["aktif"] = 1
        for c in ["nama","catatan","alias"]:
            if c in df_src.columns:
                df_src[c] = df_src[c].astype(str).str.strip()
        df_src = df_src[df_src["nama"] != ""]

        st.caption("Preview CSV (maks 30 baris)")
        st.dataframe(df_src.head(30), width="stretch")

        if st.button("🚀 Impor & Gabung (Upsert by nama)", type="primary", width="stretch", key="btn_import_pp"):
            df = _load_pp_csv()
            inserted = updated = skipped = 0
            for _, r in df_src.iterrows():
                nm = str(r.get("nama","")).strip()
                if not nm:
                    skipped += 1; continue
                df, status = upsert_pp_by_nama_csv(
                    df,
                    nama = nm,
                    aktif = 1 if _is_active_value(r.get("aktif",1)) else 0,
                    catatan = str(r.get("catatan","") or ""),
                    alias = str(r.get("alias","") or "")
                )
                if status == "inserted": inserted += 1
                elif status == "updated": updated += 1
                else: skipped += 1
            _save_pp_csv(df)
            st.success(f"Selesai impor: INSERTED={inserted}, UPDATED={updated}, SKIPPED={skipped}")
            st.rerun()
    else:
        st.caption("Belum ada file yang diunggah.")

# ===================== Tabel Utama =====================
pp_df = _load_pp_csv()
if pp_df.empty:
    st.info("Belum ada data PP. Klik ➕ Tambah PP atau gunakan Import CSV.")
else:
    view = pp_df.copy()
    view["Aktif%s"] = view["aktif"].apply(_is_active_value).map({True:"YA", False:"TIDAK"})

    # filter / urut / paging ringan
    st.markdown("---")
    c1, c2, c3 = st.columns([1, 1.6, 0.9])
    page_size = c1.selectbox("Baris/hal", [10, 50, 100], index=0, key="pp_ps")
    sort_options = ["(tanpa urut)","Nama","Aktif%s"]
    sort_by = c2.selectbox("Urutkan berdasarkan", sort_options, index=0, key="pp_sortcol")
    asc = c3.toggle("Naik%s", value=True, key="pp_asc")

    sig = f"{page_size}|{sort_by}|{asc}|{len(view)}"
    if st.session_state.get("pp_sig") != sig:
        st.session_state["pp_sig"] = sig
        st.session_state["pp_page"] = 1
    page = int(st.session_state.get("pp_page", 1))

    if sort_by != "(tanpa urut)":
        key = "nama" if sort_by == "Nama" else ("aktif" if sort_by == "Aktif%s" else None)
        if key:
            view = view.sort_values(key, ascending=asc, kind="stable")

    total_rows = len(view)
    page_size = int(page_size)
    total_pages = max(1, math.ceil(total_rows / page_size))
    page = min(max(1, page), total_pages)
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    page_df = view.iloc[start_idx:end_idx].reset_index(drop=True)

    # Header grid
    COLS = [2.6, 1.0, 2.8, 2.2, 0.9, 0.9]
    h = st.columns(COLS)
    h[0].markdown("**Nama**"); h[1].markdown("**Aktif**")
    h[2].markdown("**Catatan**"); h[3].markdown("**Alias**")
    h[4].markdown("**Edit**"); h[5].markdown("**Hapus**")
    st.markdown("<hr/>", unsafe_allow_html=True)

    for i, r in page_df.iterrows():
        row_id = _safe_int(r.get("id"))
        cols = st.columns(COLS)
        cols[0].write(str(r.get("nama","")) or "-")
        cols[1].write(str(r.get("Aktif%s","-")))
        cols[2].write(str(r.get("catatan","") or ""))
        cols[3].write(str(r.get("alias","") or ""))
        with cols[4]:
            if st.button("✏️", key=f"edit_pp_{row_id or i}"):
                # buka dialog berdasarkan index relatif di dataframe lengkap
                full = pp_df.reset_index(drop=True)
                if row_id and "id" in full.columns and row_id in full["id"].tolist():
                    idx = int(full[full["id"]==row_id].index[0])
                else:
                    # fallback by nama
                    nm = str(r.get("nama",""))
                    m = full["nama"].astype(str).str.lower() == nm.lower()
                    idx = int(full[m].index[0]) if m.any() else 0
                open_pp_dialog("edit_pp", f"Edit PP: {r.get('nama','')}", {"index": idx})
                st.rerun()
        with cols[5]:
            if st.button("🗑️", key=f"del_pp_{row_id or i}"):
                df = _load_pp_csv()
                if row_id:
                    df = delete_pp_by_id_csv(df, row_id)
                else:
                    nm = str(r.get("nama",""))
                    df = df[df["nama"].astype(str).str.lower() != nm.lower()].reset_index(drop=True)
                _save_pp_csv(df)
                st.success(f"Dihapus: {r.get('nama','')}")
                st.rerun()

    # Pagination controls
    pc1, pc2, pc3 = st.columns([1,2,1])
    with pc1:
        if st.button("⬅️ Prev", width="stretch", disabled=(page<=1)):
            st.session_state["pp_page"] = page - 1; st.rerun()
    with pc2:
        st.markdown(
            f"<div style='text-align:center'>Halaman <b>{page}</b> / <b>{total_pages}</b> • "
            f"Menampilkan <b>{min(page_size, total_rows-start_idx)}</b> dari <b>{total_rows}</b> baris "
            f"(<i>{start_idx+1}-{min(end_idx,total_rows)}</i>)</div>",
            unsafe_allow_html=True
        )
    with pc3:
        if st.button("Next ➡️", width="stretch", disabled=(page>=total_pages)):
            st.session_state["pp_page"] = page + 1; st.rerun()

# Render dialog terakhir (jika terbuka)
if st.session_state.get("pp_dialog", {}).get("open"):
    render_pp_dialog(_load_pp_csv())
