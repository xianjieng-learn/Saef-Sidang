# pages/1_📥_Input_&_Hasil.py — Ketua by lowest beban(active), Anggota STRICT same SK row, PP/JS rotate
from __future__ import annotations
import pandas as pd
import streamlit as st
from datetime import date, datetime, timedelta
import re

from app_core.data_io import load_with_sk, save_table
from app_core.helpers import (
    HARI_MAP, format_tanggal_id, compute_nomor_tipe,
    next_judge_day, df_display_clean
)

# ---- Rotasi PP/JS + debug hooks (graceful fallback) ----
try:
    from app_core.helpers_rotate_from_db_noaktif import (
        rotate_pp, rotate_js_cross, debug_sk_for_ketua, refresh_sk_cache
    )
except Exception:
    try:
        from app_core.helpers_rotate_from_db import rotate_pp, rotate_js_cross, set_sk_use_aktif, refresh_sk_cache  # type: ignore
        try: set_sk_use_aktif(False)
        except Exception: pass
        def debug_sk_for_ketua(hakim, rekap_df=None): return {"matched_rows": pd.DataFrame(), "pp_candidates": [], "js_candidates": [], "pp_counts": {}, "js_counts": {}, "pp_pick": None, "js_pick": None}
    except Exception:
        from app_core.helpers import rotate_pp, rotate_js_cross  # type: ignore
        def debug_sk_for_ketua(hakim, rekap_df=None): return {"matched_rows": pd.DataFrame(), "pp_candidates": [], "js_candidates": [], "pp_counts": {}, "js_counts": {}, "pp_pick": None, "js_pick": None}
        def refresh_sk_cache(): pass

# ---- JS Ghoib otomatis dari DB js_ghoib ----
try:
    from app_core.helpers_js_ghoib import choose_js_ghoib_db, debug_js_ghoib
except Exception:
    def choose_js_ghoib_db(rekap_df, use_aktif=True): return ""
    def debug_js_ghoib(rekap_df, use_aktif=True): return {"candidates": [], "counts": {}, "pick": "", "table": pd.DataFrame()}

st.set_page_config(page_title="📥 Input & Hasil", page_icon="📥", layout="wide")
st.header("📥 Input & Hasil")

# ==== LOAD ====
hakim_df, pp_df, js_df, js_ghoib_df, libur_df, rekap_df, sk_df = load_with_sk()
if sk_df is None or (isinstance(sk_df, pd.DataFrame) and sk_df.empty):
    sk_df = st.session_state.get("sk_df", pd.DataFrame())

# ==== Helpers ====
_PREFIX_RX = re.compile(r"^\s*((drs?|prof|ir|apt|h|hj|kh|ust|ustadz|ustadzah)\.?\s+)+", flags=re.IGNORECASE)
_SUFFIX_PATTERNS = [
    r"s\.?\s*h\.?", r"m\.?\s*h\.?", r"m\.?\s*h\.?\s*i\.?",
    r"s\.?\s*ag", r"m\.?\s*ag", r"m\.?\s*kn", r"m\.?\s*hum",
    r"s\.?\s*kom", r"s\.?\s*psi", r"s\.?\s*e", r"m\.?\s*m", r"m\.?\s*a",
    r"llb", r"llm", r"phd"
]
_SUFFIX_RX = re.compile(r"(,?\s+(" + r"|".join(_SUFFIX_PATTERNS) + r"))+$", flags=re.IGNORECASE)

def _name_key(s: str) -> str:
    if not isinstance(s, str): return ""
    x = s.replace(",", " ").strip()
    x = _SUFFIX_RX.sub("", x)
    x = _PREFIX_RX.sub("", x)
    x = x.replace(".", " ")
    x = re.sub(r"\s+", " ", x).strip().lower()
    toks = [t for t in x.split() if t not in {"s","h","m","e"}]
    return " ".join(toks)

def _is_active_value(v) -> bool:
    s = str(v).strip().upper()
    if s in {"1","YA","Y","TRUE","T","AKTIF","ON"}: return True
    if s in {"0","TIDAK","TDK","NO","N","FALSE","F","NONAKTIF","OFF","", "NONE", "NAN"}: return False
    try: return float(s) != 0.0
    except Exception: return False

