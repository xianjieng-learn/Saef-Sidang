# app_core/helpers_rotate_from_sk.py
"""
Rotasi PP & JS *hanya* dari paket SK Majelis untuk ketua bersangkutan.
- Tidak memeriksa aktif/tidaknya di master PP/JS.
- Mencocokkan nama ketua yang bertitel (buang gelar, titik/koma) agar robust.
- Memilih kandidat dengan beban total paling sedikit (berdasarkan tabel 'rekap').

Cara pakai (di halaman Input & Hasil):
    from app_core.helpers import rotate_pp as rotate_pp_old, rotate_js_cross as rotate_js_old
    try:
        # override dengan versi SK-only
        from app_core.helpers_rotate_from_sk import rotate_pp, rotate_js_cross
    except Exception:
        rotate_pp = rotate_pp_old
        rotate_js_cross = rotate_js_old
"""
from __future__ import annotations
import re
import pandas as pd

# --- normalisasi nama: buang gelar, titik/koma, spasi ganda -> tokens lower() ---
_PREFIX_RX = re.compile(r"^\s*((drs?|prof|ir|apt|h|hj|kh|ust|ustadz(ah)?)\.?\s+)+", re.I)
_SUFFIX_PATTERNS = [
    r"s\.?\s*h\.?", r"m\.?\s*h\.?", r"m\.?\s*h\.?\s*i\.?",
    r"s\.?\s*ag", r"m\.?\s*ag", r"m\.?\s*kn", r"m\.?\s*hum",
    r"s\.?\s*kom", r"s\.?\s*psi", r"s\.?\s*e", r"m\.?\s*m", r"m\.?\s*a",
    r"llb", r"llm", r"phd"
]
_SUFFIX_RX = re.compile(r"(,?\s+(" + r"|".join(_SUFFIX_PATTERNS) + r"))+$", re.I)

def _name_tokens(name: str) -> list[str]:
    if not isinstance(name, str): return []
    s = name.replace(",", " ").replace(".", " ")
    s = _SUFFIX_RX.sub("", s)
    s = _PREFIX_RX.sub("", s)
    s = re.sub(r"\s+", " ", s).strip().lower()
    return [t for t in s.split() if t]

def _norm_flat(s: str) -> str:
    # normalisasi sederhana untuk lookup di rekap
    return re.sub(r"\s+", " ", re.sub(r"[^\w]+", " ", str(s or "").lower())).strip()

def _flag_active(v) -> bool:
    s=str(v).strip().upper()
    if s in {"1","YA","Y","TRUE","T","AKTIF","ON"}: return True
    if s in {"0","TIDAK","TDK","NO","N","FALSE","F","NONAKTIF","OFF","NONE","NAN",""}: return False
    try: return float(s) != 0.0
    except Exception: return False

def _rows_for_ketua_from_sk(sk_df: pd.DataFrame, ketua: str) -> pd.DataFrame:
    """Cari baris SK (yang aktif) untuk ketua; toleran gelar/variasi nama."""
    if sk_df is None or sk_df.empty: 
        return pd.DataFrame(columns=sk_df.columns if isinstance(sk_df, pd.DataFrame) else [])
    sdf = sk_df.copy()
    # hormati flag aktif di SK (kalau mau abaikan, komentari dua baris berikut):
    if "aktif" in sdf.columns:
        sdf = sdf[sdf["aktif"].apply(_flag_active)]
    tgt = set(_name_tokens(ketua))
    if not tgt:
        return sdf.iloc[0:0]

    mask = []
    for _, r in sdf.iterrows():
        kt = set(_name_tokens(r.get("ketua","")))
        # cocok jika subset dua arah atau minimal semua token ketua input ada di SK
        ok = bool(kt) and (tgt.issubset(kt) or kt.issubset(tgt))
        mask.append(ok)
    out = sdf[pd.Series(mask, index=sdf.index)]
    return out

def _collect_candidates_from_sk(sk_df: pd.DataFrame, ketua: str) -> tuple[list[str], list[str]]:
    rows = _rows_for_ketua_from_sk(sk_df, ketua)
    pp_cand, js_cand = [], []
    for _, row in rows.iterrows():
        for col in ("pp1","pp2","pp"):   # dukung skema lama
            v = str(row.get(col,"")).strip()
            if v: pp_cand.append(v)
        for col in ("js1","js2","js"):
            v = str(row.get(col,"")).strip()
            if v: js_cand.append(v)
    # unique (pertahankan urutan)
    def uniq(seq):
        seen=set(); out=[]
        for x in seq:
            k=x.strip()
            if k and k not in seen:
                seen.add(k); out.append(x)
        return out
    return uniq(pp_cand), uniq(js_cand)

def _counts_from_rekap(rekap_df: pd.DataFrame, col: str) -> dict:
    """Hitung total beban (semua metode) per nama (normalized flat)."""
    if rekap_df is None or rekap_df.empty or col not in rekap_df.columns:
        return {}
    r = rekap_df.copy()
    r["nm"] = r[col].astype(str).map(_norm_flat)
    return r.groupby("nm").size().to_dict()

def _pick_min_load(candidates: list[str], counts: dict) -> str | None:
    if not candidates: return None
    # pilih berdasar beban total terkecil; tie-break urutan SK (stabil)
    pairs = [(c, counts.get(_norm_flat(c), 0)) for c in candidates]
    pairs.sort(key=lambda x: (x[1],))  # urutan asli candidates jadi tie-break
    return pairs[0][0]

# ==== Rotasi PP/JS: hanya dari SK utk ketua ====
def rotate_pp(hakim_ketua: str,
              rekap_df: pd.DataFrame,
              pp_df: pd.DataFrame | None = None,
              sk_df: pd.DataFrame | None = None) -> str:
    cand_pp, _ = _collect_candidates_from_sk(sk_df, hakim_ketua)
    if not cand_pp: 
        return ""   # tidak fallback ke master; harus dari SK
    cnt = _counts_from_rekap(rekap_df, "pp")
    return _pick_min_load(cand_pp, cnt) or ""

def rotate_js_cross(hakim_ketua: str,
                    rekap_df: pd.DataFrame,
                    js_df: pd.DataFrame | None = None,
                    sk_df: pd.DataFrame | None = None) -> str:
    _, cand_js = _collect_candidates_from_sk(sk_df, hakim_ketua)
    if not cand_js:
        return ""
    cnt = _counts_from_rekap(rekap_df, "js")
    return _pick_min_load(cand_js, cnt) or ""
