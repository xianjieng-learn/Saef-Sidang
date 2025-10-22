# pages/3e_📅_Data_Libur.py (CSV-only)
# Manajemen hari libur dengan penyimpanan **murni CSV** (tanpa DB)
# Fitur: Upload CSV (merge/replace) → Simpan ke data/libur.csv + Mirror data/libur_df.csv
#        Sorting & pagination (10/50 baris per halaman), tambah/edit/hapus baris, template CSV,
#        date picker untuk input tanggal, dan tombol Download Full CSV

import io
import math
from pathlib import Path
from typing import Optional, Dict

import pandas as pd
import streamlit as st

# ====== Setup dasar ======
st.set_page_config(page_title="Data: Libur (CSV)", layout="wide")
st.header("📅 Data Libur — CSV Only")

DATA_DIR = Path.cwd() / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
LIBUR_PATH = DATA_DIR / "libur.csv"         # storage utama
LIBUR_DF_PATH = DATA_DIR / "libur_df.csv"   # mirror untuk user/UI

# ====== Helpers ======
def format_tanggal_id(x):
    try:
        dt = pd.to_datetime(x)
        bulan_id = [
            "Januari", "Februari", "Maret", "April", "Mei", "Juni",
            "Juli", "Agustus", "September", "Oktober", "November", "Desember"
        ]
        return f"{dt.day:02d} {bulan_id[dt.month-1]} {dt.year}"
    except Exception:
        return str(x)

def _safe_int(x) -> int:
    try:
        if pd.isna(x):
            return 0
    except Exception:
        pass
    try:
        return int(x)
    except Exception:
        return 0

def _has_rows(df: Optional[pd.DataFrame]) -> bool:
    return bool(isinstance(df, pd.DataFrame) and not df.empty and len(df.dropna(how="all")) > 0)

def _parse_tanggal(x) -> pd.Timestamp:
    if pd.isna(x):
        return pd.NaT
    s = str(x).strip()
    if not s:
        return pd.NaT
    dt = pd.to_datetime(s, errors="coerce", dayfirst=True)
    if pd.isna(dt):
        dt = pd.to_datetime(s, errors="coerce")
    return dt

def _fmt_date_out(dt) -> str:
    ts = _parse_tanggal(dt)
    if pd.isna(ts):
        return ""
    return ts.date().isoformat()

def _standardize_input_columns(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=["tanggal", "keterangan"])
    rename: Dict[str, str] = {}
    for c in df.columns:
        raw = str(c).replace("\ufeff", "").strip()
        k = raw.lower().replace("_", " ")
        if k in {"tanggal", "tgl", "date", "hari"}:
            new = "tanggal"
        elif k in {"keterangan", "ket", "deskripsi", "description"}:
            new = "keterangan"
        else:
            new = raw
        rename[c] = new
    out = df.rename(columns=rename).copy()
    keep = [c for c in ["tanggal", "keterangan"] if c in out.columns]
    out = out[keep]
    out["tanggal"] = out.get("tanggal", pd.Series(dtype="object")).apply(_fmt_date_out)
    out["keterangan"] = out.get("keterangan", "").astype(str).fillna("").str.strip()
    out = out[out["tanggal"] != ""].copy()
    out = (
        out.sort_values("tanggal")
           .groupby("tanggal", as_index=False)
           .agg({"keterangan": "last"})
    )
    return out.reset_index(drop=True)

# ====== CSV I/O ======
def load_csv() -> pd.DataFrame:
    for p in [LIBUR_PATH, LIBUR_DF_PATH]:
        if p.exists():
            try:
                df = pd.read_csv(p)
            except Exception:
                df = pd.read_csv(p, encoding="utf-8-sig")
            df = _standardize_input_columns(df)
            return df
    return pd.DataFrame(columns=["tanggal", "keterangan"])

