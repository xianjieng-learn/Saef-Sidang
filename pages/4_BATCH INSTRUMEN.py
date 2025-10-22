# pages/Batch_Instrument_PerGroup.py
import streamlit as st
import pandas as pd
from datetime import date, datetime
from io import BytesIO
from xml.sax.saxutils import escape as html_escape
from app_core.login import _ensure_auth  
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
)
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics

from app_core.data_io import load_all
from app_core.helpers import format_tanggal_id

st.set_page_config(page_title="Batch Instrument (Table PDF)", layout="wide")
st.header("🧰 Batch Instrument – Tabel PDF (Group by JS/PP/Hakim)")

# ===== Load =====
hakim_df, pp_df, js_df, js_ghoib_df, libur_df, rekap_df = load_all()
if rekap_df is None or rekap_df.empty:
    st.warning("Belum ada data rekap.")
    st.stop()

# ensure datetime
rekap_df["tgl_register"] = pd.to_datetime(rekap_df["tgl_register"], errors="coerce")
if "tgl_sidang" in rekap_df.columns:
    rekap_df["tgl_sidang"] = pd.to_datetime(rekap_df.get("tgl_sidang", pd.NaT), errors="coerce")

# ===== Filter & Group selector =====
c1, c2, c3 = st.columns([1,1,1.2])
with c1:
    tgl_awal = st.date_input("Tanggal Register Awal", value=date.today())
with c2:
    tgl_akhir = st.date_input("Tanggal Register Akhir", value=date.today())
with c3:
    group_by = st.selectbox("Group by", ["JS", "PP", "Hakim"], index=0)

mask = (rekap_df["tgl_register"].dt.date >= tgl_awal) & (rekap_df["tgl_register"].dt.date <= tgl_akhir)
sub = rekap_df.loc[mask].copy()

if sub.empty:
    st.info("Tidak ada data di rentang tanggal ini.")
    st.stop()

sub = sub.sort_values(["tgl_register", "nomor_perkara"], na_position="last").reset_index(drop=True)

# ===== Mapping baris =====
def fmt_dt_id(x):
    return format_tanggal_id(pd.to_datetime(x, errors="coerce")) if pd.notna(x) else ""

# Note: tambahkan "No." di paling kiri
HEADERS = [
    "No.", "Nomor Perkara", "Register", "Klasifikasi P", "Metode",
    "GHOIB", "ISTBAT", "Hakim", "PP", "JS", "Tanggal Sidang"
]
# indices setelah penambahan "No.": Hakim=7, PP=8, JS=9

def row_from_rekap(r) -> list[str]:
    nomor = str(r.get("nomor_perkara", "") or "").strip()
    reg = fmt_dt_id(r.get("tgl_register"))
    klas = str(r.get("klasifikasi", "") or "").strip()
    metode = str(r.get("metode", "") or "").strip()  # E-Court / Manual
    jenis_proc = str(r.get("jenis_perkara", "") or "").strip().upper()

    # ⬇️ perubahan di sini: MAFQUD & ROGATORI ikut kolom "GHOIB"
    if jenis_proc in {"GHOIB", "MAFQUD", "ROGATORI"}:
        ghoib = jenis_proc   # tampilkan jenis sebenarnya di kolom GHOIB
    else:
        ghoib = ""

    istbat = "ISTBAT" if jenis_proc == "ISTBAT" else ""

    hakim = str(r.get("hakim", "") or "").strip()
    pp = str(r.get("pp", "") or "").strip()
    js = str(r.get("js", "") or "").strip()
    sidang = fmt_dt_id(r.get("tgl_sidang"))

    # Jika kamu pakai versi dengan kolom "No." di paling kiri:
    return ["", nomor, reg, klas, metode, ghoib, istbat, hakim, pp, js, sidang]
    # Jika belum pakai kolom "No.", gunakan ini:
    # return [nomor, reg, klas, metode, ghoib, istbat, hakim, pp, js, sidang]


group_map = {"JS": 9, "PP": 8, "Hakim": 7}
group_idx = group_map[group_by]
group_label = group_by

# Build rows & group
all_rows = [row_from_rekap(r) for _, r in sub.iterrows()]
all_rows.sort(key=lambda x: (x[group_idx] or "").lower())

groups: dict[str, list[list[str]]] = {}
for row in all_rows:
    key = row[group_idx] or f"(Tanpa {group_label})"
    groups.setdefault(key, []).append(row)

# ===== Footer timestamp + nomor halaman =====
def _footer(canvas, doc):
    canvas.saveState()
    ts = datetime.now().strftime("%d/%m/%Y %H:%M")
    w = doc.pagesize[0]
    canvas.setFont("Helvetica", 8)
    canvas.drawString(18, 16, f"Dibuat: {ts}")
    canvas.drawRightString(w - 18, 16, f"Hal. {doc.page}")
    canvas.restoreState()

