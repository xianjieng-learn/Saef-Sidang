# app_core/mirror_all.py
from __future__ import annotations
import os
import pandas as pd
from typing import Optional

# Default CSV paths (you can change these if needed)
DEFAULTS = {
    "hakim":     "data/hakim_df.csv",
    "pp":        "data/pp_df.csv",
    "js":        "data/js_df.csv",
    "js_ghoib":  "data/js_ghoib_df.csv",
    "libur":     "data/libur_df.csv",
    "sk":        "data/sk_df.csv",
    "rekap":     "data/rekap_df.csv",
}

def _atomic_write_csv(df: pd.DataFrame, path: str, encoding: str = "utf-8-sig") -> None:
    """Write CSV atomically to avoid partial files (safe for Windows/POSIX)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    df.to_csv(tmp, index=False, encoding=encoding)
    os.replace(tmp, path)

def _norm_df(df: pd.DataFrame) -> pd.DataFrame:
    """Light normalization: strip 'nama' column if present; keep the rest AS-IS."""
    if not isinstance(df, pd.DataFrame):
        return pd.DataFrame()
    out = df.copy()
    if "nama" in out.columns:
        out["nama"] = out["nama"].astype(str).str.strip()
    return out

def mirror_csv(df: Optional[pd.DataFrame], path: str) -> str:
    """Write-through mirror a dataframe to CSV. Returns absolute path."""
    if not isinstance(df, pd.DataFrame):
        df = pd.DataFrame()
    out = _norm_df(df)
    _atomic_write_csv(out, path)
    return os.path.abspath(path)

# Specific helpers (so pages can call a clear name)
def mirror_hakim_csv(df: Optional[pd.DataFrame], path: str = DEFAULTS["hakim"]) -> str:
    return mirror_csv(df, path)

def mirror_pp_csv(df: Optional[pd.DataFrame], path: str = DEFAULTS["pp"]) -> str:
    return mirror_csv(df, path)

def mirror_js_csv(df: Optional[pd.DataFrame], path: str = DEFAULTS["js"]) -> str:
    return mirror_csv(df, path)

def mirror_js_ghoib_csv(df: Optional[pd.DataFrame], path: str = DEFAULTS["js_ghoib"]) -> str:
    return mirror_csv(df, path)

def mirror_libur_csv(df: Optional[pd.DataFrame], path: str = DEFAULTS["libur"]) -> str:
    return mirror_csv(df, path)

def mirror_sk_csv(df: Optional[pd.DataFrame], path: str = DEFAULTS["sk"]) -> str:
    return mirror_csv(df, path)

def mirror_rekap_csv(df: Optional[pd.DataFrame], path: str = DEFAULTS["rekap"]) -> str:
    return mirror_csv(df, path)

# Convenience: mirror multiple at once if you want
def mirror_all(**dfs) -> dict:
    """
    mirror_all(
       hakim=hakim_df, pp=pp_df, js=js_df, js_ghoib=js_ghoib_df,
       libur=libur_df, sk=sk_df, rekap=rekap_df
    )
    Returns mapping {name: path_written}
    """
    written = {}
    for name, df in dfs.items():
        if name not in DEFAULTS:
            continue
        path = DEFAULTS[name]
        written[name] = mirror_csv(df, path)
    return written
