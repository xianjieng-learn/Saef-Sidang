import re
import pandas as pd
from datetime import date, timedelta
from typing import Dict, Tuple, Optional, List
from db_io import load_table
from db import get_conn

# ================= Normalisasi Nama =================
GELAR_PAT = re.compile(r'\b(Drs\.?|Dr\.?|H\.|Hj\.|S\.H\.?|S\.HI\.?|M\.H\.?|M\.H\.I\.?|S\.E\.?|S\.Kom\.?|Ir\.?|Sp\.|SH|MH|SE|MM|SAg|MSi|M\.Si\.?)\b', flags=re.IGNORECASE)

def normalize_name(s: str) -> str:
    if not isinstance(s, str):
        return ""
    s2 = GELAR_PAT.sub(" ", s)
    s2 = re.sub(r"[.,]", " ", s2)
    s2 = re.sub(r"\s+", " ", s2).strip()
    return s2.lower()

# ================= Kalender & Format =================
NAMA_BULAN = ["Januari","Februari","Maret","April","Mei","Juni","Juli","Agustus","September","Oktober","November","Desember"]
HARI_MAP = {
    "Senin":0, "Selasa":1, "Rabu":2, "Kamis":3, "Jumat":4, "Sabtu":5, "Minggu":6,
    "senin":0, "selasa":1, "rabu":2, "kamis":3, "jumat":4, "sabtu":5, "minggu":6
}

def format_tanggal_id(d: date) -> str:
    # "Rabu, 3 September 2025"
    nama_hari = ["Senin","Selasa","Rabu","Kamis","Jumat","Sabtu","Minggu"][d.weekday()]
    return f"{nama_hari}, {d.day} {NAMA_BULAN[d.month-1]} {d.year}"

def load_libur_set() -> set:
    lib = load_table("libur")
    if lib.empty:
        return set()
    return set(str(x) for x in lib["tanggal"].astype(str).tolist())

def next_judge_day(start: date, target_weekday: int, holidays: set) -> date:
    # maju hingga ketemu weekday yang diminta, bukan libur/weekend
    d = start
    def ok(x: date) -> bool:
        if x.weekday() >= 5: return False
        if x.strftime("%Y-%m-%d") in holidays: return False
        return True
    while d.weekday() != target_weekday or not ok(d):
        d += timedelta(days=1)
    return d

def exclude_weekends(df: pd.DataFrame, date_col: str="tgl_register") -> pd.DataFrame:
    if df.empty or date_col not in df.columns: return df
    s = pd.to_datetime(df[date_col], errors="coerce")
    return df[~s.dt.weekday.isin([5,6])].copy()

def exclude_libur(df: pd.DataFrame, date_col: str="tgl_register") -> pd.DataFrame:
    if df.empty or date_col not in df.columns: return df
    lib = load_libur_set()
    if not lib: return df
    s = pd.to_datetime(df[date_col], errors="coerce").dt.date.astype("string")
    return df[~s.isin(lib)].copy()

# ================= SK Majelis & Rotasi =================
def build_sk_lookup() -> Dict[str, Dict[str, str]]:
    sk = load_table("sk_majelis")
    if sk.empty:
        return {}
    sk = sk.fillna("")
    if "aktif" in sk.columns:
        sk = sk[sk["aktif"]==1]
    out = {}
    for _, r in sk.iterrows():
        ket = normalize_name(r.get("ketua",""))
        out[ket] = {
            "hari": r.get("hari",""),
            "majelis": r.get("majelis",""),
            "anggota1": r.get("anggota1",""),
            "anggota2": r.get("anggota2",""),
            "pp1": r.get("pp1",""), "pp2": r.get("pp2",""),
            "js1": r.get("js1",""), "js2": r.get("js2","")
        }
    return out

def last_value_for(df: pd.DataFrame, ketua: str, col: str) -> Optional[str]:
    if df.empty or col not in df.columns: return None
    sub = df[df.get("hakim","")==ketua]
    if sub.empty: return None
    return str(sub.iloc[-1].get(col) or "")

def rotate_two(seed1: str, seed2: str, last_used: Optional[str]) -> str:
    if not seed1 and not seed2:
        return ""
    if not last_used:  # pertama kali
        return seed1 or seed2
    if last_used == seed1 and seed2:
        return seed2
    return seed1 or seed2

