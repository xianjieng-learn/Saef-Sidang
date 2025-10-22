# pages/1_📥_Input_&_Hasil.py
# Ketua by beban(aktif), Anggota STRICT dari baris SK
# PP/JS dari SK, rotate HANYA saat Simpan (pair 4-step: P1J1→P2J1→P1J2→P2J2)
# Tgl sidang: "Biasa" = H+8..H+14, skip libur, ke hari sidang ketua berikutnya
from __future__ import annotations
import re
import json
import os
DISABLE_DB = os.getenv("SAEF_DISABLE_DB", "0") == "1"

def _try_conn():
    try:
        if DISABLE_DB:
            return None
        return get_conn()
    except Exception:
        return None

import hashlib
from datetime import date, datetime, timedelta
from pathlib import Path
import math
import numpy as np
import pandas as pd
import streamlit as st

def _none_if_nan(v):
    """Ubah NaN/NaT/blank string -> None; numpy scalar -> python scalar; Timestamp -> py datetime/date."""
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except Exception:
        pass
    if isinstance(v, float) and math.isnan(v):
        return None
    if isinstance(v, (np.generic,)):
        v = v.item()
    if isinstance(v, pd.Timestamp):
        return v.to_pydatetime()
    if isinstance(v, (date, datetime)):
        return v
    if isinstance(v, str):
        s = v.strip()
        return s if s != "" else None
    return v
# --- Tambahkan helper ini (letakkan dekat fungsi DB lain) ---
def _get_existing_columns(table: str) -> set[str]:
    con = _try_conn()
    if not con:
        return set()
    try:
        cur = con.cursor()  # bisa tuple cursor atau DictCursor
        try:
            cur.execute(f"SHOW COLUMNS FROM `{table}`")
        except Exception:
            # tabel tidak ada / tidak bisa diakses
            return set()
        cols: set[str] = set()
        for row in cur.fetchall():
            # SHOW COLUMNS biasanya -> ('Field','Type',...) ATAU {'Field': '...', ...}
            if isinstance(row, (list, tuple)):
                if row:
                    cols.add(str(row[0]))
            elif isinstance(row, dict):
                fld = row.get("Field")
                if fld is None and row:  # fallback ekstrim kalau key beda
                    # ambil nilai pertama di dict
                    fld = next(iter(row.values()))
                if fld is not None:
                    cols.add(str(fld))
        return cols
    finally:
        try:
            con.close()
        except Exception:
            pass


def _get_from_data(data: dict, logical_key: str):
    # Nilai dengan fallback dari key alternatif (mis: ketua <- hakim; jenis_input <- metode)
    alts = {
        "ketua": ["hakim"],
        "jenis_input": ["metode"],
    }.get(logical_key, [])
    for k in [logical_key] + alts:
        if k in data:
            return _none_if_nan(data.get(k))
    return None

from app_core.helpers import HARI_MAP, format_tanggal_id, compute_nomor_tipe

# -- DB connection (untuk token rotasi & opsional mirror rekap)
try:
    from db import get_conn
except Exception:
    from app_core.db import get_conn

# ====== (opsional) Auto-refresh tiap N detik bila paket tersedia ======
_has_autorefresh = False
try:
    # pip install streamlit-autorefresh
    from streamlit_autorefresh import st_autorefresh  # type: ignore
    _has_autorefresh = True
except Exception:
    pass

# ===== JS Ghoib (opsional) =====
try:
    from app_core.helpers_js_ghoib import choose_js_ghoib_db
except Exception:
    def choose_js_ghoib_db(rekap_df, use_aktif=True):
        cand_df = js_ghoib_df if 'js_ghoib_df' in globals() and isinstance(js_ghoib_df, pd.DataFrame) and not js_ghoib_df.empty else (
                  js_df if 'js_df' in globals() and isinstance(js_df, pd.DataFrame) and not js_df.empty else pd.DataFrame())
        names = []
        if not cand_df.empty:
            tmp = cand_df.copy()
            if use_aktif and "aktif" in tmp.columns:
                def _flag(v):
                    s=str(v).strip().upper()
                    if s in {"1","YA","Y","TRUE","T","AKTIF","ON"}: return True
                    if s in {"0","TIDAK","TDK","NO","N","FALSE","F","NONAKTIF","OFF","NONE","NAN",""}: return False
                    try: return float(s) != 0.0
                    except Exception: return False
                tmp = tmp[tmp["aktif"].apply(_flag)]
            name_col = next((c for c in ["nama","js","Nama","NAMA"] if c in tmp.columns), None)
            if name_col:
                names = [str(x).strip() for x in tmp[name_col].tolist() if str(x).strip()]
        if not names and isinstance(rekap_df, pd.DataFrame) and "js" in rekap_df.columns:
            names = sorted({str(x).strip() for x in rekap_df["js"].tolist() if str(x).strip()})
        if not names:
            return ""
        counts = {}
        if isinstance(rekap_df, pd.DataFrame) and not rekap_df.empty and all(c in rekap_df.columns for c in ["js","jenis_perkara"]):
            r = rekap_df.copy()
            r["jenis_u"] = r["jenis_perkara"].astype(str).str.upper().str.strip()
            r = r[r["jenis_u"] == "GHOIB"]
            if not r.empty:
                r["js_norm"] = r["js"].astype(str).str.lower().str.strip()
                counts = r["js_norm"].value_counts().to_dict()
        def score(nm: str):
            return (counts.get(nm.lower().strip(), 0), nm.lower())
        names_sorted = sorted(names, key=score)
        return names_sorted[0] if names_sorted else ""

