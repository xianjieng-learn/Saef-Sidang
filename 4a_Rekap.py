# pages/4a_📊_Rekap.py
import streamlit as st
import pandas as pd
from math import ceil
from datetime import date
from pathlib import Path
from db import get_conn, init_db

# ===== Optional helpers (safe fallbacks) =====
try:
    from app_core.ui import inject_styles  # type: ignore
except Exception:
    def inject_styles(): pass

try:
    from app_core.exports import export_csv as _export_csv_fn  # type: ignore
except Exception:
    _export_csv_fn = None

st.set_page_config(page_title="Rekap", layout="wide")
inject_styles()
st.header("📊 Rekap Data")
init_db()

# ===== DB helpers =====
def load_table(name: str) -> pd.DataFrame:
    con = get_conn()
    try:
        return pd.read_sql_query(f"SELECT * FROM {name}", con)
    except Exception:
        return pd.DataFrame()
    finally:
        con.close()

# ===== Auto-export rekap_df.csv =====
def _export_rekap_csv(df: pd.DataFrame):
    """Tulis rekap_df.csv (UTF-8-SIG) ke lokasi standar aplikasi atau data/."""
    try:
        out = df.copy()
        if _export_csv_fn:
            _export_csv_fn(out, "rekap_df.csv")
        else:
            data_dir = Path("data"); data_dir.mkdir(parents=True, exist_ok=True)
            out.to_csv(data_dir / "rekap_df.csv", index=False, encoding="utf-8-sig")
        st.toast("rekap_df.csv diperbarui", icon="✅")
    except Exception as e:
        st.warning(f"Gagal auto-generate rekap_df.csv: {e}")

def _fingerprint(df: pd.DataFrame):
    """Sidik jari ringan untuk deteksi perubahan isi rekap."""
    try:
        if "id" in df.columns:
            return (int(pd.to_numeric(df["id"], errors="coerce").max() or 0), int(len(df)))
    except Exception:
        pass
    try:
        from pandas.util import hash_pandas_object
        return (int(hash_pandas_object(df, index=True).sum() % (1<<31)), int(len(df)))
    except Exception:
        return (tuple(df.columns), int(len(df)))

# ===== Utils filter/search/sort =====
def _to_dt(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series.astype(str), errors="coerce", dayfirst=True)

def _normalize_searchable_text(df: pd.DataFrame) -> pd.Series:
    obj_cols = [c for c in df.columns if pd.api.types.is_object_dtype(df[c]) or pd.api.types.is_string_dtype(df[c])]
    if not obj_cols:
        return pd.Series([""] * len(df), index=df.index)
    combo = df[obj_cols].fillna("").astype(str).agg(" ".join, axis=1)
    return combo.str.lower()

def _filter_rekap(df: pd.DataFrame, date_field: str, start: date | None, end: date | None, q: str) -> pd.DataFrame:
    if df.empty:
        return df
    tmp = df.copy()

    # Filter tanggal
    if date_field in tmp.columns:
        dts = _to_dt(tmp[date_field])
        if start:
            tmp = tmp[dts >= pd.to_datetime(start)]
        if end:
            tmp = tmp[dts <= (pd.to_datetime(end) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1))]

    # Search sederhana: semua kata harus muncul
    q = (q or "").strip().lower()
    if q:
        hay = _normalize_searchable_text(tmp)
        words = [w for w in q.split() if w]
        mask = pd.Series(True, index=tmp.index)
        for w in words:
            mask &= hay.str.contains(w, na=False)
        tmp = tmp[mask]

    return tmp

def _sort_df(df: pd.DataFrame, sort_col: str | None, ascending: bool) -> pd.DataFrame:
    if not sort_col or sort_col not in df.columns or df.empty:
        return df
    # coba tanggal dulu
    if 'tgl' in sort_col or 'tanggal' in sort_col:
        return df.sort_values(sort_col, key=lambda s: _to_dt(s), ascending=ascending)
    return df.sort_values(sort_col, ascending=ascending)

# ===== Load + auto-export jika berubah =====
rekap = load_table("rekap")

