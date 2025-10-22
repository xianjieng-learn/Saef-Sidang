# app_core/data_io.py
from __future__ import annotations
import os, io, json, tempfile
from typing import Tuple
import pandas as pd

# ==== Konfigurasi lokasi penyimpanan ====
# Ubah ke path yang kamu mau (pastikan user punya write permission)
DATA_DIR = os.environ.get("APP_DATA_DIR", os.path.join(os.getcwd(), "data"))

# Nama file tabel (CSV). Kamu bisa ganti ke .parquet kalau mau.
FILES = {
    "hakim":       "hakim.csv",
    "pp":          "pp.csv",
    "js":          "js.csv",
    "js_ghoib":    "js_ghoib.csv",
    "libur":       "libur.csv",
    "rekap":       "rekap.csv",
    "sk_majelis":  "sk_majelis.csv",   # <— SK disimpan permanen di sini
}

def _ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)

def _path(name: str) -> str:
    _ensure_data_dir()
    fname = FILES.get(name, f"{name}.csv")
    return os.path.join(DATA_DIR, fname)

# ==== Helper aman untuk tulis file (atomic write) ====
def _atomic_write_csv(df: pd.DataFrame, path: str):
    tmp_fd, tmp_path = tempfile.mkstemp(prefix="tmp_", suffix=".csv", dir=os.path.dirname(path))
    os.close(tmp_fd)
    try:
        df.to_csv(tmp_path, index=False)
        # ganti atomik
        if os.path.exists(path):
            os.replace(tmp_path, path)
        else:
            os.rename(tmp_path, path)
    finally:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass

# ==== API publik: save/load ====
def save_table(df: pd.DataFrame, name: str) -> None:
    """
    Simpan DataFrame ke CSV permanen.
    name: salah satu key di FILES, mis. "sk_majelis", "rekap", dst.
    """
    if not isinstance(df, pd.DataFrame):
        raise ValueError("save_table expects a pandas DataFrame")
    path = _path(name)
    _atomic_write_csv(df, path)

def _read_csv_safe(path: str) -> pd.DataFrame:
    if not os.path.exists(path):
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception:
        # Fallback: kadang encoding bermasalah
        with open(path, "rb") as f:
            raw = f.read()
        return pd.read_csv(io.BytesIO(raw))

def load_table(name: str) -> pd.DataFrame:
    """Baca CSV → DataFrame. Kalau belum ada, kembalikan df kosong."""
    return _read_csv_safe(_path(name))

def load_all() -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Kompat lama: tanpa SK. (hakim, pp, js, js_ghoib, libur, rekap)
    """
    hakim_df    = load_table("hakim")
    pp_df       = load_table("pp")
    js_df       = load_table("js")
    js_ghoib_df = load_table("js_ghoib")
    libur_df    = load_table("libur")
    rekap_df    = load_table("rekap")
    # parse tanggal kalau ada kolom tgl_*
    for df in (rekap_df, libur_df):
        for c in list(df.columns):
            if c.startswith("tgl_") or c == "tanggal":
                try:
                    df[c] = pd.to_datetime(df[c], errors="coerce")
                except Exception:
                    pass
    return hakim_df, pp_df, js_df, js_ghoib_df, libur_df, rekap_df

def load_with_sk() -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Versi lengkap: termasuk SK Majelis.
    Return: (hakim_df, pp_df, js_df, js_ghoib_df, libur_df, rekap_df, sk_df)
    """
    hakim_df, pp_df, js_df, js_ghoib_df, libur_df, rekap_df = load_all()
    sk_df = load_table("sk_majelis")
    return hakim_df, pp_df, js_df, js_ghoib_df, libur_df, rekap_df, sk_df
