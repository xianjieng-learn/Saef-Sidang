# app_core/helpers_js_ghoib.py
from __future__ import annotations
"""
Pilih JS Ghoib otomatis dari tabel SQLite `js_ghoib` (halaman 3d),
dengan kriteria beban GHOIB paling kecil berdasarkan `rekap`.
- Default hanya ambil yang AKTIF (kalau kolom `aktif` ada). Bisa dimatikan via argumen.
"""
import re
import pandas as pd
from db import get_conn

def _norm_flat(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w]+", " ", str(s or "").lower())).strip()

def _load_js_ghoib(use_aktif: bool = True) -> pd.DataFrame:
    con = get_conn()
    try:
        df = pd.read_sql_query("SELECT * FROM js_ghoib", con)
    except Exception:
        df = pd.DataFrame()
    finally:
        con.close()
    if use_aktif and not df.empty and "aktif" in df.columns:
        def _flag(v):
            s=str(v).strip().upper()
            if s in {"1","YA","Y","TRUE","T","AKTIF","ON"}: return True
            if s in {"0","TIDAK","TDK","NO","N","FALSE","F","NONAKTIF","OFF","NONE","NAN",""}: return False
            try: return float(s) != 0.0
            except Exception: return False
        df = df[df["aktif"].apply(_flag)]
    return df

def choose_js_ghoib_db(rekap_df: pd.DataFrame, use_aktif: bool = True) -> str:
    """
    Return nama JS Ghoib dengan beban GHOIB terkecil menurut `rekap`.
    Jika tabel kosong atau tidak ada kandidat, return "".
    """
    master = _load_js_ghoib(use_aktif=use_aktif)
    if master.empty or "nama" not in master.columns:
        return ""
    # kandidat (urutan stabil sesuai DB)
    candidates = [str(x).strip() for x in master["nama"].dropna().tolist() if str(x).strip()]
    if not candidates:
        return ""
    # hitung beban dari rekap untuk perkara GHOIB saja
    counts = {}
    if isinstance(rekap_df, pd.DataFrame) and not rekap_df.empty and all(c in rekap_df.columns for c in ["js","jenis_perkara"]):
        r = rekap_df.copy()
        r["jenis_u"] = r["jenis_perkara"].astype(str).str.upper().str.strip()
        r = r[r["jenis_u"] == "GHOIB"]
        if not r.empty:
            r["js_norm"] = r["js"].astype(str).map(_norm_flat)
            counts = r.groupby("js_norm").size().to_dict()
    # pilih kandidat dengan beban paling kecil (tie -> alfabet)
    pairs = [(c, counts.get(_norm_flat(c), 0)) for c in candidates]
    pairs.sort(key=lambda x: (x[1], x[0].lower()))
    return pairs[0][0] if pairs else ""

# helper debug opsional
def debug_js_ghoib(rekap_df: pd.DataFrame, use_aktif: bool = True) -> dict:
    master = _load_js_ghoib(use_aktif=use_aktif)
    cands = [str(x).strip() for x in master.get("nama", pd.Series([])).dropna().tolist() if str(x).strip()]
    counts = {}
    if isinstance(rekap_df, pd.DataFrame) and not rekap_df.empty and all(c in rekap_df.columns for c in ["js","jenis_perkara"]):
        r = rekap_df.copy()
        r["jenis_u"] = r["jenis_perkara"].astype(str).str.upper().str.strip()
        r = r[r["jenis_u"] == "GHOIB"]
        if not r.empty:
            r["js_norm"] = r["js"].astype(str).map(_norm_flat)
            counts = r.groupby("js_norm").size().to_dict()
    pick = choose_js_ghoib_db(rekap_df, use_aktif=use_aktif)
    return {"candidates": cands, "counts": counts, "pick": pick, "table": master}
