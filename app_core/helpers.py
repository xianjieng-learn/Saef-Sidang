# app_core/helpers.py — versi bersih & tahan banting

from __future__ import annotations
import re
import pandas as pd
from datetime import datetime, timedelta, date
from io import BytesIO
from typing import Optional, Tuple, List

# =========================
# KONSTAN & UTIL DASAR
# =========================

NAMA_BULAN = ["Januari","Februari","Maret","April","Mei","Juni","Juli","Agustus","September","Oktober","November","Desember"]
HARI_MAP = {"Senin":1,"Selasa":2,"Rabu":3,"Kamis":4}

def _first_col(df: pd.DataFrame, cands: List[str]) -> Optional[str]:
    """Cari kolom pertama yang tersedia dari kandidat."""
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return None
    for c in cands:
        if c in df.columns:
            return c
    return None

def _norm_tokens(s: str) -> List[str]:
    """Normalisasi nama (buang gelar/simbol), untuk cocokkan alias santai."""
    if not isinstance(s, str):
        return []
    s = s.strip().replace(",", " ").replace(".", " ")
    s = re.sub(r"\s+", " ", s).strip().lower()
    return [t for t in s.split() if len(t) > 1 and t not in {"s","h","m","e"}]

def _count_perkara_for_ketua(rekap_df: pd.DataFrame, ketua_name: str) -> int:
    """Hitung banyak perkara milik ketua (0-based count untuk rotasi)."""
    if rekap_df is None or rekap_df.empty or not ketua_name:
        return 0
    kcol = _first_col(rekap_df, ["ketua","hakim","ketua_hakim","ketua majelis"])
    if not kcol:
        return 0
    return int((rekap_df[kcol].astype(str) == str(ketua_name)).sum())

# =========================
# FUNGSI LAMA (DIPERTAHANKAN)
# =========================

def format_tanggal_id(d: date, with_day=True):
    if not isinstance(d, (datetime, date)):
        return "-"
    hari = ["Senin","Selasa","Rabu","Kamis","Jumat","Sabtu","Minggu"][d.isoweekday()-1]
    bulan = NAMA_BULAN[d.month-1]
    tgl_str = f"{d.day} {bulan} {d.year}"
    return f"{hari}, {tgl_str}" if with_day else tgl_str

def compute_nomor_tipe(nomor, klasifikasi_text, pilihan):
    import re as _re
    def s(x):
        return "" if (x is None or (isinstance(x, float) and pd.isna(x))) else str(x)
    n = s(nomor).strip()
    k = s(klasifikasi_text).strip().upper()
    p = s(pilihan).strip()
    if p and p != "Otomatis":
        tipe = p
    else:
        if "/P" in n.upper():
            tipe = "Pdt.P"
        elif "VERZET" in k:
            tipe = "Pdt.Plw"
        else:
            tipe = "Pdt.G"
    n_base = n.replace("/P", "").replace("/p", "")
    n_base = _re.sub(r"\s+", " ", n_base).strip()
    return (n_base + " " + tipe).strip(), tipe

def next_judge_day(dasar: date, hari_sidang_num: int, libur_dates: set):
    d = dasar
    delta = (hari_sidang_num - d.isoweekday()) % 7
    calon = d + timedelta(days=delta)
    while True:
        if calon.isoweekday() >= 6:
            calon = calon + timedelta(days=(8 - calon.isoweekday()) % 7)
            delta2 = (hari_sidang_num - calon.isoweekday()) % 7
            calon = calon + timedelta(days=delta2)
            continue
        if calon.strftime("%Y-%m-%d") in libur_dates:
            calon = calon + timedelta(days=7)
            continue
        break
    return calon

def choose_hakim_auto(hakim_df, rekap_df, tanggal_reg: date):
    if hakim_df.empty: return ""
    aktif_view = hakim_df.copy()
    counts_total = rekap_df["hakim"].value_counts() if not rekap_df.empty and "hakim" in rekap_df.columns else pd.Series(dtype=int)
    counts_today = pd.Series(dtype=int)
    if (not rekap_df.empty) and ("tgl_register" in rekap_df.columns):
        mask = rekap_df["tgl_register"].notna() & (rekap_df["tgl_register"].dt.date == tanggal_reg)
        counts_today = rekap_df.loc[mask, "hakim"].value_counts()
    aktif_view["beban_now"] = aktif_view["nama"].map(counts_total).fillna(0).astype(int)
    aktif_view["hari_kuota"] = aktif_view["nama"].map(counts_today).fillna(0).astype(int)
    if "max_per_hari" in aktif_view.columns:
        def allowed(r):
            m = r.get("max_per_hari", 0)
            return (r["hari_kuota"] < m) if (m and m > 0) else True
        aktif_view = aktif_view[aktif_view.apply(allowed, axis=1)]
    if aktif_view.empty:
        aktif_view = hakim_df.copy()
        aktif_view["beban_now"] = aktif_view["nama"].map(counts_total).fillna(0).astype(int)
    row = aktif_view.sort_values(["beban_now","nama"]).iloc[0]
    return row["nama"]