def _majelis_rank(s: str) -> int:
    m = re.search(r"(\d+)", str(s))
    return int(m.group(1)) if m else 10**9

def _get_sk_row_for_ketua(sk: pd.DataFrame, ketua: str) -> pd.Series | None:
    """Match ketua by normalized name. Prefer aktif rows if available. If multiple, pick lowest majelis rank."""
    if sk is None or sk.empty or not ketua: return None
    df = sk.copy()
    key = _name_key(ketua)
    # prefer aktif==YA jika ada
    if "aktif" in df.columns:
        m_act = df["aktif"].apply(_is_active_value)
        df_act = df.loc[m_act]
        cand = df_act[df_act["ketua"].astype(str).map(_name_key) == key]
        if cand.empty:
            cand = df[df["ketua"].astype(str).map(_name_key) == key]
    else:
        cand = df[df["ketua"].astype(str).map(_name_key) == key]
    if cand.empty: 
        return None
    if "majelis" in cand.columns:
        cand = cand.assign(__rank=cand["majelis"].astype(str).map(_majelis_rank))
        cand = cand.sort_values(["__rank","majelis"], kind="stable")
    return cand.iloc[0]

def _pick_ketua_by_beban(hakim_df: pd.DataFrame, rekap_df: pd.DataFrame) -> tuple[str, pd.Series | None]:
    """Pilih ketua berdasarkan beban (total baris rekap) di antara hakim yang aktif (hakim_df.aktif==YA)."""
    if hakim_df is None or hakim_df.empty or "nama" not in hakim_df.columns:
        return "", None
    df = hakim_df.copy()
    df["__aktif"] = df.get("aktif", 1).apply(_is_active_value)
    df = df[df["__aktif"] == True]
    if df.empty:
        return "", None
    counts = {}
    if isinstance(rekap_df, pd.DataFrame) and not rekap_df.empty and "hakim" in rekap_df.columns:
        counts = rekap_df["hakim"].astype(str).str.strip().value_counts().to_dict()
    df["__load"] = df["nama"].astype(str).str.strip().map(lambda n: int(counts.get(n, 0)))
    df = df.sort_values(["__load","nama"], kind="stable").reset_index(drop=True)
    ketua = str(df.iloc[0]["nama"])
    # cari baris SK untuk ketua tsb (anggota harus dari SK yang sama)
    sk_row = _get_sk_row_for_ketua(sk_df, ketua)
    return ketua, sk_row

# ==== Form ====
left, right = st.columns([2, 1])
with left:
    nomor = st.text_input("Nomor Perkara")
    tgl_register_input = st.date_input("Tanggal Register", value=date.today())
    KLAS_OPTS = ["CG","CT","VERZET","PAW","WARIS","ISTBAT","HAA","Dispensasi","Poligami","Maqfud","Asal Usul","Perwalian","Harta Bersama","EkSya","Lain-Lain","Lainnya (ketik)"]
    klas_sel = st.selectbox("Klasifikasi Perkara", KLAS_OPTS, index=0)
    klas_final = st.text_input("Tulis klasifikasi lainnya") if klas_sel == "Lainnya (ketik)" else klas_sel
    jenis = st.selectbox("Jenis Perkara (Proses)", ["Biasa","ISTBAT","GHOIB","ROGATORI","MAFQUD"])

with right:
    metode_input = st.selectbox("Metode", ["E-Court","Manual"], index=0)
    semua_nama = []
    if not hakim_df.empty and "nama" in hakim_df.columns:
        df_sorted = hakim_df.copy()
        df_sorted["__aktif_rank"] = (~df_sorted.get("aktif",1).apply(_is_active_value)).astype(int)
        df_sorted = df_sorted.sort_values(["__aktif_rank","nama"], kind="stable")
        semua_nama = df_sorted["nama"].dropna().astype(str).tolist()
    hakim_manual = st.selectbox("Ketua (opsional, override otomatis)", [""] + semua_nama)
    pp_manual = st.text_input("PP Manual (opsional)")
    js_manual = st.text_input("JS Manual (opsional)")
    tipe_pdt = st.selectbox("Tipe Perkara (Pdt)", ["Otomatis","Pdt.G","Pdt.P","Pdt.Plw"])