cur_fp = _fingerprint(rekap)
prev_fp = st.session_state.get("__rekap_fp")
if prev_fp != cur_fp:
    _export_rekap_csv(rekap)
    st.session_state["__rekap_fp"] = cur_fp

# ===== Sidebar / Top Filters =====
with st.container():
    st.markdown(
        """
        <style>
        /* rapikan spacing kecil */
        div[data-testid="stHorizontalBlock"] > div { padding-bottom: 0.2rem; }
        </style>
        """,
        unsafe_allow_html=True
    )
    c1, c2, c3, c4 = st.columns([1.2, 1.5, 1.5, 1.6])

    # Field tanggal
    date_cols = [c for c in ["tgl_sidang", "tgl_register"] if c in rekap.columns]
    if not date_cols:
        date_cols = ["tgl_sidang"]
    date_field = c1.selectbox("Field Tanggal", options=date_cols, index=0)

    # Range minimal / maksimal dari data
    if date_field in rekap.columns and not rekap.empty:
        dts_all = _to_dt(rekap[date_field])
        min_d = pd.to_datetime(dts_all.min()).date() if not pd.isna(dts_all.min()) else (pd.to_datetime("today") - pd.Timedelta(days=30)).date()
        max_d = pd.to_datetime(dts_all.max()).date() if not pd.isna(dts_all.max()) else pd.to_datetime("today").date()
    else:
        min_d = (pd.to_datetime("today") - pd.Timedelta(days=30)).date()
        max_d = pd.to_datetime("today").date()

    d1, d2 = c2.columns(2)
    start_date = d1.date_input("Dari", value=min_d if isinstance(min_d, date) else None, key="rekap_start")
    end_date   = d2.date_input("Sampai", value=max_d if isinstance(max_d, date) else None, key="rekap_end")

    # Pencarian + ukuran halaman + urutan
    q = c3.text_input("🔎 Cari", value=st.session_state.get("rekap_q", ""), placeholder="Nomor, nama, klasifikasi, dll.")
    st.session_state["rekap_q"] = q

    size_col, sort_col = c4.columns([1, 2])
    page_size = size_col.selectbox("Baris/hal", [10, 50, 100], index={10:0,50:1,100:2}[st.session_state.get("rekap_size", 10)])
    st.session_state["rekap_size"] = page_size

    sort_options = ["(tidak diurutkan)"] + list(rekap.columns)
    sc = sort_col.selectbox("Urutkan berdasarkan", sort_options, index=0)
    asc_desc = sort_col.toggle("Naik?", value=False, key="rekap_sort_asc")

# ===== Kolom tampil + opsi lanjutan =====
with st.expander("⚙️ Opsi Tampilan", expanded=False):
    preferred = ["nomor_perkara","tgl_register","tgl_sidang","klasifikasi","jenis_perkara","metode",
                 "hakim","anggota1","anggota2","pp","js"]
    default_cols = [c for c in preferred if c in rekap.columns] or list(rekap.columns)
    visible_cols = st.multiselect("Pilih kolom yang ditampilkan", options=list(rekap.columns),
                                  default=st.session_state.get("rekap_cols", default_cols))
    st.session_state["rekap_cols"] = visible_cols

    cA, cB, cC = st.columns([1,1,2])
    if cA.button("↺ Reset Filter", use_container_width=True):
        st.session_state["rekap_q"] = ""
        st.session_state["rekap_start"] = min_d
        st.session_state["rekap_end"] = max_d
        st.session_state["rekap_page"] = 1
        st.rerun()
    if cB.button("🧹 Bersihkan Pencarian", use_container_width=True):
        st.session_state["rekap_q"] = ""
        st.rerun()

# ===== Filter + Sort + Paging =====
def _sig(date_field, start_date, end_date, q, page_size, sort_key, asc):
    return f"{date_field}|{start_date}|{end_date}|{q}|{page_size}|{sort_key}|{asc}"

