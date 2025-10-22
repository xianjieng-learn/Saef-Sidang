# pages/3d_🧞‍♂️_Data_JS_Ghoib.py
from __future__ import annotations
import io, re
from pathlib import Path
from typing import Optional, Dict

import pandas as pd
import streamlit as st

st.set_page_config(page_title="🧞‍♂️ Data JS Ghoib", layout="wide")
st.header("🧞‍♂️ Data Jurusita (GHOIB) — CSV Only")

# ───────────────────────── Paths (CSV) ─────────────────────────
DATA_DIR = Path("data"); DATA_DIR.mkdir(parents=True, exist_ok=True)
JS_FILE     = DATA_DIR / "js_ghoib.csv"      # source of truth
MIRROR_FILE = DATA_DIR / "js_ghoib_df.csv"   # mirror opsional

# ───────────────────────── Helpers ─────────────────────────
def _is_active_value(v) -> bool:
    s = re.sub(r"[^A-Z0-9]+", "", str(v).strip().upper())
    if s in {"1","YA","Y","TRUE","T","AKTIF","ON"}: return True
    if s in {"0","TIDAK","TDK","NO","N","FALSE","F","NONAKTIF","OFF","NONE","NAN",""}: return False
    try: return float(s) != 0.0
    except Exception: return False

def _safe_int(x) -> int:
    try:
        if pd.isna(x): return 0
    except Exception: ...
    try: return int(float(str(x).strip()))
    except Exception: return 0

def _has_rows(df: Optional[pd.DataFrame]) -> bool:
    return isinstance(df, pd.DataFrame) and not df.empty and len(df.dropna(how="all")) > 0

def _norm_name(s: str) -> str:
    return re.sub(r"\s+", " ", str(s or "").strip().lower())

