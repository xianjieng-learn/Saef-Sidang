# pages/3_JS_&_JS_Ghoib.py
# Gabungan: Data JS + Data JS Ghoib (dua tab)
# - Tab 1: 📝 Data JS  (CSV-only)      [gabungan dari 3c_📝_Data_JS.py]
# - Tab 2: 🫥 Data JS Ghoib (CSV-only) [gabungan dari 3d_🫥_Data_JS_Ghoib.py]
# Catatan:
# - Penamaan fungsi diprefix agar tidak bentrok: JS_* untuk Data JS, JSG_* untuk JS Ghoib.
# - Tombol gunakan width='stretch' (sesuai standar yang kamu sebut).
# - Struktur & perilaku mempertahankan fitur asli masing-masing halaman.

from __future__ import annotations
import io, re, math
from pathlib import Path
from typing import Tuple, Dict, Set, Optional
from app_core.login import _ensure_auth
import pandas as pd
import streamlit as st
from app_core.nav import render_top_nav
render_top_nav()  # tampilkan top bar

# ============== PAGE CONFIG ==============
st.set_page_config(page_title="Data JS & JS Ghoib (CSV-only)", layout="wide", initial_sidebar_state="collapsed")
st.header("📚 Data Jurusita (JS) & JS Ghoib — CSV-only")

DATA_DIR = Path("data")
DATA_DIR.mkdir(parents=True, exist_ok=True)

# ========================================
# ========= Utilities (umum) =============
# ========================================
def U_is_active_value(v) -> bool:
    s = re.sub(r"[^A-Z0-9]+", "", str(v).replace("\ufeff","").strip().upper())
    if s in {"1","YA","Y","TRUE","T","AKTIF","ON"}: return True
    if s in {"0","TIDAK","TDK","NO","N","FALSE","F","NONAKTIF","OFF","NONE","NAN",""}: return False
    try: return float(s) != 0.0
    except Exception: return False

def U_safe_int(v) -> int:
    try:
        if pd.isna(v): return 0
    except Exception: ...
    try: return int(v)
    except Exception:
        try: return int(float(str(v).strip()))
        except Exception: return 0

def U_read_csv(path: Path) -> pd.DataFrame:
    if not path.exists(): return pd.DataFrame()
    for enc in ["utf-8-sig","utf-8","cp1252"]:
        try:
            return pd.read_csv(path, encoding=enc)
        except Exception:
            continue
    return pd.read_csv(path)

