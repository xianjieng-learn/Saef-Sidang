# pages/2a_📊_Rekap.py
# -*- coding: utf-8 -*-
from __future__ import annotations

import io
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

# ===== UI helper optional =====
try:
    from app_core.ui import inject_styles  # type: ignore
except Exception:
    def inject_styles(): 
        pass

st.set_page_config(page_title="📊 Rekap", layout="wide")
inject_styles()
st.header("📊 Rekap Data")

# =========================================================
# Utils
# =========================================================
DATA_FILE = Path("data/rekap.csv")

def _to_dt_series(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s.astype(str), errors="coerce")

def _load_rekap_from_csv() -> pd.DataFrame:
    if not DATA_FILE.exists():
        return pd.DataFrame()
    try:
        df = pd.read_csv(DATA_FILE, encoding="utf-8-sig")
    except Exception:
        df = pd.read_csv(DATA_FILE)
    # normalisasi tanggal
    for c in ("tgl_register", "tgl_sidang"):
        if c in df.columns:
            df[c] = _to_dt_series(df[c])
    return df

def _export_view_to_csv(df: pd.DataFrame, filename: str = "rekap_terfilter.csv") -> bytes:
    out = df.copy()
    for c in ("tgl_register", "tgl_sidang"):
        if c in out.columns:
            out[c] = pd.to_datetime(out[c], errors="coerce").dt.strftime("%Y-%m-%d")
    return out.to_csv(index=False).encode("utf-8-sig")

def _format_tanggal_id(d) -> str:
    if pd.isna(d):
        return ""
    dd = pd.to_datetime(d).date()
    hari = ["Senin","Selasa","Rabu","Kamis","Jumat","Sabtu","Minggu"][dd.weekday()]
    bulan = ["Januari","Februari","Maret","April","Mei","Juni","Juli",
             "Agustus","September","Oktober","November","Desember"][dd.month-1]
    return f"{hari}, {dd.day:02d} {bulan} {dd.year}"

def _detect_tipe_from_nomor(nomor: str) -> str:
    s = str(nomor or "").upper().replace(" ", "")
    if "PDT.P" in s: return "P"
    if "PDT.PLW" in s: return "G"
    if "PDT.G" in s: return "G"
    return "G"

def _norm_metode(m: str) -> str:
    s = str(m or "").strip().lower()
    if "e-court" in s or "ecourt" in s or s == "e":
        return "E-Court"
    return "Manual"

# =========================================================
# Load data
# =========================================================
rekap = _load_rekap_from_csv()
st.caption(f"🗂️ Sumber data: **CSV** • Total baris: **{len(rekap):,}**")

# =========================================================
# Filter panel
# =========================================================
st.markdown("---")
st.subheader("🎯 Filter")

if rekap.empty:
    st.info("Belum ada data rekap (CSV kosong).")
else:
    # default range: bulan berjalan
    today = date.today()
    default_start = today.replace(day=1)
    default_end = today

    if "rekap_from" not in st.session_state:
        st.session_state["rekap_from"] = default_start
    if "rekap_to" not in st.session_state:
        st.session_state["rekap_to"] = default_end
    if "q_text" not in st.session_state:
        st.session_state["q_text"] = ""

    with st.expander("Filter Lanjutan", expanded=True):
        col1, col2, col3 = st.columns([1, 1, 2])
        from_day = pd.to_datetime(col1.date_input("Dari tanggal", key="rekap_from")).normalize()
        to_day   = pd.to_datetime(col2.date_input("Sampai tanggal", key="rekap_to")).normalize()
        q = col3.text_input("Cari (nomor/hakim/PP/JS/klasifikasi/jenis)", key="q_text")

    # pilih kolom tanggal acuan
    date_col = "tgl_register" if "tgl_register" in rekap.columns else "tgl_sidang"

    work = rekap.copy()
    work["__ts"] = pd.to_datetime(work[date_col], errors="coerce").dt.normalize()

    # filter range tanggal
    mask = (work["__ts"] >= from_day) & (work["__ts"] <= to_day)

    # filter teks
    if q.strip():
        qq = q.strip().lower()
        def _hit(row) -> bool:
            fields = [
                str(row.get("nomor_perkara", "")),
                str(row.get("hakim", "")),
                str(row.get("pp", "")),
                str(row.get("js", "")),
                str(row.get("klasifikasi", "")),
                str(row.get("jenis_perkara", "")),
            ]
            return any(qq in s.lower() for s in fields)
        mask = mask & work.apply(_hit, axis=1)

    show_df = work.loc[mask].drop(columns=["__ts"], errors="ignore")

    # Tambah kolom tanggal ID
    if "tgl_register" in show_df.columns:
        show_df["tgl_register(ID)"] = show_df["tgl_register"].map(_format_tanggal_id)
    if "tgl_sidang" in show_df.columns:
        show_df["tgl_sidang(ID)"] = show_df["tgl_sidang"].map(_format_tanggal_id)

    # Urutkan
    sort_cols = [c for c in ("tgl_register", "tgl_sidang", "nomor_perkara") if c in show_df.columns]
    if sort_cols:
        show_df = show_df.sort_values(sort_cols, ascending=[False]*len(sort_cols), kind="stable")

    st.markdown("### Tabel Rekap")
    if show_df.empty:
        st.info("Tidak ada data untuk filter saat ini. Coba ubah rentang tanggal atau kata kunci.")
    else:
        preferred = [
            "nomor_perkara","tgl_register","tgl_register(ID)",
            "klasifikasi","jenis_perkara","hakim","anggota1","anggota2",
            "pp","js","tgl_sidang","tgl_sidang(ID)","tgl_sidang_override",
        ]
        default_cols = [c for c in preferred if c in show_df.columns] or list(show_df.columns)
        visible_cols = st.multiselect(
            "Kolom tampil", options=list(show_df.columns),
            default=st.session_state.get("rekap_cols", default_cols),
            key="rekap_cols",
        )
        st.dataframe(show_df[visible_cols], width="stretch", hide_index=True)

        with st.expander("⬇️ Unduh hasil terfilter (CSV)"):
            st.download_button(
                "Unduh CSV",
                data=_export_view_to_csv(show_df),
                file_name="rekap_terfilter.csv",
                mime="text/csv",
                width="stretch",
            )

