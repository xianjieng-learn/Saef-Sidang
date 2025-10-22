# pages/3e_🗓️_Cuti_Hakim.py
from __future__ import annotations
from pathlib import Path
from datetime import date
from typing import Dict, List, Set, Tuple
import math
import pandas as pd
import streamlit as st
import re


st.set_page_config(page_title="🗓️ Daftar Nama & Cuti Hakim", layout="wide")
st.header("🗓️ Daftar Nama & Manajemen Cuti Hakim ")

DATA_DIR = Path("data"); DATA_DIR.mkdir(parents=True, exist_ok=True)
CUTI_FILE = DATA_DIR / "cuti_hakim.csv"
HAKIM_CSV = DATA_DIR / "hakim_df.csv"
HAKIM_FILE = DATA_DIR / "hakim_df.csv"
REKAP_CSV = DATA_DIR / "rekap.csv"
# ---------------- Utils ----------------


# ===================== Utilities =====================
def _is_active_value(v) -> bool:
    s = str(v).replace("\ufeff","").strip().upper()
    if s in {"1","YA","Y","TRUE","T","AKTIF","ON"}: return True
    if s in {"0","TIDAK","TDK","NO","N","FALSE","F","NONAKTIF","OFF","NONE","NAN",""}: return False
    try: return float(s) != 0.0
    except Exception: return False

def _safe_int(v) -> int:
    try:
        if pd.isna(v): return 0
    except Exception:
        pass
    try: return int(v)
    except Exception:
        try: return int(float(str(v).strip()))
        except Exception: return 0

def _to_dt(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s.astype(str), errors="coerce", dayfirst=True)

def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists(): return pd.DataFrame()
    for enc in ("utf-8-sig","utf-8","cp1252"):
        try: return pd.read_csv(path, encoding=enc)
        except Exception: pass
    return pd.read_csv(path)