st.set_page_config(page_title="📥 Input & Hasil", page_icon="📥", layout="wide")
st.header("Input & Hasil")

if DISABLE_DB:
    st.warning("⚠️ Database dimatikan (SAEF_DISABLE_DB=1). Semua data pakai CSV/JSON fallback.")

# ===== Util teks/nama =====
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

# ===== Basic IO helpers =====
def _load_table_db(name: str) -> pd.DataFrame:
    con = _try_conn()
    if not con:
        return pd.DataFrame()
    try:
        return pd.read_sql_query(f"SELECT * FROM `{name}`", con)
    finally:
        con.close()

def _load_csv(path_like: Path) -> pd.DataFrame:
    p = Path(path_like)
    if not p.exists(): return pd.DataFrame()
    try:
        return pd.read_csv(p, encoding="utf-8-sig")
    except Exception:
        return pd.read_csv(p)

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
    Path("data").mkdir(parents=True, exist_ok=True)
    cols = ["nomor_perkara","tgl_register","klasifikasi","jenis_perkara",
            "metode","hakim","anggota1","anggota2","pp","js",
            "tgl_sidang","tgl_sidang_override"]
    df2 = df.copy()
    for c in cols:
        if c not in df2.columns:
            df2[c] = pd.NaT if c in ("tgl_register","tgl_sidang") else (0 if c=="tgl_sidang_override" else "")
    for c in ["tgl_register","tgl_sidang"]:
        df2[c] = pd.to_datetime(df2[c], errors="coerce").dt.date.astype("string")
    df2[cols].to_csv("data/rekap.csv", index=False, encoding="utf-8-sig")

# ====== Loader master data (DB-first, CSV fallback) ======
data_dir = Path("data")

hakim_df    = _load_table_db("hakim");      hakim_src = "DB" if not hakim_df.empty else ""
pp_df       = _load_table_db("pp");         pp_src    = "DB" if not pp_df.empty else ""
js_df       = _load_table_db("js");         js_src    = "DB" if not js_df.empty else ""
sk_df_db    = _load_table_db("sk_majelis"); sk_src0   = "DB" if not sk_df_db.empty else ""

def _set_src(cur_df, cur_src, csv_name):
    if not cur_df.empty: return cur_df, (cur_src or "DB")
    df = _load_csv(data_dir / csv_name)
    return df, (f"CSV: data/{csv_name}" if not df.empty else "DB")

hakim_df, hakim_src = _set_src(hakim_df, hakim_src, "hakim_df.csv")
pp_df, pp_src       = _set_src(pp_df, pp_src, "pp_df.csv")
js_df, js_src       = _set_src(js_df, js_src, "js_df.csv")

# Libur: DB or CSV
def _load_libur_db_or_csv() -> tuple[pd.DataFrame, str]:
    df = _load_table_db("libur")
    src = "DB"
    if df.empty:
        df = _load_csv(data_dir / "libur.csv")
        src = "CSV: data/libur.csv" if not df.empty else "DB"
    if not df.empty:
        cand = None
        for c in ["tanggal", "tgl", "date", "hari_libur"]:
            if c in df.columns: cand = c; break
        if cand: df = df.rename(columns={cand: "tanggal"})
    return df, src

libur_df, libur_src = _load_libur_db_or_csv()

# ===== Resolve SK (DB → CSV) =====
def _load_sk_fallback_from_csv() -> tuple[pd.DataFrame, str]:
    candidates = [data_dir / n for n in ("sk_df.csv","sk_majelis.csv","sk.csv")]
    if data_dir.exists():
        for p in data_dir.glob("*.csv"):
            if "sk" in p.name.lower() and p not in candidates:
                candidates.append(p)
    for p in candidates:
        df = _load_csv(p)
        df = _standardize_cols(df)
        if not df.empty and "ketua" in df.columns:
            return df, f"CSV: {p.as_posix()}"
    return pd.DataFrame(), ""

sk_resolved = _standardize_cols(sk_df_db)
sk_src = "DB"
if sk_resolved.empty or "ketua" not in sk_resolved.columns:
    sk_csv, sk_src = _load_sk_fallback_from_csv()
    if not sk_csv.empty: sk_resolved = sk_csv
