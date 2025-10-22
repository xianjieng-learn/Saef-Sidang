# app_core/helpers_rotate_from_db_noaktif.py
from __future__ import annotations
"""
Rotasi PP/JS langsung dari DB (sk_majelis) — *tanpa* filter aktif secara default.
Tambahan: fungsi debug `debug_sk_for_ketua(ketua)` untuk melihat baris match & kandidat.
"""
import re, time, pandas as pd
from db import get_conn

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
    s = _SUFFIX_RX.sub("", s); s = re.sub(r"\s+", " ", s).strip().lower()
    return [t for t in s.split() if t]
def _norm_flat(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w]+", " ", str(s or "").lower())).strip()

def _counts_from_rekap(rekap_df: pd.DataFrame, col: str) -> dict:
    if rekap_df is None or rekap_df.empty or col not in rekap_df.columns:
        return {}
    r = rekap_df.copy(); r["nm"] = r[col].astype(str).map(_norm_flat)
    return r.groupby("nm").size().to_dict()

def _pick_min_load(candidates: list[str], counts: dict) -> str | None:
    if not candidates: return None
    pairs = [(c, counts.get(_norm_flat(c), 0)) for c in candidates]
    pairs.sort(key=lambda x: (x[1],))
    return pairs[0][0]

_SK_CACHE = {"df": None, "ts": 0.0}
_SK_TTL_SEC = 10.0
_SK_USE_AKTIF = False  # <--- default: TIDAK filter aktif
def set_sk_use_aktif(flag: bool = False):
    global _SK_USE_AKTIF; _SK_USE_AKTIF = bool(flag); _SK_CACHE["ts"] = 0.0
def refresh_sk_cache(): _SK_CACHE["ts"] = 0.0

def _load_sk_from_db() -> pd.DataFrame:
    now = time.time()
    if _SK_CACHE["df"] is not None and (now - _SK_CACHE["ts"] < _SK_TTL_SEC):
        return _SK_CACHE["df"]
    con = get_conn()
    try:
        df = pd.read_sql_query("SELECT * FROM sk_majelis", con)
    except Exception:
        df = pd.DataFrame()
    finally:
        con.close()
    if _SK_USE_AKTIF and not df.empty and "aktif" in df.columns:
        def _flag(v):
            s=str(v).strip().upper()
            if s in {"1","YA","Y","TRUE","T","AKTIF","ON"}: return True
            if s in {"0","TIDAK","TDK","NO","N","FALSE","F","NONAKTIF","OFF","NONE","NAN",""}: return False
            try: return float(s) != 0.0
            except Exception: return False
        df = df[df["aktif"].apply(_flag)]
    _SK_CACHE["df"] = df.copy(); _SK_CACHE["ts"] = now
    return _SK_CACHE["df"]

def _collect_candidates_from_db(ketua: str) -> tuple[list[str], list[str], pd.DataFrame]:
    sdf = _load_sk_from_db()
    if sdf is None or sdf.empty: return [], [], pd.DataFrame()
    tgt = set(_name_tokens(ketua))
    if not tgt: return [], [], sdf.iloc[0:0]
    mask = []
    for _, r in sdf.iterrows():
        kt = set(_name_tokens(r.get("ketua","")))
        ok = bool(kt) and (tgt.issubset(kt) or kt.issubset(tgt))
        mask.append(ok)
    rows = sdf[pd.Series(mask, index=sdf.index)]
    pp_cand, js_cand = [], []
    for _, row in rows.iterrows():
        for c in ("pp1","pp2","pp"):
            v = str(row.get(c,"")).strip()
            if v: pp_cand.append(v)
        for c in ("js1","js2","js"):
            v = str(row.get(c,"")).strip()
            if v: js_cand.append(v)
    def uniq(seq):
        seen=set(); out=[]
        for x in seq:
            k=x.strip()
            if k and k not in seen:
                seen.add(k); out.append(x)
        return out
    return uniq(pp_cand), uniq(js_cand), rows.copy()

def rotate_pp(hakim_ketua: str, rekap_df: pd.DataFrame, *_args, **_kwargs) -> str:
    cand_pp, _, _ = _collect_candidates_from_db(hakim_ketua)
    if not cand_pp: return ""
    cnt = _counts_from_rekap(rekap_df, "pp")
    return _pick_min_load(cand_pp, cnt) or ""

def rotate_js_cross(hakim_ketua: str, rekap_df: pd.DataFrame, *_args, **_kwargs) -> str:
    _, cand_js, _ = _collect_candidates_from_db(hakim_ketua)
    if not cand_js: return ""
    cnt = _counts_from_rekap(rekap_df, "js")
    return _pick_min_load(cand_js, cnt) or ""

# --- Debugging helper ---
def debug_sk_for_ketua(ketua: str, rekap_df: pd.DataFrame | None = None) -> dict:
    """Return info: rows matched, candidates, counts, picks."""
    pp_c, js_c, rows = _collect_candidates_from_db(ketua)
    cnt_pp = _counts_from_rekap(rekap_df, "pp") if rekap_df is not None else {}
    cnt_js = _counts_from_rekap(rekap_df, "js") if rekap_df is not None else {}
    pick_pp = _pick_min_load(pp_c, cnt_pp) if pp_c else None
    pick_js = _pick_min_load(js_c, cnt_js) if js_c else None
    return {
        "matched_rows": rows,
        "pp_candidates": pp_c,
        "js_candidates": js_c,
        "pp_counts": cnt_pp,
        "js_counts": cnt_js,
        "pp_pick": pick_pp,
        "js_pick": pick_js,
    }