def _read_csv_any(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    for enc in ("utf-8-sig", "utf-8", "cp1252"):
        try:
            return pd.read_csv(path, encoding=enc)
        except Exception:
            continue
    return pd.read_csv(path)

def _write_csv_atomic(df: pd.DataFrame, path: Path):
    tmp = path.with_suffix(".tmp.csv")
    df.to_csv(tmp, index=False, encoding="utf-8-sig")
    tmp.replace(path)

# ───────────────────────── Standarisasi kolom ─────────────────────────
# Kolom utama CSV:
#   nama (str), aktif (0/1), jml_ghoib (int), catatan (str), alias (str)
JS_COLS = ["nama", "aktif", "jml_ghoib", "catatan", "alias"]

def _standardize_input_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Map kolom import → ['nama','aktif','jml_ghoib','catatan','alias'] (+id jika ada, diabaikan)."""
    if df is None or df.empty:
        return pd.DataFrame(columns=["nama","aktif","jml_ghoib","catatan","alias"])

    # --- rename kolom ke standar ---
    rename_map: Dict[str, str] = {}
    for c in list(df.columns):
        raw = str(c).replace("\ufeff","").strip()
        k = re.sub(r"\s+", " ", raw).strip().lower().replace("_"," ")
        if   k in {"nama","name"}:                          new = "nama"
        elif k in {"aktif","status","active","is active"}:  new = "aktif"
        elif k in {"total ghoib","jml_ghoib","ghoib","beban","beban ghoib"}:
            new = "jml_ghoib"
        elif k in {"catatan","keterangan","note","notes"}:  new = "catatan"
        elif k in {"alias","a.k.a","aka"}:                  new = "alias"
        elif k in {"id"}:                                   new = "id"
        else:                                               new = raw
        rename_map[c] = new
    out = df.rename(columns=rename_map).copy()

    # --- pilih kolom yang dipakai ---
    keep = [c for c in ["id","nama","aktif","jml_ghoib","catatan","alias"] if c in out.columns]
    out = out[keep] if keep else pd.DataFrame(columns=["nama","aktif","jml_ghoib","catatan","alias"])

    # --- normalisasi isi ---
    # nama
    if "nama" not in out.columns:
        out["nama"] = ""
    out["nama"] = out["nama"].astype(str).str.strip()
    out = out[out["nama"] != ""].copy()

    # aktif (default 1) → bool-int 0/1
    if "aktif" in out.columns:
        # buat Series default 1 untuk nilai NaN
        out["aktif"] = out["aktif"].apply(lambda v: 1 if _is_active_value(v) else 0)
    else:
        out["aktif"] = 1

    # jml_ghoib (default 0) → int
    if "jml_ghoib" in out.columns:
        out["jml_ghoib"] = pd.to_numeric(out["jml_ghoib"], errors="coerce").fillna(0).astype(int)
    else:
        out["jml_ghoib"] = 0

    # catatan & alias
    for c in ["catatan","alias"]:
        if c in out.columns:
            out[c] = out[c].astype(str).str.strip()
        else:
            out[c] = ""

    # susun kolom final
    out = out[["nama","aktif","jml_ghoib","catatan","alias"]].reset_index(drop=True)
    return out

# ───────────────────────── CRUD CSV ─────────────────────────
def load_js() -> pd.DataFrame:
    df = _read_csv_any(JS_FILE)
    if df.empty:
        return pd.DataFrame(columns=JS_COLS)
    df = _standardize_input_columns(df)
    return df

def save_js(df: pd.DataFrame):
    df2 = _standardize_input_columns(df)
    # urut alfabet agar stabil
    df2 = df2.sort_values(["aktif","jml_ghoib","nama"], ascending=[False, True, True], kind="stable").reset_index(drop=True)
    _write_csv_atomic(df2, JS_FILE)
    try:
        _write_csv_atomic(df2, MIRROR_FILE)
    except Exception:
        pass

def upsert_by_nama(nama: str, aktif: int, jml_ghoib: int, catatan: str, alias: str):
    df = load_js()
    mask = df["nama"].str.casefold() == str(nama).strip().casefold()
    row = {
        "nama": nama.strip(),
        "aktif": 1 if _is_active_value(aktif) else 0,
        "jml_ghoib": _safe_int(jml_ghoib),
        "catatan": str(catatan or "").strip(),
        "alias": str(alias or "").strip(),
    }
    if mask.any():
        i = mask[mask].index[0]
        for k,v in row.items():
            df.loc[i, k] = v
    else:
        df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    save_js(df)

def update_by_index(idx: int, nama: str, aktif: int, jml_ghoib: int, catatan: str, alias: str):
    df = load_js()
    if 0 <= idx < len(df):
        df.loc[idx, ["nama","aktif","jml_ghoib","catatan","alias"]] = [
            nama.strip(), 1 if _is_active_value(aktif) else 0, _safe_int(jml_ghoib), catatan.strip(), alias.strip()
        ]
        save_js(df)

def delete_by_index(idx: int):
    df = load_js()
    if 0 <= idx < len(df):
        df = df.drop(index=idx).reset_index(drop=True)
        save_js(df)

def replace_all(df_in: pd.DataFrame):
    save_js(df_in)

def upsert_bulk(df_in: pd.DataFrame):
    df_std = _standardize_input_columns(df_in)
    if df_std.empty: return
    base = load_js()
    for _, r in df_std.iterrows():
        upsert_by_nama(
            str(r.get("nama","")),
            int(r.get("aktif",1)),
            _safe_int(r.get("jml_ghoib",0)),
            str(r.get("catatan","")),
            str(r.get("alias","")),
        )

# ───────────────────────── Rekomendasi Otomatis (hanya dari CSV) ─────────────────────────
def choose_js_ghoib_csv(use_aktif: bool = True) -> tuple[str, dict]:
    """
    Pilih JS Ghoib otomatis berbasis js_ghoib.csv:
      - kandidat dari CSV (filter aktif bila use_aktif=True)
      - beban = kolom jml_ghoib
      - tie-break alfabet.
    """
    master = load_js()
    if master.empty:
        return "", {"candidates": [], "reason": "js_ghoib.csv kosong."}

    if use_aktif:
        master = master[master["aktif"].apply(_is_active_value)]

    candidates = master[["nama","jml_ghoib"]].copy()
    if candidates.empty:
        return "", {"candidates": [], "reason": "Tidak ada kandidat aktif."}

    pairs = [(r["nama"], _safe_int(r["jml_ghoib"])) for _, r in candidates.iterrows()]
    pairs.sort(key=lambda x: (x[1], x[0].lower()))  # beban kecil dulu; seri → alfabet
    pick = pairs[0][0] if pairs else ""
    debug = {"candidates": [p[0] for p in pairs], "sorted": pairs, "reason": "Memilih jml_ghoib terkecil (tie → alfabet)."}
    return pick, debug

# ───────────────────────── Lokasi Penyimpanan ─────────────────────────
with st.expander("ℹ️ Lokasi Penyimpanan", expanded=False):
    st.write("**CSV utama:**", str(JS_FILE))
    st.write("**Mirror CSV (opsional):**", str(MIRROR_FILE))

# ───────────────────────── Toolbar ─────────────────────────
c1, c2, c3, c4 = st.columns([1.3,1.5,1.8,1.4])
with c1:
    if st.button("➕ Tambah JS Ghoib", use_container_width=True):
        st.session_state["jsg_dialog"] = {"open": True, "mode": "add", "payload": {}}
with c2:
    if st.button("⬇️ Export Mirror (CSV)", use_container_width=True):
        df = load_js()
        if _has_rows(df):
            _write_csv_atomic(df, MIRROR_FILE)
            st.success(f"Mirror ditulis: {MIRROR_FILE.name}")
        else:
            st.warning("CSV utama kosong, tidak ada yang diekspor.")
with c3:
    up_file = st.file_uploader("Upload CSV", type=["csv"], label_visibility="collapsed")
with c4:
    mode = st.radio("Mode import", ["Upsert", "Replace"], horizontal=True, label_visibility="collapsed")

if up_file is not None:
    try:
        raw = up_file.read()
        df_in = pd.read_csv(io.BytesIO(raw), encoding="utf-8-sig")
    except Exception:
        up_file.seek(0); df_in = pd.read_csv(up_file)
    df_std = _standardize_input_columns(df_in)
    st.caption("Preview import (maks 200 baris):")
    st.dataframe(df_std.head(200), use_container_width=True, hide_index=True)
    if not df_std.empty and st.button("🚀 Jalankan Import", type="primary"):
        if mode == "Replace":
            replace_all(df_std); st.success(f"Replace {len(df_std)} baris.")
        else:
            upsert_bulk(df_std); st.success(f"Upsert {len(df_std)} baris.")
        st.rerun()

st.markdown("---")

# ───────────────────────── Rekomendasi Otomatis + Debug ─────────────────────────
colA, colB = st.columns([1.6, 2.4])
pick, dbg = choose_js_ghoib_csv(use_aktif=True)
with colA:
    st.markdown("#### 🔮 Rekomendasi JS untuk perkara **GHOIB** (berdasarkan *jml_ghoib* di CSV)")
    if pick:
        beban_now = next((b for (n,b) in dbg.get("sorted", []) if n == pick), 0)
        st.success(f"Auto-pick: **{pick}** (jml_ghoib: {beban_now})")
    else:
        st.warning("Belum ada kandidat aktif di **js_ghoib.csv**.")

with colB:
    if dbg.get("sorted"):
        rank_df = pd.DataFrame(dbg["sorted"], columns=["Nama", "Total GHOIB"])
        st.dataframe(rank_df, use_container_width=True, hide_index=True)
    with st.expander("Debug detail"):
        st.write(dbg)

st.markdown("---")

# ───────────────────────── Dialog Tambah/Edit/Hapus (CSV) ─────────────────────────
if "jsg_dialog" not in st.session_state:
    st.session_state["jsg_dialog"] = {"open": False, "mode": "", "payload": {}}

def _open_dialog(mode: str, payload: dict | None = None):
    st.session_state["jsg_dialog"] = {"open": True, "mode": mode, "payload": payload or {}}

def _render_dialog(current_df: pd.DataFrame):
    dlg = st.session_state.get("jsg_dialog", {"open": False})
    if not dlg.get("open"): return
    mode = dlg.get("mode"); payload = dlg.get("payload", {}) or {}

    row_idx = None; nama_init=""; aktif_init=True; alias_init=""; cat_init=""; tot_init=0
    if mode == "edit" and _has_rows(current_df):
        i = int(payload.get("index", 0))
        r = current_df.reset_index(drop=True).iloc[i]
        row_idx = i
        nama_init = str(r.get("nama",""))
        aktif_init = _is_active_value(r.get("aktif",1))
        alias_init = str(r.get("alias",""))
        cat_init = str(r.get("catatan",""))
        tot_init = _safe_int(r.get("jml_ghoib", 0))

    with st.form("jsg_form"):
        st.subheader("Edit JS Ghoib" if (mode=="edit" and row_idx is not None) else "Tambah JS Ghoib")
        nama  = st.text_input("Nama", value=nama_init)
        aktif = st.checkbox("Aktif", value=aktif_init)
        total = st.number_input("Total GHOIB", min_value=0, step=1, value=int(tot_init))
        alias = st.text_area("Alias (opsional, pisahkan ;)", value=alias_init, height=70)
        catatan = st.text_area("Catatan", value=cat_init, height=70)

        c1, c2, c3 = st.columns(3)
        sbtn = c1.form_submit_button("💾 Simpan", use_container_width=True)
        cbtn = c2.form_submit_button("Batal", use_container_width=True)
        del_confirm = c3.checkbox("Konfirmasi hapus", value=False)
        dbtn = c3.form_submit_button("🗑️ Hapus", use_container_width=True,
                                     disabled=not (mode=="edit" and row_idx is not None and del_confirm))

        if sbtn:
            if not nama.strip():
                st.error("Nama wajib diisi.")
            else:
                if mode == "edit" and row_idx is not None:
                    update_by_index(int(row_idx), nama, 1 if aktif else 0, int(total), catatan, alias)
                else:
                    upsert_by_nama(nama, 1 if aktif else 0, int(total), catatan, alias)
                st.session_state["jsg_dialog"]["open"] = False
                st.success("Tersimpan ✅"); st.rerun()

        if dbtn and mode == "edit" and row_idx is not None and del_confirm:
            delete_by_index(int(row_idx))
            st.session_state["jsg_dialog"]["open"] = False
            st.success("Dihapus 🗑️"); st.rerun()

        if cbtn and not sbtn and not dbtn:
            st.session_state["jsg_dialog"]["open"] = False
            st.info("Dibatalkan."); st.rerun()

# ───────────────────────── Tabel Utama (CSV) — sesuai js_ghoib.csv ─────────────────────────
df = load_js()

if not _has_rows(df):
    st.warning("Belum ada data JS Ghoib. Klik **➕ Tambah** atau upload CSV.")
else:
    # tampilkan hanya kolom yang ada di CSV utama
    cols_csv = ["nama","aktif","jml_ghoib","catatan","alias"]
    view = df.copy()
    for c in cols_csv:
        if c not in view.columns:
            view[c] = 0 if c in {"aktif","jml_ghoib"} else ""
    view = view[cols_csv].reset_index(drop=True)

    # Header + kolom aksi
    COLS = [2.6, 0.9, 3.0, 1.5]  # terakhir = Aksi
    h = st.columns(COLS)
    h[0].markdown("**Nama**")
    h[1].markdown("**Aktif**")
    h[2].markdown("**Jumlah Ghoib**")
    h[3].markdown("**Aksi**")
    st.markdown("<hr/>", unsafe_allow_html=True)

    for i, r in view.iterrows():
        cols = st.columns(COLS)
        cols[0].write(str(r["nama"]))
        cols[1].write(int(r["aktif"]))          # tampilkan persis nilai CSV (0/1)
        cols[2].write(int(r["jml_ghoib"]))

        with cols[3]:
            cA, cB = st.columns(2)
            if cA.button("✏️", key=f"edit_{i}"):
                _open_dialog("edit", {"index": int(i)}); st.rerun()
            if cB.button("🗑️", key=f"del_{i}"):
                _open_dialog("edit", {"index": int(i)})
                st.warning("Centang 'Konfirmasi hapus' lalu klik 🗑️ Hapus.")
                st.rerun()

# ────────── Render dialog kalau terbuka ──────────
if st.session_state.get("jsg_dialog", {}).get("open"):
    _render_dialog(df)
