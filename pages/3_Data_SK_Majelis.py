# pages/3d_📝_Data_SK_Majelis.py
import streamlit as st
import pandas as pd
import re
import math
from pathlib import Path
from typing import Optional, List
from app_core.login import _ensure_auth  
# --- Hilangkan impor DB ---
# from db import get_conn, init_db     # (hapus)
from app_core.exports import export_csv

st.set_page_config(page_title="Data: SK Majelis", layout="wide")
st.header("📝 Data SK Majelis")

# ==================== Config path CSV ====================
DATA_DIR = Path("data")
DATA_DIR.mkdir(parents=True, exist_ok=True)

SK_CSV      = DATA_DIR / "sk_majelis.csv"  # source of truth
SK_DF_CSV   = DATA_DIR / "sk_df.csv"       # mirror (opsional)
HAKIM_CSV   = DATA_DIR / "hakim.csv"
PP_CSV      = DATA_DIR / "pp.csv"
JS_CSV      = DATA_DIR / "js.csv"

st.caption(f"📄 Sumber data: `{SK_CSV}`")

# ==================== Utils umum ====================
def _is_active_value(v) -> bool:
    s = str(v).replace("\ufeff","").strip().upper()
    if s in {"1","YA","Y","TRUE","T","AKTIF","ON"}: return True
    if s in {"0","TIDAK","TDK","NO","N","FALSE","F","NONAKTIF","OFF","NONE","NAN",""}: return False
    try: return float(s) != 0.0
    except Exception: return False

def _to_int(v, default=0) -> int:
    try:
        if pd.isna(v): return default
    except Exception:
        pass
    try: return int(v)
    except Exception:
        try: return int(float(str(v).strip()))
        except Exception: return default

def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    for enc in ["utf-8-sig","utf-8","cp1252"]:
        try:
            return pd.read_csv(path, encoding=enc)
        except Exception:
            continue
    return pd.read_csv(path)

def _write_csv_atomic(df: pd.DataFrame, path: Path):
    tmp = path.with_suffix(".tmp.csv")
    df.to_csv(tmp, index=False, encoding="utf-8-sig")
    tmp.replace(path)

# ==================== SK Majelis: load/save/upsert ====================
SK_COLS = ["id","majelis","hari","ketua","anggota1","anggota2","pp1","pp2","js1","js2","aktif","catatan"]