def rotate_pp(ketua: str, rekap_df: pd.DataFrame, pp_df: pd.DataFrame, sk_df: Optional[pd.DataFrame]=None, seed_pp: str="pp1") -> str:
    sk = build_sk_lookup() if sk_df is None else {normalize_name(r.get("ketua","")):{k:r.get(k,"") for k in ["pp1","pp2"]} for _,r in sk_df.iterrows()}
    d = sk.get(normalize_name(ketua), {})
    p1, p2 = d.get("pp1",""), d.get("pp2","")
    last = last_value_for(rekap_df, ketua, "pp")
    return rotate_two(p1, p2, last)

def rotate_js_cross(ketua: str, rekap_df: pd.DataFrame, js_df: pd.DataFrame, sk_df: Optional[pd.DataFrame]=None, seed_js: str="js1") -> str:
    sk = build_sk_lookup() if sk_df is None else {normalize_name(r.get("ketua","")):{k:r.get(k,"") for k in ["js1","js2"]} for _,r in sk_df.iterrows()}
    d = sk.get(normalize_name(ketua), {})
    j1, j2 = d.get("js1",""), d.get("js2","")
    last = last_value_for(rekap_df, ketua, "js")
    return rotate_two(j1, j2, last)

def choose_js_ghoib(js_ghoib_df: pd.DataFrame) -> str:
    if js_ghoib_df is None or js_ghoib_df.empty or "nama" not in js_ghoib_df.columns:
        return ""
    tmp = js_ghoib_df.copy()
    tmp["total_ghoib"] = tmp.get("total_ghoib",0).fillna(0).astype(int)
    tmp = tmp.sort_values(["total_ghoib","nama"])
    return str(tmp.iloc[0]["nama"])

def choose_anggota_auto(ketua: str, rekap_df: pd.DataFrame, hakim_df: pd.DataFrame, n: int=2) -> Tuple[str,str]:
    # prioritas: dari SK; fallback: ambil 2 hakim aktif lain secara alfabetis
    sk = build_sk_lookup()
    d = sk.get(normalize_name(ketua), {})
    a1, a2 = d.get("anggota1",""), d.get("anggota2","")
    if a1 or a2:
        return a1, a2
    if hakim_df is None or hakim_df.empty: return "",""
    names = [x for x in hakim_df.get("nama",[]).astype(str).tolist() if x and x != ketua]
    names.sort()
    names = names[:2] + ["",""]
    return names[0], names[1]

# ================= Auto pilih Ketua =================
def choose_hakim_auto(hakim_df: pd.DataFrame, rekap_df: pd.DataFrame, tanggal: date) -> str:
    if hakim_df is None or hakim_df.empty:
        return ""
    hk = hakim_df.copy().fillna({"aktif":1, "max_per_hari":9999})
    hk = hk[hk["aktif"]==1]
    if hk.empty:
        return ""
    # hitung beban per tanggal (mengacu tgl_register)
    count_map = {}
    if rekap_df is not None and not rekap_df.empty and "tgl_register" in rekap_df.columns:
        tmp = rekap_df.copy()
        tmp["tgl_register"] = pd.to_datetime(tmp["tgl_register"], errors="coerce").dt.date
        tmp = tmp[tmp["tgl_register"]==tanggal]
        for _, r in tmp.iterrows():
            nm = str(r.get("hakim",""))
            if nm:
                count_map[nm] = count_map.get(nm,0)+1
    # pilih yang belum capai kuota dan beban terendah
    candidates = []
    for _, r in hk.iterrows():
        nm = str(r["nama"])
        cnt = count_map.get(nm,0)
        quota = int(r.get("max_per_hari",9999) or 9999)
        if cnt < quota:
            candidates.append((cnt, nm))
    if not candidates:
        # kalau semua penuh, pakai yang beban terendah walau melewati kuota
        candidates = [(count_map.get(str(r["nama"]),0), str(r["nama"])) for _, r in hk.iterrows()]
    candidates.sort(key=lambda x: (x[0], x[1].lower()))
    return candidates[0][1] if candidates else ""

# ================= Nomor / Tipe =================
def compute_nomor_tipe(nomor: str, klasifikasi: str, tipe_pdt: str) -> tuple[str,str]:
    # placeholder sederhana: nomor apa adanya, tipe final = tipe_pdt jika bukan "Otomatis"
    tipe_final = tipe_pdt if tipe_pdt != "Otomatis" else "Pdt"
    nomor_fmt = (nomor or "").strip()
    return nomor_fmt, tipe_final

# ================= Display Helper =================
def df_display_clean(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    for col in ["tgl_register","tgl_sidang"]:
        if col in d.columns:
            d[col] = pd.to_datetime(d[col], errors="coerce").dt.strftime("%Y/%m/%d")
    return d