def save_csv(df: pd.DataFrame):
    if not _has_rows(df):
        pd.DataFrame(columns=["tanggal", "keterangan"]).to_csv(LIBUR_PATH, index=False, encoding="utf-8-sig")
        pd.DataFrame(columns=["tanggal", "keterangan"]).to_csv(LIBUR_DF_PATH, index=False, encoding="utf-8-sig")
        return
    out = _standardize_input_columns(df)
    out.to_csv(LIBUR_PATH, index=False, encoding="utf-8-sig")
    out.to_csv(LIBUR_DF_PATH, index=False, encoding="utf-8-sig")

# ====== Info lokasi ======
with st.expander("ℹ️ Lokasi Penyimpanan"):
    st.write("**Folder data CSV:**", str(DATA_DIR))
    if LIBUR_PATH.exists():
        st.write("• Storage utama:", str(LIBUR_PATH))
    if LIBUR_DF_PATH.exists():
        st.write("• Mirror UI:", str(LIBUR_DF_PATH))

# ====== Toolbar ======
c1, c2, c3, c4 = st.columns([1.2, 1.6, 1.6, 1.6])
with c1:
    if st.button("➕ Tambah Libur", use_container_width=True):
        st.session_state["libur_dialog"] = {"open": True, "mode": "add", "payload": {}}
with c2:
    if st.button("💾 Simpan/Mirror ke CSV", use_container_width=True):
        cur = st.session_state.get("libur_df_state")
        if isinstance(cur, pd.DataFrame):
            save_csv(cur)
            st.success("CSV diperbarui dari memori.")
        else:
            st.info("Tidak ada perubahan. CSV tetap.")
with c3:
    if st.button("🩺 Heal dari libur_df.csv", use_container_width=True):
        if LIBUR_DF_PATH.exists():
            try:
                df = pd.read_csv(LIBUR_DF_PATH)
            except Exception:
                df = pd.read_csv(LIBUR_DF_PATH, encoding="utf-8-sig")
            df = _standardize_input_columns(df)
            save_csv(df)
            st.success(f"Diisi dari mirror: {len(df)} baris.")
        else:
            st.warning("Mirror libur_df.csv tidak ditemukan.")
with c4:
    tmpl = pd.DataFrame([{"tanggal": "2025-12-25", "keterangan": "Hari Raya"}])
    st.download_button(
        "⬇️ Template CSV",
        data=tmpl.to_csv(index=False).encode("utf-8-sig"),
        file_name="template_libur.csv",
        mime="text/csv",
        use_container_width=True,
    )

# ====== Upload CSV → storage ======
st.markdown("### ⬆️ Upload CSV (ke storage)")
up_col1, up_col2 = st.columns([2, 1])
with up_col1:
    up_file = st.file_uploader("Pilih CSV (header bebas → dipetakan ke: tanggal, keterangan)", type=["csv"])
with up_col2:
    mode = st.radio("Mode import", ["Merge/Upsert", "Replace semua"], index=0)

base_df = load_csv()
if up_file is not None:
    try:
        raw = up_file.read()
        df_in = pd.read_csv(io.BytesIO(raw), encoding="utf-8-sig")
    except Exception:
        up_file.seek(0)
        df_in = pd.read_csv(up_file)
    df_std = _standardize_input_columns(df_in)
    st.write("📄 **Preview (maks 200):**")
    st.dataframe(df_std.head(200), use_container_width=True, hide_index=True)

    if not df_std.empty:
        if st.button("🚀 Proses Upload", type="primary"):
            if mode.startswith("Replace"):
                new_df = df_std.copy()
            else:
                new_df = pd.concat([base_df, df_std], ignore_index=True)
                new_df = (
                    new_df.sort_values("tanggal")
                          .groupby("tanggal", as_index=False)
                          .agg({"keterangan": "last"})
                )
            save_csv(new_df)
            st.session_state["libur_df_state"] = new_df.copy()
            st.success(f"Tersimpan: {len(new_df)} baris.")
            st.rerun()
    else:
        st.warning("Tidak ada baris valid (kolom tanggal wajib).")

st.markdown("---")

# ====== Dialog ======
if "libur_dialog" not in st.session_state:
    st.session_state["libur_dialog"] = {"open": False, "mode": "", "payload": {}}