sig = _sig(date_field, start_date, end_date, q, page_size, sc, asc_desc)
if "rekap_filter_sig" not in st.session_state:
    st.session_state["rekap_filter_sig"] = sig
if st.session_state["rekap_filter_sig"] != sig:
    st.session_state["rekap_filter_sig"] = sig
    st.session_state["rekap_page"] = 1

page = int(st.session_state.get("rekap_page", 1))

fdf = _filter_rekap(rekap, date_field, start_date, end_date, q)
if sc != "(tidak diurutkan)":
    fdf = _sort_df(fdf, sc, asc_desc)

total_rows = len(fdf)
page_size = int(page_size)
total_pages = max(1, ceil(total_rows / page_size))
page = min(max(1, int(page)), total_pages)

start_idx = (page - 1) * page_size
end_idx = start_idx + page_size
show_df = fdf.iloc[start_idx:end_idx].reset_index(drop=True)

# ===== Quick metrics =====
with st.container():
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Baris (terfilter)", f"{total_rows:,}")
    # distribusi metode
    if "metode" in fdf.columns and not fdf.empty:
        m = fdf["metode"].astype(str).str.strip().str.lower().replace({"ecourt":"e-court","e court":"e-court"})
        c2.metric("E‑Court", f"{(m=='e-court').sum():,}")
        c3.metric("Manual", f"{(m=='manual').sum():,}")
    else:
        c2.metric("E‑Court", "-")
        c3.metric("Manual", "-")
    # periode ringkas
    if date_field in fdf.columns and not fdf.empty:
        dd = _to_dt(fdf[date_field])
        try:
            rng = f"{pd.to_datetime(dd.min()).date()} → {pd.to_datetime(dd.max()).date()}"
        except Exception:
            rng = "-"
        c4.metric("Periode tampil", rng)
    else:
        c4.metric("Periode tampil", "-")

st.markdown("---")

# ===== Pagination Controls =====
left, mid, right = st.columns([1,2,1])
with left:
    colA, colB = st.columns(2)
    if colA.button("⏮️ Awal", use_container_width=True, disabled=(page<=1)):
        st.session_state["rekap_page"] = 1; st.rerun()
    if colB.button("⬅️ Prev", use_container_width=True, disabled=(page<=1)):
        st.session_state["rekap_page"] = page - 1; st.rerun()
with mid:
    st.markdown(
        f"<div style='text-align:center'>Halaman <b>{page}</b> / <b>{total_pages}</b> • "
        f"Menampilkan <b>{len(show_df)}</b> dari <b>{total_rows}</b> baris "
        f"(<i>{start_idx+1}-{min(end_idx,total_rows)}</i>)</div>",
        unsafe_allow_html=True
    )
with right:
    colC, colD = st.columns(2)
    if colC.button("Next ➡️", use_container_width=True, disabled=(page>=total_pages)):
        st.session_state["rekap_page"] = page + 1; st.rerun()
    if colD.button("Akhir ⏭️", use_container_width=True, disabled=(page>=total_pages)):
        st.session_state["rekap_page"] = total_pages; st.rerun()

# Jump
jump_container = st.columns([1,3,1])[1]
new_page = jump_container.number_input("Loncat ke halaman", min_value=1, max_value=total_pages, value=page, step=1, key="__page_jump")
if int(new_page) != page:
    st.session_state["rekap_page"] = int(new_page); st.rerun()

# ===== Table =====
if show_df.empty:
    st.info("Tidak ada data untuk filter saat ini.")
else:
    # Default kolom yang ditampilkan
    if visible_cols:
        cols_to_show = [c for c in visible_cols if c in show_df.columns]
    else:
        cols_to_show = list(show_df.columns)
    st.dataframe(show_df[cols_to_show], use_container_width=True, hide_index=True)

# ===== Download filtered CSV =====
with st.expander("⬇️ Unduh hasil terfilter (CSV)"):
    st.download_button(
        "Unduh CSV",
        data=fdf.to_csv(index=False).encode("utf-8-sig"),
        file_name="rekap_terfilter.csv",
        mime="text/csv",
        use_container_width=True
    )