else:
    sk_src = sk_src0 or "DB"

st.session_state["_sk_resolved"] = sk_resolved
st.session_state["_sk_src"] = sk_src
sk_df = st.session_state["_sk_resolved"]
sk_src = st.session_state["_sk_src"]

# ===== Rekap: CSV sebagai sumber kebenaran =====
rekap_csv_path = data_dir / "rekap.csv"
rekap_df = _load_csv(rekap_csv_path)
rekap_src = "CSV: data/rekap.csv" if not rekap_df.empty else "CSV (kosong)"

# ===== Badges sumber =====
st.caption(
    "🗂️ Sumber data → "
    f"**SK**: {sk_src} • "
    f"**Hakim**: {hakim_src} • "
    f"**PP**: {pp_src} • "
    f"**JS**: {js_src} • "
    f"**Libur**: {libur_src} • "
    f"**Rekap**: {rekap_src}"
)

# ================== OPSIONAL: AUTO SYNC rekap.csv → DB ==================
with st.expander("⚙️ Auto-sync rekap.csv → DB (opsional)", expanded=False):
    autosync_on = st.toggle(
        "Aktifkan auto-sync CSV → DB",
        value=False,
        key="rekap_autosync_on",
        help="Jika aktif, ketika rekap.csv berubah maka otomatis diimpor ke DB."
    )
    sync_mode_label = st.radio(
        "Mode impor saat berubah",
        ["UPsert (gabung)", "REPLACE (timpa semua)"],
        index=0,
        horizontal=True,
        key="rekap_sync_mode"
    )
    auto_refresh_user = False
    if _has_autorefresh:
        auto_refresh_user = st.toggle(
            "Auto-refresh 10s (opsional)",
            value=False,
            key="rekap_sync_refresh",
            help="Tanpa auto-refresh, perubahan file hanya terdeteksi saat ada interaksi/refresh."
        )

    p = rekap_csv_path
    fp_key = f"rekap_csv_fp::{p.as_posix()}"
    exists = p.exists()
    try:
        size = (p.stat().st_size if exists else 0)
        mtime_dt = (datetime.fromtimestamp(p.stat().st_mtime) if exists else None)
    except Exception:
        size, mtime_dt = 0, None

    try:
        fp_now_preview = hashlib.md5(open(p, "rb").read(2_000_000)).hexdigest() if exists else ""
    except Exception:
        fp_now_preview = ""

    last_sync_ts = st.session_state.get("rekap_last_sync_ts", "—")
    last_fp = st.session_state.get(fp_key, "—")
    mode_now = ("REPLACE" if "REPLACE" in str(st.session_state.get("rekap_sync_mode")).upper() else "UPSERT")

    cols = st.columns(3)
    cols[0].markdown(f"**File**: `{p.as_posix()}`")
    cols[1].markdown(f"**Ada file?** {'✅' if exists else '❌'}")
    cols[2].markdown(f"**Mode**: `{mode_now}`")

    cols = st.columns(3)
    cols[0].markdown(f"**Ukuran**: {size:,} byte")
    cols[1].markdown(f"**Mtime**: {(mtime_dt.strftime('%Y-%m-%d %H:%M:%S') if mtime_dt else '—')}")
    cols[2].markdown(f"**Auto-sync ON?** {'🟢 YA' if autosync_on else '⚪ TIDAK'}")

    cols = st.columns(2)
    cols[0].markdown(f"**FP sekarang (preview)**: `{fp_now_preview or '—'}`")
    cols[1].markdown(f"**FP terakhir diingat**: `{last_fp}`")
    st.caption(f"Terakhir impor ke DB: **{last_sync_ts}**")

    if st.button("⏩ Jalankan impor sekarang", key="rekap_manual_import_btn"):
        st.session_state["rekap_manual_import_trigger"] = True
        st.session_state["rekap_manual_mode"] = ("replace" if mode_now == "REPLACE" else "upsert")
        st.toast("Menjalankan impor manual…", icon="⏳")
        st.rerun()

def _fingerprint_file(p: str) -> str:
    try:
        stat = os.stat(p)
        size = stat.st_size
        mtime = int(stat.st_mtime)
        with open(p, "rb") as f:
            chunk = f.read(2_000_000)
        h = hashlib.md5(chunk).hexdigest()
        return f"{size}:{mtime}:{h}"
    except Exception:
        return ""

if st.session_state.get("rekap_autosync_on") and _has_autorefresh:
    if st.session_state.get("rekap_sync_refresh"):
        st_autorefresh(interval=10_000, key="rekap_autorefresh_user")
    else:
        st_autorefresh(interval=5_000, key="rekap_autorefresh_bg")

