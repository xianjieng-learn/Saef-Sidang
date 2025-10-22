# app_core/utils_data.py
from __future__ import annotations
import re, uuid
from datetime import date, timedelta, datetime
from pathlib import Path
from typing import Iterable
import pandas as pd
import streamlit as st

from .helpers import HARI_MAP, format_tanggal_id  # pakai punyamu

# ===== [1] DRY: header-like & aktif parsing =====
HEADER_TOKENS = {
    "nama","ketua","anggota","anggota1","anggota 1","anggota2","anggota 2",
    "pp","pp1","pp2","js","js1","js2","hari","majelis","status","aktif",
    "keterangan","catatan","tanggal","tgl","date","hakim","pp/pp1","js/js1"
}

def is_header_like(val: str) -> bool:
    s = str(val or "").strip().lower()
    return s in HEADER_TOKENS or s == ""

def is_active_value(v) -> bool:
    s = re.sub(r"[^A-Z0-9]+", "", str(v).strip().upper())
    if s in {"1","YA","Y","TRUE","T","AKTIF","ON"}: return True
    if s in {"0","TIDAK","TDK","NO","N","FALSE","F","NONAKTIF","OFF","NONE","NAN",""}: return False
    try: return float(s) != 0.0
    except: return False

# ===== [1] DRY: name cleaning =====
_PREFIX_RX = re.compile(r"^\s*((drs?|dra|prof|ir|apt|h|hj|kh|ust|ustadz|ustadzah)\.?\s+)+", flags=re.IGNORECASE)
_SUFFIX_PATTERNS = [
    r"s\.?\s*h\.?", r"s\.?\s*h\.?\s*i\.?", r"m\.?\s*h\.?", r"m\.?\s*h\.?\s*i\.?",
    r"s\.?\s*ag", r"m\.?\s*ag", r"m\.?\s*kn", r"m\.?\s*hum", r"s\.?\s*kom",
    r"s\.?\s*psi", r"s\.?\s*e", r"m\.?\s*m", r"m\.?\s*a", r"llb", r"llm",
    r"phd", r"se", r"ssi", r"sh", r"mh"
]
_SUFFIX_RX = re.compile(r"(,?\s+(" + r"|".join(_SUFFIX_PATTERNS) + r"))+$", flags=re.IGNORECASE)

def clean_text(s: str) -> str:
    x = str(s or "").replace("\u00A0", " ").strip()
    x = x.replace(" ,", ",").replace(" .", ".")
    x = re.sub(r"\s+", " ", x).strip()
    return x

def name_key(s: str) -> str:
    if not isinstance(s, str): return ""
    x = clean_text(s).replace(",", " ")
    x = _SUFFIX_RX.sub("", x)
    x = _PREFIX_RX.sub("", x)
    x = re.sub(r"[^\w\s]", " ", x)
    x = re.sub(r"\s+", " ", x).strip().lower()
    toks = [t for t in x.split() if t not in {"s","h","m","e"}]
    return " ".join(toks)

def toktok(s: str) -> set[str]:
    return set([t for t in name_key(s).split() if t])

def majelis_rank(s: str) -> int:
    m = re.search(r"(\d+)", str(s))
    return int(m.group(1)) if m else 10**9

# ===== [1,7] DRY: options dari master & libur_set =====
def libur_set_from_df(libur_df: pd.DataFrame) -> set[str]:
    if not isinstance(libur_df, pd.DataFrame) or libur_df.empty or "tanggal" not in libur_df.columns:
        return set()
    try:
        return set(pd.to_datetime(libur_df["tanggal"], errors="coerce").dt.date.astype(str).tolist())
    except:
        return set(str(x) for x in libur_df["tanggal"].astype(str).tolist())

def options_from_master(df: pd.DataFrame, prefer_active=True) -> list[str]:
    if not isinstance(df, pd.DataFrame) or df.empty: return []
    name_col = next((c for c in ["nama", "pp", "js", "nama_lengkap", "Nama", "NAMA"] if c in df.columns), None)
    if not name_col: return []
    x = df[[name_col]].copy()
    x[name_col] = x[name_col].astype(str).map(lambda s: s.strip())
    x = x[~x[name_col].map(is_header_like)]
    if x.empty: return []
    if prefer_active and "aktif" in df.columns:
        df2 = df.copy(); df2["_aktif__"] = df2["aktif"].apply(is_active_value)
        x = x.join(df2["_aktif__"])
        x = x.sort_values(by=["_aktif__", name_col], ascending=[False, True], kind="stable")
        names = x[name_col].tolist()
    else:
        names = sorted(x[name_col].unique().tolist())
    out, seen = [], set()
    for n in names:
        if n not in seen:
            seen.add(n); out.append(n)
    return out

def weekday_num_from(hari_text: str) -> int:
    try: return int(HARI_MAP.get(str(hari_text), 0))
    except: return 0

# ===== [5] Rules tanggal sidang (parametris) =====
DATE_RULES = {
    "BIASA": {"start": 8, "end_cap": 14},       # 8–14 hari
    "ISTBAT": {"start": 21},
    "GHOIB": {"start": 31, "special_klas": {"CT":124, "CG":124}},
    "ROGATORI": {"start": 124},
    "MAFQUD": {"start": 246},
}

def next_judge_day_strict(start_date: date, hari_sidang_num: int, libur_set: set[str]) -> date:
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
    rule = DATE_RULES.get(J)
    if not rule: return base
    start = rule.get("start", 0)
    if J == "GHOIB" and "special_klas" in rule:
        start = rule["special_klas"].get(K, start)
    start_d = base + timedelta(days=start)
    if "end_cap" in rule:
        end_cap = base + timedelta(days=rule["end_cap"])
        d = next_judge_day_strict(start_d, hari_sidang_num, libur_set)
        return d if d <= end_cap else next_judge_day_strict(end_cap, hari_sidang_num, libur_set)
    return next_judge_day_strict(start_d, hari_sidang_num, libur_set)

# ===== [7] Indexer untuk hakim_df (hemat waktu) =====
_hakim_index_cache = None
_hakim_df_ref = None

def set_hakim_df(df: pd.DataFrame):
    """Panggil sekali di awal app setelah load hakim_df."""
    global _hakim_df_ref, _hakim_index_cache
    _hakim_df_ref = df.copy() if isinstance(df, pd.DataFrame) else None
    _hakim_index_cache = None

def hakim_index():
    global _hakim_index_cache
    if _hakim_index_cache is None and _hakim_df_ref is not None and not _hakim_df_ref.empty and "nama" in _hakim_df_ref.columns:
        _hakim_index_cache = _hakim_df_ref.set_index("nama")
    return _hakim_index_cache

def hari_sidang_num_for(nama_hakim: str) -> int:
    try:
        idx = hakim_index()
        if idx is None: return 0
        row = idx.loc[nama_hakim]
        hari_text = str(row["hari_sidang"] if "hari_sidang" in _hakim_df_ref.columns else row.get("hari",""))
        return weekday_num_from(hari_text)
    except: 
        return 0

# ===== [9] Key namespacing untuk Streamlit =====
def K(ns: str, name: str) -> str:
    return f"{ns}::{name}"