def _write_csv(df: pd.DataFrame, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8-sig")

_PREFIX_RX = re.compile(r"^\s*((drs?|dra|prof|ir|apt|h|hj|kh|ust|ustadz|ustadzah)\.?\s+)+", re.I)
_SUFFIX_PATTERNS = [
    r"s\.?\s*h\.?", r"s\.?\s*h\.?\s*i\.?", r"m\.?\s*h\.?", r"m\.?\s*h\.?\s*i\.?",
    r"s\.?\s*ag", r"m\.?\s*ag", r"m\.?\s*kn", r"m\.?\s*hum", r"s\.?\s*kom",
    r"s\.?\s*psi", r"s\.?\s*e", r"m\.?\s*m", r"m\.?\s*a", r"llb", r"llm",
    r"phd", r"se", r"ssi", r"sh", r"mh"
]
_SUFFIX_RX = re.compile(r"(,?\s+(" + r"|".join(_SUFFIX_PATTERNS) + r"))+$", re.I)
def _clean_text(s: str) -> str:
    x = str(s or "").replace("\u00A0"," ").strip()
    x = re.sub(r"\s+"," ", x)
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

def _standardize_cuti(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=["nama","mulai","akhir","_nama_norm"])
    # map kolom
    ren = {}
    for c in df.columns:
        k = re.sub(r"\s+"," ", str(c).replace("\ufeff","").strip()).lower()
        if   k in {"nama","hakim","ketua"}: new="nama"
        elif k in {"tanggal","tgl"}:        new="tanggal"
        elif k in {"mulai","start","dari"}: new="mulai"
        elif k in {"akhir","end","sampai"}: new="akhir"
        else: new=c
        ren[c]=new
    out = df.rename(columns=ren).copy()

    # dukung format 1 (nama,tanggal) dan format 2 (nama,mulai,akhir)
    if "tanggal" in out.columns:
        out["mulai"] = pd.to_datetime(out["tanggal"], errors="coerce").dt.normalize()
        out["akhir"] = out["mulai"]
    else:
        out["mulai"] = pd.to_datetime(out.get("mulai"), errors="coerce").dt.normalize()
        out["akhir"] = pd.to_datetime(out.get("akhir"), errors="coerce").dt.normalize()

    out["nama"] = out.get("nama","").astype(str).map(str.strip)
    out = out.dropna(subset=["nama","mulai","akhir"]).copy()

    # pastikan mulai<=akhir
    bad = out["mulai"] > out["akhir"]
    out.loc[bad, ["mulai","akhir"]] = out.loc[bad, ["akhir","mulai"]].values

    out["_nama_norm"] = out["nama"].map(_name_key)
    out = out[["_nama_norm","nama","mulai","akhir"]].sort_values(["_nama_norm","mulai","akhir"])
    out = out.reset_index(drop=True)
    return out

def _merge_ranges(df: pd.DataFrame) -> pd.DataFrame:
    """Gabungkan rentang cuti yang overlap/berdempetan per nama."""
    if df.empty: return df
    rows = []
    for _, sub in df.groupby("_nama_norm", sort=True):
        sub = sub.sort_values(["mulai","akhir"]).reset_index(drop=True)
        cur_s, cur_e = None, None
        show_name = sub.iloc[0]["nama"]
        for _, r in sub.iterrows():
            s, e = r["mulai"], r["akhir"]
            if cur_s is None:
                cur_s, cur_e = s, e
            else:
                # gabung kalau overlap atau menempel (e.g. 2025-10-01..02 + 2025-10-03 → digabung jika mau menempel juga)
                if s <= (cur_e + pd.Timedelta(days=1)):
                    cur_e = max(cur_e, e)
                else:
                    rows.append([r["_nama_norm"], show_name, cur_s, cur_e])
                    cur_s, cur_e = s, e
        rows.append([sub.iloc[0]["_nama_norm"], show_name, cur_s, cur_e])
    out = pd.DataFrame(rows, columns=["_nama_norm","nama","mulai","akhir"])
    return out.sort_values(["_nama_norm","mulai","akhir"]).reset_index(drop=True)

def load_cuti() -> pd.DataFrame:
    return _standardize_cuti(_read_csv(CUTI_FILE))

def save_cuti(df: pd.DataFrame):
    df2 = _merge_ranges(_standardize_cuti(df))
    # simpan tanpa kolom helper
    _write_csv(df2[["nama","mulai","akhir"]], CUTI_FILE)

# ---------------- Master Hakim (untuk dropdown) ----------------
hakim_df = _read_csv(HAKIM_FILE)
def _hakim_options() -> list[str]:
    if hakim_df.empty: return []
    df = hakim_df.copy()
    if "aktif" in df.columns:
        def _is_active_value(v):
            s = re.sub(r"[^A-Z0-9]+", "", str(v).strip().upper())
            if s in {"1","YA","Y","TRUE","T","AKTIF","ON"}: return True
            if s in {"0","TIDAK","TDK","NO","N","FALSE","F","NONAKTIF","OFF","NONE","NAN",""}: return False
            try: return float(s) != 0.0
            except Exception: return False
        df = df[df["aktif"].apply(_is_active_value)]
    name_col = "nama" if "nama" in df.columns else df.columns[0]
    names = (
        df[name_col].dropna().astype(str).map(str.strip)
        .replace("", pd.NA).dropna().drop_duplicates().sort_values().tolist()
    )
    return names

# ---------------- Toolbar ----------------
c1, c2, c3 = st.columns([1.2,1.2,1.6])
with c1:
    st.download_button("⬇️ Unduh cuti_hakim.csv",
        data=_read_csv(CUTI_FILE).to_csv(index=False, encoding="utf-8-sig") if CUTI_FILE.exists() else b"",
        file_name="cuti_hakim.csv", mime="text/csv", use_container_width=True)

with c2:
    # template kosong
    tpl = pd.DataFrame({"nama": [], "mulai": [], "akhir": []})
    st.download_button("⬇️ Template kosong",
        data=tpl.to_csv(index=False, encoding="utf-8-sig"),
        file_name="cuti_hakim_template.csv", mime="text/csv", use_container_width=True)

with c3:
    up = st.file_uploader("Impor CSV (akan di-merge otomatis)", type=["csv"], accept_multiple_files=False)
    if up is not None:
        try:
            df_in = pd.read_csv(up, encoding="utf-8-sig")
        except Exception:
            up.seek(0); df_in = pd.read_csv(up)
        base = load_cuti()
        merged = pd.concat([base, _standardize_cuti(df_in)], ignore_index=True)
        save_cuti(merged)
        st.success("Berhasil impor & merge.")
        st.rerun()

st.markdown("---")

# ===================== Loader Hakim (CSV) =====================
BASE_COLS = ["id","nama","hari","aktif","max_per_hari","alias","jabatan","catatan"]

def _ensure_hakim_cols(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    # normalisasi nama kolom umum
    ren = {}
    for c in out.columns:
        k = re.sub(r"\s+", " ", str(c).replace("\ufeff","").strip().lower())
        if k == "id": new="id"
        elif k in {"nama","nama hakim","hakim"}: new="nama"
        elif k in {"hari","hari sidang"}: new="hari"
        elif k in {"aktif","status"}: new="aktif"
        elif k in {"max","max per hari","max_per_hari","maks per hari"}: new="max_per_hari"
        elif k in {"alias"}: new="alias"
        elif k in {"jabatan"}: new="jabatan"
        elif k in {"catatan","keterangan"}: new="catatan"
        else: new=c
        ren[c]=new
    out = out.rename(columns=ren)

    for c in BASE_COLS:
        if c not in out.columns:
            out[c] = 0 if c in {"id","aktif","max_per_hari"} else ""

    # tipe data
    out["id"] = pd.to_numeric(out["id"], errors="coerce").fillna(0).astype(int)
    out["aktif"] = out["aktif"].apply(_is_active_value).astype(int)
    out["max_per_hari"] = pd.to_numeric(out["max_per_hari"], errors="coerce").fillna(0).astype(int)
    for c in ["nama","hari","alias","jabatan","catatan"]:
        out[c] = out[c].astype(str).fillna("").map(lambda s: s.strip())
    # urutkan kolom
    out = out[BASE_COLS]
    return out

def _load_hakim_csv() -> pd.DataFrame:
    df = _read_csv(HAKIM_CSV)
    if df.empty:
        # buat file awal bila belum ada
        df = pd.DataFrame(columns=BASE_COLS)
        _write_csv(df, HAKIM_CSV)
    return _ensure_hakim_cols(df)

def _save_hakim_csv(df: pd.DataFrame):
    _write_csv(_ensure_hakim_cols(df), HAKIM_CSV)
    st.toast("hakim_df.csv tersimpan ✅", icon="✅")

# ===================== Loader Rekap (CSV) =====================
def _load_rekap_csv() -> pd.DataFrame:
    df = _read_csv(REKAP_CSV)
    if df.empty: return pd.DataFrame()
    # standar kolom penting
    if "register" in df.columns and "tgl_register" not in df.columns:
        df = df.rename(columns={"register":"tgl_register"})
    for c in ("tgl_register","tgl_sidang"):
        if c in df.columns:
            df[c] = _to_dt(df[c])
    # pastikan kolom "hakim" ada
    if "hakim" not in df.columns:
        for cand in ["Hakim (Ketua)","ketua","hakim_ketua","nama_hakim"]:
            if cand in df.columns:
                df["hakim"] = df[cand]
                break
    return df

hakim_df = _load_hakim_csv()
rekap_df = _load_rekap_csv()

tab1, tab2, = st.tabs([
    "Data Cuti",
    "Tambah Cuti"
])
with tab1:
    # ---------------- Tabel daftar cuti ----------------
    df = load_cuti()
    st.subheader("Daftar Cuti")
    if df.empty:
        st.info("Belum ada data cuti.")
    else:
        show = df.copy()
        show["mulai"] = pd.to_datetime(show["mulai"]).dt.date
        show["akhir"] = pd.to_datetime(show["akhir"]).dt.date
        show = show[["nama","mulai","akhir"]]

        # render tabel + tombol hapus baris
        COLS = [2.6, 1.2, 1.2, 0.8]
        h = st.columns(COLS)
        h[0].markdown("**Nama**"); h[1].markdown("**Mulai**"); h[2].markdown("**Akhir**"); h[3].markdown("**Aksi**")
        st.markdown("<hr/>", unsafe_allow_html=True)

        idxed = show.reset_index(drop=True)
        for i, r in idxed.iterrows():
            c = st.columns(COLS)
            c[0].write(str(r["nama"]))
            c[1].write(str(r["mulai"]))
            c[2].write(str(r["akhir"]))
            if c[3].button("🗑️", key=f"del_{i}"):
                base = load_cuti()
                # hapus baris yang matching (nama+mulai+akhir)
                m = (
                    (base["nama"].astype(str) == r["nama"]) &
                    (pd.to_datetime(base["mulai"]).dt.normalize() == pd.to_datetime(r["mulai"])) &
                    (pd.to_datetime(base["akhir"]).dt.normalize() == pd.to_datetime(r["akhir"]))
                )
                base = base[~m].reset_index(drop=True)
                save_cuti(base)
                st.success("Baris dihapus."); st.rerun()
with tab2:
    # ---------------- Form tambah cuti ----------------
    left, right = st.columns([2,1])
    with left:
        st.subheader("Tambah Cuti")
        names = _hakim_options()
        pilih_dari_master = st.toggle("Pilih dari master hakim", value=bool(names))
        if pilih_dari_master and names:
            nama = st.selectbox("Nama hakim", names)
        else:
            nama = st.text_input("Nama hakim (ketik)", value="")

        mode = st.radio("Mode input tanggal", ["Satu tanggal", "Rentang tanggal"], horizontal=True)
        if mode == "Satu tanggal":
            t = st.date_input("Tanggal", value=date.today())
            mulai, akhir = pd.to_datetime(t), pd.to_datetime(t)
        else:
            c1, c2 = st.columns(2)
            mulai = c1.date_input("Mulai", value=date.today())
            akhir = c2.date_input("Akhir", value=date.today())
            mulai, akhir = pd.to_datetime(mulai), pd.to_datetime(akhir)
            if akhir < mulai:
                st.warning("Tanggal akhir lebih kecil dari mulai — akan ditukar saat simpan.")

        if st.button("💾 Tambah / Gabungkan", type="primary"):
            if not str(nama).strip():
                st.error("Nama wajib diisi.")
            else:
                cur = load_cuti()
                new = pd.DataFrame([{
                    "nama": str(nama).strip(),
                    "mulai": mulai.normalize(),
                    "akhir": akhir.normalize()
                }])
                merged = pd.concat([cur, new], ignore_index=True)
                save_cuti(merged)
                st.success("Ditambahkan & digabung jika perlu.")
                st.rerun()

    with right:
        st.subheader("Info")
        st.caption(f"File: `{CUTI_FILE.as_posix()}`")
        if hakim_df.empty:
            st.info("Master hakim (data/hakim_df.csv) kosong — masih bisa ketik manual.")

    st.markdown("---")