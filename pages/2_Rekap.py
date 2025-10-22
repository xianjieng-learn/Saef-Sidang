# pages/2a_📊_Rekap.py
# -*- coding: utf-8 -*-
from __future__ import annotations

import io
from datetime import date
from pathlib import Path
import calendar
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

# ==== PDF utils ====
try:
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.pdfbase import pdfmetrics
except Exception:
    SimpleDocTemplate = None  # penanda reportlab belum tersedia

ID_MONTHS = ["Januari","Februari","Maret","April","Mei","Juni","Juli",
             "Agustus","September","Oktober","November","Desember"]

def _ensure_reportlab():
    if SimpleDocTemplate is None:
        raise RuntimeError(
            "reportlab belum terpasang. Jalankan: pip install reportlab"
        )

def _df_to_pdf_bytes(title: str, df: pd.DataFrame, landscape_mode: bool = True) -> bytes:
    """Render DataFrame ke PDF bytes (tabel sederhana)."""
    _ensure_reportlab()
    buf = io.BytesIO()
    pagesize = landscape(A4) if landscape_mode else A4
    doc = SimpleDocTemplate(buf, pagesize=pagesize, leftMargin=24, rightMargin=24, topMargin=28, bottomMargin=24)

    styles = getSampleStyleSheet()
    story = [Paragraph(title, styles["Title"]), Spacer(1, 6)]

    # siapkan data tabel (header + rows) dalam bentuk string
    headers = [str(c) for c in df.columns]
    rows = [[("" if pd.isna(v) else str(v)) for v in r] for _, r in df.iterrows()]
    data = [headers] + rows

    # auto width: pakai stringWidth (dengan margin minimum)
    def _col_widths(table_data):
        # ambil width maksimum per kolom
        ncol = len(table_data[0])
        widths = [0] * ncol
        for row in table_data:
            for j, cell in enumerate(row):
                w = pdfmetrics.stringWidth(str(cell), "Helvetica", 9) + 16  # padding
                widths[j] = max(widths[j], w)
        # batasi agar tidak melewati page width
        avail = (pagesize[0] - doc.leftMargin - doc.rightMargin)
        total = sum(widths)
        if total > avail and total > 0:
            scale = avail / total
            widths = [max(48, w * scale) for w in widths]  # min 48pt
        return widths

    col_widths = _col_widths(data)
    tbl = Table(data, colWidths=col_widths, repeatRows=1)

    tbl.setStyle(TableStyle([
        ("FONT", (0,0), (-1,-1), "Helvetica", 9),
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#f0f0f0")),
        ("TEXTCOLOR", (0,0), (-1,0), colors.black),
        ("GRID", (0,0), (-1,-1), 0.25, colors.grey),
        ("ALIGN", (0,0), (-1,0), "CENTER"),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.whitesmoke, colors.white]),
        ("TOPPADDING", (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 3),
    ]))

    story.append(tbl)
    doc.build(story)
    pdf = buf.getvalue()
    buf.close()
    return pdf

LIBUR_FILE = Path("data/libur.csv")

def _load_holidays() -> set[pd.Timestamp]:
    """Baca daftar hari libur dari data/libur.csv (kolom: tanggal)."""
    if not LIBUR_FILE.exists():
        return set()
    try:
        dfh = pd.read_csv(LIBUR_FILE, encoding="utf-8-sig")
    except Exception:
        dfh = pd.read_csv(LIBUR_FILE)
    # cari kolom tanggal yang tepat
    cand = [c for c in dfh.columns if str(c).strip().lower() in {"tanggal", "tgl", "date"}]
    if not cand:
        return set()
    ts = pd.to_datetime(dfh[cand[0]], errors="coerce").dt.normalize()
    return set(ts.dropna().tolist())

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

# ================== TABS ================================
tab1, tab2, tab3 = st.tabs(["🎯 Filter", "🗓️ Ringkasan Harian", "📅 Rekap Bulanan per Majelis (Hakim)"])

with tab1:
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
                "nomor_perkara","tgl_register(ID)",
                "klasifikasi","jenis_perkara","hakim","anggota1","anggota2",
                "pp","js","tgl_sidang(ID)",
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