# ==== Tentukan Ketua (beban aktif) ====
if str(hakim_manual).strip():
    ketua = str(hakim_manual).strip()
    sk_row = _get_sk_row_for_ketua(sk_df, ketua)
    if sk_row is None:
        st.warning("Ketua manual tidak ditemukan di SK. Anggota akan dikosongkan.")
else:
    ketua, sk_row = _pick_ketua_by_beban(hakim_df, rekap_df)

hakim = ketua or ""  # yang ditulis ke rekap_df

# ==== Anggota STRICT dari baris SK yang sama ====
anggota1 = str(sk_row.get("anggota1","")) if isinstance(sk_row, pd.Series) else ""
anggota2 = str(sk_row.get("anggota2","")) if isinstance(sk_row, pd.Series) else ""
if not isinstance(sk_row, pd.Series):
    st.info("Baris SK untuk ketua tidak ditemukan ⇒ Anggota 1/2 dikosongkan.")
else:
    if not (anggota1.strip() and anggota2.strip()):
        st.info("Baris SK ketua belum lengkap Anggota1/2. Lengkapi di Data SK.")

# ==== PP & JS (rotasi) ====
if pp_manual.strip():
    pp_val = pp_manual.strip()
else:
    pp_val = rotate_pp(hakim, rekap_df)

if js_manual.strip():
    js_val = js_manual.strip()
else:
    if str(jenis).upper() == "GHOIB":
        js_val = choose_js_ghoib_db(rekap_df, use_aktif=True) or rotate_js_cross(hakim, rekap_df)
    else:
        js_val = rotate_js_cross(hakim, rekap_df)

# ==== Jadwal sidang ====
base = tgl_register_input if isinstance(tgl_register_input, (datetime, date)) else date.today()
hari_sidang_num = 0
if not hakim_df.empty and hakim and "nama" in hakim_df.columns and ("hari_sidang" in hakim_df.columns or "hari" in hakim_df.columns):
    try:
        if "hari_sidang" in hakim_df.columns:
            hari_text = hakim_df.set_index("nama").loc[hakim, "hari_sidang"]
        else:
            hari_text = hakim_df.set_index("nama").loc[hakim, "hari"]
        hari_sidang_num = HARI_MAP.get(str(hari_text), 0)
    except Exception:
        pass
libur_set = set(libur_df["tanggal"].astype(str).tolist()) if isinstance(libur_df, pd.DataFrame) and "tanggal" in libur_df.columns else set()

if jenis == "Biasa":
    calon_min8 = base + timedelta(days=8)
    d1 = next_judge_day(calon_min8, hari_sidang_num, libur_set) if hari_sidang_num else calon_min8
    tgl_sidang = d1 if (d1 - base).days <= 14 else (next_judge_day(base + timedelta(days=14), hari_sidang_num, libur_set) if hari_sidang_num else base + timedelta(days=14))
elif jenis == "ISTBAT":
    calon = base + timedelta(days=21); tgl_sidang = next_judge_day(calon, hari_sidang_num, libur_set) if hari_sidang_num else calon
elif jenis == "GHOIB":
    offset = 124 if str(klas_final).upper() in ("CT","CG") else 31
    calon = base + timedelta(days=offset); tgl_sidang = next_judge_day(calon, hari_sidang_num, libur_set) if hari_sidang_num else calon
elif jenis == "ROGATORI":
    calon = base + timedelta(days=124); tgl_sidang = next_judge_day(calon, hari_sidang_num, libur_set) if hari_sidang_num else calon
elif jenis == "MAFQUD":
    calon = base + timedelta(days=246); tgl_sidang = next_judge_day(calon, hari_sidang_num, libur_set) if hari_sidang_num else calon