def _normalize_sk_df(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        out = pd.DataFrame(columns=SK_COLS)
    else:
        out = df.copy()
        # bersihkan header BOM dan spasi
        out.columns = [str(c).replace("\ufeff","").strip() for c in out.columns]
        # pastikan semua kolom ada
        for c in SK_COLS:
            if c not in out.columns:
                out[c] = "" if c != "aktif" else 1
        # strip object cols
        for c in out.columns:
            if out[c].dtype == object:
                out[c] = out[c].astype(str).map(lambda s: s.replace("\ufeff","").strip())
        # id -> int, aktif -> int 0/1
        out["id"] = pd.to_numeric(out["id"], errors="coerce").fillna(0).astype(int)
        out["aktif"] = out["aktif"].apply(lambda x: 1 if _is_active_value(x) else 0)
        out = out[SK_COLS]
    # generate id kalau belum ada / nol
    if out.empty:
        return out
    max_id = int(pd.to_numeric(out["id"], errors="coerce").fillna(0).max())
    need_id_mask = (out["id"] == 0)
    if need_id_mask.any():
        count = need_id_mask.sum()
        new_ids = range(max_id+1, max_id+1+count)
        out.loc[need_id_mask, "id"] = list(new_ids)
    return out

def load_sk() -> pd.DataFrame:
    return _normalize_sk_df(_read_csv(SK_CSV))

def save_sk(df: pd.DataFrame):
    df2 = _normalize_sk_df(df)
    _write_csv_atomic(df2, SK_CSV)
    # mirror (opsional)
    try:
        export_csv(df2, SK_DF_CSV.name)
        export_csv(df2, "sk_majelis.csv")
        export_csv(df2, "sk_df.csv")
    except Exception:
        # fallback manual
        _write_csv_atomic(df2, SK_DF_CSV)

def export_sk_csv():
    try:
        df = load_sk().copy()
        export_csv(df, "sk_df.csv")
        export_csv(df, "sk_majelis.csv")
        st.toast("sk_df.csv & sk_majelis.csv diperbarui ✅", icon="✅")
    except Exception as e:
        st.warning(f"Gagal export SK: {e}")

def find_sk_id_by_majelis(df: pd.DataFrame, majelis: str) -> Optional[int]:
    if not majelis: return None
    m = df.loc[df["majelis"].astype(str) == str(majelis)]
    if m.empty: return None
    return int(pd.to_numeric(m["id"], errors="coerce").dropna().iloc[0]) if "id" in m.columns else None

def find_sk_id_by_ketua_hari(df: pd.DataFrame, ketua: str, hari: str) -> Optional[int]:
    if not ketua: return None
    if hari:
        m = df.loc[(df["ketua"].astype(str)==str(ketua)) & (df["hari"].astype(str)==str(hari))]
        if not m.empty:
            return int(pd.to_numeric(m["id"], errors="coerce").dropna().iloc[0])
    m2 = df.loc[df["ketua"].astype(str)==str(ketua)]
    if not m2.empty:
        return int(pd.to_numeric(m2["id"], errors="coerce").dropna().iloc[0])
    return None

def insert_sk_row(df: pd.DataFrame, majelis, hari, ketua, a1, a2, pp1, pp2, js1, js2, aktif, catatan):
    next_id = (int(df["id"].max()) + 1) if not df.empty else 1
    new = {
        "id": next_id,
        "majelis": str(majelis or "").strip(),
        "hari": str(hari or "").strip(),
        "ketua": str(ketua or "").strip(),
        "anggota1": str(a1 or "").strip(),
        "anggota2": str(a2 or "").strip(),
        "pp1": str(pp1 or "").strip(),
        "pp2": str(pp2 or "").strip(),
        "js1": str(js1 or "").strip(),
        "js2": str(js2 or "").strip(),
        "aktif": 1 if _is_active_value(aktif) else 0,
        "catatan": str(catatan or "").strip(),
    }
    return pd.concat([df, pd.DataFrame([new])], ignore_index=True)

def update_sk_by_id(df: pd.DataFrame, row_id: int, majelis, hari, ketua, a1, a2, pp1, pp2, js1, js2, aktif, catatan):
    idx = df.index[df["id"]==int(row_id)]
    if len(idx)==0: return df
    i = idx[0]
    df.loc[i, ["majelis","hari","ketua","anggota1","anggota2","pp1","pp2","js1","js2","aktif","catatan"]] = [
        str(majelis or "").strip(),
        str(hari or "").strip(),
        str(ketua or "").strip(),
        str(a1 or "").strip(),
        str(a2 or "").strip(),
        str(pp1 or "").strip(),
        str(pp2 or "").strip(),
        str(js1 or "").strip(),
        str(js2 or "").strip(),
        1 if _is_active_value(aktif) else 0,
        str(catatan or "").strip(),
    ]
    return df

def delete_sk_by_id(df: pd.DataFrame, row_id: int):
    return df.loc[df["id"]!=int(row_id)].reset_index(drop=True)

def upsert_sk(key_mode: str, majelis, hari, ketua, a1, a2, pp1, pp2, js1, js2, aktif, catatan):
    """key_mode: 'majelis' atau 'ketua_hari'; operasi langsung ke CSV."""
    df = load_sk()
    if key_mode == "majelis":
        rid = find_sk_id_by_majelis(df, majelis)
    else:
        rid = find_sk_id_by_ketua_hari(df, ketua, hari)
    if rid:
        df = update_sk_by_id(df, rid, majelis, hari, ketua, a1, a2, pp1, pp2, js1, js2, aktif, catatan)
        save_sk(df)
        return "updated"
    else:
        df = insert_sk_row(df, majelis, hari, ketua, a1, a2, pp1, pp2, js1, js2, aktif, catatan)
        save_sk(df)
        return "inserted"

# ==================== Sumber dropdown (dari CSV) ====================
def _read_names_from_csv(path: Path, nama_col="nama", aktif_col="aktif") -> List[str]:
    df = _read_csv(path)
    if df.empty: return []
    # deteksi kolom nama
    if nama_col not in df.columns:
        for c in df.columns:
            if re.sub(r"\W+","",str(c).lower()) == "nama":
                nama_col = c; break
        if nama_col not in df.columns:
            return []
    # filter aktif (kalau ada)
    if aktif_col in df.columns:
        ok = df[aktif_col].apply(_is_active_value)
        df = df.loc[ok]
    names = (
        df[nama_col]
        .astype(str).fillna("").map(lambda s: s.strip())
        .replace("", pd.NA).dropna().drop_duplicates().sort_values().tolist()
    )
    return names

def _with_blank(opts: List[str]) -> List[str]:
    return [""] + (opts or [])

HAKIM_OPTS = _with_blank(_read_names_from_csv(HAKIM_CSV, "nama", "aktif"))
PP_OPTS    = _with_blank(_read_names_from_csv(PP_CSV, "nama", "aktif"))
JS_OPTS    = _with_blank(_read_names_from_csv(JS_CSV, "nama", "aktif"))
HARI_OPTS  = ["", "Senin", "Selasa", "Rabu", "Kamis", "Jumat"]

# ==================== Dialog Tambah/Edit ====================
if "sk_dialog" not in st.session_state:
    st.session_state["sk_dialog"] = {"open": False, "mode": "", "payload": {}}

def open_sk_dialog(mode: str, payload: dict | None = None):
    st.session_state["sk_dialog"] = {"open": True, "mode": mode, "payload": payload or {}}

def render_sk_dialog(current_df: pd.DataFrame):
    dlg = st.session_state.get("sk_dialog", {"open": False})
    if not dlg.get("open"): return
    mode = dlg.get("mode")
    payload = dlg.get("payload", {}) or {}

    if mode == "edit" and not current_df.empty:
        idx = int(payload.get("index", 0))
        row = current_df.reset_index(drop=True).iloc[idx]
        rid = _to_int(row.get("id"))
        init = {k: str(row.get(k,"") or "") for k in
                ["majelis","hari","ketua","anggota1","anggota2","pp1","pp2","js1","js2","catatan"]}
        aktif_init = _is_active_value(row.get("aktif",1))
    else:
        rid = None
        init = {k:"" for k in ["majelis","hari","ketua","anggota1","anggota2","pp1","pp2","js1","js2","catatan"]}
        aktif_init = True

    with st.form("sk_edit_form", clear_on_submit=False):
        st.subheader("Edit SK Majelis" if mode=="edit" else "Tambah SK Majelis")
        majelis = st.text_input("Majelis", value=init["majelis"])
        hari    = st.selectbox("Hari", options=HARI_OPTS, index=HARI_OPTS.index(init["hari"]) if init["hari"] in HARI_OPTS else 0)

        ketua  = st.selectbox("Ketua (Hakim)", options=HAKIM_OPTS,
                              index=HAKIM_OPTS.index(init["ketua"]) if init["ketua"] in HAKIM_OPTS else 0)
        c1, c2 = st.columns(2)
        with c1:
            a1  = st.selectbox("Anggota 1 (Hakim)", options=HAKIM_OPTS,
                               index=HAKIM_OPTS.index(init["anggota1"]) if init["anggota1"] in HAKIM_OPTS else 0)
            pp1 = st.selectbox("PP 1", options=PP_OPTS,
                               index=PP_OPTS.index(init["pp1"]) if init["pp1"] in PP_OPTS else 0)
            js1 = st.selectbox("JS 1", options=JS_OPTS,
                               index=JS_OPTS.index(init["js1"]) if init["js1"] in JS_OPTS else 0)
        with c2:
            a2  = st.selectbox("Anggota 2 (Hakim)", options=HAKIM_OPTS,
                               index=HAKIM_OPTS.index(init["anggota2"]) if init["anggota2"] in HAKIM_OPTS else 0)
            pp2 = st.selectbox("PP 2", options=PP_OPTS,
                               index=PP_OPTS.index(init["pp2"]) if init["pp2"] in PP_OPTS else 0)
            js2 = st.selectbox("JS 2", options=JS_OPTS,
                               index=JS_OPTS.index(init["js2"]) if init["js2"] in JS_OPTS else 0)

        aktif  = st.checkbox("Aktif", value=aktif_init)
        catatan= st.text_area("Catatan", value=init["catatan"], height=70)

        b1, b2, b3 = st.columns([1,1,1])
        with b1:
            sbtn = st.form_submit_button("💾 Simpan", width="stretch")
        with b2:
            cbtn = st.form_submit_button("Batal", width="stretch")
        with b3:
            dbtn = st.form_submit_button("🗑️ Hapus", width="stretch") if (mode=="edit" and rid) else None

        if sbtn:
            if not ketua.strip():
                st.error("Ketua wajib diisi.")
            else:
                if mode=="edit" and rid:
                    df = load_sk()
                    df = update_sk_by_id(df, rid, majelis.strip(), hari.strip(), ketua.strip(),
                                         a1.strip(), a2.strip(), pp1.strip(), pp2.strip(),
                                         js1.strip(), js2.strip(), 1 if aktif else 0, catatan.strip())
                    save_sk(df)
                else:
                    df = load_sk()
                    df = insert_sk_row(df, majelis.strip(), hari.strip(), ketua.strip(),
                                       a1.strip(), a2.strip(), pp1.strip(), pp2.strip(),
                                       js1.strip(), js2.strip(), 1 if aktif else 0, catatan.strip())
                    save_sk(df)
                export_sk_csv()
                st.session_state["sk_dialog"]["open"] = False
                st.success("Tersimpan ✅"); st.rerun()

        if dbtn and (mode=="edit" and rid):
            df = load_sk()
            df = delete_sk_by_id(df, rid)
            save_sk(df)
            export_sk_csv()
            st.session_state["sk_dialog"]["open"] = False
            st.success("Dihapus 🗑️"); st.rerun()

        if cbtn and not sbtn and not dbtn:
            st.session_state["sk_dialog"]["open"] = False
            st.info("Dibatalkan."); st.rerun()

# ==================== Toolbar ====================
t1, t2, t3 = st.columns([1,1,1])
with t1:
    if st.button("🔄 Refresh dari CSV", width="stretch"):
        st.rerun()
with t2:
    if st.button("➕ Tambah Baris SK", width="stretch"):
        open_sk_dialog("add", {})
with t3:
    if st.button("⬇️ Export CSV (sinkron)", width="stretch"):
        export_sk_csv()

# ==================== Import CSV → SK (upsert ke file) ====================
with st.expander("📥 Import CSV → SK (CSV only)", expanded=False):
    st.write("Unggah CSV dengan kolom: **majelis, hari, ketua, anggota1, anggota2, pp1, pp2, js1, js2, aktif, catatan** (sebagian opsional).")
    up = st.file_uploader("Pilih CSV", type=["csv"], key="sk_csv_up")

    def _std_cols(df: pd.DataFrame) -> pd.DataFrame:
        if df.empty: return df
        ren = {}
        for c in df.columns:
            raw = str(c).replace("\ufeff","").strip()
            k = re.sub(r"\s+", " ", raw).lower().replace("_", " ")
            if   k in {"majelis","nama majelis","majelis ruang sidang","majelis rs"}: new = "majelis"
            elif k in {"hari","hari sidang","hari sk"}:                               new = "hari"
            elif k in {"ketua","hakim ketua","ketua majelis"}:                        new = "ketua"
            elif k in {"anggota1","anggota 1","a1","anggota i"}:                      new = "anggota1"
            elif k in {"anggota2","anggota 2","a2","anggota ii"}:                     new = "anggota2"
            elif k in {"pp1","panitera pengganti 1","panitera 1"}:                    new = "pp1"
            elif k in {"pp2","panitera pengganti 2","panitera 2"}:                    new = "pp2"
            elif k in {"js1","jurusita 1"}:                                           new = "js1"
            elif k in {"js2","jurusita 2"}:                                           new = "js2"
            elif k in {"aktif","status"}:                                             new = "aktif"
            elif k in {"catatan","keterangan"}:                                       new = "catatan"
            else:                                                                      new = raw
            ren[c] = new
        out = df.rename(columns=ren).copy()
        for c in out.columns:
            if out[c].dtype == object:
                out[c] = out[c].astype(str).map(lambda s: s.replace("\ufeff","").strip())
        return out

    df_src = _std_cols(pd.read_csv(up)) if up else pd.DataFrame()
    if not df_src.empty:
        st.caption("Preview CSV (maks 30 baris)")
        st.dataframe(df_src.head(30), width="stretch")

        target_cols = ["majelis","hari","ketua","anggota1","anggota2","pp1","pp2","js1","js2","aktif","catatan"]
        cols = ["— none —"] + list(df_src.columns)
        def pick(label, default):
            default_val = default if default in df_src.columns else "— none —"
            return st.selectbox(label, cols, index=cols.index(default_val))

        st.markdown("**Pemetaan Kolom**")
        c1, c2 = st.columns(2)
        with c1:
            map_majelis = pick("majelis",  "majelis")
            map_hari    = pick("hari",     "hari")
            map_ketua   = pick("ketua *",  "ketua")
            map_a1      = pick("anggota1", "anggota1")
            map_a2      = pick("anggota2", "anggota2")
        with c2:
            map_pp1     = pick("pp1",      "pp1")
            map_pp2     = pick("pp2",      "pp2")
            map_js1     = pick("js1",      "js1")
            map_js2     = pick("js2",      "js2")
            map_aktif   = pick("aktif",    "aktif")
            map_catatan = pick("catatan",  "catatan")

        key_mode = st.radio(
            "Kunci upsert", ["majelis","ketua_hari"], horizontal=True,
            help="Pilih 'majelis' jika kolom majelis unik. Jika tidak, gunakan pasangan (ketua,hari)."
        )

        mapped = pd.DataFrame({
            "majelis":  df_src[map_majelis] if map_majelis  != "— none —" else "",
            "hari":     df_src[map_hari]    if map_hari     != "— none —" else "",
            "ketua":    df_src[map_ketua]   if map_ketua    != "— none —" else "",
            "anggota1": df_src[map_a1]      if map_a1       != "— none —" else "",
            "anggota2": df_src[map_a2]      if map_a2       != "— none —" else "",
            "pp1":      df_src[map_pp1]     if map_pp1      != "— none —" else "",
            "pp2":      df_src[map_pp2]     if map_pp2      != "— none —" else "",
            "js1":      df_src[map_js1]     if map_js1      != "— none —" else "",
            "js2":      df_src[map_js2]     if map_js2      != "— none —" else "",
            "aktif":    df_src[map_aktif]   if map_aktif    != "— none —" else "",
            "catatan":  df_src[map_catatan] if map_catatan  != "— none —" else "",
        }).copy()

        for c in mapped.columns:
            mapped[c] = mapped[c].astype(str).fillna("").str.strip()
        mapped["_aktif_int"] = mapped["aktif"].map(lambda x: 1 if _is_active_value(x) else 0)

        # buang baris header nyasar
        mask_header = (
            (mapped["majelis"].str.lower()=="majelis") &
            (mapped["hari"].str.lower()=="hari") &
            (mapped["ketua"].str.lower()=="ketua")
        )
        mapped = mapped[~mask_header].reset_index(drop=True)

        st.caption("Mapping hasil (cek dulu sebelum impor, 10 baris teratas):")
        st.dataframe(mapped.head(10), width="stretch")

        if st.button("🚀 Impor ke CSV (Upsert)", type="primary", width="stretch"):
            if map_ketua == "— none —":
                st.error("Kolom **ketua** wajib diisi/mapped.")
            else:
                df = load_sk()
                inserted = updated = skipped = 0
                for _, r in mapped.iterrows():
                    ketua = r["ketua"]
                    if not ketua:
                        skipped += 1
                        continue
                    status = upsert_sk(
                        key_mode,
                        r["majelis"], r["hari"], r["ketua"], r["anggota1"], r["anggota2"],
                        r["pp1"], r["pp2"], r["js1"], r["js2"],
                        int(r["_aktif_int"]), r["catatan"]
                    )
                    if status == "inserted": inserted += 1
                    else: updated += 1
                export_sk_csv()
                st.success(f"Selesai impor: INSERTED={inserted}, UPDATED={updated}, SKIPPED={skipped}")
                st.rerun()

# ==================== Tabel utama (Edit/Hapus) ====================
def _normalize_view(df: pd.DataFrame) -> pd.DataFrame:
    for c in SK_COLS:
        if c not in df.columns: df[c] = "" if c != "aktif" else 1
    out = df[SK_COLS].copy()
    out["aktif_bool"] = out["aktif"].apply(_is_active_value)
    return out

raw = load_sk()
# jaga-jaga: kalau ada mirror lama
try:
    if raw.empty and SK_DF_CSV.exists():
        raw = _normalize_sk_df(_read_csv(SK_DF_CSV))
except Exception:
    pass

view = _normalize_view(raw)

# Filter & sort
st.markdown("---")
f1, f2, f3, f4 = st.columns([1.6, 0.8, 1.2, 0.8])
with f1:
    q = st.text_input("🔎 Cari (majelis/hari/ketua/anggota/PP/JS)", "")
with f2:
    only_active = st.toggle("Hanya aktif", value=False)
with f3:
    sort_by = st.selectbox("Urutkan", ["(tanpa urut)", "Majelis", "Hari", "Ketua", "Aktif%s"])
with f4:
    asc = st.toggle("Naik%s", value=True)

if q.strip():
    ks = q.strip().lower()
    mask = (
        view["majelis"].astype(str).str.lower().str.contains(ks) |
        view["hari"].astype(str).str.lower().str.contains(ks) |
        view["ketua"].astype(str).str.lower().str.contains(ks) |
        view["anggota1"].astype(str).str.lower().str.contains(ks) |
        view["anggota2"].astype(str).str.lower().str.contains(ks) |
        view["pp1"].astype(str).str.lower().str.contains(ks) |
        view["pp2"].astype(str).str.lower().str.contains(ks) |
        view["js1"].astype(str).str.lower().str.contains(ks) |
        view["js2"].astype(str).str.lower().str.contains(ks)
    )
    view = view[mask]

if only_active:
    view = view[view["aktif_bool"] == True]

sort_map = {"Majelis":"majelis", "Hari":"hari", "Ketua":"ketua", "Aktif%s":"aktif_bool"}
if sort_by != "(tanpa urut)":
    key = sort_map.get(sort_by)
    if key in view.columns:
        view = view.sort_values(key, ascending=asc, kind="stable")

# Pagination
psel = st.selectbox("Baris per halaman", [10, 25, 50, 100], index=0)
ps = int(psel)
total = len(view)
pages = max(1, math.ceil(total/ps))
page_key = "sk_page_simple"
page = int(st.session_state.get(page_key, 1))
page = min(max(1, page), pages)
start, end = (page-1)*ps, (page-1)*ps + ps
page_df = view.iloc[start:end].reset_index(drop=True)

# Header
COLS = [0.6, 1.5, 0.8, 1.4, 1.4, 1.1, 1.1, 1.1, 0.6, 0.6]
h = st.columns(COLS)
h[0].markdown("**ID**"); h[1].markdown("**Majelis**"); h[2].markdown("**Hari**"); h[3].markdown("**Ketua**")
h[4].markdown("**Anggota 1**"); h[5].markdown("**Anggota 2**")
h[6].markdown("**PP1**"); h[7].markdown("**PP2**"); h[8].markdown("**Aktif%s**"); h[9].markdown("**Aksi**")
st.markdown("<hr/>", unsafe_allow_html=True)

# Rows
full_now = raw
page_df_reset = page_df.reset_index(drop=True)

def _valid_id(x):
    try:
        return (x is not None) and (str(x).strip() != "") and (not pd.isna(x)) and (int(x) != 0)
    except Exception:
        return False

for i, r in page_df_reset.iterrows():
    cols = st.columns(COLS)

    rid_raw = r.get("id")
    try:
        rid = int(rid_raw);  rid = None if rid == 0 else rid
    except Exception:
        rid = None

    safe_hash = abs(hash(
        "|".join(str(r.get(c,"")) for c in ["majelis","hari","ketua","anggota1","anggota2","pp1","pp2","js1","js2"])
    )) % 10_000_000
    rowkey = f"id_{rid}" if _valid_id(rid_raw) else f"p{page}_i{start+i}_{safe_hash}"

    cols[0].write(str(rid) if _valid_id(rid_raw) else "-")
    cols[1].write(str(r.get("majelis","")) or "-")
    cols[2].write(str(r.get("hari","")) or "-")
    cols[3].write(str(r.get("ketua","")) or "-")
    cols[4].write(str(r.get("anggota1","")) or "-")
    cols[5].write(str(r.get("anggota2","")) or "-")
    cols[6].write(str(r.get("pp1","")) or "-")
    cols[7].write(str(r.get("pp2","")) or "-")
    cols[8].write("YA" if _is_active_value(r.get("aktif",1)) else "TIDAK")

    with cols[9]:
        cA, cB = st.columns(2)
        with cA:
            if st.button("✏️", key=f"edit_{rowkey}"):
                full = load_sk().reset_index(drop=True)
                target_idx = None

                if "id" in full.columns and _valid_id(rid_raw):
                    match = full.index[full["id"] == int(rid_raw)]
                    if len(match) > 0:
                        target_idx = int(match[0])

                if target_idx is None:
                    keys = ["majelis","hari","ketua","anggota1","anggota2","pp1","pp2","js1","js2"]
                    mask = pd.Series([True]*len(full))
                    for k in keys:
                        rv = str(r.get(k,"") or "")
                        mask = mask & (full[k].astype(str).fillna("") == rv)
                    m2 = full.index[mask]
                    if len(m2) > 0:
                        target_idx = int(m2[0])
                    else:
                        target_idx = int(start + i) if (start + i) < len(full) else 0

                open_sk_dialog("edit", {"index": target_idx})

        with cB:
            if st.button("🗑️", key=f"del_{rowkey}"):
                if _valid_id(rid_raw):
                    df = load_sk()
                    df = delete_sk_by_id(df, int(rid_raw))
                    save_sk(df)
                    export_sk_csv()
                    st.success("Baris dihapus."); st.rerun()
                else:
                    st.warning("Tidak bisa hapus: baris ini tidak memiliki ID yang valid.")

# Pagination controls
pc1, pc2, pc3 = st.columns([1,2,1])
with pc1:
    if st.button("⬅️ Prev", width="stretch", disabled=(page<=1)):
        st.session_state[page_key] = page - 1; st.rerun()
with pc2:
    st.markdown(
        f"<div style='text-align:center'>Hal <b>{page}</b> / <b>{pages}</b> • "
        f"Tampil <b>{min(ps, total-start)}</b> dari <b>{total}</b> baris "
        f"(<i>{start+1}-{min(end,total)}</i>)</div>", unsafe_allow_html=True
    )
with pc3:
    if st.button("Next ➡️", width="stretch", disabled=(page>=pages)):
        st.session_state[page_key] = page + 1; st.rerun()

# ==================== Render dialog (wajib ada) ====================
render_sk_dialog(load_sk())
