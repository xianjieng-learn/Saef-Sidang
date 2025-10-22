
import streamlit as st
import pandas as pd
from datetime import date
from io import BytesIO

from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics

from app_core.data_io import load_all
from app_core.helpers import format_tanggal_id

st.set_page_config(page_title="Batch Instrument (Table PDF)", layout="wide")
st.header("🧰 Batch Instrument – Tabel PDF (Auto-fit Column)")

# ===== Load =====
hakim_df, pp_df, js_df, js_ghoib_df, libur_df, rekap_df = load_all()
if rekap_df is None or rekap_df.empty:
    st.warning("Belum ada data rekap.")
    st.stop()

# ensure datetime
rekap_df["tgl_register"] = pd.to_datetime(rekap_df["tgl_register"], errors="coerce")
if "tgl_sidang" in rekap_df.columns:
    rekap_df["tgl_sidang"] = pd.to_datetime(rekap_df.get("tgl_sidang", pd.NaT), errors="coerce")

# ===== Filter tanggal =====
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

sub = sub.sort_values(["tgl_register", "nomor_perkara"], na_position="last").reset_index(drop=True)

# ===== Mapping baris =====
def tick(cond: bool) -> str:
    return "✓" if bool(cond) else ""

def fmt_dt_id(x):
    return format_tanggal_id(pd.to_datetime(x, errors="coerce")) if pd.notna(x) else ""

rows = []
for _, r in sub.iterrows():
    nomor = str(r.get("nomor_perkara", "") or "").strip()
    reg = fmt_dt_id(r.get("tgl_register"))
    klas = str(r.get("klasifikasi", "") or "").strip()
    metode = str(r.get("metode", "") or "").strip()  # E‑Court / Manual
    jenis_proc = str(r.get("jenis_perkara", "") or "").strip().upper()
    ghoib = tick(jenis_proc == "GHOIB")
    istbat = "ISTBAT" if jenis_proc == "ISTBAT" else ""
    hakim = str(r.get("hakim", "") or "").strip()
    pp = str(r.get("pp", "") or "").strip()
    js = str(r.get("js", "") or "").strip()
    sidang = fmt_dt_id(r.get("tgl_sidang"))
    rows.append([nomor, reg, klas, metode, ghoib, istbat, hakim, pp, js, sidang])

HEADERS = [
    "Nomor Perkara", "Register", "Klasifikasi P", "Metode",
    "GHOIB", "ISTBAT", "Hakim", "PP", "JS", "Tanggal Sidang"
]

# ===== PDF builder (auto-fit kolom ke lebar halaman) =====
def build_pdf(table_rows: list[list[str]], title_text: str) -> bytes:
    page_size = landscape(A4)
    page_w = page_size[0]
    margins = dict(left=18, right=18, top=24, bottom=24)
    avail_w = page_w - margins["left"] - margins["right"]

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=page_size,
        leftMargin=margins["left"], rightMargin=margins["right"],
        topMargin=margins["top"], bottomMargin=margins["bottom"]
    )
    styles = getSampleStyleSheet()
    title = Paragraph(title_text, styles["Heading2"])

    data = [HEADERS] + table_rows

    # Hitung lebar kolom berdasarkan string terpanjang pada setiap kolom
    font_name = "Helvetica"
    font_size = 9
    padd = 20  # padding horizontal
    min_w = 45  # minimal width per kolom agar tetap terbaca
    col_widths = []
    for col_idx in range(len(HEADERS)):
        texts = [str(row[col_idx]) for row in data]
        # handle multiline by panjang baris terpanjang
        longest = max((max(t.split("\n"), key=len) for t in texts), key=len)
        w = pdfmetrics.stringWidth(longest, font_name, font_size) + padd
        col_widths.append(max(min_w, w))

    total = sum(col_widths)
    if total > avail_w:
        scale = avail_w / total
        col_widths = [max(min_w, w * scale) for w in col_widths]
        # Jika setelah min_w total masih melebihi avail, skala lagi ringan
        total2 = sum(col_widths)
        if total2 > avail_w:
            scale2 = avail_w / total2
            col_widths = [w * scale2 for w in col_widths]

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
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.whitesmoke, colors.white]),
    ]))

    story = [title, Spacer(1, 6), tbl]
    doc.build(story)
    return buf.getvalue()

# ===== Preview =====
st.subheader("📄 Preview Data")
preview_df = pd.DataFrame(rows, columns=HEADERS)
st.dataframe(preview_df, use_container_width=True, hide_index=True)

# ===== Download =====
if st.button("📑 Generate PDF (Auto-fit)"):
    try:
        title_text = f"INSTRUMEN SIDANG – REKAP TABEL ({tgl_awal:%d %b %Y} s.d. {tgl_akhir:%d %b %Y})"
        pdf_bytes = build_pdf(rows, title_text=title_text)
        st.success(f"Berhasil generate {len(rows)} baris.")
        st.download_button(
            "⬇️ Download PDF",
            data=pdf_bytes,
            file_name=f"Instrumen_Table_{tgl_awal}_{tgl_akhir}.pdf",
            mime="application/pdf",
        )
    except Exception as e:
        st.error(f"Gagal generate PDF: {e}")