with tab2:
    # =========================================================
    # Ringkasan Harian (E-Court vs Manual) — tanpa Sabtu/Minggu & hari libur
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

        # label kategori
        tmp["E_G"] = ((tmp["__metode"] == "E-Court") & (tmp["__tipe"] == "G")).astype(int)
        tmp["E_P"] = ((tmp["__metode"] == "E-Court") & (tmp["__tipe"] == "P")).astype(int)
        tmp["M_G"] = ((tmp["__metode"] == "Manual")  & (tmp["__tipe"] == "G")).astype(int)
        tmp["M_P"] = ((tmp["__metode"] == "Manual")  & (tmp["__tipe"] == "P")).astype(int)

        # pilih bulan & tahun
        _today = date.today()
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

        # daftar hari libur (opsional) + filter akhir pekan
        libur_set = _load_holidays()
        def _is_kerja(ts: pd.Timestamp) -> bool:
            if pd.isna(ts): return False
            # weekday: Mon=0 ... Sun=6 → hanya 0..4
            if ts.weekday() >= 5:
                return False
            if ts.normalize() in libur_set:
                return False
            return True

        # filter data sumber ke hari kerja saja dalam bulan terpilih
        in_month = (tmp["__tgl"] >= first_day) & (tmp["__tgl"] <= last_day)
        is_workday = tmp["__tgl"].map(_is_kerja)
        tmp_month = tmp.loc[in_month & is_workday].copy()

        # bangun index hanya hari kerja (tanpa Sabtu/Minggu/libur)
        all_days = pd.date_range(first_day, last_day, freq="D")
        workdays = [d for d in all_days if _is_kerja(d)]
        if len(workdays) == 0:
            st.info("Tidak ada hari kerja pada bulan/konfigurasi libur yang dipilih.")
            st.stop()

        # agregasi harian lalu reindex ke daftar hari kerja
        grp = (
            tmp_month.groupby("__tgl")[["E_G", "E_P", "M_G", "M_P"]]
            .sum()
            .reindex(workdays, fill_value=0)
        )
        grp.index.name = "Tanggal"

        # ringkasan bulanan
        monthly_E_G = int(grp["E_G"].sum())
        monthly_E_P = int(grp["E_P"].sum())
        monthly_M_G = int(grp["M_G"].sum())
        monthly_M_P = int(grp["M_P"].sum())
        monthly_total = monthly_E_G + monthly_E_P + monthly_M_G + monthly_M_P

        with c3: st.metric("Gugatan (E-Court)", f"{monthly_E_G:,}")
        with c4: st.metric("Permohonan (E-Court)", f"{monthly_E_P:,}")
        with c5: st.metric("Gugatan (Manual)", f"{monthly_M_G:,}")
        with c6: st.metric("Permohonan (Manual)", f"{monthly_M_P:,}")
        st.caption(f"**Total bulanan (hari kerja saja)** {monthly_total:,} perkara "
                f"(E-Court: {monthly_E_G + monthly_E_P:,} • Manual: {monthly_M_G + monthly_M_P:,})")

        # tabel harian (hari kerja saja)
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
            file_name=f"rekap_harian_{tahun:04d}_{bulan:02d}_hari-kerja.csv",
            mime="text/csv",
            width="stretch",
        )
        # === Download PDF ===
        try:
            title_pdf = f"Ringkasan Harian (Hari Kerja) — {ID_MONTHS[bulan-1]} {tahun}"
            pdf_bytes = _df_to_pdf_bytes(title_pdf, out)
            st.download_button(
                "📄 Unduh Ringkasan Harian (PDF)",
                data=pdf_bytes,
                file_name=f"rekap_harian_{tahun:04d}_{bulan:02d}_hari-kerja.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
        except Exception as e:
            st.caption(f"PDF tidak tersedia: {e}")

with tab3:
    # =========================================================
    # Rekap per Majelis (Hakim) — 1 kontrol Rentang Tanggal
    # Default: bulan ini (tgl 1 → tgl terakhir bulan berjalan)
    # =========================================================
    st.markdown("---")
    st.subheader("📅 Rekap per Majelis (Hakim)")

    if rekap.empty:
        st.info("Belum ada data untuk rekap per majelis.")
    else:
        # --- deteksi kolom tanggal & hakim ---
        cand_date_cols = ["tgl_register", "tgl_sidang", "tanggal"]
        date_col = next((c for c in cand_date_cols if c in rekap.columns), None)

        cand_hakim_cols = ["hakim", "ketua", "majelis"]
        hakim_col = next((c for c in cand_hakim_cols if c in rekap.columns), None)

        if date_col is None:
            st.warning(
                f"Tidak menemukan kolom tanggal dari kandidat {cand_date_cols}. "
                "Pastikan CSV punya salah satu kolom tersebut."
            )
        elif hakim_col is None:
            st.warning(
                f"Tidak menemukan kolom hakim dari kandidat {cand_hakim_cols}. "
                "Rekap per majelis tidak bisa ditampilkan."
            )
        else:
            # --- default range = bulan ini ---
            _today = date.today()
            first_day = date(_today.year, _today.month, 1)
            last_day  = date(_today.year, _today.month,
                             calendar.monthrange(_today.year, _today.month)[1])

            # === 1 kontrol range ===
            # Catatan: Streamlit akan mengembalikan tuple (start, end).
            # Pada beberapa versi/UX, user bisa memilih satu tanggal saja → normalisasi ke (d, d).
            rng = st.date_input(
                "Rentang Tanggal",
                value=(first_day, last_day),
                key="rng_majelis",
            )

            # Normalisasi keluaran (handle single date / None)
            if isinstance(rng, (list, tuple)) and len(rng) == 2:
                tgl_awal, tgl_akhir = rng
            elif isinstance(rng, (list, tuple)) and len(rng) == 1:
                tgl_awal = tgl_akhir = rng[0]
            elif isinstance(rng, date):
                tgl_awal = tgl_akhir = rng
            else:
                tgl_awal, tgl_akhir = first_day, last_day

            # Normalisasi jika user terbalik
            if tgl_awal > tgl_akhir:
                tgl_awal, tgl_akhir = tgl_akhir, tgl_awal

            start_ts = pd.Timestamp(tgl_awal)
            end_ts   = pd.Timestamp(tgl_akhir)  # inklusif

            # --- filter & siapkan data ---
            temp = rekap.copy()
            temp["__tgl"] = pd.to_datetime(temp[date_col], errors="coerce")
            temp = temp.dropna(subset=["__tgl"])
            mask = (temp["__tgl"] >= start_ts) & (temp["__tgl"] <= end_ts)

            # --- agregasi per majelis/hakim ---
            per_majelis = (
                temp.loc[mask & (temp[hakim_col].astype(str).str.strip() != "")]
                    .groupby(temp[hakim_col].astype(str).str.strip())
                    .size()
                    .reset_index(name="Beban Perkara")
                    .rename(columns={hakim_col: "Hakim"})
                    .sort_values("Beban Perkara", ascending=False, kind="stable")
                    .reset_index(drop=True)
            )

            st.caption(
                f"Periode: **{tgl_awal.strftime('%d %b %Y')}** s.d. **{tgl_akhir.strftime('%d %b %Y')}**"
            )
            st.dataframe(per_majelis, use_container_width=True, hide_index=True)

            # --- Unduh CSV ---
            fn_csv = f"rekap_majelis_{tgl_awal:%Y%m%d}_sd_{tgl_akhir:%Y%m%d}.csv"
            st.download_button(
                "⬇️ Unduh Rekap per Majelis (CSV)",
                data=per_majelis.to_csv(index=False).encode("utf-8-sig"),
                file_name=fn_csv,
                mime="text/csv",
                use_container_width=True,
            )

            # --- Unduh PDF (jika util PDF tersedia) ---
            try:
                title_pdf = (
                    f"Rekap per Majelis — {tgl_awal.strftime('%d %b %Y')} "
                    f"s.d. {tgl_akhir.strftime('%d %b %Y')}"
                )
                pdf_bytes = _df_to_pdf_bytes(title_pdf, per_majelis, landscape_mode=False)
                st.download_button(
                    "📄 Unduh Rekap per Majelis (PDF)",
                    data=pdf_bytes,
                    file_name=f"rekap_majelis_{tgl_awal:%Y%m%d}_sd_{tgl_akhir:%Y%m%d}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )
            except Exception as e:
                st.caption(f"PDF tidak tersedia: {e}")

