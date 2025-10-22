import streamlit as st
import pandas as pd
from pathlib import Path
from app_core.exports import get_data_dir

st.set_page_config(page_title="Data Status & Checker", layout="wide")
st.header("🧪 Data Status & Checker")

data_dir = get_data_dir()
st.write(f"Folder data yang dicek: `{data_dir}`")

required = {
    "hakim_df.csv": ["id","nama","hari","aktif","max_per_hari","alias","jabatan","catatan"],
    "pp_df.csv": ["id","nama","aktif","alias","catatan"],
    "js_df.csv": ["id","nama","aktif","alias","catatan"],
    "js_ghoib_df.csv": ["id","nama","total_ghoib","aktif","catatan"],
    "libur_df.csv": ["tanggal","keterangan"],
    "sk_df.csv": ["majelis","hari","ketua","anggota1","anggota2","pp1","pp2","js1","js2","aktif","catatan"],
    "rekap_df.csv": ["nomor_perkara","tgl_register","klasifikasi","jenis_perkara","metode","hakim","anggota1","anggota2","pp","js","tgl_sidang"],
}

def _read_csv_safe(p: Path) -> pd.DataFrame:
    # Read with utf-8-sig to strip BOM automatically
    try:
        return pd.read_csv(p, encoding="utf-8-sig")
    except Exception:
        return pd.read_csv(p, encoding="utf-8")

def _normalize_cols(df: pd.DataFrame) -> list[str]:
    cols = []
    for c in df.columns:
        c2 = str(c).strip().lower().replace("\ufeff","")
        cols.append(c2)
    return cols

rows = []
for fname, must in required.items():
    p = data_dir / fname
    if not p.exists():
        rows.append((fname, "❌ MISSING", "-", "-", "-"))
        continue
    try:
        df = _read_csv_safe(p)
        cols_norm = _normalize_cols(df)
        missing_cols = [c for c in [m.lower() for m in must] if c not in cols_norm]
        status = "✅ OK" if not missing_cols else f"⚠️ Missing columns: {', '.join(missing_cols)}"
        rows.append((fname, status, len(df), ", ".join(cols_norm[:12]), str(p)))
    except Exception as e:
        rows.append((fname, f"❌ READ ERROR: {e}", "-", "-", str(p)))

st.subheader("Ringkasan file CSV")
st.dataframe(pd.DataFrame(rows, columns=["File","Status","#Rows","Columns (first ~12)","Path"]), use_container_width=True)

st.markdown("---")
st.subheader("Quick fixes")
st.markdown("""
- Pastikan file **`sk_df.csv`** berada di folder di atas, dengan nama tepat seperti itu.
- Pastikan kolomnya ada semua: `majelis,hari,ketua,anggota1,anggota2,pp1,pp2,js1,js2,aktif,catatan`.
- Jika kamu mengubah folder pada tombol *Generate CSV*, halaman hasil otomatis tetap mencari di folder *data default* di atas.
- Kalau kolom pertama terbaca aneh (misal `\\ufeffmajelis`), itu karena BOM. Baca file dengan **utf-8-sig** atau re‑export via toolbar.
""")