def open_libur_dialog(mode: str, payload: dict | None = None):
    st.session_state["libur_dialog"] = {"open": True, "mode": mode, "payload": payload or {}}

def render_libur_dialog(current_df: pd.DataFrame):
    dlg = st.session_state.get("libur_dialog", {"open": False})
    if not dlg.get("open"):
        return
    mode = dlg.get("mode")
    payload = dlg.get("payload", {}) or {}

    if mode == "edit" and _has_rows(current_df):
        i = int(payload.get("index", 0))
        row = current_df.reset_index(drop=True).iloc[i]
        tgl_init = _fmt_date_out(row.get("tanggal", ""))
        ket_init = str(row.get("keterangan", ""))
    else:
        tgl_init = ""
        ket_init = ""

    with st.form("libur_dialog_form"):
        st.subheader("Edit Libur" if (mode == "edit") else "Tambah Libur")
        try:
            _init_dt = _parse_tanggal(tgl_init)
            _init_date = None if pd.isna(_init_dt) else _init_dt.date()
        except Exception:
            _init_date = None
        tgl = st.date_input("Tanggal", value=_init_date)
        ket = st.text_input("Keterangan", value=ket_init)

        c1, c2, c3 = st.columns([1, 1, 1])
        sbtn = c1.form_submit_button("💾 Simpan", use_container_width=True)
        cbtn = c2.form_submit_button("Batal", use_container_width=True)
        del_ok = c3.checkbox("Konfirmasi hapus", value=False)
        dbtn = c3.form_submit_button("🗑️ Hapus", use_container_width=True, disabled=(mode != "edit") or not del_ok)

        if sbtn:
            tgl_std = _fmt_date_out(tgl)
            if not tgl_std:
                st.error("Tanggal tidak valid.")
            else:
                cur = st.session_state.get("libur_df_state", load_csv())
                cur = _standardize_input_columns(cur)
                if mode == "edit":
                    old_row = current_df.reset_index(drop=True).iloc[int(payload.get("index", 0))]
                    old_tgl = _fmt_date_out(old_row.get("tanggal", ""))
                    cur = cur[cur["tanggal"] != old_tgl]
                add_df = pd.DataFrame([{"tanggal": tgl_std, "keterangan": ket.strip()}])
                cur = pd.concat([cur, add_df], ignore_index=True)
                cur = (
                    cur.sort_values("tanggal")
                       .groupby("tanggal", as_index=False)
                       .agg({"keterangan": "last"})
                )
                save_csv(cur)
                st.session_state["libur_df_state"] = cur.copy()
                st.session_state["libur_dialog"]["open"] = False
                st.success("Tersimpan ✅"); st.rerun()

        if dbtn and (mode == "edit") and del_ok:
            cur = st.session_state.get("libur_df_state", load_csv())
            cur = _standardize_input_columns(cur)
            old_row = current_df.reset_index(drop=True).iloc[int(payload.get("index", 0))]
            old_tgl = _fmt_date_out(old_row.get("tanggal", ""))
            cur = cur[cur["tanggal"] != old_tgl]
            save_csv(cur)
            st.session_state["libur_df_state"] = cur.copy()
            st.session_state["libur_dialog"]["open"] = False
            st.success("Dihapus 🗑️"); st.rerun()

        if cbtn and not sbtn and not dbtn:
            st.session_state["libur_dialog"]["open"] = False
            st.info("Dibatalkan."); st.rerun()

# ====== Tabel utama ======
libur_df = st.session_state.get("libur_df_state", load_csv())
if not _has_rows(libur_df):
    st.warning("Belum ada data libur. Gunakan **Upload CSV** atau klik **➕ Tambah Libur**.")