# === Helper impor ke DB ===
def _import_rekap_dataframe_to_db(df_csv: pd.DataFrame, mode: str = "upsert"):
    df = df_csv.copy()

    for col in ["tgl_register", "tgl_sidang", "tgl_putus"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce", dayfirst=True)

    for col in df.columns:
        df[col] = df[col].where(df[col].notna(), None)
        if df[col].dtype == object:
            df[col] = df[col].map(lambda x: x.strip() if isinstance(x, str) else x)

    for _, r in df.iterrows():
        payload = {
            "nomor_perkara": _none_if_nan(r.get("nomor_perkara")),
            # "para_pihak":  (DIHAPUS – kolom tidak ada di DB)
            "jenis_perkara": _none_if_nan(r.get("jenis_perkara")),
            "ketua": _none_if_nan(r.get("ketua")),
            "anggota1": _none_if_nan(r.get("anggota1")),
            "anggota2": _none_if_nan(r.get("anggota2")),
            "pp": _none_if_nan(r.get("pp")),
            "js": _none_if_nan(r.get("js")),
            "tgl_register": _none_if_nan(r.get("tgl_register")),
            "tgl_sidang": _none_if_nan(r.get("tgl_sidang")),
            "tgl_putus": _none_if_nan(r.get("tgl_putus")),
            "jenis_input": _none_if_nan(r.get("jenis_input")),
            "catatan": _none_if_nan(r.get("catatan")),
            "tgl_sidang_override": int(bool(_none_if_nan(r.get("tgl_sidang_override", 0)))),
        }
        _upsert_rekap_db(payload)

# === GANTI fungsi _upsert_rekap_db dengan versi dinamis ini ===
def _upsert_rekap_db(data: dict):
    if DISABLE_DB:
        return
    con = _try_conn()
    if not con:
        return
    cur = con.cursor()

    existing = _get_existing_columns("rekap")

    # Peta "logical field" -> kandidat nama fisik di DB (urutkan dari yang paling diinginkan)
    # Kalau kandidat pertama tidak ada di DB, akan dipilih kandidat berikutnya.
    logical_to_phys = {
        "nomor_perkara": ["nomor_perkara", "no_perkara", "no_register", "nomor"],
        "jenis_perkara": ["jenis_perkara", "jenis"],
        "ketua":         ["ketua", "hakim", "hakim_ketua"],
        "anggota1":      ["anggota1", "anggota_1", "a1"],
        "anggota2":      ["anggota2", "anggota_2", "a2"],
        "pp":            ["pp", "panitera", "panitera_pengganti"],
        "js":            ["js", "jurusita"],
        "tgl_register":  ["tgl_register", "tanggal_register", "register_date", "tgl_reg"],
        "tgl_sidang":    ["tgl_sidang", "tanggal_sidang", "sidang_date"],
        "tgl_putus":     ["tgl_putus", "tanggal_putus", "putusan_date"],
        "jenis_input":   ["jenis_input", "metode", "input_via"],
        "catatan":       ["catatan", "keterangan", "notes"],
        "tgl_sidang_override": ["tgl_sidang_override", "sidang_override", "is_override"],
    }

    # Pilih kolom fisik yang benar-benar ada di DB
    logical_keys: list[str] = []
    phys_cols: list[str] = []
    for logical, candidates in logical_to_phys.items():
        phys = next((c for c in candidates if c in existing), None)
        if phys is not None:
            logical_keys.append(logical)
            phys_cols.append(phys)

    # Wajib ada PK/unik sebagai identitas (diasumsikan 'nomor_perkara')
    if "nomor_perkara" not in logical_keys:
        # Tidak bisa upsert tanpa identitas. Kamu bisa ubah ke REPLACE atau INSERT biasa kalau mau.
        return

    # Siapkan values dengan fallback antar logical key (lihat _get_from_data)
    vals = tuple(_get_from_data(data, k) for k in logical_keys)

    placeholders = ",".join(["%s"] * len(phys_cols))
    col_list = ",".join(f"`{c}`" for c in phys_cols)

    # Bagian update: semua selain kolom identitas (nomor_perkara)
    update_phys = [
        pc for (lk, pc) in zip(logical_keys, phys_cols)
        if lk != "nomor_perkara"
    ]
    set_list = ",".join([f"`{c}`=VALUES(`{c}`)" for c in update_phys])

    sql = f"INSERT INTO `rekap` ({col_list}) VALUES ({placeholders})"
    if set_list:
        sql += f" ON DUPLICATE KEY UPDATE {set_list}"

    # (opsional) sanity check:
    # assert sql.count("%s") == len(vals), (sql.count("%s"), len(vals), logical_keys, phys_cols)

    cur.execute(sql, vals)
    con.commit()
    con.close()


# === TRIGGER: impor manual + auto-sync berbasis fingerprint ===
p = rekap_csv_path
fp_now = _fingerprint_file(p.as_posix()) if p.exists() else ""
fp_key = f"rekap_csv_fp::{p.as_posix()}"
if fp_key not in st.session_state:
    st.session_state[fp_key] = fp_now

if st.session_state.get("rekap_manual_import_trigger"):
    mode_val = st.session_state.get("rekap_manual_mode", "upsert")
    df_csv = _load_csv(p)
    if (not df_csv.empty) or (mode_val == "replace"):
        _import_rekap_dataframe_to_db(df_csv, mode=mode_val)
        st.session_state[fp_key] = fp_now
        st.session_state["rekap_last_sync_ts"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            if not df_csv.empty:
                latest_day = pd.to_datetime(df_csv.get("tgl_register")).max().date()
                st.session_state["rekap_filter_date"] = latest_day
        except Exception:
            pass
        st.session_state["rekap_manual_import_trigger"] = False
        st.toast(f"Impor manual rekap.csv → DB ({mode_val.upper()}) selesai ✅", icon="✅")
        st.rerun()
    else:
        st.session_state["rekap_manual_import_trigger"] = False
        st.toast("CSV kosong, tidak ada yang diimpor (mode UPSERT).", icon="⚠️")

if st.session_state.get("rekap_autosync_on"):
    fp_last = st.session_state.get(fp_key, "")
    mode_val = "replace" if "REPLACE" in str(st.session_state.get("rekap_sync_mode")).upper() else "upsert"

    if fp_now and fp_now != fp_last:
        df_csv = _load_csv(p)
        if (not df_csv.empty) or (mode_val == "replace"):
            _import_rekap_dataframe_to_db(df_csv, mode=mode_val)
            st.session_state[fp_key] = fp_now
            st.session_state["rekap_last_sync_ts"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            try:
                if not df_csv.empty:
                    latest_day = pd.to_datetime(df_csv.get("tgl_register")).max().date()
                    st.session_state["rekap_filter_date"] = latest_day
            except Exception:
                pass
            st.toast(f"Auto-sync rekap.csv → DB ({mode_val.upper()}) selesai ✅", icon="✅")
            st.rerun()
        else:
            st.session_state[fp_key] = fp_now
# ===== Fallback file untuk token rotasi PP/JS + offline queue =====
_RR_LOCAL_PATH = Path("data/rrpair_tokens.json")
_RR_LOCAL_PATH.parent.mkdir(parents=True, exist_ok=True)

def _rr_file_load() -> dict:
    try:
        if _RR_LOCAL_PATH.exists() and _RR_LOCAL_PATH.stat().st_size > 0:
            with open(_RR_LOCAL_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
    except Exception:
        pass
    # struktur dasar
    return {"tokens": {}, "pending": {}}
    # tokens:  { rrkey: {"idx": int, "meta": {...}, "updated_at": "iso"} }
    # pending: { rrkey: {"idx": int, "meta": {...}, "updated_at": "iso"} }  # menunggu sync ke DB

def _rr_file_save(d: dict) -> None:
    try:
        d = d or {}
        if "tokens" not in d:  d["tokens"] = {}
        if "pending" not in d: d["pending"] = {}
        tmp = _RR_LOCAL_PATH.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False)
        os.replace(tmp, _RR_LOCAL_PATH)  # atomic di OS modern
    except Exception:
        pass

def _rr_table_ensure():
    con = _try_conn()
    if not con:
        return
    try:
        cur = con.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS rrpair_token (
              rrkey VARCHAR(190) PRIMARY KEY,
              idx   INT NOT NULL DEFAULT 0,
              meta  JSON NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)
        con.commit()
    finally:
        try: con.close()
        except Exception: pass

def _rr_sync_pending():
    """Coba kirim semua perubahan pending (waktu DB sebelumnya mati) ke DB."""
    _rr_table_ensure()
    con = _try_conn()
    if not con:
        return False
    try:
        store = _rr_file_load()
        pending = dict(store.get("pending") or {})
        if not pending:
            return True
        cur = con.cursor()
        for rrkey, rec in pending.items():
            idx  = int(rec.get("idx", 0))
            meta = json.dumps(rec.get("meta") or {}, ensure_ascii=False)
            cur.execute("""
                INSERT INTO rrpair_token (rrkey, idx, meta)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE idx=VALUES(idx), meta=VALUES(meta);
            """, (rrkey, idx, meta))
            # Jika sukses, pindahkan ke tokens dan hapus dari pending
            store.setdefault("tokens", {})[rrkey] = {
                "idx": idx, "meta": rec.get("meta") or {}, "updated_at": datetime.now().isoformat()
            }
            if rrkey in store.get("pending", {}):
                del store["pending"][rrkey]
        con.commit()
        _rr_file_save(store)
        return True
    except Exception:
        return False
    finally:
        try: con.close()
        except Exception: pass

def _rr_get_idx(rrkey: str) -> int:
    """
    Ambil idx. Urutan:
    1) DB (kalau ada) -> mirror ke file juga.
    2) File tokens (kalau DB gagal).
    3) 0 sebagai default.
    """
    _rr_table_ensure()
    con = _try_conn()
    if con:
        try:
            cur = con.cursor()
            cur.execute("SELECT idx, COALESCE(meta,'{}') FROM rrpair_token WHERE rrkey=%s;", (rrkey,))
            row = cur.fetchone()
            if row:
                idx = int(row[0])
                try:
                    meta = json.loads(row[1]) if isinstance(row[1], (str, bytes, bytearray)) else (row[1] or {})
                except Exception:
                    meta = {}
                # mirror ke file
                store = _rr_file_load()
                store.setdefault("tokens", {})[rrkey] = {
                    "idx": idx, "meta": meta, "updated_at": datetime.now().isoformat()
                }
                _rr_file_save(store)
                # simpan info sumber untuk panel debug (opsional)
                st.session_state["_rr_last_source"] = "DB"
                return idx
        except Exception:
            pass
        finally:
            try: con.close()
            except Exception: pass

    # Fallback file
    store = _rr_file_load()
    rec = (store.get("tokens") or {}).get(rrkey) or (store.get("pending") or {}).get(rrkey) or {}
    try:
        idx = int(rec.get("idx", 0))
    except Exception:
        idx = 0
    st.session_state["_rr_last_source"] = "FILE"
    return idx

def _rr_set_idx(rrkey: str, idx: int, meta: dict | None = None):
    """
    Set idx:
    - Selalu tulis ke file (tokens) agar UI tetap konsisten offline.
    - Coba tulis ke DB; jika gagal, simpan ke 'pending' untuk disync nanti.
    """
    idx = int(idx)
    meta = meta or {}
    now_iso = datetime.now().isoformat()

    # 1) Tulis ke file dulu (optimistic local write)
    store = _rr_file_load()
    store.setdefault("tokens", {})[rrkey] = {"idx": idx, "meta": meta, "updated_at": now_iso}
    _rr_file_save(store)

    # 2) Coba tulis ke DB
    _rr_table_ensure()
    con = _try_conn()
    if not con:
        # tandai pending
        store = _rr_file_load()
        store.setdefault("pending", {})[rrkey] = {"idx": idx, "meta": meta, "updated_at": now_iso}
        _rr_file_save(store)
        return

    try:
        cur = con.cursor()
        m = json.dumps(meta, ensure_ascii=False)
        cur.execute("""
            INSERT INTO rrpair_token (rrkey, idx, meta)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE idx=VALUES(idx), meta=VALUES(meta);
        """, (rrkey, idx, m))
        con.commit()
        # jika sukses, pastikan tidak ada pending utk rrkey ini
        store = _rr_file_load()
        if rrkey in (store.get("pending") or {}):
            del store["pending"][rrkey]
        # juga pastikan tokens up-to-date
        store.setdefault("tokens", {})[rrkey] = {"idx": idx, "meta": meta, "updated_at": now_iso}
        _rr_file_save(store)
    except Exception:
        # gagal ke DB → tandai pending
        store = _rr_file_load()
        store.setdefault("pending", {})[rrkey] = {"idx": idx, "meta": meta, "updated_at": now_iso}
        _rr_file_save(store)
    finally:
        try: con.close()
        except Exception: pass



def _rr_key_per_ketua(ketua: str) -> str:
    norm = re.sub(r"[^a-z0-9]+", "-", _name_key(ketua)).strip("-")
    return f"rrpair::per_ketua::{norm or 'unknown'}"

# ===== Pilih ketua by beban aktif + ambil baris SK =====
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

def _pick_ketua_by_beban(hakim_df: pd.DataFrame, rekap_df: pd.DataFrame) -> tuple[str, pd.Series | None]:
    if hakim_df is None or hakim_df.empty or "nama" not in hakim_df.columns:
        return "", None
    df = hakim_df.copy()
    df["__aktif"] = df.get("aktif", 1).apply(_is_active_value)
    df = df[df["__aktif"] == True]
    if df.empty: return "", None
    counts = {}
    if isinstance(rekap_df, pd.DataFrame) and not rekap_df.empty and "hakim" in rekap_df.columns:
        counts = rekap_df["hakim"].astype(str).str.strip().value_counts().to_dict()
    df["__load"] = df["nama"].astype(str).str.strip().map(lambda n: int(counts.get(n, 0)))
    df = df.sort_values(["__load","nama"], kind="stable").reset_index(drop=True)
    ketua = str(df.iloc[0]["nama"])
    sk_row = _best_sk_row_for_ketua(sk_df, ketua)
    return ketua, sk_row

# ===== PP/JS: pair 4-step, ROTATE =====
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
    key = _rr_key_per_ketua(ketua)
    idx = _rr_get_idx(key) % len(combos) if combos else 0
    pp, js = combos[idx] if combos else ("", "")
    if str(jenis).strip().upper() == "GHOIB":
        js_gh = choose_js_ghoib_db(rekap_df, use_aktif=True)
        if js_gh: js = js_gh
    return pp, js

def _consume_pair_on_save_once(ketua: str, sk_row: pd.Series, jenis: str, rekap_df: pd.DataFrame) -> tuple[str,str]:
    combos = _pair_combos_from_sk(sk_row)
    key = _rr_key_per_ketua(ketua)
    cur = _rr_get_idx(key)
    idx = (cur % len(combos)) if combos else 0
    pp, js = combos[idx] if combos else ("", "")
    if str(jenis).strip().upper() == "GHOIB":
        js_gh = choose_js_ghoib_db(rekap_df, use_aktif=True)
        if js_gh: js = js_gh
    next_idx = (idx + 1) % max(1, len(combos))
    _rr_set_idx(key, next_idx, meta={
        "ketua": ketua,
        "combos_len": len(combos),
        "last_used_combo": {"pp": pp, "js": js}
    })
    return pp, js

# ===== Tanggal Sidang (strict) =====
def _weekday_num_from_map(hari_text: str) -> int:
    try: return int(HARI_MAP.get(str(hari_text), 0))
    except Exception: return 0

def _next_judge_day_strict(start_date: date, hari_sidang_num: int, libur_set: set[str]) -> date:
    if not isinstance(start_date, (date, datetime)) or not hari_sidang_num:
        return start_date
    target_py = (hari_sidang_num - 1) % 7
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

# ====== Panel kontrol ======
left_ctl, right_ctl = st.columns([1,3])
with left_ctl:
    if st.button("🔄 Refresh (muat ulang CSV/DB)", use_container_width=True):
        st.rerun()
with right_ctl:
    if _has_autorefresh:
        auto = st.toggle("Auto-refresh 10s", value=False)
        if auto:
            st_autorefresh(interval=10_000, key="auto_refresh_input_hasil")

# ====== Form seed: reset total setelah simpan ======
if "form_seed" not in st.session_state:
    st.session_state["form_seed"] = 0
fs = st.session_state["form_seed"]
st.caption(f"⏱️ Heartbeat: {datetime.now().strftime('%H:%M:%S')}")

# ===== Form input — gunakan key berbasis form_seed =====
left, right = st.columns([2, 1])
with st.form(f"form_perkara_{fs}", clear_on_submit=True):
    with left:
        nomor = st.text_input("Nomor Perkara", key=f"nomor_{fs}")
        tgl_register_input = st.date_input("Tanggal Register", value=date.today(), key=f"tglreg_{fs}")
        KLAS_OPTS = ["CG","CT","VERZET","PAW","WARIS","ISTBAT","HAA","Dispensasi","Poligami","Maqfud","Asal Usul","Perwalian","Harta Bersama","EkSya","Lain-Lain","Lainnya (ketik)"]
        klas_sel = st.selectbox("Klasifikasi Perkara", KLAS_OPTS, index=0, key=f"klas_sel_{fs}")
        klas_final = st.text_input("Tulis klasifikasi lainnya", key=f"klas_other_{fs}") if klas_sel == "Lainnya (ketik)" else klas_sel
        jenis = st.selectbox("Jenis Perkara (Proses)", ["Biasa","ISTBAT","GHOIB","ROGATORI","MAFQUD"], key=f"jenis_{fs}")
    with right:
        metode_input = st.selectbox("Metode", ["E-Court","Manual"], index=0, key=f"metode_{fs}")

        semua_nama = []
        if isinstance(hakim_df, pd.DataFrame) and "nama" in hakim_df.columns:
            df_sorted = hakim_df.copy()
            df_sorted["__aktif_rank"] = (~df_sorted.get("aktif",1).apply(_is_active_value)).astype(int)
            df_sorted = df_sorted.sort_values(["__aktif_rank","nama"], kind="stable")
            semua_nama = df_sorted["nama"].dropna().astype(str).tolist()
        hakim_manual = st.selectbox("Ketua (opsional, override otomatis)", [""] + semua_nama, key=f"hakim_manual_{fs}")

        def _options_from_master(df: pd.DataFrame, prefer_active=True) -> list[str]:
            if not isinstance(df, pd.DataFrame) or df.empty: return []
            name_col = None
            for c in ["nama", "pp", "js", "nama_lengkap", "Nama", "NAMA"]:
                if c in df.columns: name_col = c; break
            if not name_col: return []
            x = df[[name_col]].copy()
            x[name_col] = x[name_col].astype(str).str.strip()
            x = x[x[name_col] != ""]
            if prefer_active and "aktif" in df.columns:
                df["_aktif__"] = df["aktif"].apply(_is_active_value)
                x = x.join(df["_aktif__"])
                x = x.sort_values(by=["_aktif__", name_col], ascending=[False, True])
                names = x[name_col].tolist()
            else:
                names = sorted(x[name_col].unique().tolist())
            seen, out = set(), []
            for n in names:
                if n not in seen:
                    seen.add(n); out.append(n)
            return out

        pp_opts = _options_from_master(pp_df, prefer_active=True)
        js_opts = _options_from_master(js_df, prefer_active=True)
        pp_manual = st.selectbox("PP Manual (opsional)", [""] + pp_opts, key=f"pp_manual_{fs}")
        js_manual = st.selectbox("JS Manual (opsional)", [""] + js_opts, key=f"js_manual_{fs}")

        tipe_pdt = st.selectbox("Tipe Perkara (Pdt)", ["Otomatis","Pdt.G","Pdt.P","Pdt.Plw"], key=f"tipe_pdt_{fs}")

    if str(hakim_manual).strip():
        ketua = str(hakim_manual).strip()
        sk_row = _best_sk_row_for_ketua(sk_df, ketua)
        if sk_row is None:
            st.warning("Ketua manual tidak ditemukan di SK. Anggota/PP/JS akan dikosongkan.")
    else:
        ketua, sk_row = _pick_ketua_by_beban(hakim_df, rekap_df)
    hakim = ketua or ""

    anggota1 = str(sk_row.get("anggota1","")) if isinstance(sk_row, pd.Series) else ""
    anggota2 = str(sk_row.get("anggota2","")) if isinstance(sk_row, pd.Series) else ""
    if not isinstance(sk_row, pd.Series):
        st.info("Baris SK untuk ketua tidak ditemukan ⇒ Anggota/PP/JS dikosongkan.")
    else:
        if not (anggota1.strip() and anggota2.strip()):
            st.info("Baris SK ketua belum lengkap Anggota1/2. Lengkapi di Data SK.")

    def _peek_pair(ketua: str, sk_row: pd.Series, jenis: str, rekap_df: pd.DataFrame) -> tuple[str,str]:
        combos = _pair_combos_from_sk(sk_row)
        key = _rr_key_per_ketua(ketua)
        idx = _rr_get_idx(key) % len(combos) if combos else 0
        pp, js = combos[idx] if combos else ("", "")
        if str(jenis).strip().upper() == "GHOIB":
            js_gh = choose_js_ghoib_db(rekap_df, use_aktif=True)
            if js_gh: js = js_gh
        return pp, js

    if str(pp_manual).strip():
        pp_preview = pp_manual.strip()
        js_preview = js_manual.strip() if str(js_manual).strip() else _peek_pair(hakim, sk_row, jenis, rekap_df)[1]
    else:
        if str(js_manual).strip():
            pp_preview = _peek_pair(hakim, sk_row, jenis, rekap_df)[0]
            js_preview = js_manual.strip()
        else:
            pp_preview, js_preview = _peek_pair(hakim, sk_row, jenis, rekap_df)

    base = tgl_register_input if isinstance(tgl_register_input, (datetime, date)) else date.today()
    hari_sidang_num = 0
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

    tgl_sidang_effective = tgl_sidang_manual if use_override else tgl_sidang_auto

    nomor_fmt, tipe_final = compute_nomor_tipe(nomor, klas_final, tipe_pdt)
    st.subheader("Hasil Otomatis (Preview)")
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

    simpan = st.form_submit_button("💾 Simpan ke Rekap (CSV)", use_container_width=True, disabled=not bool(hakim))
    if simpan:
        pair_pp, pair_js = _consume_pair_on_save_once(hakim, sk_row, jenis, rekap_df)
        pp_val = pp_manual.strip() if str(pp_manual).strip() else pair_pp
        js_val = js_manual.strip() if str(js_manual).strip() else pair_js

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

        current_csv = _load_csv(rekap_csv_path)
        rekap_new = pd.concat([current_csv, pd.DataFrame([new_row])], ignore_index=True)
        _export_rekap_csv(rekap_new)

        try:
            _upsert_rekap_db(new_row)
        except Exception:
            pass
        try:
            effective_day = pd.to_datetime(base).date()
        except Exception:
            effective_day = date.today()
        st.session_state["_force_rekap_date"] = effective_day
        st.session_state["rekap_filter_date"] = effective_day
        st.session_state["form_seed"] = fs + 1

        st.toast(f"Tersimpan ke CSV! (PP/JS: {pp_val or '-'} / {js_val or '-'})", icon="✅")
        st.rerun()

    with st.expander("🔧 Debug Rotasi PP/JS", expanded=False):
        combos_dbg = _pair_combos_from_sk(sk_row)
        rrkey_dbg = _rr_key_per_ketua(hakim)
        idx_dbg = _rr_get_idx(rrkey_dbg)
        st.write("RR Key:", rrkey_dbg)
        st.write("Idx sekarang:", idx_dbg, f"(source: {st.session_state.get('_rr_last_source','?')})")
        ...

# ===== Rekap (berdasarkan Tanggal Register dari CSV) =====
st.markdown("---")
st.subheader("Rekap (berdasarkan Tanggal Register)")

def _fmt_id(x):
    dt = pd.to_datetime(x, errors="coerce")
    return format_tanggal_id(dt) if pd.notna(dt) else "-"

tmp = _load_csv(rekap_csv_path)
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