else:
    tgl_sidang = base

# ==== Output ====
nomor_fmt, tipe_final = compute_nomor_tipe(nomor, klas_final, tipe_pdt)
st.subheader("Hasil Otomatis")
resL, resR = st.columns(2)
with resL:
    st.write("**Hakim (Ketua):**", hakim or "-")
    st.write("**Anggota 1**:", anggota1 or "-")
    st.write("**Anggota 2**:", anggota2 or "-")
with resR:
    st.write("**PP**:", pp_val or "-")
    st.write("**JS**:", js_val or "-")
    st.markdown("**Tanggal Sidang**")
    st.markdown(f"<div style='font-size:1.4rem;font-weight:600'>{format_tanggal_id(tgl_sidang)}</div>", unsafe_allow_html=True)

# ==== Simpan ====
if st.button("💾 Simpan ke Rekap", use_container_width=True, disabled=not bool(hakim)):
    new_row = {
        "nomor_perkara": nomor_fmt,
        "tgl_register": pd.to_datetime(base),
        "klasifikasi": klas_final,
        "jenis_perkara": jenis,
        "metode": metode_input,
        "hakim": hakim,  # sama dengan ketua
        "anggota1": anggota1, "anggota2": anggota2,
        "pp": pp_val, "js": js_val,
        "tgl_sidang": pd.to_datetime(tgl_sidang)
    }
    tmp_df = pd.concat([rekap_df, pd.DataFrame([new_row])], ignore_index=True)
    save_table(tmp_df, "rekap")
    st.success("Tersimpan!"); st.rerun()

# ==== Rekap harian ====
st.markdown("---")
st.subheader("Rekap Hari Ini (berdasarkan Tanggal Register)")
filter_date = st.date_input("Filter tanggal", value=base, key="filter_rekap_input")
if not rekap_df.empty and "tgl_register" in rekap_df.columns:
    try:
        rekap_df["tgl_register"] = pd.to_datetime(rekap_df["tgl_register"], errors="coerce")
    except Exception: pass
    mask = rekap_df["tgl_register"].dt.date == filter_date
    view = rekap_df.loc[mask].copy()
    view = df_display_clean(view)
    st.dataframe(view, use_container_width=True)
else:
    st.info("Belum ada data rekap.")

# ==== Debug ====
with st.expander("🔍 Debug Auto-Assign"):
    colA, colB = st.columns([1,1])
    with colA:
        if st.button("🔄 Reload SK dari DB (clear cache)", use_container_width=True):
            try:
                refresh_sk_cache()
            finally:
                st.rerun()
    # debug SK paket
    try:
        info = debug_sk_for_ketua(hakim, rekap_df)
        st.write("**[SK Paket] PP candidates:**", info.get("pp_candidates", []))
        st.write("**[SK Paket] JS candidates:**", info.get("js_candidates", []))
        st.write("**[SK Paket] PP pick:**", info.get("pp_pick"), " | **JS pick:**", info.get("js_pick"))
        rows = info.get("matched_rows")
        st.markdown("**Baris SK yang cocok dengan Ketua:**")
        if isinstance(rows, pd.DataFrame) and not rows.empty:
            st.dataframe(rows, use_container_width=True)
        else:
            st.info("Tidak ada baris SK yang cocok. Cek nama Ketua & kolom pp/js di SK.")
    except Exception as e:
        st.warning(f"Debug SK tidak tersedia: {e}")
    # debug JS ghoib
    try:
        dbg = debug_js_ghoib(rekap_df, use_aktif=True)
        st.write("**[JS Ghoib] Kandidat:**", dbg.get("candidates", []))
        st.write("**[JS Ghoib] Beban (rekap GHOIB):**", dbg.get("counts", {}))
        st.write("**[JS Ghoib] Pick:**", dbg.get("pick", ""))
        tbl = dbg.get("table")
        if isinstance(tbl, pd.DataFrame) and not tbl.empty:
            st.dataframe(tbl, use_container_width=True)
    except Exception as e:
        st.warning(f"Debug JS Ghoib tidak tersedia: {e}")