# =========================================================
# Ringkasan Harian (E-Court vs Manual)
# =========================================================
st.markdown("---")
st.subheader("🗓️ Ringkasan Harian (E-Court vs Manual)")

if rekap.empty:
    st.info("Belum ada data untuk ringkasan.")
else:
    date_col = "tgl_register" if "tgl_register" in rekap.columns else "tgl_sidang"
    tmp = rekap.copy()
    tmp["__tgl"] = pd.to_datetime(tmp[date_col], errors="coerce").dt.normalize()
    tmp = tmp.dropna(subset=["__tgl"])
    tmp["__metode"] = tmp["metode"].map(_norm_metode) if "metode" in tmp.columns else "Manual"
    tmp["__tipe"] = tmp["nomor_perkara"].map(_detect_tipe_from_nomor) if "nomor_perkara" in tmp.columns else "G"

    tmp["E_G"] = ((tmp["__metode"] == "E-Court") & (tmp["__tipe"] == "G")).astype(int)
    tmp["E_P"] = ((tmp["__metode"] == "E-Court") & (tmp["__tipe"] == "P")).astype(int)
    tmp["M_G"] = ((tmp["__metode"] == "Manual")  & (tmp["__tipe"] == "G")).astype(int)
    tmp["M_P"] = ((tmp["__metode"] == "Manual")  & (tmp["__tipe"] == "P")).astype(int)

    _today = date.today()
    # ── 6 kolom: Tahun | Bulan | 4 metric bulanan ──────────────────────────────
    c1, c2, c3, c4, c5, c6 = st.columns([0.9, 1.1, 1.2, 1.2, 1.2, 1.2])
    with c1:
        tahun = st.number_input("Tahun", 2000, 2100, _today.year, step=1)
    with c2:
        bulan = st.selectbox(
            "Bulan",
            list(range(1, 13)),
            index=_today.month - 1,
            format_func=lambda m: [
                "Januari","Februari","Maret","April","Mei","Juni","Juli",
                "Agustus","September","Oktober","November","Desember"
            ][m-1]
        )

    # rentang bulan terpilih
    first_day = pd.Timestamp(int(tahun), int(bulan), 1).normalize()
    last_day = (first_day + pd.offsets.MonthEnd(0)).normalize()
    all_days = pd.date_range(first_day, last_day, freq="D")

    grp = tmp.groupby("__tgl")[["E_G", "E_P", "M_G", "M_P"]].sum().reindex(all_days, fill_value=0)
    grp.index.name = "Tanggal"

    # ── REKAP PER-BULAN (agregasi) ─────────────────────────────────────────────
    monthly_E_G = int(grp["E_G"].sum())
    monthly_E_P = int(grp["E_P"].sum())
    monthly_M_G = int(grp["M_G"].sum())
    monthly_M_P = int(grp["M_P"].sum())
    monthly_total = monthly_E_G + monthly_E_P + monthly_M_G + monthly_M_P

    # tampilkan ringkasannya DI SAMPING dropdown (kolom c3..c6)
    with c3:
        st.metric("Gugatan (E-Court)", f"{monthly_E_G:,}")
    with c4:
        st.metric("Permohonan (E-Court)", f"{monthly_E_P:,}")
    with c5:
        st.metric("Gugatan (Manual)", f"{monthly_M_G:,}")
    with c6:
        st.metric("Permohonan (Manual)", f"{monthly_M_P:,}")
    # total bulanan kecil di bawah baris metric
    st.caption(f"**Total bulanan** {monthly_total:,} perkara "
               f"(E-Court: {monthly_E_G + monthly_E_P:,} • Manual: {monthly_M_G + monthly_M_P:,})")

    # ── Tabel harian detail bulan terpilih (tetap seperti semula) ─────────────
    out = grp.reset_index()
    out["Tanggal (ID)"] = out["Tanggal"].map(_format_tanggal_id)
    out["Total"] = out[["E_G", "E_P", "M_G", "M_P"]].sum(axis=1)
    out = out.rename(columns={
        "E_G": "Gugatan (E-Court)",
        "E_P": "Permohonan (E-Court)",
        "M_G": "Gugatan (Manual)",
        "M_P": "Permohonan (Manual)"
    })[["Tanggal","Tanggal (ID)","Gugatan (E-Court)","Permohonan (E-Court)","Gugatan (Manual)","Permohonan (Manual)","Total"]]

    st.dataframe(out, width="stretch", hide_index=True)
    st.download_button(
        "⬇️ Unduh Ringkasan Harian (CSV)",
        data=out.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"rekap_harian_{tahun:04d}_{bulan:02d}.csv",
        mime="text/csv",
        width="stretch",
    )