def choose_js_ghoib(js_ghoib_df):
    if js_ghoib_df.empty: return ""
    pool = js_ghoib_df.copy()
    if "aktif" in pool.columns:
        pool = pool[pool["aktif"].astype(str).str.upper()=="YA"]
    if "exclude" in pool.columns:
        pool = pool[pool["exclude"].astype(str).str.upper()!="YES"]
    if "total_ghoib" in pool.columns:
        pool = pool.sort_values(["total_ghoib","js"])
    else:
        pool = pool.sort_values(["js"])
    return pool.iloc[0]["js"] if not pool.empty else ""

def choose_anggota_auto(hakim, rekap_df, hakim_df, n=2):
    if not hakim or hakim_df.empty:
        return ["", ""][:n]
    pasangan = []
    if "pasangan1" in hakim_df.columns or "pasangan2" in hakim_df.columns:
        try:
            row = hakim_df.set_index("nama").loc[hakim]
            if "pasangan1" in row and str(row["pasangan1"]).strip(): pasangan.append(str(row["pasangan1"]).strip())
            if "pasangan2" in row and str(row["pasangan2"]).strip(): pasangan.append(str(row["pasangan2"]).strip())
        except Exception:
            pasangan = []
    pasangan = [p for p in pasangan if p and p != hakim]
    if pasangan:
        pasangan = pasangan[:n] + [""]*max(0, n-len(pasangan))
        return pasangan[:n]
    try:
        hari_hakim = hakim_df.set_index("nama").loc[hakim, "hari_sidang"]
    except Exception:
        hari_hakim = None
    df_all = hakim_df.copy()
    counts = rekap_df["hakim"].value_counts() if not rekap_df.empty and "hakim" in rekap_df.columns else pd.Series(dtype=int)
    df_all["beban_now"] = df_all["nama"].map(counts).fillna(0).astype(int)
    pool = df_all[(df_all["nama"] != hakim)]
    if hari_hakim is not None:
        pool = pool[pool["hari_sidang"] == hari_hakim]
    pool = pool.sort_values(["beban_now","nama"])
    picked = pool["nama"].tolist()[:n]
    if len(picked) < n:
        others = df_all[(df_all["nama"] != hakim) & (~df_all["nama"].isin(picked))].sort_values(["beban_now","nama"])
        for nm in others["nama"].tolist():
            if len(picked) < n: picked.append(nm)
            else: break
    while len(picked) < n: picked.append("")
    return picked[:n]

