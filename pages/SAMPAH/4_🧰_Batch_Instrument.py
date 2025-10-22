# pages/4_🧰_Batch_Instrument.py
import streamlit as st
import pandas as pd
from datetime import date
from io import BytesIO

from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics

from app_core.data_io import load_all
from app_core.helpers import format_tanggal_id

st.set_page_config(page_title="Batch Instrument (Table PDF)", layout="wide")
st.header("🧰 Batch Instrument – Tabel PDF (Auto-fit Column)")

hakim_df, pp_df, js_df, js_ghoib_df, libur_df, rekap_df = load_all()
if rekap_df.empty:
    st.warning("Belum ada data rekap.")
    st.stop()

rekap_df["tgl_register"] = pd.to_datetime(rekap_df["tgl_register"], errors="coerce")
rekap_df["tgl_sidang"] = pd.to_datetime(rekap_df.get("tgl_sidang", pd.NaT), errors="coerce")

# ===== Filter
c1, c2 = st.columns(2)
with c1:
    tgl_awal = st.date_input("Tanggal Register Awal", value=date.today())
with c2:
    tgl_akhir = st.date_input("Tanggal Register Akhir", value=date.today())

mask = (rekap_df["tgl_register"].dt.date >= tgl_awal) & (rekap_df["tgl_register"].dt.date <= tgl_akhir)
sub = rekap_df.loc[mask].copy()

if sub.empty:
    st.info("Tidak ada data di rentang tanggal ini.")
    st.stop()

sub = sub.sort_values(["tgl_register", "nomor_perkara"]).reset_index(drop=True)

# ===== Mapping
def tick(cond: bool) -> str:
    return "✓" if cond else ""

def fmt_dt_id(x):
    return format_tanggal_id(pd.to_datetime(x, errors="coerce")) if pd.notna(x) else ""

rows = []
for _, r in sub.iterrows():
    nomor = str(r.get("nomor_perkara", "")).strip()
    reg = fmt_dt_id(r.get("tgl_register"))
    klas = str(r.get("klasifikasi", "")).strip()
    metode = str(r.get("metode", "")).strip()
    jenis_proc = str(r.get("jenis_perkara", "")).strip().upper()
    ghoib = tick(jenis_proc == "GHOIB")
    istbat = "ISTBAT" if jenis_proc == "ISTBAT" else ""
    hakim = str(r.get("hakim", "")).strip()
    pp = str(r.get("pp", "")).strip()
    js = str(r.get("js", "")).strip()
    sidang = fmt_dt_id(r.get("tgl_sidang"))
    rows.append([nomor, reg, klas, metode, ghoib, istbat, hakim, pp, js, sidang])

HEADERS = [
    "Nomor Perkara", "Register", "Klasifikasi P", "Jenis",
    "GHOIB", "ISTBAT", "Hakim", "PP", "JS", "Tanggal Sidang"
]

# ===== PDF builder (auto-fit kolom)
def build_pdf(table_rows: list[list[str]]) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=landscape(A4),
        leftMargin=18, rightMargin=18, topMargin=24, bottomMargin=24
    )
    styles = getSampleStyleSheet()
    title = Paragraph("INSTRUMEN SIDANG – REKAP TABEL", styles["Heading2"])

    data = [HEADERS] + table_rows

    # hitung lebar kolom berdasarkan teks terpanjang
    font_name = "Helvetica"
    font_size = 9
    col_widths = []
    for col_idx in range(len(HEADERS)):
        texts = [str(row[col_idx]) for row in data]
        max_text = max(texts, key=len)
        width = pdfmetrics.stringWidth(max_text, font_name, font_size) + 20  # padding
        col_widths.append(width)

    tbl = Table(data, repeatRows=1, colWidths=col_widths)

    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#d9edf7")),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,0), 9),
        ("ALIGN", (0,0), (-1,0), "CENTER"),
        ("GRID", (0,0), (-1,-1), 0.5, colors.grey),
        ("FONTNAME", (0,1), (-1,-1), "Helvetica"),
        ("FONTSIZE", (0,1), (-1,-1), 9),
        ("VALIGN", (0,1), (-1,-1), "MIDDLE"),
    ]))

    doc.build([title, tbl])
    return buf.getvalue()

# ===== Preview & Download
st.subheader("📄 Preview Data")
st.dataframe(pd.DataFrame(rows, columns=HEADERS), use_container_width=True, hide_index=True)

if st.button("📑 Generate PDF (Auto-fit)"):
    try:
        pdf_bytes = build_pdf(rows)
        st.success(f"Berhasil generate {len(rows)} baris.")
        st.download_button(
            "⬇️ Download PDF",
            data=pdf_bytes,
            file_name=f"Instrumen_Table_{tgl_awal}_{tgl_akhir}.pdf",
            mime="application/pdf",
        )
    except Exception as e:
        st.error(f"Gagal generate PDF: {e}")