# ===== PDF builder =====
def build_pdf_per_group(grouped_rows: dict[str, list[list[str]]], title_prefix: str, label: str) -> bytes:
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
    cell_style = ParagraphStyle(
        "cell",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=9,
        wordWrap="CJK",
        splitLongWords=True,
        spaceAfter=0,
        spaceBefore=0,
    )
    head_style = ParagraphStyle(
        "head",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=13,
        spaceAfter=6,
    )

    # --- hitung col widths global (termasuk kolom "No.") ---
    font_name = "Helvetica"; font_size = 8; padd = 20; min_w = 40
    sample_rows = [HEADERS[:]] + [r for rows in grouped_rows.values() for r in rows]
    col_widths = []
    for col_idx in range(len(HEADERS)):
        texts = [str(row[col_idx]) for row in sample_rows]
        longest = max((max(t.split("\n"), key=len) for t in texts), key=len)
        w = pdfmetrics.stringWidth(longest, font_name, font_size) + padd
        # Kolom "No." diset minimum lebih kecil
        if col_idx == 0:
            col_widths.append(max(32, w))
        else:
            col_widths.append(max(min_w, w))
    total = sum(col_widths)
    if total > avail_w:
        scale = avail_w / total
        col_widths = [max(32 if i==0 else min_w, w * scale) for i, w in enumerate(col_widths)]
        total2 = sum(col_widths)
        if total2 > avail_w:
            scale2 = avail_w / total2
            col_widths = [w * scale2 for w in col_widths]

    def P(text: str) -> Paragraph:
        return Paragraph(html_escape(str(text or "")), cell_style)

    # --- build story per group (1 halaman per value) ---
    story = []
    group_names = sorted(grouped_rows.keys(), key=lambda s: s.lower())
    for gi, name in enumerate(group_names):
        title = Paragraph(f"{title_prefix} – {label}: <b>{html_escape(name)}</b>", head_style)
        story.append(title)
        story.append(Spacer(1, 4))

        data = [HEADERS[:]]
        # isi “No.” 1..N dalam grup saat render
        for idx, r in enumerate(grouped_rows[name], start=1):
            row = r[:]  # copy
            row[0] = str(idx)  # set kolom "No."
            data.append([P(row[0]), P(row[1]), P(row[2]), P(row[3]), P(row[4]), P(row[5]),
                         P(row[6]), P(row[7]), P(row[8]), P(row[9]), P(row[10])])

        tbl = Table(data, repeatRows=1, colWidths=col_widths)
        tbl.setStyle(TableStyle([
            # Header
            ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#d9edf7")),
            ("FONTNAME",  (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTSIZE",  (0,0), (-1,0), 9),
            ("ALIGN",     (0,0), (-1,0), "CENTER"),
            ("GRID",      (0,0), (-1,0), 0.5, colors.grey),
            ("TOPPADDING",    (0,0), (-1,0), 5),
            ("BOTTOMPADDING", (0,0), (-1,0), 5),
            ("LEFTPADDING",   (0,0), (-1,0), 6),
            ("RIGHTPADDING",  (0,0), (-1,0), 6),

            # Data rows
            ("GRID",      (0,1), (-1,-1), 0.5, colors.grey),
            ("FONTNAME",  (0,1), (-1,-1), "Helvetica"),
            ("FONTSIZE",  (0,1), (-1,-1), 9),
            ("VALIGN",    (0,1), (-1,-1), "MIDDLE"),

            # Align per kolom (No. center)
            ("ALIGN", (0,1), (0,-1), "CENTER"),
            ("ALIGN", (1,1), (1,-1), "LEFT"),
            ("ALIGN", (2,1), (2,-1), "CENTER"),
            ("ALIGN", (3,1), (3,-1), "CENTER"),
            ("ALIGN", (4,1), (5,-1), "CENTER"),
            ("ALIGN", (6,1), (8,-1), "LEFT"),
            ("ALIGN", (9,1), (9,-1), "LEFT"),
            ("ALIGN", (10,1), (10,-1), "CENTER"),

            ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.whitesmoke, colors.white]),
            ("TOPPADDING",    (0,1), (-1,-1), 3),
            ("BOTTOMPADDING", (0,1), (-1,-1), 4),
            ("LEFTPADDING",   (0,1), (-1,-1), 3),
            ("RIGHTPADDING",  (0,1), (-1,-1), 3),
        ]))

        story.append(tbl)
        if gi < len(group_names) - 1:
            story.append(PageBreak())

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()

# ===== Preview: tampilkan No. per grup =====
st.subheader(f"📄 Preview Data (per - {group_label})")
preview_rows = []
for name in sorted(groups.keys(), key=lambda s: s.lower()):
    for i, r in enumerate(groups[name], start=1):
        row = r[:]
        row[0] = i  # kolom "No."
        preview_rows.append(row)

preview_df = pd.DataFrame(preview_rows, columns=HEADERS)
st.dataframe(preview_df, width="stretch", hide_index=True)

# ===== Download =====
if st.button(f"📑 Generate PDF per-{group_label} (1 halaman/{group_label})"):
    try:
        title_prefix = f"INSTRUMEN SIDANG PERTAMA ({tgl_awal:%d %b %Y} s.d. {tgl_akhir:%d %b %Y})"
        pdf_bytes = build_pdf_per_group(groups, title_prefix=title_prefix, label=group_label)
        st.success(f"Berhasil generate {len(preview_rows)} baris, {len(groups)} halaman (per-{group_label}).")
        st.download_button(
            f"⬇️ Download PDF per-{group_label}",
            data=pdf_bytes,
            file_name=f"Instrumen_per{group_label}_{tgl_awal}_{tgl_akhir}.pdf",
            mime="application/pdf",
        )
    except Exception as e:
        st.error(f"Gagal generate PDF: {e}")
