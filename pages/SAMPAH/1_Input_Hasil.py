# pages/1_Input_Hasil.py — Anggota STRICT by Ketua's SK, PP/JS ROTATE (not strict)
from __future__ import annotations
import pandas as pd
import streamlit as st
from datetime import date, datetime, timedelta
from pathlib import Path
import re

from app_core.data_io import load_with_sk, save_table
from app_core.helpers import (
    HARI_MAP, format_tanggal_id, compute_nomor_tipe,
    next_judge_day, df_display_clean, choose_hakim_auto as _choose_hakim_fallback
)

# ---------- CSV mirror rekap_df ----------
try:
    from app_core.exports import export_csv as _export_csv_fn  # type: ignore
except Exception:
    _export_csv_fn = None

def _auto_export_rekap_csv(df: pd.DataFrame | None = None):
    try:
        out = df.copy() if isinstance(df, pd.DataFrame) else load_with_sk()[5].copy()
    except Exception:
        out = df if isinstance(df, pd.DataFrame) else pd.DataFrame()
    try:
        if _export_csv_fn:
            _export_csv_fn(out, "rekap_df.csv")
        else:
            data_dir = Path("data"); data_dir.mkdir(parents=True, exist_ok=True)
            out.to_csv(data_dir / "rekap_df.csv", index=False, encoding="utf-8-sig")
        st.toast("rekap_df.csv diperbarui", icon="✅")
    except Exception as e:
        st.warning(f"Gagal mirror rekap_df.csv: {e}")

st.set_page_config(page_title="Input & Hasil", page_icon="📥", layout="wide")
st.header("📥 Input & Hasil")

# ---------- Load ----------
hakim_df, pp_df, js_df, js_ghoib_df, libur_df, rekap_df, sk_df = load_with_sk()
if sk_df is None or (isinstance(sk_df, pd.DataFrame) and sk_df.empty):
    sk_df = st.session_state.get("sk_df", pd.DataFrame())

# ---------- Robust name normalization ----------
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