def U_write_csv(df: pd.DataFrame, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8-sig")

def U_write_csv_atomic(df: pd.DataFrame, path: Path):
    tmp = path.with_suffix(".tmp.csv")
    df.to_csv(tmp, index=False, encoding="utf-8-sig")
    tmp.replace(path)

def U_name_key(s: str) -> str:
    return re.sub(r"\s+"," ", str(s or "").strip().lower())

# ========================================
# ============= TAB 1: JS ================
# ========================================
JS_CSV    = DATA_DIR / "js_df.csv"
REKAP_CSV = DATA_DIR / "rekap.csv"

JS_BASE_COLS = ["id","nama","aktif","alias"]  # kolom standar Data JS

def JS_ensure_cols(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    ren: Dict[str,str] = {}
    for c in out.columns:
        k = re.sub(r"\s+", " ", str(c).replace("\ufeff","").strip().lower())
        if   k == "id": new="id"
        elif k in {"nama","name","nama js","js"}: new="nama"
        elif k in {"aktif","status","active","is active"}: new="aktif"
        elif k in {"alias","a.k.a","aka"}: new="alias"
        else: new=c
        ren[c] = new
    out = out.rename(columns=ren)
    for c in JS_BASE_COLS:
        if c not in out.columns:
            out[c] = 0 if c in {"id","aktif"} else ""
    out["id"] = pd.to_numeric(out["id"], errors="coerce").fillna(0).astype(int)
    out["aktif"] = out["aktif"].apply(U_is_active_value).astype(int)
    for c in ["nama","alias"]:
        out[c] = out[c].astype(str).fillna("").map(lambda s: s.strip())
    out = out[out["nama"] != ""].copy()
    return out[JS_BASE_COLS].reset_index(drop=True)

def JS_load() -> pd.DataFrame:
    df = U_read_csv(JS_CSV)
    if df.empty:
        df = pd.DataFrame(columns=JS_BASE_COLS)
        U_write_csv(df, JS_CSV)
    return JS_ensure_cols(df)

def JS_save(df: pd.DataFrame):
    U_write_csv(JS_ensure_cols(df), JS_CSV)
    st.toast("js_df.csv tersimpan ✅", icon="✅")

def JS_next_id(df: pd.DataFrame) -> int:
    if "id" not in df.columns or df.empty: return 1
    mx = pd.to_numeric(df["id"], errors="coerce").fillna(0).astype(int).max()
    return int(mx) + 1

def JS_upsert_by_nama(df: pd.DataFrame, nama: str, aktif: int, alias: str) -> Tuple[pd.DataFrame, str]:
    work = JS_ensure_cols(df)
    nm = str(nama or "").strip()
    if not nm: return work, "skipped"
    mask = work["nama"].str.lower() == nm.lower()
    if not mask.any():
        new_row = {"id": JS_next_id(work), "nama": nm, "aktif": int(aktif), "alias": alias.strip()}
        work = pd.concat([work, pd.DataFrame([new_row])], ignore_index=True)
        return work, "inserted"
    else:
        work.loc[mask, ["nama","aktif","alias"]] = [nm, int(aktif), alias.strip()]
        return work, "updated"

def JS_update_by_id(df: pd.DataFrame, row_id: int, nama: str, aktif: int, alias: str) -> pd.DataFrame:
    work = JS_ensure_cols(df)
    mask = work["id"] == int(row_id)
    if mask.any():
        work.loc[mask, ["nama","aktif","alias"]] = [nama.strip(), int(aktif), alias.strip()]
    return work

def JS_delete_by_id(df: pd.DataFrame, row_id: int) -> pd.DataFrame:
    work = JS_ensure_cols(df)
    return work[work["id"] != int(row_id)].reset_index(drop=True)

def JS_load_rekap() -> pd.DataFrame:
    df = U_read_csv(REKAP_CSV)
    if df.empty: return df
    ren = {}
    for c in df.columns:
        k = re.sub(r"\s+"," ", str(c).replace("\ufeff","").strip().lower())
        if   k in {"pp","panitera pengganti"}: new="pp"
        elif k in {"js","jurusita"}: new="js"
        elif k in {"metode","method"}: new="metode"
        elif k in {"jenis_perkara","jenis"}: new="jenis_perkara"
        else: new=c
        ren[c]=new
    return df.rename(columns=ren)

def JS_build_metode_norm(s: pd.Series) -> pd.Series:
    m = s.astype(str).str.strip().str.lower()
    m = m.replace({"ecourt":"e-court","e court":"e-court"})
    ok = m.isin(["e-court","manual"])
    return m.where(ok, "e-court")

def JS_compute_workload(js_df: pd.DataFrame) -> pd.DataFrame:
    if js_df.empty:
        return js_df.assign(**{"E-Court":0,"Manual":0,"Ghoib":0,"Total":0})
    r = JS_load_rekap()
    if r.empty or "js" not in r.columns:
        return js_df.assign(**{"E-Court":0,"Manual":0,"Ghoib":0,"Total":0})

    r = r.copy()
    r["js_norm"] = r["js"].astype(str).map(U_name_key)
    r["m_norm"] = JS_build_metode_norm(r.get("metode", pd.Series(index=r.index, dtype="string")))
    r["jenis_u"] = r.get("jenis_perkara", pd.Series(index=r.index)).astype(str).str.upper().str.strip()

    by_js_m = r.groupby(["js_norm","m_norm"]).size().unstack(fill_value=0)
    ghoib_ct = r[r["jenis_u"]=="GHOIB"].groupby("js_norm").size() if "jenis_u" in r.columns else pd.Series(dtype=int)

    js = js_df.copy()
    js["__name_norm"] = js["nama"].map(U_name_key)
    js["E-Court"] = js["__name_norm"].map(lambda k: int(by_js_m.loc[k, "e-court"]) if ("e-court" in by_js_m.columns and k in by_js_m.index) else 0)
    js["Manual"]  = js["__name_norm"].map(lambda k: int(by_js_m.loc[k, "manual"])  if ("manual"  in by_js_m.columns and k in by_js_m.index) else 0)
    js["Ghoib"]   = js["__name_norm"].map(lambda k: int(ghoib_ct.get(k, 0)))
    js["Total"]   = js["E-Court"] + js["Manual"]
    return js.drop(columns=["__name_norm"])

# Dialog state (JS)
if "JS_dialog" not in st.session_state:
    st.session_state["JS_dialog"] = {"open": False, "mode": "", "title": "", "payload": {}}

def JS_open_dialog(mode: str, title: str, payload: dict | None = None):
    st.session_state["JS_dialog"] = {"open": True, "mode": mode, "title": title, "payload": payload or {}}

def JS_render_dialog(current_df: pd.DataFrame):
    dlg = st.session_state.get("JS_dialog", {"open": False})
    if not dlg.get("open"): return
    mode = dlg.get("mode"); title = dlg.get("title", ""); payload = dlg.get("payload", {}) or {}

    with st.form("JS_dialog_form"):
        if mode == "edit_js" and not current_df.empty:
            i = int(payload.get("index", 0))
            row = current_df.reset_index(drop=True).iloc[i]
            row_id = U_safe_int(row.get("id"))
            nama_init  = str(row.get("nama",""))
            aktif_init = U_is_active_value(row.get("aktif", 1))
            alias_init = str(row.get("alias",""))
        else:
            row_id = None
            nama_init = ""; aktif_init = True; alias_init = ""

        st.subheader(title or ("Edit JS" if row_id else "Tambah JS"))
        nama  = st.text_input("Nama", value=nama_init, key="JS_dlg_nama")
        aktif = st.checkbox("Aktif", value=aktif_init, key="JS_dlg_aktif")
        alias = st.text_area("Alias", value=alias_init, height=70, help="Pisahkan dengan ; atau baris baru (opsional)", key="JS_dlg_alias")

        c1, c2, c3 = st.columns([1,1,1])
        with c1: sbtn = st.form_submit_button("💾 Simpan", width="stretch")
        with c2: cbtn = st.form_submit_button("Batal", width="stretch")
        with c3: dbtn = st.form_submit_button("🗑️ Hapus", width="stretch") if (mode=="edit_js" and row_id) else None

        if sbtn:
            if not nama.strip():
                st.error("Nama wajib diisi.")
            else:
                df = JS_load()
                if mode == "edit_js" and row_id:
                    df = JS_update_by_id(df, row_id, nama, 1 if aktif else 0, alias)
                else:
                    df, _ = JS_upsert_by_nama(df, nama, 1 if aktif else 0, alias)
                JS_save(df)
                st.session_state["JS_dialog"]["open"] = False
                st.success("Tersimpan ✅"); st.rerun()

        if dbtn and (mode=="edit_js" and row_id):
            df = JS_load()
            df = JS_delete_by_id(df, row_id)
            JS_save(df)
            st.session_state["JS_dialog"]["open"] = False
            st.success("Dihapus 🗑️"); st.rerun()

        if cbtn and not sbtn and not dbtn:
            st.session_state["JS_dialog"]["open"] = False
            st.info("Dibatalkan."); st.rerun()

# ========================================
# ========= TAB 2: JS Ghoib ==============
# ========================================
JSG_FILE     = DATA_DIR / "js_ghoib.csv"     # source of truth
JSG_MIRROR   = DATA_DIR / "js_ghoib_df.csv"  # mirror opsional
JSG_COLS     = ["nama", "aktif", "jml_ghoib", "catatan", "alias"]

def JSG_standardize_input_columns(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=["nama","aktif","jml_ghoib","catatan","alias"])
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
    keep = [c for c in ["id","nama","aktif","jml_ghoib","catatan","alias"] if c in out.columns]
    out = out[keep] if keep else pd.DataFrame(columns=["nama","aktif","jml_ghoib","catatan","alias"])

    if "nama" not in out.columns:
        out["nama"] = ""
    out["nama"] = out["nama"].astype(str).str.strip()
    out = out[out["nama"] != ""].copy()

    if "aktif" in out.columns:
        out["aktif"] = out["aktif"].apply(lambda v: 1 if U_is_active_value(v) else 0)
    else:
        out["aktif"] = 1

    if "jml_ghoib" in out.columns:
        out["jml_ghoib"] = pd.to_numeric(out["jml_ghoib"], errors="coerce").fillna(0).astype(int)
    else:
        out["jml_ghoib"] = 0

    for c in ["catatan","alias"]:
        if c in out.columns: out[c] = out[c].astype(str).str.strip()
        else: out[c] = ""

    return out[["nama","aktif","jml_ghoib","catatan","alias"]].reset_index(drop=True)

def JSG_load() -> pd.DataFrame:
    df = U_read_csv(JSG_FILE)
    if df.empty:
        return pd.DataFrame(columns=JSG_COLS)
    return JSG_standardize_input_columns(df)

def JSG_save(df: pd.DataFrame):
    df2 = JSG_standardize_input_columns(df)
    df2 = df2.sort_values(["aktif","jml_ghoib","nama"], ascending=[False, True, True], kind="stable").reset_index(drop=True)
    U_write_csv_atomic(df2, JSG_FILE)
    try:
        U_write_csv_atomic(df2, JSG_MIRROR)
    except Exception:
        pass

def JSG_upsert_by_nama(nama: str, aktif: int, jml_ghoib: int, catatan: str, alias: str):
    df = JSG_load()
    mask = df["nama"].str.casefold() == str(nama).strip().casefold()
    row = {
        "nama": nama.strip(),
        "aktif": 1 if U_is_active_value(aktif) else 0,
        "jml_ghoib": U_safe_int(jml_ghoib),
        "catatan": str(catatan or "").strip(),
        "alias": str(alias or "").strip(),
    }
    if mask.any():
        i = mask[mask].index[0]
        for k,v in row.items(): df.loc[i, k] = v
    else:
        df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    JSG_save(df)

def JSG_update_by_index(idx: int, nama: str, aktif: int, jml_ghoib: int, catatan: str, alias: str):
    df = JSG_load()
    if 0 <= idx < len(df):
        df.loc[idx, ["nama","aktif","jml_ghoib","catatan","alias"]] = [
            nama.strip(), 1 if U_is_active_value(aktif) else 0, U_safe_int(jml_ghoib), catatan.strip(), alias.strip()
        ]
        JSG_save(df)

def JSG_delete_by_index(idx: int):
    df = JSG_load()
    if 0 <= idx < len(df):
        df = df.drop(index=idx).reset_index(drop=True)
        JSG_save(df)

def JSG_replace_all(df_in: pd.DataFrame):
    JSG_save(df_in)

def JSG_upsert_bulk(df_in: pd.DataFrame):
    df_std = JSG_standardize_input_columns(df_in)
    if df_std.empty: return
    for _, r in df_std.iterrows():
        JSG_upsert_by_nama(
            str(r.get("nama","")),
            int(r.get("aktif",1)),
            U_safe_int(r.get("jml_ghoib",0)),
            str(r.get("catatan","")),
            str(r.get("alias","")),
        )

def JSG_choose_auto(use_aktif: bool = True) -> tuple[str, dict]:
    master = JSG_load()
    if master.empty:
        return "", {"candidates": [], "reason": "js_ghoib.csv kosong."}
    if use_aktif:
        master = master[master["aktif"].apply(U_is_active_value)]
    candidates = master[["nama","jml_ghoib"]].copy()
    if candidates.empty:
        return "", {"candidates": [], "reason": "Tidak ada kandidat aktif."}
    pairs = [(r["nama"], U_safe_int(r["jml_ghoib"])) for _, r in candidates.iterrows()]
    pairs.sort(key=lambda x: (x[1], x[0].lower()))
    pick = pairs[0][0] if pairs else ""
    debug = {"candidates": [p[0] for p in pairs], "sorted": pairs, "reason": "Memilih jml_ghoib terkecil (seri → alfabet)."}
    return pick, debug

# Dialog state (JSG)
if "JSG_dialog" not in st.session_state:
    st.session_state["JSG_dialog"] = {"open": False, "mode": "", "payload": {}}

def JSG_open_dialog(mode: str, payload: dict | None = None):
    st.session_state["JSG_dialog"] = {"open": True, "mode": mode, "payload": payload or {}}

def JSG_render_dialog(current_df: pd.DataFrame):
    dlg = st.session_state.get("JSG_dialog", {"open": False})
    if not dlg.get("open"): return
    mode = dlg.get("mode"); payload = dlg.get("payload", {}) or {}

    row_idx = None; nama_init=""; aktif_init=True; alias_init=""; cat_init=""; tot_init=0
    if mode == "edit" and isinstance(current_df, pd.DataFrame) and not current_df.empty:
        i = int(payload.get("index", 0))
        r = current_df.reset_index(drop=True).iloc[i]
        row_idx   = i
        nama_init = str(r.get("nama",""))
        aktif_init= U_is_active_value(r.get("aktif",1))
        alias_init= str(r.get("alias",""))
        cat_init  = str(r.get("catatan",""))
        tot_init  = U_safe_int(r.get("jml_ghoib", 0))

    with st.form("JSG_form"):
        st.subheader("Edit JS Ghoib" if (mode=="edit" and row_idx is not None) else "Tambah JS Ghoib")
        nama    = st.text_input("Nama", value=nama_init, key="JSG_nama")
        aktif   = st.checkbox("Aktif", value=aktif_init, key="JSG_aktif")
        total   = st.number_input("Total GHOIB", min_value=0, step=1, value=int(tot_init), key="JSG_total")
        alias   = st.text_area("Alias (opsional, pisahkan ;)", value=alias_init, height=70, key="JSG_alias")
        catatan = st.text_area("Catatan", value=cat_init, height=70, key="JSG_cat")

        c1, c2, c3 = st.columns(3)
        sbtn = c1.form_submit_button("💾 Simpan", width="stretch")
        cbtn = c2.form_submit_button("Batal", width="stretch")
        del_confirm = c3.checkbox("Konfirmasi hapus", value=False, key="JSG_delconf")
        dbtn = c3.form_submit_button("🗑️ Hapus", width="stretch",
                                     disabled=not (mode=="edit" and row_idx is not None and del_confirm))

        if sbtn:
            if not nama.strip():
                st.error("Nama wajib diisi.")
            else:
                if mode == "edit" and row_idx is not None:
                    JSG_update_by_index(int(row_idx), nama, 1 if aktif else 0, int(total), catatan, alias)
                else:
                    JSG_upsert_by_nama(nama, 1 if aktif else 0, int(total), catatan, alias)
                st.session_state["JSG_dialog"]["open"] = False
                st.success("Tersimpan ✅"); st.rerun()

        if dbtn and mode == "edit" and row_idx is not None and del_confirm:
            JSG_delete_by_index(int(row_idx))
            st.session_state["JSG_dialog"]["open"] = False
            st.success("Dihapus 🗑️"); st.rerun()

        if cbtn and not sbtn and not dbtn:
            st.session_state["JSG_dialog"]["open"] = False
            st.info("Dibatalkan."); st.rerun()

# ========================================
# ============= RENDER TABS ==============
# ========================================
tab1, tab2 = st.tabs(["📝 Data JS", "🫥 Data JS Ghoib"])

# ------------- Tab 1: Data JS -------------
with tab1:
    topL, topR = st.columns([1,1])
    with topR:
        if st.button("➕ Tambah JS", key="JS_add", width="stretch"):
            JS_open_dialog("add_js", "Tambah JS")

    # Import (opsional)
    with st.expander("📥 Import CSV → js_df.csv (gabung by nama)", expanded=False):
        st.write("Unggah CSV dengan kolom minimal **nama**. Kolom opsional: aktif, alias.")
        up = st.file_uploader("Pilih CSV", type=["csv"], key="JS_up")
        df_src = pd.DataFrame()
        if up is not None:
            try:
                up.seek(0); df_src = pd.read_csv(up, encoding="utf-8-sig")
            except Exception:
                up.seek(0); df_src = pd.read_csv(up)
        if not df_src.empty:
            ren: Dict[str,str] = {}
            for c in df_src.columns:
                k = re.sub(r"\s+"," ", str(c).replace("\ufeff","").strip().lower())
                if   k in {"nama","name","nama js","js"}: new="nama"
                elif k in {"aktif","status","active"}: new="aktif"
                elif k in {"alias","a.k.a","aka"}: new="alias"
                elif k == "id": new="id"
                else: new=c
                ren[c]=new
            df_src = df_src.rename(columns=ren)
            keep = [c for c in ["id","nama","aktif","alias"] if c in df_src.columns]
            df_src = df_src[keep]
            if "aktif" in df_src.columns:
                df_src["aktif"] = df_src["aktif"].apply(lambda v: 1 if U_is_active_value(v) else 0)
            else:
                df_src["aktif"] = 1
            for c in ["nama","alias"]:
                if c in df_src.columns:
                    df_src[c] = df_src[c].astype(str).str.strip()
            df_src = df_src[df_src["nama"] != ""]
            st.caption("Preview CSV (maks 30 baris)")
            st.dataframe(df_src.head(30), width="stretch")
            if st.button("🚀 Impor & Gabung (Upsert by nama)", type="primary", width="stretch", key="JS_import"):
                df = JS_load()
                inserted = updated = skipped = 0
                for _, r in df_src.iterrows():
                    nm = str(r.get("nama","")).strip()
                    if not nm:
                        skipped += 1; continue
                    df, status = JS_upsert_by_nama(
                        df,
                        nama = nm,
                        aktif = 1 if U_is_active_value(r.get("aktif",1)) else 0,
                        alias = str(r.get("alias","") or "")
                    )
                    if status == "inserted": inserted += 1
                    elif status == "updated": updated += 1
                    else: skipped += 1
                JS_save(df)
                st.success(f"Selesai impor: INSERTED={inserted}, UPDATED={updated}, SKIPPED={skipped}")
                st.rerun()
        else:
            st.caption("Belum ada file yang diunggah.")

    js_df = JS_load()
    view = JS_compute_workload(js_df)

    if view.empty:
        st.info("Belum ada data JS. Klik ➕ Tambah JS atau gunakan Import CSV.")
    else:
        view["Aktif%s"] = view["aktif"].apply(U_is_active_value).map({True:"YA", False:"TIDAK"})

        st.markdown("---")
        c1, c2, c3 = st.columns([1, 2.2, 0.9])
        page_size = c1.selectbox("Baris/hal", [10, 50, 100], index=0, key="JS_ps")
        sort_options = ["(tanpa urut)","Nama","Aktif%s","E-Court","Manual","Ghoib","Total"]
        sort_by = c2.selectbox("Urutkan berdasarkan", sort_options, index=0, key="JS_sortcol")
        asc = c3.toggle("Naik%s", value=True, key="JS_asc")

        sig = f"{page_size}|{sort_by}|{asc}|{len(view)}"
        if st.session_state.get("JS_sig") != sig:
            st.session_state["JS_sig"] = sig
            st.session_state["JS_page"] = 1
        page = int(st.session_state.get("JS_page", 1))

        sort_map = {
            "Nama":"nama", "Aktif%s":"aktif",
            "E-Court":"E-Court", "Manual":"Manual", "Ghoib":"Ghoib", "Total":"Total"
        }
        if sort_by != "(tanpa urut)":
            key = sort_map.get(sort_by)
            if key in view.columns:
                view = view.sort_values(key, ascending=asc, kind="stable")

        total_rows = len(view)
        page_size = int(page_size)
        total_pages = max(1, math.ceil(total_rows / page_size))
        page = min(max(1, page), total_pages)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        page_df = view.iloc[start_idx:end_idx].reset_index(drop=True)

        COLS = [2.4, 0.9, 0.9, 0.9, 0.9, 0.95, 2.2, 0.9, 0.9]
        h = st.columns(COLS)
        h[0].markdown("**Nama**"); h[1].markdown("**Aktif%s**")
        h[2].markdown("**E-Court**"); h[3].markdown("**Manual**"); h[4].markdown("**Ghoib**"); h[5].markdown("**Total**")
        h[6].markdown("**Alias**"); h[7].markdown("**Edit**"); h[8].markdown("**Hapus**")
        st.markdown("<hr/>", unsafe_allow_html=True)

        base = js_df.reset_index(drop=True)
        for i, r in page_df.iterrows():
            row_id = U_safe_int(r.get("id"))
            cols = st.columns(COLS)
            cols[0].write(str(r.get("nama","")) or "-")
            cols[1].write(str(r.get("Aktif%s","-")))
            cols[2].write(int(r.get("E-Court",0)))
            cols[3].write(int(r.get("Manual",0)))
            cols[4].write(int(r.get("Ghoib",0)))
            cols[5].write(int(r.get("Total",0)))
            cols[6].write(str(r.get("alias","") or ""))
            with cols[7]:
                if st.button("✏️", key=f"JS_edit_{row_id or i}"):
                    if row_id and "id" in base.columns and row_id in base["id"].tolist():
                        idx = int(base[base["id"]==row_id].index[0])
                    else:
                        nm = str(r.get("nama",""))
                        m = base["nama"].astype(str).str.lower() == nm.lower()
                        idx = int(m[m].index[0]) if m.any() else 0
                    JS_open_dialog("edit_js", f"Edit JS: {r.get('nama','')}", {"index": idx})
                    st.rerun()
            with cols[8]:
                if st.button("🗑️", key=f"JS_del_{row_id or i}"):
                    df = JS_load()
                    if row_id:
                        df = JS_delete_by_id(df, row_id)
                    else:
                        nm = str(r.get("nama",""))
                        df = df[df["nama"].astype(str).str.lower() != nm.lower()].reset_index(drop=True)
                    JS_save(df)
                    st.success(f"Dihapus: {r.get('nama','')}")
                    st.rerun()

        pc1, pc2, pc3 = st.columns([1,2,1])
        with pc1:
            if st.button("⬅️ Prev", key="JS_prev", width="stretch", disabled=(page<=1)):
                st.session_state["JS_page"] = page - 1; st.rerun()
        with pc2:
            st.markdown(
                f"<div style='text-align:center'>Halaman <b>{page}</b> / <b>{total_pages}</b> • "
                f"Menampilkan <b>{min(page_size, total_rows-start_idx)}</b> dari <b>{total_rows}</b> baris "
                f"(<i>{start_idx+1}-{min(end_idx,total_rows)}</i>)</div>",
                unsafe_allow_html=True
            )
        with pc3:
            if st.button("Next ➡️", key="JS_next", width="stretch", disabled=(page>=total_pages)):
                st.session_state["JS_page"] = page + 1; st.rerun()

    if st.session_state.get("JS_dialog", {}).get("open"):
        JS_render_dialog(JS_load())

# ------------- Tab 2: Data JS Ghoib -------------
with tab2:
    with st.expander("ℹ️ Lokasi Penyimpanan", expanded=False):
        st.write("**CSV utama (JS Ghoib):**", str(JSG_FILE))
        st.write("**Mirror CSV (opsional):**", str(JSG_MIRROR))

    c1, c2, c3, c4 = st.columns([1.3,1.5,1.8,1.4])
    with c1:
        if st.button("➕ Tambah JS Ghoib", use_container_width=True, key="JSG_add"):
            st.session_state["JSG_dialog"] = {"open": True, "mode": "add", "payload": {}}
            st.experimental_rerun()
    with c2:
        if st.button("⬇️ Export Mirror (CSV)", use_container_width=True, key="JSG_export"):
            df = JSG_load()
            if isinstance(df, pd.DataFrame) and not df.empty:
                U_write_csv_atomic(df, JSG_MIRROR)
                st.success(f"Mirror ditulis: {JSG_MIRROR.name}")
            else:
                st.warning("CSV utama kosong, tidak ada yang diekspor.")
    with c3:
        up_file = st.file_uploader("Upload CSV", type=["csv"], label_visibility="collapsed", key="JSG_up")
    with c4:
        mode = st.radio("Mode import", ["Upsert", "Replace"], horizontal=True, label_visibility="collapsed", key="JSG_import_mode")

    if up_file is not None:
        try:
            raw = up_file.read()
            df_in = pd.read_csv(io.BytesIO(raw), encoding="utf-8-sig")
        except Exception:
            up_file.seek(0); df_in = pd.read_csv(up_file)
        df_std = JSG_standardize_input_columns(df_in)
        st.caption("Preview import (maks 200 baris):")
        st.dataframe(df_std.head(200), use_container_width=True, hide_index=True)
        if not df_std.empty and st.button("🚀 Jalankan Import", type="primary", key="JSG_do_import"):
            if mode == "Replace":
                JSG_replace_all(df_std); st.success(f"Replace {len(df_std)} baris.")
            else:
                JSG_upsert_bulk(df_std); st.success(f"Upsert {len(df_std)} baris.")
            st.rerun()
    else:
        st.caption("Belum ada file yang diunggah.")

    st.markdown("---")
    colA, colB = st.columns([1.6, 2.4])
    pick, dbg = JSG_choose_auto(use_aktif=True)
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
    df = JSG_load()
    if isinstance(df, pd.DataFrame) and not df.empty:
        cols_csv = ["nama","aktif","jml_ghoib","catatan","alias"]
        view = df.copy()
        for c in cols_csv:
            if c not in view.columns:
                view[c] = 0 if c in {"aktif","jml_ghoib"} else ""
        view = view[cols_csv].reset_index(drop=True)

        COLS = [2.6, 0.9, 3.0, 1.5]  # terakhir Aksi
        h = st.columns(COLS)
        h[0].markdown("**Nama**")
        h[1].markdown("**Aktif**")
        h[2].markdown("**Jumlah Ghoib**")
        h[3].markdown("**Aksi**")
        st.markdown("<hr/>", unsafe_allow_html=True)

        for i, r in view.iterrows():
            cols = st.columns(COLS)
            cols[0].write(str(r["nama"]))
            cols[1].write(int(r["aktif"]))
            cols[2].write(int(r["jml_ghoib"]))
            with cols[3]:
                cA, cB = st.columns(2)
                if cA.button("✏️", key=f"JSG_edit_{i}"):
                    st.session_state["JSG_dialog"] = {"open": True, "mode": "edit", "payload": {"index": int(i)}}
                    st.rerun()
                if cB.button("🗑️", key=f"JSG_del_{i}"):
                    st.session_state["JSG_dialog"] = {"open": True, "mode": "edit", "payload": {"index": int(i)}}
                    st.warning("Centang 'Konfirmasi hapus' lalu klik 🗑️ Hapus.")
                    st.rerun()
    else:
        st.warning("Belum ada data JS Ghoib. Klik **➕ Tambah** atau upload CSV.")

    if st.session_state.get("JSG_dialog", {}).get("open"):
        JSG_render_dialog(JSG_load())