def df_display_clean(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty: return df
    view = df.copy()
    if "nomor_perkara" in view.columns:
        mask_nonempty = view["nomor_perkara"].notna() & (view["nomor_perkara"].astype(str).str.strip() != "")
        view = view.loc[mask_nonempty]
    view = view.fillna("-")
    if "tgl_register" in view.columns:
        view["tgl_register (ID)"] = view["tgl_register"].apply(lambda x: format_tanggal_id(x) if (x != "-" and pd.notna(x)) else "-")
    if "tgl_sidang" in view.columns:
        view["tgl_sidang (ID)"] = view["tgl_sidang"].apply(lambda x: format_tanggal_id(x) if (x != "-" and pd.notna(x)) else "-")
    return view

def to_excel_bytes(df: pd.DataFrame) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Rekap")
    return output.getvalue()

# =========================
# ROTASI PP/JS VIA SK MAJELIS
# =========================

def _match_row_by_ketua(sk_df: pd.DataFrame, ketua_name: str) -> Optional[pd.Series]:
    if sk_df is None or sk_df.empty or not ketua_name:
        return None
    kcol = _first_col(sk_df, ["ketua","ketua_hakim","hakim_ketua","ketua majelis","nm_ketua","nama_ketua"])
    if not kcol:
        return None
    tgt = set(_norm_tokens(ketua_name))
    best = None
    best_score = -1
    for _, r in sk_df.iterrows():
        nm = str(r.get(kcol,""))
        if not nm:
            continue
        toks = set(_norm_tokens(nm))
        score = len(tgt & toks)
        if score > best_score:
            best_score = score
            best = r
    return best

def _extract_pp_js_from_sk_row(row: pd.Series) -> Tuple[str,str,str,str]:
    PP1 = ["pp1","pp 1","pp_1","panitera1","panitera_1","panitera"]
    PP2 = ["pp2","pp 2","pp_2","panitera2","panitera_2"]
    JS1 = ["js1","js 1","js_1","jurusita1","jurusita_1"]
    JS2 = ["js2","js 2","js_2","jurusita2","jurusita_2"]
    def get(cands):
        for c in cands:
            if c in row.index and str(row.get(c,"")).strip():
                return str(row.get(c,"")).strip()
        return ""
    return get(PP1), get(PP2), get(JS1), get(JS2)

def get_pp_js_from_sk(sk_df: pd.DataFrame, ketua: str) -> Tuple[str,str,str,str]:
    r = _match_row_by_ketua(sk_df, ketua)
    if r is None:
        return "","","",""
    return _extract_pp_js_from_sk_row(r)

def rotate_pp_from_sk(ketua: str, rekap_df: pd.DataFrame, sk_df: pd.DataFrame, *, seed_pp: str="pp1") -> str:
    """PP selang-seling berdasarkan SK. seed_pp: 'pp1' atau 'pp2'."""
    pp1, pp2, _, _ = get_pp_js_from_sk(sk_df, ketua)
    if not (pp1 or pp2):
        return ""
    n = _count_perkara_for_ketua(rekap_df, ketua)
    if str(seed_pp).lower() == "pp1":
        return pp1 if (n % 2 == 0) else pp2
    else:
        return pp2 if (n % 2 == 0) else pp1

def rotate_js_from_sk(ketua: str, rekap_df: pd.DataFrame, sk_df: pd.DataFrame, *, seed_js: str="js1") -> str:
    """JS blok 2–2 berdasarkan SK. seed_js: 'js1' atau 'js2'."""
    _, _, js1, js2 = get_pp_js_from_sk(sk_df, ketua)
    if not (js1 or js2):
        return ""
    n = _count_perkara_for_ketua(rekap_df, ketua)
    block = (n // 2) % 2  # 0,0,1,1,0,0,1,1,...
    if str(seed_js).lower() == "js1":
        return js1 if block == 0 else js2
    else:
        return js2 if block == 0 else js1

def get_pp_js_aktif_from_sk(ketua: str, rekap_df: pd.DataFrame, sk_df: pd.DataFrame,
                            *, seed_pp: str="pp1", seed_js: str="js1") -> Tuple[str,str]:
    """Wrapper: (PP_aktif, JS_aktif) dari SK, rotasi PP 1–1 dan JS 2–2."""
    return (
        rotate_pp_from_sk(ketua, rekap_df, sk_df, seed_pp=seed_pp),
        rotate_js_from_sk(ketua, rekap_df, sk_df, seed_js=seed_js),
    )

# =========================
# BACKWARD COMPAT (PAKAI SK JIKA ADA)
# =========================

def rotate_pp(hakim, rekap_df, pp_df, *, seed_pp: str = "pp1", sk_df: pd.DataFrame = None):
    """
    Kompatibel:
      - Jika sk_df diberikan → pakai SK (selang-seling).
      - Else → pakai tabel pp_df (cara lama). Jika kolom key tidak ada → return "" (tanpa KeyError).
    """
    if sk_df is not None and isinstance(sk_df, pd.DataFrame) and not sk_df.empty:
        return rotate_pp_from_sk(hakim, rekap_df, sk_df, seed_pp=seed_pp)

    if pp_df is None or pp_df.empty or not hakim:
        return ""
    kcol = _first_col(pp_df, ["hakim","ketua","ketua_hakim","ketua majelis"])
    if not kcol or kcol not in pp_df.columns:
        return ""
    row = pp_df[pp_df[kcol].astype(str).str.strip().str.lower() == str(hakim).strip().lower()]
    if row.empty:
        return ""
    pp1, pp2 = str(row.iloc[0].get("pp1","")).strip(), str(row.iloc[0].get("pp2","")).strip()
    cnt = _count_perkara_for_ketua(rekap_df, hakim)
    if str(seed_pp).lower() == "pp1":
        return pp1 if cnt % 2 == 0 else pp2
    else:
        return pp2 if cnt % 2 == 0 else pp1

def rotate_js_cross(hakim, rekap_df, js_df, *, seed_js: str = "js1", sk_df: pd.DataFrame = None):
    """
    Kompatibel:
      - Jika sk_df diberikan → pakai SK (blok 2–2).
      - Else → pakai tabel js_df (cara lama). Jika kolom key tidak ada → return "" (tanpa KeyError).
    """
    if sk_df is not None and isinstance(sk_df, pd.DataFrame) and not sk_df.empty:
        return rotate_js_from_sk(hakim, rekap_df, sk_df, seed_js=seed_js)

    if js_df is None or js_df.empty or not hakim:
        return ""
    kcol = _first_col(js_df, ["hakim","ketua","ketua_hakim","ketua majelis"])
    if not kcol or kcol not in js_df.columns:
        return ""
    row = js_df[js_df[kcol].astype(str).str.strip().str.lower() == str(hakim).strip().lower()]
    if row.empty:
        return ""
    js1, js2 = str(row.iloc[0].get("js1","")).strip(), str(row.iloc[0].get("js2","")).strip()
    n = _count_perkara_for_ketua(rekap_df, hakim)
    block = (n // 2) % 2
    if str(seed_js).lower() == "js1":
        return js1 if block == 0 else js2
    else:
        return js2 if block == 0 else js1