def _active_sk(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty: return pd.DataFrame()
    if "aktif" in df.columns:
        m = df["aktif"].apply(_is_active_value)
        return df.loc[m].copy()
    return df.copy()

def _majelis_rank(s: str) -> int:
    import re
    m = re.search(r"(\d+)", str(s))
    return int(m.group(1)) if m else 10**9

# ---------- Ketua from SK aktif (beban kecil) ----------
def pick_ketua_from_sk(sk: pd.DataFrame, rekap: pd.DataFrame) -> tuple[str, pd.Series | None]:
    if sk is None or sk.empty or "ketua" not in sk.columns:
        return "", None
    df = _active_sk(sk).copy()
    if df.empty: return "", None
    cnt = {}
    if isinstance(rekap, pd.DataFrame) and not rekap.empty and "hakim" in rekap.columns:
        keys = rekap["hakim"].astype(str).map(_name_key)
        cnt = keys.value_counts().to_dict()
    df["__key"] = df["ketua"].astype(str).map(_name_key)
    df["__load"] = df["__key"].map(lambda k: int(cnt.get(k, 0)))
    df["__rank"] = df["majelis"].astype(str).map(_majelis_rank) if "majelis" in df.columns else 0
    df = df.sort_values(["__load","__rank","majelis"], kind="stable").reset_index(drop=True)
    cho = df.iloc[0]
    return str(cho["ketua"]), cho

def get_sk_row_for_ketua(sk: pd.DataFrame, ketua: str) -> pd.Series | None:
    """Return SK row for a Ketua by normalized name. IGNORE day. If multiple, pick lowest majelis rank."""
    if sk is None or sk.empty or not ketua: return None
    df = _active_sk(sk)
    if df.empty: return None
    key = _name_key(ketua)
    cand = df[df["ketua"].astype(str).map(_name_key) == key]
    if cand.empty: return None
    if "majelis" in cand.columns:
        cand = cand.assign(__rank=cand["majelis"].astype(str).map(_majelis_rank))
        cand = cand.sort_values(["__rank","majelis"], kind="stable")
    return cand.iloc[0]

# ---------- Fallback rotation if helpers missing ----------
def _rotate_pp_fallback(hakim_name: str, rekap_df: pd.DataFrame) -> str:
    if pp_df is None or pp_df.empty or "nama" not in pp_df.columns:
        return ""
    act = pp_df.copy()
    act["__aktif"] = act.get("aktif", 1).apply(_is_active_value)
    act = act[act["__aktif"] == True]
    if act.empty: return ""
    counts = {}
    if isinstance(rekap_df, pd.DataFrame) and not rekap_df.empty and "pp" in rekap_df.columns:
        counts = rekap_df["pp"].astype(str).str.strip().value_counts().to_dict()
    def key(n): return counts.get(str(n).strip(), 0)
    return act.sort_values("nama").sort_values(by="nama").iloc[act["nama"].map(key).argsort()].iloc[0]["nama"]

def _rotate_js_fallback(hakim_name: str, rekap_df: pd.DataFrame) -> str:
    if js_df is None or js_df.empty or "nama" not in js_df.columns:
        return ""
    act = js_df.copy()
    act["__aktif"] = act.get("aktif", 1).apply(_is_active_value)
    act = act[act["__aktif"] == True]
    if act.empty: return ""
    counts = {}
    if isinstance(rekap_df, pd.DataFrame) and not rekap_df.empty and "js" in rekap_df.columns:
        counts = rekap_df["js"].astype(str).str.strip().value_counts().to_dict()
    def key(n): return counts.get(str(n).strip(), 0)
    return act.sort_values("nama").sort_values(by="nama").iloc[act["nama"].map(key).argsort()].iloc[0]["nama"]

try:
    from app_core.helpers import rotate_pp as _rotate_pp_lib, rotate_js_cross as _rotate_js_lib  # type: ignore
    def rotate_pp(hakim_name: str, rekap_df: pd.DataFrame) -> str:
        try:
            return _rotate_pp_lib(hakim_name, rekap_df)
        except Exception:
            return _rotate_pp_fallback(hakim_name, rekap_df)
    def rotate_js_cross(hakim_name: str, rekap_df: pd.DataFrame) -> str:
        try:
            return _rotate_js_lib(hakim_name, rekap_df)
        except Exception:
            return _rotate_js_fallback(hakim_name, rekap_df)
except Exception:
    rotate_pp = _rotate_pp_fallback
    rotate_js_cross = _rotate_js_fallback

# ---------- Form ----------
left, right = st.columns([2, 1])
with left:
    nomor = st.text_input("Nomor Perkara")
    tgl_register_input = st.date_input("Tanggal Register", value=date.today())
    KLAS = ["CG","CT","VERZET","PAW","WARIS","ISTBAT","HAA","Dispensasi","Poligami","Maqfud","Asal Usul","Perwalian","Harta Bersama","EkSya","Lain-Lain","Lainnya (ketik)"]
    klas_sel = st.selectbox("Klasifikasi Perkara", KLAS, index=0)
    klas_final = st.text_input("Tulis klasifikasi lainnya") if klas_sel == "Lainnya (ketik)" else klas_sel
    jenis = st.selectbox("Jenis Perkara (Proses)", ["Biasa","ISTBAT","GHOIB","ROGATORI","MAFQUD"])

with right:
    metode_input = st.selectbox("Metode", ["E-Court","Manual"], index=0)
    semua_nama = []
    if not hakim_df.empty and "nama" in hakim_df.columns:
        df_sorted = hakim_df.copy()
        aktif_flag = df_sorted.get("aktif","YA").astype(str).str.upper().isin(["YA","Y","1","TRUE"])
        df_sorted["__aktif_rank"] = (~aktif_flag).astype(int)
        df_sorted = df_sorted.sort_values(["__aktif_rank","nama"], kind="stable")
        semua_nama = df_sorted["nama"].dropna().astype(str).tolist()
    hakim_manual = st.selectbox("Hakim (kosongkan untuk otomatis)", [""] + semua_nama)

# ---------- Pilih Ketua ----------
if str(hakim_manual).strip():
    hakim = str(hakim_manual).strip()
    sk_row = get_sk_row_for_ketua(sk_df, hakim)
else:
    hakim, sk_row = pick_ketua_from_sk(sk_df, rekap_df)
    if not hakim:
        hakim = _choose_hakim_fallback(hakim_df, rekap_df, tgl_register_input) if not hakim_df.empty else ""
        sk_row = get_sk_row_for_ketua(sk_df, hakim)

# ---------- Hitung tanggal sidang ----------
base = tgl_register_input if isinstance(tgl_register_input, (datetime, date)) else date.today()
# gunakan hari dari master hakim hanya untuk menghitung tanggal, TIDAK mempengaruhi anggota
hari_sidang_num = 0
if not hakim_df.empty and hakim and "nama" in hakim_df.columns and ("hari" in hakim_df.columns or "hari_sidang" in hakim_df.columns):
    try:
        if "hari" in hakim_df.columns:
            hari_text = str(hakim_df.set_index("nama").loc[hakim, "hari"])
        else:
            hari_text = str(hakim_df.set_index("nama").loc[hakim, "hari_sidang"])
        hari_sidang_num = HARI_MAP.get(hari_text, 0)
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

# ---------- Anggota 1 & 2 STRICT by Ketua (ignore day) ----------
anggota1 = str(sk_row.get("anggota1","")) if isinstance(sk_row, pd.Series) else ""
anggota2 = str(sk_row.get("anggota2","")) if isinstance(sk_row, pd.Series) else ""

if not isinstance(sk_row, pd.Series):
    st.warning("Ketua tidak ditemukan pada SK aktif ⇒ Anggota 1/2 dikosongkan. Periksa SK atau pilih ketua lain.")
else:
    if not (anggota1.strip() and anggota2.strip()):
        st.info("Baris SK untuk ketua tersebut tidak memiliki Anggota 1/2 lengkap. Lengkapi di Data SK.")

# ---------- PP/JS ROTATION (NOT strict to SK) ----------
# PP: rotasi berdasarkan beban rekap & status aktif
pp_val = rotate_pp(hakim, rekap_df)

# JS: untuk GHOIB, coba pilih dari DB ghoib; kalau tidak, rotasi biasa
try:
    from app_core.helpers_js_ghoib import choose_js_ghoib_db
except Exception:
    def choose_js_ghoib_db(rekap_df, use_aktif=True): return ""
if str(jenis).upper() == "GHOIB":
    js_val = choose_js_ghoib_db(rekap_df, use_aktif=True) or rotate_js_cross(hakim, rekap_df)
else:
    js_val = rotate_js_cross(hakim, rekap_df)

# ---------- Output ----------
nomor_fmt, tipe_final = compute_nomor_tipe(nomor, klas_final, "Otomatis")
st.subheader("Hasil Otomatis")
resL, resR = st.columns(2)
with resL:
    st.write("**Hakim**:", hakim or "-")
    st.write("**Anggota 1**:", anggota1 or "-")
    st.write("**Anggota 2**:", anggota2 or "-")
with resR:
    st.write("**PP**:", pp_val or "-")
    st.write("**JS**:", js_val or "-")
    st.markdown("**Tanggal Sidang**")
    st.markdown(f"<div style='font-size:1.4rem;font-weight:600'>{format_tanggal_id(tgl_sidang)}</div>", unsafe_allow_html=True)

# ---------- Simpan ----------
if st.button("💾 Simpan ke Rekap", use_container_width=True, disabled=not hakim):
    new_row = {
        "nomor_perkara": nomor_fmt,
        "tgl_register": pd.to_datetime(base),
        "klasifikasi": klas_final,
        "jenis_perkara": jenis,
        "metode": metode_input,
        "hakim": hakim, "anggota1": anggota1, "anggota2": anggota2,
        "pp": pp_val, "js": js_val,
        "tgl_sidang": pd.to_datetime(tgl_sidang)
    }
    tmp_df = pd.concat([rekap_df, pd.DataFrame([new_row])], ignore_index=True)
    save_table(tmp_df, "rekap")
    _auto_export_rekap_csv(tmp_df)
    st.success("Tersimpan!"); st.rerun()

# ---------- Rekap harian ----------
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