else:
    view = libur_df.copy()
    view["__tgl_ts"] = pd.to_datetime(view["tanggal"], errors="coerce", dayfirst=True)
    view["__tgl_fmt"] = view["__tgl_ts"].apply(lambda x: format_tanggal_id(x) if pd.notna(x) else "")

    ctrl1, ctrl2, ctrl3 = st.columns([1, 1.2, 0.8])
    page_size = ctrl1.selectbox("Baris/hal", [10, 50], index=0, key="libur_size")
    sort_by = ctrl2.selectbox("Urutkan berdasarkan", ["tanggal", "keterangan"], index=0, key="libur_sort_by")
    asc = ctrl3.toggle("Naik", value=True, key="libur_sort_asc")

    sig = f"{page_size}|{sort_by}|{asc}"
    if st.session_state.get("libur_sig") != sig:
        st.session_state["libur_sig"] = sig
        st.session_state["libur_page"] = 1

    if sort_by == "tanggal":
        view = view.sort_values("__tgl_ts", ascending=asc, kind="stable")
    else:
        view = view.sort_values("keterangan", ascending=asc, kind="stable")

    total_rows = len(view)
    page_size = int(page_size)
    total_pages = max(1, math.ceil(total_rows / page_size))
    page = min(max(1, int(st.session_state.get("libur_page", 1))), total_pages)
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    page_df = view.iloc[start_idx:end_idx].reset_index(drop=True)

    COLS = [1.4, 1.8, 3.0, 0.9, 0.9]
    h = st.columns(COLS)
    h[0].markdown("**Tanggal (ISO)**")
    h[1].markdown("**Tanggal (ID)**")
    h[2].markdown("**Keterangan**")
    h[3].markdown("**Edit**")
    h[4].markdown("**Hapus**")
    st.markdown("<hr/>", unsafe_allow_html=True)

    base_unsorted = libur_df.reset_index(drop=True).copy()
    for i, row in page_df.iterrows():
        tgl_iso = str(row.get("tanggal", "")) or "-"
        tgl_idn = str(row.get("__tgl_fmt", "")) or "-"
        ket = str(row.get("keterangan", "")) or "-"

        cols = st.columns(COLS)
        cols[0].write(tgl_iso)
        cols[1].write(tgl_idn)
        cols[2].write(ket)

        key_suffix = f"p{page}_i{i}"
        try:
            orig_index = int(base_unsorted[base_unsorted["tanggal"] == tgl_iso].index[0])
        except Exception:
            orig_index = 0

        with cols[3]:
            if st.button("✏️", key=f"edit_libur_{key_suffix}"):
                open_libur_dialog("edit", {"index": int(orig_index)})
                st.rerun()
        with cols[4]:
            if st.button("🗑️", key=f"del_libur_{key_suffix}"):
                open_libur_dialog("edit", {"index": int(orig_index)})
                st.warning("Centang 'Konfirmasi hapus' lalu klik 🗑️ Hapus di dialog.")
                st.rerun()

    pc1, pc2, pc3 = st.columns([1, 2, 1])
    with pc1:
        if st.button("⬅️ Prev", use_container_width=True, disabled=(page <= 1)):
            st.session_state["libur_page"] = page - 1
            st.rerun()
    with pc2:
        st.markdown(
            f"<div style='text-align:center'>Halaman <b>{page}</b> / <b>{total_pages}</b> • "
            f"Menampilkan <b>{len(page_df)}</b> dari <b>{total_rows}</b> baris "
            f"(<i>{start_idx+1}-{min(end_idx,total_rows)}</i>)</div>",
            unsafe_allow_html=True,
        )
    with pc3:
        if st.button("Next ➡️", use_container_width=True, disabled=(page >= total_pages)):
            st.session_state["libur_page"] = page + 1
            st.rerun()

# Render dialog bila dibuka
if st.session_state.get("libur_dialog", {}).get("open"):
    render_libur_dialog(st.session_state.get("libur_df_state", load_csv()))

# ====== Export Full CSV ======
full_df = st.session_state.get("libur_df_state", load_csv())
if _has_rows(full_df):
    st.download_button(
        "⬇️ Download Full CSV",
        data=full_df.to_csv(index=False, encoding="utf-8-sig"),
        file_name="data_libur_full.csv",
        mime="text/csv",
    )
