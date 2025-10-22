# pages/1_📥_Input_&_Hasil.py
# Ketua by beban(aktif), Anggota STRICT dari baris SK
# PP/JS dari SK, rotate HANYA saat Simpan (pair 4-step: P1J1→P2J1→P1J2→P2J2)
# Tgl sidang: "Biasa" = H+8..H+14, skip libur, ke hari sidang ketua berikutnya

from __future__ import annotations
import re
import json
import hashlib
from datetime import date, datetime, timedelta
from pathlib import Path
import pandas as pd
import streamlit as st

from app_core.helpers import HARI_MAP, format_tanggal_id, compute_nomor_tipe

# ====================== CSV-ONLY ======================
DATA_DIR = Path("data")
DATA_DIR.mkdir(parents=True, exist_ok=True)

def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    for enc in ("utf-8-sig", "utf-8", "cp1252"):
        try:
            return pd.read_csv(path, encoding=enc)
        except Exception:
            continue
    return pd.read_csv(path)

def _write_csv(df: pd.DataFrame, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8-sig")

rekap_csv_path = DATA_DIR / "rekap.csv"

# ====================== UI & HEADER ==========================
st.set_page_config(page_title="📥 Input & Hasil", page_icon="📥", layout="wide")
st.header("Input & Hasil (CSV-only)")

# ====================== UTIL TEKS/NAMA =======================
_PREFIX_RX = re.compile(r"^\s*((drs?|dra|prof|ir|apt|h|hj|kh|ust|ustadz|ustadzah)\.?\s+)+", flags=re.IGNORECASE)
_SUFFIX_PATTERNS = [
    r"s\.?\s*h\.?", r"s\.?\s*h\.?\s*i\.?", r"m\.?\s*h\.?", r"m\.?\s*h\.?\s*i\.?",
    r"s\.?\s*ag", r"m\.?\s*ag", r"m\.?\s*kn", r"m\.?\s*hum",
    r"s\.?\s*kom", r"s\.?\s*psi", r"s\.?\s*e", r"m\.?\s*m", r"m\.?\s*a",
    r"llb", r"llm", r"phd", r"se", r"ssi", r"sh", r"mh"
]
_SUFFIX_RX = re.compile(r"(,?\s+(" + r"|".join(_SUFFIX_PATTERNS) + r"))+$", flags=re.IGNORECASE)

def _clean_text(s: str) -> str:
    x = str(s or "").replace("\u00A0", " ").strip()
    x = x.replace(" ,", ",").replace(" .", ".")
    x = re.sub(r"\s+", " ", x).strip()
    return x

def _name_key(s: str) -> str:
    if not isinstance(s, str): return ""
    x = _clean_text(s).replace(",", " ")
    x = _SUFFIX_RX.sub("", x)
    x = _PREFIX_RX.sub("", x)
    x = re.sub(r"[^\w\s]", " ", x)
    x = re.sub(r"\s+", " ", x).strip().lower()
    toks = [t for t in x.split() if t not in {"s","h","m","e"}]
    return " ".join(toks)

def _tokset(s: str) -> set[str]:
    return set([t for t in _name_key(s).split() if t])

def _is_active_value(v) -> bool:
    s = re.sub(r"[^A-Z0-9]+", "", str(v).strip().upper())
    if s in {"1","YA","Y","TRUE","T","AKTIF","ON"}: return True
    if s in {"0","TIDAK","TDK","NO","N","FALSE","F","NONAKTIF","OFF","NONE","NAN",""}: return False
    try: return float(s) != 0.0
    except Exception: return False

def _majelis_rank(s: str) -> int:
    m = re.search(r"(\d+)", str(s))
    return int(m.group(1)) if m else 10**9

def _standardize_cols(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty: return pd.DataFrame()
    ren = {}
    for c in list(df.columns):
        raw = str(c).replace("\ufeff","").strip()
        k = re.sub(r"\s+", " ", raw).strip().lower().replace("_"," ")
        if   k in {"majelis","nama majelis","majelis ruang sidang","majelis rs"}: new = "majelis"
        elif k in {"hari","hari sidang","hari sk"}: new = "hari"
        elif k in {"ketua","hakim ketua","ketua majelis"}: new = "ketua"
        elif k in {"anggota1","anggota 1","a1","anggota i"}: new = "anggota1"
        elif k in {"anggota2","anggota 2","a2","anggota ii"}: new = "anggota2"
        elif k in {"pp1","panitera pengganti 1","panitera 1"}: new = "pp1"
        elif k in {"pp2","panitera pengganti 2","panitera 2"}: new = "pp2"
        elif k in {"js1","jurusita 1"}: new = "js1"
        elif k in {"js2","jurusita 2"}: new = "js2"
        elif k in {"aktif","status"}: new = "aktif"
        elif k in {"catatan","keterangan"}: new = "catatan"
        else: new = raw
        ren[c] = new
    out = df.rename(columns=ren).copy()
    for c in out.columns:
        if out[c].dtype == "object":
            out[c] = out[c].astype(str).map(_clean_text)
    return out

def _to_iso(d):
    if d is None or (isinstance(d, str) and d.strip() == ""):
        return None
    try:
        dt = pd.to_datetime(d, errors="coerce")
        if pd.isna(dt): return None
        return str(dt.date())
    except Exception:
        return None

def _export_rekap_csv(df: pd.DataFrame):
    cols = ["nomor_perkara","tgl_register","klasifikasi","jenis_perkara",
            "metode","hakim","anggota1","anggota2","pp","js",
            "tgl_sidang","tgl_sidang_override"]
    df2 = df.copy()
    for c in cols:
        if c not in df2.columns:
            df2[c] = pd.NaT if c in ("tgl_register","tgl_sidang") else (0 if c=="tgl_sidang_override" else "")
    for c in ["tgl_register","tgl_sidang"]:
        df2[c] = pd.to_datetime(df2[c], errors="coerce").dt.date.astype("string")
    _write_csv(df2[cols], rekap_csv_path)

# === CUTI HAKIM (CSV) ===
CUTI_FILE = DATA_DIR / "cuti_hakim.csv"

@st.cache_data(show_spinner=False)
def _load_cuti_df() -> pd.DataFrame:
    """Dukung dua format:
       A) nama,tanggal
       B) nama,mulai,akhir   (inklusif)
    """
    df = _read_csv(CUTI_FILE)
    if df.empty:
        return pd.DataFrame(columns=["nama","mulai","akhir","_nama_norm"])
    cols = {c.lower().strip(): c for c in df.columns}

    if "tanggal" in cols:  # mode A
        df = df.rename(columns={cols.get("nama","nama"):"nama", cols["tanggal"]:"tanggal"})
        df["mulai"] = pd.to_datetime(df["tanggal"], errors="coerce").dt.normalize()
        df["akhir"] = df["mulai"]
        df = df.drop(columns=["tanggal"])
    else:                  # mode B
        nama_col  = cols.get("nama","nama")
        mulai_col = cols.get("mulai") or cols.get("start") or cols.get("dari")
        akhir_col = cols.get("akhir") or cols.get("end") or cols.get("sampai")
        if not (mulai_col and akhir_col):
            return pd.DataFrame(columns=["nama","mulai","akhir","_nama_norm"])
        df = df.rename(columns={nama_col:"nama", mulai_col:"mulai", akhir_col:"akhir"})
        df["mulai"] = pd.to_datetime(df["mulai"], errors="coerce").dt.normalize()
        df["akhir"] = pd.to_datetime(df["akhir"], errors="coerce").dt.normalize()

    df["nama"] = df["nama"].astype(str).str.strip()
    df = df.dropna(subset=["nama","mulai","akhir"]).reset_index(drop=True)
    swap = df["mulai"] > df["akhir"]
    df.loc[swap, ["mulai","akhir"]] = df.loc[swap, ["akhir","mulai"]].values
    df["_nama_norm"] = df["nama"].map(_name_key)  # samakan normalisasi dengan _is_hakim_cuti
    return df[["nama","mulai","akhir","_nama_norm"]]

def _is_hakim_cuti(nama: str, tanggal: pd.Timestamp, cuti_df: pd.DataFrame) -> bool:
    """True jika 'nama' cuti pada 'tanggal' (inklusif)."""
    if not nama or cuti_df is None or cuti_df.empty or tanggal is None:
        return False
    t = pd.to_datetime(tanggal).normalize()
    nn = _name_key(nama)  # sudah lower/trim tanpa gelar
    sub = cuti_df[cuti_df["_nama_norm"] == nn]
    return bool(((sub["mulai"] <= t) & (t <= sub["akhir"])).any())

# ====== header-like filter (untuk buang "nama", "ketua", dll yang nyasar dari CSV) ======
_HEADER_TOKENS = {
    "nama","ketua","anggota","anggota1","anggota 1","anggota2","anggota 2",
    "pp","pp1","pp2","js","js1","js2","hari","majelis","status","aktif",
    "keterangan","catatan","tanggal","tgl","date"
}
def _is_header_like(val: str) -> bool:
    s = str(val or "").strip().lower()
    return s in _HEADER_TOKENS or s == ""

# ====================== LOAD MASTER CSVs =====================
hakim_df = _read_csv(DATA_DIR / "hakim_df.csv")
pp_df    = _read_csv(DATA_DIR / "pp_df.csv")
js_df    = _read_csv(DATA_DIR / "js_df.csv")

libur_df = _read_csv(DATA_DIR / "libur.csv")
if not libur_df.empty:
    cand = None
    for c in ["tanggal","tgl","date","hari_libur"]:
        if c in libur_df.columns:
            cand = c; break
    if cand and cand != "tanggal":
        libur_df = libur_df.rename(columns={cand:"tanggal"})

def _load_sk_csv_only() -> tuple[pd.DataFrame, str]:
    candidates = [DATA_DIR / "sk_df.csv", DATA_DIR / "sk_majelis.csv", DATA_DIR / "sk.csv"]
    if DATA_DIR.exists():
        for p in DATA_DIR.glob("*.csv"):
            if "sk" in p.name.lower() and p not in candidates:
                candidates.append(p)
    for p in candidates:
        df = _standardize_cols(_read_csv(p))
        if not df.empty and "ketua" in df.columns:
            return df, f"CSV: {p.as_posix()}"
    return pd.DataFrame(), "CSV (tidak ada)"

sk_df, sk_src = _load_sk_csv_only()
rekap_df = _read_csv(rekap_csv_path)

hakim_src = "CSV: data/hakim_df.csv" if not hakim_df.empty else "CSV (kosong)"
pp_src    = "CSV: data/pp_df.csv"    if not pp_df.empty    else "CSV (kosong)"
js_src    = "CSV: data/js_df.csv"    if not js_df.empty    else "CSV (kosong)"
libur_src = "CSV: data/libur.csv"    if not libur_df.empty else "CSV (kosong)"
rekap_src = "CSV: data/rekap.csv"    if not rekap_df.empty else "CSV (kosong)"

st.caption(
    "🗂️ Sumber data → "
    f"**SK**: {sk_src} • "
    f"**Hakim**: {hakim_src} • "
    f"**PP**: {pp_src} • "
    f"**JS**: {js_src} • "
    f"**Libur**: {libur_src} • "
    f"**Rekap**: {rekap_src}"
)

# --- helper ambil jabatan dari master hakim_df ---
_JBTN_COLS = ["jabatan", "posisi", "role", "status_jabatan"]  # sesuaikan nama kolom di hakim_df.csv
_JBTN_SPECIAL_RE = r"\b(ketua|wakil)\b"  # peran yang dikecualikan dari auto-pick

def _get_jabatan_for(nama: str) -> str:
    """Balikkan teks jabatan untuk nama hakim ("" jika tidak ada)."""
    try:
        if not isinstance(hakim_df, pd.DataFrame) or hakim_df.empty or "nama" not in hakim_df.columns:
            return ""
        jcol = next((c for c in _JBTN_COLS if c in hakim_df.columns), None)
        if not jcol:
            return ""
        return str(hakim_df.set_index("nama").loc[nama, jcol])
    except Exception:
        return ""

# ================== JS Ghoib fallback =====================
# ================== JS Ghoib: ambil dari data/js_ghoib.csv (terendah jml_ghoib) =====================
def _load_js_ghoib_csv() -> pd.DataFrame:
    p = DATA_DIR / "js_ghoib.csv"
    df = _read_csv(p)
    if df.empty:
        return df
    # normalisasi kolom
    ren = {}
    for c in df.columns:
        raw = str(c).replace("\ufeff", "").strip()
        k = re.sub(r"\s+", " ", raw).lower().replace("_", " ")
        if k in {"nama","js","nama js","nama jurusita","nama_jurusita"}: new = "nama"
        elif k in {"jml ghoib","jml_ghoib","jumlah ghoib","jml","beban ghoib","beban"}: new = "jml_ghoib"
        elif k in {"aktif","status","is aktif","is_aktif","on"}: new = "aktif"
        else: new = raw
        ren[c] = new
    out = df.rename(columns=ren).copy()
    # bersihkan teks & header-like
    if "nama" in out.columns:
        out["nama"] = out["nama"].astype(str).map(lambda s: s.strip())
        out = out[~out["nama"].map(_is_header_like)]
    else:
        out["nama"] = ""
    # angka jml_ghoib (NaN -> besar)
    if "jml_ghoib" in out.columns:
        out["jml_ghoib"] = pd.to_numeric(out["jml_ghoib"], errors="coerce")
    else:
        out["jml_ghoib"] = pd.NA
    # aktif filter opsional (pakai _is_active_value yang sudah ada)
    if "aktif" in out.columns:
        out["_aktif__"] = out["aktif"].apply(_is_active_value)
    else:
        out["_aktif__"] = True
    return out

def choose_js_ghoib_db(rekap_df: pd.DataFrame, use_aktif: bool = True) -> str:
    """
    Urutan sumber:
      1) data/js_ghoib.csv  -> pilih baris aktif (opsional) dengan jml_ghoib paling rendah
         tie-break: nama (a-z).
      2) data/js_df.csv      -> pilih nama aktif pertama (a-z).
      3) rekap.csv           -> ambil nama JS yang pernah dipakai untuk perkara GHOIB,
                                pilih yang paling sedikit dipakai (beban), tie nama.
    """
    # 1) js_ghoib.csv
    gh = _load_js_ghoib_csv()
    if not gh.empty and "nama" in gh.columns:
        cand = gh.copy()
        if use_aktif:
            cand = cand[cand["_aktif__"] == True]
        cand = cand[cand["nama"].astype(str).str.strip() != ""]
        if not cand.empty:
            # NaN jml_ghoib -> taruh di akhir (besar)
            max_num = (cand["jml_ghoib"].max(skipna=True) or 0) + 10_000
            jml = cand["jml_ghoib"].fillna(max_num)
            cand = cand.assign(_jml=jml)
            cand = cand.sort_values(by=["_jml", "nama"], ascending=[True, True], kind="stable")
            nm = str(cand.iloc[0]["nama"]).strip()
            return "" if _is_header_like(nm) else nm

    # 2) js_df.csv (master JS)
    if isinstance(js_df, pd.DataFrame) and not js_df.empty:
        name_col = next((c for c in ["nama","js","Nama","NAMA"] if c in js_df.columns), None)
        if name_col:
            tmp = js_df[[name_col]].copy()
            tmp[name_col] = tmp[name_col].astype(str).map(lambda s: s.strip())
            tmp = tmp[~tmp[name_col].map(_is_header_like)]
            if "aktif" in js_df.columns and use_aktif:
                js_df["_aktif__"] = js_df["aktif"].apply(_is_active_value)
                tmp = tmp.join(js_df["_aktif__"])
                tmp = tmp[tmp["_aktif__"] == True]
            names = sorted(tmp[name_col].dropna().unique().tolist())
            if names:
                return names[0]

    # 3) fallback dari rekap: pilih JS GHOIB dengan beban paling sedikit
    if isinstance(rekap_df, pd.DataFrame) and not rekap_df.empty and all(c in rekap_df.columns for c in ["js","jenis_perkara"]):
        r = rekap_df.copy()
        r["jenis_u"] = r["jenis_perkara"].astype(str).str.upper().str.strip()
        r = r[r["jenis_u"] == "GHOIB"]
        r["js_clean"] = r["js"].astype(str).map(lambda s: s.strip())
        r = r[~r["js_clean"].map(_is_header_like)]
        if not r.empty:
            counts = r["js_clean"].str.lower().value_counts().to_dict()
            names = sorted(set(r["js_clean"].tolist()))
            # pilih yang frekuensinya paling sedikit
            best = sorted(names, key=lambda nm: (counts.get(nm.lower(), 0), nm.lower()))[0]
            return best

    return ""

# ================== ROTASI via JSON ========================
_RR_JSON = DATA_DIR / "rrpair_token.json"

def _rr_load():
    if _RR_JSON.exists():
        try: return json.loads(_RR_JSON.read_text(encoding="utf-8"))
        except Exception: return {}
    return {}

def _rr_save(obj):
    _RR_JSON.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")

def _rr_key_per_ketua(ketua: str) -> str:
    norm = re.sub(r"[^a-z0-9]+", "-", _name_key(ketua)).strip("-")
    return f"rrpair::per_ketua::{norm or 'unknown'}"

def _rr_get_idx(rrkey: str) -> int:
    obj = _rr_load()
    try: return int(obj.get(rrkey, {}).get("idx", 0))
    except Exception: return 0

def _rr_set_idx(rrkey: str, idx: int, meta: dict | None = None):
    obj = _rr_load()
    obj[rrkey] = {"idx": int(idx), "meta": (meta or {})}
    _RR_JSON.parent.mkdir(parents=True, exist_ok=True)
    _rr_save(obj)


# ================== PICK KETUA & SK ========================
def _best_sk_row_for_ketua(sk: pd.DataFrame, ketua: str) -> pd.Series | None:
    if sk is None or sk.empty or not ketua: return None
    df = _standardize_cols(sk)
    if "ketua" not in df.columns: return None
    df["__ketua_key"] = df["ketua"].astype(str).map(_name_key)
    df["__ketua_tok"] = df["__ketua_key"].map(lambda s: set(s.split()))
    target = _tokset(ketua)
    if not target: return None
    cand = df[df["__ketua_tok"].apply(lambda s: len(s & target) > 0)].copy()
    if cand.empty:
        key = _name_key(ketua)
        cand = df[df["__ketua_key"] == key].copy()
        if cand.empty:
            return None
    cand["__overlap"] = cand["__ketua_tok"].apply(lambda s: len(s & target))
    cand["__aktif"] = df.get("aktif", pd.Series([True]*len(df))).apply(_is_active_value) if "aktif" in df.columns else True
    cand["__rank"] = df.get("majelis", pd.Series([""]*len(df))).astype(str).map(_majelis_rank) if "majelis" in df.columns else 10**9
    cand = cand.sort_values(["__aktif","__overlap","__rank"], ascending=[False, False, True], kind="stable")
    return cand.iloc[0]

def _pick_ketua_by_beban(
    hakim_df: pd.DataFrame,
    rekap_df: pd.DataFrame,
    tgl_register_input,          # datetime.date
    jenis: str,                  # "Biasa"/"ISTBAT"/"GHOIB"/...
    klasifikasi: str,            # klas_final
    libur_df: pd.DataFrame       # data/libur.csv
) -> tuple[str, pd.Series | None]:
    """Pilih ketua otomatis:
       - hanya hakim aktif,
       - KECUALIKAN jabatan spesial (Ketua/Wakil),
       - KECUALIKAN yang sedang cuti pada rencana tgl sidang,
       - KECUALIKAN yang tidak punya hari sidang,
       - urutkan berdasarkan beban di rekap (paling sedikit, lalu alfabet).
    """
    # jika master kosong
    if hakim_df is None or hakim_df.empty or "nama" not in hakim_df.columns:
        return "", None

    # siapkan libur_set
    libur_set = set()
    if isinstance(libur_df, pd.DataFrame) and "tanggal" in libur_df.columns and not libur_df.empty:
        try:
            libur_set = set(pd.to_datetime(libur_df["tanggal"], errors="coerce").dt.date.astype(str).tolist())
        except Exception:
            libur_set = set(str(x) for x in libur_df["tanggal"].astype(str).tolist())

    # helper: ambil hari sidang & hitung rencana tgl sidang
    def _hari_sidang_num_for(nama_hakim: str) -> int:
        try:
            row = hakim_df.set_index("nama").loc[nama_hakim]
            hari_text = str(row["hari_sidang"] if "hari_sidang" in hakim_df.columns else row.get("hari",""))
            return _weekday_num_from_map(hari_text)
        except Exception:
            return 0

    def _rencana_tgl_sidang(nama_hakim: str):
        hnum = _hari_sidang_num_for(nama_hakim)
        if hnum == 0:
            return None
        base = tgl_register_input if isinstance(tgl_register_input, (datetime, date)) else date.today()
        d = compute_tgl_sidang(
            base=base if isinstance(base, date) else base.date(),
            jenis=jenis,
            hari_sidang_num=hnum,
            libur_set=libur_set,
            klasifikasi=klasifikasi
        )
        return pd.to_datetime(d) if d else None

    # mulai dari hakim aktif
    df = hakim_df.copy()
    df["__aktif"] = df.get("aktif", 1).apply(_is_active_value)
    df = df[df["__aktif"] == True]
    if df.empty: 
        return "", None

    # kecualikan jabatan spesial (Ketua/Wakil)
    jcol = next((c for c in _JBTN_COLS if c in df.columns), None)
    if jcol:
        mask_spesial = df[jcol].astype(str).str.contains(_JBTN_SPECIAL_RE, case=False, regex=True, na=False)
        df = df[~mask_spesial]
    if df.empty:
        return "", None

    # hitung rencana tgl & exclude yang tak punya hari sidang
    df["__nama"] = df["nama"].astype(str).map(str.strip)
    df["__rencana"] = df["__nama"].map(_rencana_tgl_sidang)
    df = df[df["__rencana"].notna()]
    if df.empty:
        return "", None

    # exclude yang cuti pada tanggal rencana
    cuti_df = _load_cuti_df()
    if not cuti_df.empty:
        df = df[~df.apply(lambda r: _is_hakim_cuti(r["__nama"], r["__rencana"], cuti_df), axis=1)]
    if df.empty:
        return "", None

    # beban berdasarkan rekap (berapa kali jadi "hakim" dalam CSV)
    counts = {}
    if isinstance(rekap_df, pd.DataFrame) and not rekap_df.empty and "hakim" in rekap_df.columns:
        counts = rekap_df["hakim"].astype(str).str.strip().value_counts().to_dict()

    df["__load"] = df["__nama"].map(lambda n: int(counts.get(n, 0)))
    df = df.sort_values(["__load","__nama"], kind="stable").reset_index(drop=True)

    ketua = str(df.iloc[0]["__nama"])
    sk_row = _best_sk_row_for_ketua(sk_df, ketua)
    return ketua, sk_row


# ================== PP/JS ROTATION =========================
def _pair_combos_from_sk(sk_row: pd.Series) -> list[tuple[str,str]]:
    if not isinstance(sk_row, pd.Series): return []
    p1 = str(sk_row.get("pp1","")).strip()
    p2 = str(sk_row.get("pp2","")).strip()
    j1 = str(sk_row.get("js1","")).strip()
    j2 = str(sk_row.get("js2","")).strip()
    pp_opts = [x for x in [p1, p2] if x]
    js_opts = [x for x in [j1, j2] if x]
    combos: list[tuple[str,str]] = []
    if pp_opts and js_opts:
        order = [(0,0),(1,0),(0,1),(1,1)]
        for ip, ij in order:
            if ip < len(pp_opts) and ij < len(js_opts):
                combos.append((pp_opts[ip], js_opts[ij]))
    elif pp_opts:
        combos = [(pp_opts[0], "")]
        if len(pp_opts) > 1: combos.append((pp_opts[1], ""))
    elif js_opts:
        combos = [("", js_opts[0])]
        if len(js_opts) > 1: combos.append(("", js_opts[1]))
    else:
        combos = []
    dedup = []
    for t in combos:
        if not dedup or dedup[-1] != t:
            dedup.append(t)
    return dedup or [("", "")]

def _peek_pair(ketua: str, sk_row: pd.Series, jenis: str, rekap_df: pd.DataFrame) -> tuple[str,str]:
    combos = _pair_combos_from_sk(sk_row)
    key = _rr_key_per_ketua(ketua or "unknown")
    idx = _rr_get_idx(key) % len(combos) if combos else 0
    pp, js = combos[idx] if combos else ("", "")
    if str(jenis).strip().upper() == "GHOIB":
        js_gh = choose_js_ghoib_db(rekap_df, use_aktif=True)
        if js_gh: js = js_gh
    # saring header-like
    if _is_header_like(pp): pp = ""
    if _is_header_like(js): js = ""
    return pp, js

def _consume_pair_on_save_once(ketua: str, sk_row: pd.Series, jenis: str, rekap_df: pd.DataFrame) -> tuple[str,str]:
    combos = _pair_combos_from_sk(sk_row)
    key = _rr_key_per_ketua(ketua or "unknown")
    cur = _rr_get_idx(key)
    idx = (cur % len(combos)) if combos else 0
    pp, js = combos[idx] if combos else ("", "")

    # Jika GHOIB → pilih dari js_ghoib.csv & naikkan beban +1
    if str(jenis).strip().upper() == "GHOIB":
        js_gh = choose_js_ghoib_db(rekap_df, use_aktif=True)
        if js_gh:
            js = js_gh
            try:
                p = DATA_DIR / "js_ghoib.csv"
                df = _read_csv(p)
                if not df.empty:
                    # cari kolom nama & jml
                    name_col = next((c for c in df.columns if "nama" in c.lower()), None)
                    cnt_col  = next((c for c in df.columns if ("ghoib" in c.lower()) or (c.lower() in {"jml","jumlah"})), None)
                    if name_col and cnt_col:
                        mask = df[name_col].astype(str).str.strip().str.lower() == str(js_gh).strip().lower()
                        # jika tidak ada baris → tambahkan baris baru
                        if not mask.any():
                            new = pd.DataFrame([{name_col: js_gh, cnt_col: 1, "aktif": 1}])
                            df = pd.concat([df, new], ignore_index=True)
                        else:
                            df.loc[mask, cnt_col] = pd.to_numeric(df.loc[mask, cnt_col], errors="coerce").fillna(0) + 1
                        df.to_csv(p, index=False, encoding="utf-8-sig")
            except Exception as e:
                st.warning(f"Gagal update js_ghoib.csv (+1): {e}")

    # simpan index rotasi ke rrpair_token.json
    next_idx = (idx + 1) % max(1, len(combos))
    _rr_set_idx(key, next_idx, meta={
        "ketua": ketua,
        "combos_len": len(combos),
        "last_used_combo": {"pp": pp, "js": js}
    })
    # sanitasi simbol header
    if str(pp).strip().lower() in {"pp","pp1","pp2"}: pp = ""
    if str(js).strip().lower() in {"js","js1","js2"}: js = ""
    return pp, js

# ================== TANGGAL SIDANG =========================
def _weekday_num_from_map(hari_text: str) -> int:
    try: return int(HARI_MAP.get(str(hari_text), 0))
    except Exception: return 0

def _next_judge_day_strict(start_date: date, hari_sidang_num: int, libur_set: set[str]) -> date:
    if not isinstance(start_date, (date, datetime)) or not hari_sidang_num:
        return start_date
    target_py = (hari_sidang_num - 1) % 7  # Mon=0..Sun=6
    d0 = start_date if isinstance(start_date, date) else start_date.date()
    for i in range(0, 120):
        d = d0 + timedelta(days=i)
        if d.weekday() != target_py: continue
        if str(d) in libur_set: continue
        return d
    return d0

def compute_tgl_sidang(base: date, jenis: str, hari_sidang_num: int, libur_set: set[str], klasifikasi: str = "") -> date:
    J = str(jenis).strip().upper()
    K = str(klasifikasi).strip().upper()
    if J == "BIASA":
        start = base + timedelta(days=8)
        end_cap = base + timedelta(days=14)
        d = _next_judge_day_strict(start, hari_sidang_num, libur_set)
        if d <= end_cap: return d
        return _next_judge_day_strict(end_cap, hari_sidang_num, libur_set)
    elif J == "ISTBAT":
        start = base + timedelta(days=21)
        return _next_judge_day_strict(start, hari_sidang_num, libur_set)
    elif J == "GHOIB":
        off = 124 if K in {"CT", "CG"} else 31
        start = base + timedelta(days=off)
        return _next_judge_day_strict(start, hari_sidang_num, libur_set)
    elif J == "ROGATORI":
        start = base + timedelta(days=124)
        return _next_judge_day_strict(start, hari_sidang_num, libur_set)
    elif J == "MAFQUD":
        start = base + timedelta(days=246)
        return _next_judge_day_strict(start, hari_sidang_num, libur_set)
    return base

# ================== 🧪 Debug Pemilihan & Beban JS Ghoib ==================
with st.expander("🧪 Debug Pemilihan & Beban JS Ghoib", expanded=False):
    p = DATA_DIR / "js_ghoib.csv"
    st.caption(f"File: `{p.as_posix()}`")

    df = _load_js_ghoib_csv()
    if df.empty:
        st.warning("js_ghoib.csv kosong / tidak ditemukan. Buat file dengan kolom minimal: nama,jml_ghoib,aktif.")
    else:
        # tampilkan tabel
        show = df[["nama","jml_ghoib"] + (["aktif"] if "aktif" in df.columns else [])].copy()
        show = show.sort_values(by=["jml_ghoib","nama"], ascending=[True, True], kind="stable")
        st.dataframe(show, width="stretch", height=min(360, 52 + 28*len(show)))

        # kandidat terpilih sekarang
        winner = choose_js_ghoib_db(rekap_df, use_aktif=True)
        if winner:
            cur = show[show["nama"].str.lower() == winner.lower()]
            cur_n = None if cur.empty else (cur.iloc[0]["jml_ghoib"] if pd.notna(cur.iloc[0]["jml_ghoib"]) else 0)
            st.success(f"JS Ghoib kandidat saat ini: **{winner}** (beban={cur_n})")

        st.markdown("---")
        c1, c2, c3, c4 = st.columns([1.5,1,1,1])
        with c1:
            target = st.selectbox("Pilih JS", [""] + show["nama"].tolist(), index=0, key="dbg_js_pick")
        with c2:
            if st.button("➕ +1 beban", width="stretch"):
                if target:
                    raw = _read_csv(p)
                    name_col = next((c for c in raw.columns if "nama" in c.lower()), None)
                    cnt_col  = next((c for c in raw.columns if ("ghoib" in c.lower()) or (c.lower() in {"jml","jumlah"})), None)
                    if name_col and cnt_col:
                        m = raw[name_col].astype(str).str.strip().str.lower() == target.strip().lower()
                        if m.any():
                            raw.loc[m, cnt_col] = pd.to_numeric(raw.loc[m, cnt_col], errors="coerce").fillna(0) + 1
                            raw.to_csv(p, index=False, encoding="utf-8-sig")
                            st.success("Beban ditambah +1"); st.rerun()
        with c3:
            if st.button("♻️ Set 0", width="stretch"):
                if target:
                    raw = _read_csv(p)
                    name_col = next((c for c in raw.columns if "nama" in c.lower()), None)
                    cnt_col  = next((c for c in raw.columns if ("ghoib" in c.lower()) or (c.lower() in {"jml","jumlah"})), None)
                    if name_col and cnt_col:
                        m = raw[name_col].astype(str).str.strip().str.lower() == target.strip().lower()
                        if m.any():
                            raw.loc[m, cnt_col] = 0
                            raw.to_csv(p, index=False, encoding="utf-8-sig")
                            st.success("Beban di-set 0"); st.rerun()
        with c4:
            if st.button("🔄 Refresh", width="stretch"):
                st.rerun()

# ================== PANEL & FORM ===========================
left_ctl, right_ctl = st.columns([1,3])
with left_ctl:
    if st.button("🔄 Refresh (muat ulang CSV)", width="stretch"):
        st.rerun()
with right_ctl:
    st.caption(
        "Sumber data = SK: CSV; Hakim: CSV; PP: CSV; JS: CSV; Libur: CSV; Rekap: CSV"
    )

if "form_seed" not in st.session_state:
    st.session_state["form_seed"] = 0
fs = st.session_state["form_seed"]

left, right = st.columns([2, 1])
with st.form(f"form_perkara_{fs}", clear_on_submit=True):
    with left:
        nomor = st.text_input("Nomor Perkara", key=f"nomor_{fs}")
        tgl_register_input = st.date_input("Tanggal Register", value=date.today(), key=f"tglreg_{fs}")
        KLAS_OPTS = ["CG","CT","VERZET","PAW","WARIS","ISTBAT","HAA","Dispensasi","Poligami","Maqfud","Asal Usul","Perwalian","Harta Bersama","EkSya","Lain-Lain","Lainnya (ketik)"]
        klas_sel = st.selectbox("Klasifikasi Perkara", KLAS_OPTS, index=0, key=f"klas_sel_{fs}")
        klas_final = st.text_input("Tulis klasifikasi lainnya", key=f"klas_other_{fs}") if klas_sel == "Lainnya (ketik)" else klas_sel
        jenis = st.selectbox("Jenis Perkara (Proses)", ["Biasa","ISTBAT","GHOIB","ROGATORI","MAFQUD"], key=f"jenis_{fs}")
        tipe_pdt = st.selectbox("Tipe Perkara (Pdt)", ["Otomatis","Pdt.G","Pdt.P","Pdt.Plw"], key=f"tipe_pdt_{fs}")
    with right:
        metode_input = st.selectbox("Metode", ["E-Court","Manual"], index=0, key=f"metode_{fs}")

        # === Ketua (aktif & tidak cuti di rencana tgl sidang) — bisa override tampilkan yang cuti ===
        cuti_df = _load_cuti_df()

        # siapkan libur_set untuk simulasi tgl sidang per kandidat
        libur_set_for_filter = set()
        if isinstance(libur_df, pd.DataFrame) and "tanggal" in libur_df.columns and not libur_df.empty:
            try:
                libur_set_for_filter = set(pd.to_datetime(libur_df["tanggal"], errors="coerce").dt.date.astype(str).tolist())
            except Exception:
                libur_set_for_filter = set(str(x) for x in libur_df["tanggal"].astype(str).tolist())

        def _hari_sidang_num_for(nama_hakim: str) -> int:
            try:
                if not isinstance(hakim_df, pd.DataFrame) or hakim_df.empty or "nama" not in hakim_df.columns:
                    return 0
                row = hakim_df.set_index("nama").loc[nama_hakim]
                hari_text = str(row["hari_sidang"] if "hari_sidang" in hakim_df.columns else row.get("hari",""))
                return _weekday_num_from_map(hari_text)
            except Exception:
                return 0

        def _calculated_sidang_date_for(nama_hakim: str) -> pd.Timestamp | None:
            hari_num = _hari_sidang_num_for(nama_hakim)
            if hari_num == 0: return None
            base_d = tgl_register_input if isinstance(tgl_register_input, (datetime, date)) else date.today()
            d = compute_tgl_sidang(
                base=base_d if isinstance(base_d, date) else base_d.date(),
                jenis=jenis,
                hari_sidang_num=hari_num,
                libur_set=libur_set_for_filter,
                klasifikasi=klas_final
            )
            return pd.to_datetime(d) if d else None

        # Toggle override (tampilkan yang cuti juga)
        show_cutis = st.toggle("Tampilkan yang cuti (override)", value=False)

        visible_names: list[str] = []
        hidden_reasons: dict[str, str] = {}
        cuti_names: list[str] = []
        label_map: dict[str, str] = {}

        if isinstance(hakim_df, pd.DataFrame) and (not hakim_df.empty) and ("nama" in hakim_df.columns):
            df_sorted = hakim_df.copy()
            df_sorted["_aktif_bool"] = df_sorted.get("aktif", 1).apply(_is_active_value)
            df_sorted = df_sorted[df_sorted["_aktif_bool"] == True]
            df_sorted["__nama_clean"] = df_sorted["nama"].astype(str).map(str.strip)
            df_sorted = df_sorted[~df_sorted["__nama_clean"].map(_is_header_like)]
            df_sorted["__tgl_rencana"] = df_sorted["__nama_clean"].map(_calculated_sidang_date_for)

            for _, r in df_sorted.sort_values(["__nama_clean"], kind="stable").iterrows():
                nm = r["__nama_clean"]
                tgl = r["__tgl_rencana"]
                if tgl is None:
                    hidden_reasons[nm] = "Hari sidang tidak terdata di master hakim."
                    continue
                if _is_hakim_cuti(nm, tgl, cuti_df):
                    cuti_names.append(nm)
                    hidden_reasons[nm] = f"Sedang cuti pada {format_tanggal_id(pd.to_datetime(tgl))}."
                    if show_cutis:
                        visible_names.append(nm)
                        # >>> tambahkan label jabatan
                        jbtn = _get_jabatan_for(nm)
                        extra = f" • {jbtn}" if jbtn and jbtn.strip() else ""
                        label_map[nm] = f"{nm} • CUTI ({format_tanggal_id(pd.to_datetime(tgl))}){extra}"
                    continue
                # normal—tampilkan
                visible_names.append(nm)
                # >>> tambahkan label jabatan
                jbtn = _get_jabatan_for(nm)
                extra = f" • {jbtn}" if jbtn and jbtn.strip() else ""
                label_map[nm] = nm + extra

        # fallback dari SK jika setelah filter kosong sama sekali
        if not visible_names:
            if isinstance(sk_df, pd.DataFrame) and (not sk_df.empty) and ("ketua" in sk_df.columns):
                fallback = (
                    sk_df["ketua"].astype(str).map(str.strip)
                    .replace("", pd.NA).dropna()
                )
                fallback = (
                    fallback[~fallback.map(_is_header_like)]
                    .drop_duplicates().sort_values().tolist()
                )
                visible_names = fallback
                for nm in visible_names:
                    jbtn = _get_jabatan_for(nm)
                    extra = f" • {jbtn}" if jbtn and jbtn.strip() else ""
                    label_map[nm] = nm + extra
                if not show_cutis and cuti_names:
                    st.info("Semua hakim aktif sedang cuti pada tanggal rencana—menampilkan fallback dari SK.", icon="ℹ️")

        def _fmt_opt(nm: str) -> str:
            return label_map.get(nm, nm)

        hakim_manual = st.selectbox(
            "Ketua (opsional, override otomatis)",
            [""] + visible_names,
            format_func=lambda x: ("" if x == "" else _fmt_opt(x)),
            key=f"hakim_manual_{fs}",
            help="Nama disembunyikan jika cuti atau hari sidang tidak terdata; aktifkan toggle untuk override."
        )


        # Dropdown PP & JS dari master (disaring header-like)
        def _options_from_master(df: pd.DataFrame, prefer_active=True) -> list[str]:
            if not isinstance(df, pd.DataFrame) or df.empty: return []
            name_col = None
            for c in ["nama", "pp", "js", "nama_lengkap", "Nama", "NAMA"]:
                if c in df.columns:
                    name_col = c; break
            if not name_col:
                return []
            x = df[[name_col]].copy()
            x[name_col] = x[name_col].astype(str).map(lambda s: s.strip())
            x = x[~x[name_col].map(_is_header_like)]
            if x.empty:
                return []
            if prefer_active and "aktif" in df.columns:
                df["_aktif__"] = df["aktif"].apply(_is_active_value)
                x = x.join(df["_aktif__"])
                x = x.sort_values(by=["_aktif__", name_col], ascending=[False, True])
                names = x[name_col].tolist()
            else:
                names = sorted(x[name_col].unique().tolist())
            out, seen = [], set()
            for n in names:
                if n not in seen:
                    seen.add(n); out.append(n)
            return out

        pp_opts = _options_from_master(pp_df, prefer_active=True)
        js_opts = _options_from_master(js_df, prefer_active=True)
        pp_manual = st.selectbox("PP Manual (opsional)", [""] + pp_opts, key=f"pp_manual_{fs}")
        js_manual = st.selectbox("JS Manual (opsional)", [""] + js_opts, key=f"js_manual_{fs}")

    # Tentukan Ketua & SK
    if str(hakim_manual).strip():
        ketua = str(hakim_manual).strip()
        sk_row = _best_sk_row_for_ketua(sk_df, ketua)
        if sk_row is None:
            st.warning("Ketua manual tidak ditemukan di SK. Anggota/PP/JS akan dikosongkan.")
    else:
        ketua, sk_row = _pick_ketua_by_beban(
    hakim_df, rekap_df,
    tgl_register_input, jenis, klas_final, libur_df
)
    hakim = ketua or ""

    # Anggota STRICT dari baris SK
    anggota1 = str(sk_row.get("anggota1","")) if isinstance(sk_row, pd.Series) else ""
    anggota2 = str(sk_row.get("anggota2","")) if isinstance(sk_row, pd.Series) else ""
    if not isinstance(sk_row, pd.Series):
        st.info("Baris SK untuk ketua tidak ditemukan ⇒ Anggota/PP/JS dikosongkan.")
    else:
        if not (anggota1.strip() and anggota2.strip()):
            st.info("Baris SK ketua belum lengkap Anggota1/2. Lengkapi di Data SK.")

    # Preview PP/JS
    if str(pp_manual).strip():
        pp_preview = pp_manual.strip()
        js_preview = js_manual.strip() if str(js_manual).strip() else _peek_pair(hakim, sk_row, jenis, rekap_df)[1]
    else:
        if str(js_manual).strip():
            pp_preview = _peek_pair(hakim, sk_row, jenis, rekap_df)[0]
            js_preview = js_manual.strip()
        else:
            pp_preview, js_preview = _peek_pair(hakim, sk_row, jenis, rekap_df)

    # Hitung Tgl Sidang (strict)
    base = tgl_register_input if isinstance(tgl_register_input, (datetime, date)) else date.today()
    hari_sidang_num = 0
    # 1) Coba dari master hakim
    if (
        isinstance(hakim_df, pd.DataFrame)
        and not hakim_df.empty
        and hakim
        and "nama" in hakim_df.columns
        and ("hari_sidang" in hakim_df.columns or "hari" in hakim_df.columns)
    ):
        try:
            if "hari_sidang" in hakim_df.columns:
                hari_text = hakim_df.set_index("nama").loc[hakim, "hari_sidang"]
            else:
                hari_text = hakim_df.set_index("nama").loc[hakim, "hari"]
            hari_sidang_num = _weekday_num_from_map(str(hari_text))
        except Exception:
            pass
    # 2) Fallback: pakai 'hari' dari SK
    if hari_sidang_num == 0 and isinstance(sk_row, pd.Series):
        hari_text2 = str(sk_row.get("hari","")).strip()
        if hari_text2:
            hari_sidang_num = _weekday_num_from_map(hari_text2)

    libur_set = set()
    if isinstance(libur_df, pd.DataFrame) and "tanggal" in libur_df.columns and not libur_df.empty:
        try:
            libur_set = set(pd.to_datetime(libur_df["tanggal"], errors="coerce").dt.date.astype(str).tolist())
        except Exception:
            libur_set = set(str(x) for x in libur_df["tanggal"].astype(str).tolist())

    tgl_sidang_auto = compute_tgl_sidang(
        base.date() if isinstance(base, datetime) else base,
        jenis, hari_sidang_num, libur_set, klasifikasi=klas_final
    )

    # Override tanggal sidang
    with st.expander("🗓️ Override Tanggal Sidang (opsional)", expanded=False):
        use_override = st.checkbox(
            "Gunakan tanggal sidang manual",
            value=False,
            key=f"use_override_{fs}",
            help="Jika dicentang, tanggal sidang akan memakai input di bawah."
        )
        override_raw = st.date_input(
            "Tanggal Sidang (manual)",
            value=tgl_sidang_auto,
            key=f"override_raw_{fs}"
        )
        mode = st.radio(
            "Mode tanggal manual",
            ["Bebas (pakai apa adanya)", "Sesuaikan ke hari sidang ketua + skip libur"],
            index=1 if hari_sidang_num else 0,
            key=f"mode_{fs}",
            help="Mode kedua akan menyesuaikan ke hari sidang ketua berikutnya dan melewati libur."
        )
        if mode.startswith("Sesuaikan"):
            tgl_sidang_manual = _next_judge_day_strict(override_raw, hari_sidang_num, libur_set)
            if str(tgl_sidang_manual) != str(override_raw):
                st.caption(f"Disesuaikan ke {format_tanggal_id(pd.to_datetime(tgl_sidang_manual))}")
        else:
            tgl_sidang_manual = override_raw

        if mode.startswith("Bebas") and str(tgl_sidang_manual) in libur_set:
            st.warning("Tanggal manual jatuh pada hari libur. (Mode bebas tidak mengubah tanggal.)", icon="⚠️")

    # pilih tanggal efektif untuk PREVIEW
    tgl_sidang_effective = tgl_sidang_manual if use_override else tgl_sidang_auto

    # Hasil Otomatis (preview)
    nomor_fmt, tipe_final = compute_nomor_tipe(nomor, klas_final, tipe_pdt)
    st.subheader("Hasil Otomatis")
    st.write(f"**Perkara**: **{nomor_fmt}**")
    resL, resR = st.columns(2)
    with resL:
        st.write("**Hakim (Ketua):**", hakim or "-")
        st.write("**Anggota 1**:", anggota1 or "-")
        st.write("**Anggota 2**:", anggota2 or "-")
    with resR:
        st.write("**PP**:", (pp_preview or "-"))
        st.write("**JS**:", (js_preview or "-"))
        st.markdown("**Tanggal Sidang**")
        label_override = " <span style='font-size:0.9rem;color:#888'>(override)</span>" if use_override else ""
        st.markdown(
            f"<div style='font-size:1.4rem;font-weight:600'>{format_tanggal_id(pd.to_datetime(tgl_sidang_effective))}</div>{label_override}",
            unsafe_allow_html=True
        )

    # ===== SIMPAN =====
    simpan = st.form_submit_button("💾 Simpan ke Rekap (CSV)", width="stretch", disabled=not bool(hakim))
    if simpan:
        # Rotasi sekali
        pair_pp, pair_js = _consume_pair_on_save_once(hakim, sk_row, jenis, rekap_df)
        pp_val = pp_manual.strip() if str(pp_manual).strip() else pair_pp
        js_val = js_manual.strip() if str(js_manual).strip() else pair_js
        if _is_header_like(pp_val): pp_val = ""
        if _is_header_like(js_val): js_val = ""

        new_row = {
            "nomor_perkara": nomor_fmt,
            "tgl_register": pd.to_datetime(base),
            "klasifikasi": klas_final,
            "jenis_perkara": jenis,
            "metode": metode_input,
            "hakim": hakim,
            "anggota1": anggota1,
            "anggota2": anggota2,
            "pp": pp_val,
            "js": js_val,
            "tgl_sidang": pd.to_datetime(tgl_sidang_effective),
            "tgl_sidang_override": int(bool(use_override)),
        }

        current_csv = _read_csv(rekap_csv_path)
        rekap_new = pd.concat([current_csv, pd.DataFrame([new_row])], ignore_index=True)
        _export_rekap_csv(rekap_new)

        try:
            effective_day = pd.to_datetime(base).date()
        except Exception:
            effective_day = date.today()
        st.session_state["_force_rekap_date"] = effective_day
        st.session_state["rekap_filter_date"] = effective_day
        st.session_state["form_seed"] = fs + 1

        st.toast(f"Tersimpan ke CSV! (PP/JS: {pp_val or '-'} / {js_val or '-'})", icon="✅")
        st.rerun()

# ================== REKAP (CSV) ============================
st.markdown("---")
st.subheader("Rekap (berdasarkan Tanggal Register)")

def _fmt_id(x):
    dt = pd.to_datetime(x, errors="coerce")
    return format_tanggal_id(dt) if pd.notna(dt) else "-"

tmp = _read_csv(rekap_csv_path)
if isinstance(tmp, pd.DataFrame) and not tmp.empty:
    need = ["nomor_perkara","jenis_perkara","hakim","anggota1","anggota2","pp","js","tgl_register","tgl_sidang","tgl_sidang_override"]
    for c in need:
        if c not in tmp.columns:
            tmp[c] = pd.NaT if c in ("tgl_register","tgl_sidang") else (0 if c=="tgl_sidang_override" else "")
    tmp["tgl_register"] = pd.to_datetime(tmp["tgl_register"], errors="coerce")
    tmp["tgl_sidang"]   = pd.to_datetime(tmp["tgl_sidang"], errors="coerce")

    default_day = (pd.to_datetime(tmp["tgl_register"].max()).date()
                   if pd.notna(tmp["tgl_register"].max()) else date.today())

    if "_force_rekap_date" in st.session_state:
        init_day = st.session_state.pop("_force_rekap_date")
        st.session_state["rekap_filter_date"] = init_day
    else:
        init_day = st.session_state.get("rekap_filter_date", default_day)
        st.session_state.setdefault("rekap_filter_date", init_day)

    filter_date = st.date_input("Tanggal", value=init_day, key="rekap_filter_date")
    df_filtered = tmp.loc[tmp["tgl_register"].dt.date == filter_date].copy()

    COLS = [1.3, 1.2, 0.6, 2.2, 2.2, 2.2, 1.8, 1.8, 1.8]
    h = st.columns(COLS)
    h[0].markdown("**Nomor Perkara**")
    h[1].markdown("**Register (ID)**")
    h[2].markdown("**Jenis**")
    h[3].markdown("**Hakim (Ketua)**")
    h[4].markdown("**Anggota 1**")
    h[5].markdown("**Anggota 2**")
    h[6].markdown("**PP**")
    h[7].markdown("**JS**")
    h[8].markdown("**Tgl Sidang (ID)**")
    st.markdown("<hr/>", unsafe_allow_html=True)

    if df_filtered.empty:
        st.info("Tidak ada perkara pada tanggal tersebut.")
    else:
        for _, r in df_filtered.iterrows():
            c = st.columns(COLS)
            c[0].write(str(r.get("nomor_perkara", "")) or "-")
            c[1].write(_fmt_id(r.get("tgl_register")))
            c[2].write(str(r.get("jenis_perkara", "")) or "-")
            c[3].write(str(r.get("hakim", "")) or "-")
            c[4].write(str(r.get("anggota1", "")) or "-")
            c[5].write(str(r.get("anggota2", "")) or "-")
            c[6].write(str(r.get("pp", "")) or "-")
            c[7].write(str(r.get("js", "")) or "-")

            ovr_raw = str(r.get("tgl_sidang_override", "0")).strip().lower()
            is_ovr = ovr_raw in {"1","true","y","ya","t"}
            badge = " • override" if is_ovr else ""
            c[8].write((_fmt_id(r.get("tgl_sidang")) or "-") + badge)
else:
    st.info("Belum ada data rekap (data/rekap.csv kosong).")
