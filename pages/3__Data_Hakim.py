# pages/3_🧑‍⚖️_Data_&_Cuti_Hakim.py
from __future__ import annotations
import re, math
from pathlib import Path
from datetime import date
from typing import Dict, List, Set, Tuple
import pandas as pd
import streamlit as st
from app_core.login import _ensure_auth  

# =================== Page meta ===================
st.set_page_config(page_title="🧑‍⚖️      Data & Cuti Hakim", layout="wide")
st.header("🧑‍⚖️ Data Hakim & 🗓️ Cuti Hakim")

# =================== Paths =======================
DATA_DIR   = Path("data"); DATA_DIR.mkdir(parents=True, exist_ok=True)
HAKIM_CSV  = DATA_DIR / "hakim_df.csv"
CUTI_FILE  = DATA_DIR / "cuti_hakim.csv"
REKAP_CSV  = DATA_DIR / "rekap.csv"

# =================== Utils (shared) ==============
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
    """Parse tanggal robust:
    - ISO 'YYYY-MM-DD' pakai format eksplisit (no warning)
    - selain itu, fallback dayfirst=True
    """
    ser = s.astype(str).str.strip()
    iso_mask = ser.str.match(r"^\d{4}-\d{2}-\d{2}$")

    # parse ISO (jelas formatnya)
    iso_parsed = pd.to_datetime(ser.where(iso_mask), format="%Y-%m-%d", errors="coerce")

    # sisanya: dayfirst=True
    other_parsed = pd.to_datetime(ser.where(~iso_mask), dayfirst=True, errors="coerce")

    # gabungkan hasil
    return iso_parsed.combine_first(other_parsed)

def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists(): return pd.DataFrame()
    for enc in ("utf-8-sig","utf-8","cp1252"):
        try: return pd.read_csv(path, encoding=enc)
        except Exception: pass
    return pd.read_csv(path)

def _write_csv(df: pd.DataFrame, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8-sig")

# =================== Normalisasi nama (shared) ===
_PREFIX_RX = re.compile(r"^\s*((drs?|dra|prof|ir|apt|h|hj|kh|ust|ustadz|ustadzah)\.?\s+)+", flags=re.IGNORECASE)
_SUFFIX_PATTERNS = [
    r"s\.?\s*h\.?", r"s\.?\s*h\.?\s*i\.?", r"m\.?\s*h\.?", r"m\.?\s*h\.?\s*i\.?",
    r"s\.?\s*ag", r"m\.?\s*ag", r"m\.?\s*kn", r"m\.?\s*hum",
    r"s\.?\s*kom", r"s\.?\s*psi", r"s\.?\s*e", r"m\.?\s*m", r"m\.?\s*a",
    r"llb", r"llm", r"phd", r"se", r"ssi", r"sh", r"mh"
]
_SUFFIX_RX = re.compile(r"(,?\s+(" + r"|".join(_SUFFIX_PATTERNS) + r"))+$", flags=re.IGNORECASE)

def _clean_text(s: str) -> str:
    x = str(s or "").replace("\u00A0"," ").strip()
    x = re.sub(r"\s+"," ", x)
    return x

def _normalize_name_to_tokens(name: str) -> List[str]:
    if not isinstance(name, str): return []
    s = name.strip()
    if not s: return []
    s = s.replace(",", " ")
    s = _SUFFIX_RX.sub("", s)
    s = _PREFIX_RX.sub("", s)
    s = s.replace(".", " ")
    s = re.sub(r"\s+", " ", s).strip()
    toks = [t.lower() for t in s.split() if t]
    toks = [t for t in toks if t not in {"s","h","m","e"}]
    return toks

def _name_key_full(s: str) -> str:
    return " ".join(_normalize_name_to_tokens(s))

def _alias_entries(alias_text: str) -> List[str]:
    if not isinstance(alias_text, str) or not alias_text.strip(): return []
    parts = re.split(r"[;,\n]+", alias_text)
    return [p.strip() for p in parts if p.strip()]

# =================== Loader/CRUD Hakim =============
BASE_COLS_HAKIM = ["id","nama","hari","aktif","max_per_hari","alias","jabatan","catatan"]

def _ensure_hakim_cols(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    # normalisasi kolom umum
    ren = {}
    for c in out.columns:
        k = re.sub(r"\s+", " ", str(c).replace("\ufeff","").strip().lower())
        if   k == "id": new="id"
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

    for c in BASE_COLS_HAKIM:
        if c not in out.columns:
            out[c] = 0 if c in {"id","aktif","max_per_hari"} else ""

    out["id"] = pd.to_numeric(out["id"], errors="coerce").fillna(0).astype(int)
    out["aktif"] = out["aktif"].apply(_is_active_value).astype(int)
    out["max_per_hari"] = pd.to_numeric(out["max_per_hari"], errors="coerce").fillna(0).astype(int)
    for c in ["nama","hari","alias","jabatan","catatan"]:
        out[c] = out[c].astype(str).fillna("").map(lambda s: s.strip())
    return out[BASE_COLS_HAKIM]

def _load_hakim_csv() -> pd.DataFrame:
    df = _read_csv(HAKIM_CSV)
    if df.empty:
        df = pd.DataFrame(columns=BASE_COLS_HAKIM)
        _write_csv(df, HAKIM_CSV)
    return _ensure_hakim_cols(df)

def _save_hakim_csv(df: pd.DataFrame):
    _write_csv(_ensure_hakim_cols(df), HAKIM_CSV)
    st.toast("hakim_df.csv tersimpan ✅", icon="✅")

def _next_id(df: pd.DataFrame) -> int:
    if "id" not in df.columns or df.empty: return 1
    mx = pd.to_numeric(df["id"], errors="coerce").fillna(0).astype(int).max()
    return int(mx) + 1

def upsert_hakim_by_nama_csv(df: pd.DataFrame, nama: str, hari: str, aktif: int, max_per_hari: int, catatan: str, alias: str, jabatan: str = "") -> Tuple[pd.DataFrame, str]:
    work = _ensure_hakim_cols(df)
    key = _name_key_full(nama)
    if not key: return work, "skipped"
    idx_match = None
    for i, row in work.reset_index(drop=True).iterrows():
        nm_key = _name_key_full(str(row["nama"]))
        if key == nm_key: idx_match = i; break
        for al in _alias_entries(str(row["alias"])):
            if key == _name_key_full(al):
                idx_match = i; break
        if idx_match is not None: break

    if idx_match is None:
        new_row = {
            "id": _next_id(work),
            "nama": nama.strip(),
            "hari": hari.strip(),
            "aktif": int(aktif),
            "max_per_hari": int(max_per_hari),
            "alias": alias.strip(),
            "jabatan": jabatan.strip(),
            "catatan": catatan.strip(),
        }
        work = pd.concat([work, pd.DataFrame([new_row])], ignore_index=True)
        return work, "inserted"
    else:
        work.loc[idx_match, ["nama","hari","aktif","max_per_hari","alias","jabatan","catatan"]] = [
            nama.strip(), hari.strip(), int(aktif), int(max_per_hari), alias.strip(), jabatan.strip(), catatan.strip()
        ]
        return work, "updated"

def update_hakim_by_id_csv(df: pd.DataFrame, row_id: int, nama: str, hari: str, aktif: int, max_per_hari: int, catatan: str, alias: str, jabatan: str = "") -> pd.DataFrame:
    work = _ensure_hakim_cols(df)
    mask = work["id"] == int(row_id)
    if mask.any():
        work.loc[mask, ["nama","hari","aktif","max_per_hari","alias","jabatan","catatan"]] = [
            nama.strip(), hari.strip(), int(aktif), int(max_per_hari), alias.strip(), jabatan.strip(), catatan.strip()
        ]
    return work

def delete_hakim_by_id_csv(df: pd.DataFrame, row_id: int) -> pd.DataFrame:
    work = _ensure_hakim_cols(df)
    work = work[work["id"] != int(row_id)].reset_index(drop=True)
    return work

# =================== Loader Rekap ====================
def _load_rekap_csv() -> pd.DataFrame:
    df = _read_csv(REKAP_CSV)
    if df.empty: return pd.DataFrame()
    if "register" in df.columns and "tgl_register" not in df.columns:
        df = df.rename(columns={"register":"tgl_register"})
    for c in ("tgl_register","tgl_sidang"):
        if c in df.columns:
            df[c] = _to_dt(df[c])
    if "hakim" not in df.columns:
        for cand in ["Hakim (Ketua)","ketua","hakim_ketua","nama_hakim"]:
            if cand in df.columns:
                df["hakim"] = df[cand]
                break
    return df

# =================== Cuti: transform & merge =========
def _standardize_cuti(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=["nama","mulai","akhir","_nama_norm"])
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
    if "tanggal" in out.columns:
        out["mulai"] = pd.to_datetime(out["tanggal"], errors="coerce").dt.normalize()
        out["akhir"] = out["mulai"]
    else:
        out["mulai"] = pd.to_datetime(out.get("mulai"), errors="coerce").dt.normalize()
        out["akhir"] = pd.to_datetime(out.get("akhir"), errors="coerce").dt.normalize()
    out["nama"] = out.get("nama","").astype(str).map(str.strip)
    out = out.dropna(subset=["nama","mulai","akhir"]).copy()
    bad = out["mulai"] > out["akhir"]
    out.loc[bad, ["mulai","akhir"]] = out.loc[bad, ["akhir","mulai"]].values
    out["_nama_norm"] = out["nama"].map(_name_key_full)
    out = out[["_nama_norm","nama","mulai","akhir"]].sort_values(["_nama_norm","mulai","akhir"]).reset_index(drop=True)
    return out

def _merge_ranges(df: pd.DataFrame) -> pd.DataFrame:
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
    _write_csv(df2[["nama","mulai","akhir"]], CUTI_FILE)

def _hakim_options() -> list[str]:
    df = _load_hakim_csv()
    if df.empty: return []
    if "aktif" in df.columns:
        df = df[df["aktif"].apply(_is_active_value)]
    name_col = "nama" if "nama" in df.columns else df.columns[0]
    names = (
        df[name_col].dropna().astype(str).map(str.strip)
        .replace("", pd.NA).dropna().drop_duplicates().sort_values().tolist()
    )
    return names

# =================== Tabs ===========================
tab1, tab2 = st.tabs(["🧑‍⚖️ Data Hakim", "🗓️ Cuti Hakim"])

# ------------------- TAB 1: Data Hakim --------------
with tab1:
    hakim_df = _load_hakim_csv()
    rekap_df = _load_rekap_csv()

    st.caption(
        f"🗂️ Sumber data → **Hakim**: `{HAKIM_CSV.as_posix()}` • **Rekap**: `{REKAP_CSV.as_posix()}`"
    )

    # Dialog state
    if "hakim_dialog" not in st.session_state:
        st.session_state["hakim_dialog"] = {"open": False, "mode": "", "title": "", "payload": {}}

    def open_hakim_dialog(mode: str, title: str, payload: dict | None = None):
        st.session_state["hakim_dialog"] = {"open": True, "mode": mode, "title": title, "payload": payload or {}}

    def render_hakim_dialog(current_df: pd.DataFrame):
        dlg = st.session_state.get("hakim_dialog", {"open": False})
        if not dlg.get("open"): return
        mode = dlg.get("mode"); title = dlg.get("title", ""); payload = dlg.get("payload", {}) or {}
        with st.form("hakim_dialog_form"):
            if mode == "edit_hakim" and not current_df.empty:
                i = int(payload.get("index", 0))
                row = current_df.reset_index(drop=True).iloc[i]
                row_id = _safe_int(row.get("id"))
                nama_init = str(row.get("nama","")); hari_init = str(row.get("hari",""))
                aktif_init = _is_active_value(row.get("aktif", 1))
                max_init = _safe_int(row.get("max_per_hari"))
                cat_init = str(row.get("catatan","")); alias_init = str(row.get("alias",""))
                jab_init = str(row.get("jabatan",""))
            else:
                row_id = None; nama_init = ""; hari_init = ""; aktif_init = True; max_init = 0; cat_init = ""; alias_init = ""; jab_init = ""

            st.subheader(title or ("Edit Hakim" if row_id else "Tambah Hakim"))
            nama = st.text_input("Nama", value=nama_init)
            hari = st.text_input("Hari (Senin/Selasa/...)", value=hari_init)
            aktif = st.checkbox("Aktif", value=aktif_init)
            max_per_hari = st.number_input("Max/Hari", min_value=0, step=1, value=int(max_init))
            alias = st.text_area("Alias", value=alias_init, height=70, help="Pisahkan dengan ; atau baris baru")
            jabatan = st.text_input("Jabatan (opsional)", value=jab_init)
            catatan = st.text_area("Catatan", value=cat_init, height=70)

            c1, c2, c3 = st.columns([1,1,1])
            with c1: sbtn = st.form_submit_button("💾 Simpan", width="stretch")
            with c2: cbtn = st.form_submit_button("Batal", width="stretch")
            with c3: dbtn = st.form_submit_button("🗑️ Hapus", width="stretch") if (mode=="edit_hakim" and row_id) else None

            if sbtn:
                if not nama.strip():
                    st.error("Nama wajib diisi.")
                else:
                    df = _load_hakim_csv()
                    if mode == "edit_hakim" and row_id:
                        df = update_hakim_by_id_csv(df, row_id, nama.strip(), hari.strip(), 1 if aktif else 0, int(max_per_hari), catatan.strip(), alias.strip(), jabatan.strip())
                    else:
                        df, _ = upsert_hakim_by_nama_csv(df, nama.strip(), hari.strip(), 1 if aktif else 0, int(max_per_hari), catatan.strip(), alias.strip(), jabatan.strip())
                    _save_hakim_csv(df)
                    st.session_state["hakim_dialog"]["open"] = False
                    st.success("Tersimpan ✅"); st.rerun()

            if dbtn and (mode=="edit_hakim" and row_id):
                df = _load_hakim_csv()
                df = delete_hakim_by_id_csv(df, row_id)
                _save_hakim_csv(df)
                st.session_state["hakim_dialog"]["open"] = False
                st.success("Dihapus 🗑️"); st.rerun()

            if cbtn and not sbtn and not dbtn:
                st.session_state["hakim_dialog"]["open"] = False
                st.info("Dibatalkan."); st.rerun()

    topL, topR = st.columns([1,1])
    with topR:
        if st.button("➕ Tambah Hakim", width='stretch'):
            open_hakim_dialog("add_hakim", "Tambah Hakim")

    # Import CSV → merge by nama
    with st.expander("📥 Import CSV → hakim_df.csv (gabung by nama)", expanded=False):
        st.write("Unggah CSV dengan kolom minimal **nama**. Kolom opsional: hari, aktif, max_per_hari, alias, jabatan, catatan.")
        up = st.file_uploader("Pilih CSV", type=["csv"], key="hakim_csv_up")
        df_src = pd.DataFrame()
        if up is not None:
            for enc in ["utf-8-sig","utf-8","cp1252"]:
                try:
                    up.seek(0); df_src = pd.read_csv(up, encoding=enc); break
                except Exception: continue
            if df_src.empty:
                up.seek(0); df_src = pd.read_csv(up)

        if not df_src.empty:
            st.caption("Preview CSV (maks 30 baris)")
            st.dataframe(df_src.head(30), width='stretch')

            cols = ["— none —"] + list(df_src.columns)
            def pick(label, default_name):
                default = default_name if default_name in df_src.columns else "— none —"
                return st.selectbox(label, cols, index=cols.index(default))

            st.markdown("**Pemetaan Kolom**")
            c1, c2 = st.columns(2)
            with c1:
                map_nama  = pick("nama *", "nama")
                map_hari  = pick("hari", "hari")
                map_aktif = pick("aktif", "aktif")
                map_max   = pick("max_per_hari", "max_per_hari")
            with c2:
                map_alias   = pick("alias", "alias")
                map_jabatan = pick("jabatan", "jabatan")
                map_catatan = pick("catatan", "catatan")

            def _get(colname):
                return df_src[colname] if (colname != "— none —" and colname in df_src.columns) else pd.Series([None]*len(df_src))

            if st.button("🚀 Impor & Gabung (Upsert by nama)", type="primary", width='stretch', key="btn_import_hakim"):
                if map_nama == "— none —":
                    st.error("Kolom **nama** wajib dipetakan.")
                else:
                    df = _load_hakim_csv()
                    inserted = updated = skipped = 0
                    tmp = pd.DataFrame({
                        "nama":   _get(map_nama).astype(str).str.strip(),
                        "hari":   _get(map_hari).astype(str).fillna("").str.strip(),
                        "aktif":  _get(map_aktif),
                        "max":    _get(map_max),
                        "alias":  _get(map_alias).astype(str).fillna("").str.strip(),
                        "jab":    _get(map_jabatan).astype(str).fillna("").str.strip(),
                        "cat":    _get(map_catatan).astype(str).fillna("").str.strip(),
                    })
                    for _, r in tmp.iterrows():
                        nama = str(r["nama"] or "").strip()
                        if not nama:
                            skipped += 1; continue
                        df, status = upsert_hakim_by_nama_csv(
                            df,
                            nama=nama,
                            hari=str(r["hari"] or "").strip(),
                            aktif=1 if _is_active_value(r["aktif"]) else 0,
                            max_per_hari=_safe_int(r["max"]),
                            catatan=str(r["cat"] or ""),
                            alias=str(r["alias"] or ""),
                            jabatan=str(r["jab"] or "")
                        )
                        if status == "inserted": inserted += 1
                        elif status == "updated": updated += 1
                        else: skipped += 1
                    _save_hakim_csv(df)
                    st.success(f"Selesai impor: INSERTED={inserted}, UPDATED={updated}, SKIPPED={skipped}")
                    st.rerun()

    # Hitung Beban dari rekap (exclude VERZET)
    hakim_df = _load_hakim_csv()
    rekap_df = _load_rekap_csv()

    def _build_metode_norm(df: pd.DataFrame) -> pd.Series:
        if df.empty: return pd.Series(dtype="string", index=df.index)
        m = df.get("metode", pd.Series(index=df.index, dtype="string")).astype(str).str.strip().str.lower()
        m = m.replace({"ecourt": "e-court", "e court": "e-court"})
        ok = m.isin(["e-court", "manual"])
        m = m.where(ok, "e-court")
        return m

    def _is_verzet_row(x) -> bool:
        return str(x).strip().upper() == "VERZET"

    if hakim_df.empty:
        st.info("Belum ada data Hakim. Klik ➕ Tambah Hakim atau gunakan Import CSV.")
    else:
        # Map tokens nama+alias
        name_to_idx: Dict[str, int] = {}
        token_sets: Dict[int, Set[str]] = {}
        df_idx = hakim_df.reset_index(drop=True)

        for i, row in df_idx.iterrows():
            nm = str(row.get("nama",""))
            key = _name_key_full(nm)
            if key: name_to_idx.setdefault(key, i)
            tset = set(key.split())
            for al in _alias_entries(str(row.get("alias",""))):
                k2 = _name_key_full(al)
                if k2:
                    name_to_idx.setdefault(k2, i)
                    tset |= set(k2.split())
            token_sets[i] = tset

        rdx = rekap_df.copy()
        if not rdx.empty and "klasifikasi" in rdx.columns:
            rdx = rdx[~rdx["klasifikasi"].map(_is_verzet_row)].copy()
        total_rekap = len(rekap_df)
        total_dihitung = len(rdx)

        ecount_per_idx = {i: 0 for i in range(len(df_idx))}
        mcount_per_idx = {i: 0 for i in range(len(df_idx))}
        unmatched_rows = []

        if not rdx.empty and "hakim" in rdx.columns:
            metode_norm = _build_metode_norm(rdx)
            rdx = rdx.reset_index(drop=True)
            for j, rec in rdx.iterrows():
                raw_name = str(rec.get("hakim",""))
                if not raw_name.strip():
                    unmatched_rows.append((j, raw_name, "nama kosong")); continue
                rec_key = _name_key_full(raw_name)
                idx = name_to_idx.get(rec_key)
                if idx is None:
                    rset = set(rec_key.split())
                    cands = [ii for ii, ts in token_sets.items() if rset.issubset(ts) or (rset & ts)]
                    if cands:
                        cands.sort(key=lambda ii: (-len(token_sets[ii] & rset), ii))
                        idx = cands[0]
                if idx is None:
                    unmatched_rows.append((j, raw_name, "tidak cocok")); continue
                if str(metode_norm.iloc[j]).lower() == "manual":
                    mcount_per_idx[idx] += 1
                else:
                    ecount_per_idx[idx] += 1

        st.caption(f"Total baris rekap: {total_rekap} • Dihitung: {total_dihitung} (exclude VERZET)")

        aktif_parsed = hakim_df.get("aktif", pd.Series(index=hakim_df.index)).apply(_is_active_value).reset_index(drop=True)

        records = []
        for i, row in df_idx.iterrows():
            records.append({
                "orig_i": i,
                "row_id": _safe_int(row.get("id")),
                "Nama": str(row.get("nama","")),
                "Hari": str(row.get("hari","")),
                "Aktif%s": "YA" if bool(aktif_parsed.iloc[i]) else "TIDAK",
                "_aktif_bool": bool(aktif_parsed.iloc[i]),
                "Max/Hari": _safe_int(row.get("max_per_hari")),
                "Catatan": str(row.get("catatan","") or ""),
                "Alias": str(row.get("alias","") or ""),
                "E-Court": int(ecount_per_idx.get(i,0)),
                "Manual": int(mcount_per_idx.get(i,0)),
                "Total (−Verzet)": int(ecount_per_idx.get(i,0)) + int(mcount_per_idx.get(i,0)),
            })
        view_df = pd.DataFrame.from_records(records)

        st.markdown("---")
        c1, c2, c3 = st.columns([1, 1.6, 0.9])
        page_size = c1.selectbox("Baris/hal", [10, 50, 100], index=0, key="hakim_ps")
        sort_options = ["(tanpa urut)","Nama","Hari","Aktif%s","Max/Hari","E-Court","Manual","Total (−Verzet)"]
        sort_by = c2.selectbox("Urutkan berdasarkan", sort_options, index=0, key="hakim_sortcol")
        asc = c3.toggle("Naik%s", value=True, key="hakim_asc")

        sig = f"{page_size}|{sort_by}|{asc}|{len(view_df)}"
        if st.session_state.get("hakim_sig") != sig:
            st.session_state["hakim_sig"] = sig
            st.session_state["hakim_page"] = 1
        page = int(st.session_state.get("hakim_page", 1))

        sort_map = {
            "Nama": "Nama", "Hari": "Hari", "Aktif%s": "_aktif_bool",
            "Max/Hari": "Max/Hari", "E-Court": "E-Court", "Manual":"Manual", "Total (−Verzet)":"Total (−Verzet)"
        }
        if sort_by != "(tanpa urut)":
            key = sort_map[sort_by]
            if key in view_df.columns:
                view_df = view_df.sort_values(key, ascending=asc, kind="stable")

        total_rows = len(view_df)
        page_size = int(page_size)
        total_pages = max(1, math.ceil(total_rows / page_size))
        page = min(max(1, page), total_pages)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        page_df = view_df.iloc[start_idx:end_idx].reset_index(drop=True)

        # Header grid
        COLS = [2.2,1.2,0.9,1.1,2.2,2.0,1.0,1.0,1.2,0.9,0.9]
        h = st.columns(COLS)
        h[0].markdown("**Nama**"); h[1].markdown("**Hari**"); h[2].markdown("**Aktif**"); h[3].markdown("**Max/Hari**")
        h[4].markdown("**Catatan**"); h[5].markdown("**Alias**"); h[6].markdown("**E-Court**"); h[7].markdown("**Manual**")
        h[8].markdown("**Total**"); h[9].markdown("**Edit**"); h[10].markdown("**Hapus**")
        st.markdown("<hr/>", unsafe_allow_html=True)

        for _, r in page_df.iterrows():
            cols = st.columns(COLS)
            cols[0].write(r["Nama"] or "-")
            cols[1].write(r["Hari"] or "-")
            cols[2].write(r["Aktif%s"])
            cols[3].write(int(r["Max/Hari"]))
            cols[4].write(r["Catatan"])
            cols[5].write(r["Alias"])
            cols[6].write(int(r["E-Court"]))
            cols[7].write(int(r["Manual"]))
            cols[8].write(int(r["Total (−Verzet)"]))
            orig_i = int(r["orig_i"]); row_id = int(r["row_id"]) if r["row_id"] else 0
            with cols[9]:
                if st.button("✏️", key=f"edit_hakim_{orig_i}"):
                    open_hakim_dialog("edit_hakim", f"Edit Hakim: {r['Nama']}", {"index": orig_i})
            with cols[10]:
                if st.button("🗑️", key=f"del_hakim_{row_id or orig_i}"):
                    df = _load_hakim_csv()
                    if row_id:
                        df = delete_hakim_by_id_csv(df, row_id)
                    else:
                        mask = df["nama"].astype(str).str.strip().str.lower() == str(r["Nama"]).strip().lower()
                        df = df[~mask].reset_index(drop=True)
                    _save_hakim_csv(df)
                    st.success(f"Dihapus: {r['Nama']}"); st.rerun()

        pc1, pc2, pc3 = st.columns([1,2,1])
        with pc1:
            if st.button("⬅️ Prev", width='stretch', disabled=(page<=1)):
                st.session_state["hakim_page"] = page - 1; st.rerun()
        with pc2:
            st.markdown(
                f"<div style='text-align:center'>Halaman <b>{page}</b> / <b>{total_pages}</b> • "
                f"Menampilkan <b>{min(page_size, total_rows-start_idx)}</b> dari <b>{total_rows}</b> baris "
                f"(<i>{start_idx+1}-{min(end_idx,total_rows)}</i>)</div>",
                unsafe_allow_html=True
            )
        with pc3:
            if st.button("Next ➡️", width='stretch', disabled=(page>=total_pages)):
                st.session_state["hakim_page"] = page + 1; st.rerun()

        render_hakim_dialog(hakim_df)

# ------------------- TAB 2: Cuti Hakim --------------
with tab2:
    # ====== STATE: visibilitas & payload form ======
    if "cuti_form" not in st.session_state:
        st.session_state["cuti_form"] = {
            "visible": False,
            "mode": "add",         # "add" | "edit"
            "nama": "",
            "mulai": None,         # datetime.date
            "akhir": None          # datetime.date
        }
    F = st.session_state["cuti_form"]

    # ====== Header + Tombol Tambah ======
    top_left, top_right = st.columns([2, 1])
    with top_left:
        st.subheader("Cuti Hakim")
    with top_right:
        if st.button("➕ Tambah Cuti", key="btn_show_add_cuti", width='stretch'):
            today = date.today()
            st.session_state["cuti_form"] = {
                "visible": True,
                "mode": "add",
                "nama": "",
                "mulai": today,
                "akhir": today
            }
            st.rerun()

    st.markdown("---")

    # ====== TABEL CUTI ======
    df_cuti = load_cuti()
    st.subheader("Daftar Cuti")
    if df_cuti.empty:
        st.info("Belum ada data cuti.")
    else:
        show = df_cuti.copy()
        show["mulai"] = pd.to_datetime(show["mulai"]).dt.date
        show["akhir"] = pd.to_datetime(show["akhir"]).dt.date
        show = show[["nama","mulai","akhir"]].reset_index(drop=True)

        COLS = [2.8, 1.2, 1.2, 0.9, 0.9]
        h = st.columns(COLS)
        h[0].markdown("**Nama**")
        h[1].markdown("**Mulai**")
        h[2].markdown("**Akhir**")
        h[3].markdown("**Edit**")
        h[4].markdown("**Hapus**")
        st.markdown("<hr/>", unsafe_allow_html=True)

        for i, r in show.iterrows():
            c = st.columns(COLS)
            c[0].write(str(r["nama"]))
            c[1].write(str(r["mulai"]))
            c[2].write(str(r["akhir"]))

            # EDIT → munculkan form dengan prefill
            if c[3].button("✏️", key=f"edit_cuti_{i}", width='stretch'):
                st.session_state["cuti_form"] = {
                    "visible": True,
                    "mode": "edit",
                    "nama": str(r["nama"]),
                    "mulai": pd.to_datetime(r["mulai"]).date(),
                    "akhir": pd.to_datetime(r["akhir"]).date()
                }
                st.rerun()

            # HAPUS baris langsung
            if c[4].button("🗑️", key=f"del_cuti_{i}", width='stretch'):
                base = load_cuti()
                m = (
                    (base["nama"].astype(str) == r["nama"]) &
                    (pd.to_datetime(base["mulai"]).dt.normalize() == pd.to_datetime(r["mulai"])) &
                    (pd.to_datetime(base["akhir"]).dt.normalize() == pd.to_datetime(r["akhir"]))
                )
                base2 = base[~m].reset_index(drop=True)
                save_cuti(base2)

                # jika yang dihapus kebetulan lagi terbuka di form, tutup form
                if F["visible"] and F["mode"] == "edit" and \
                   F["nama"] == str(r["nama"]) and \
                   pd.to_datetime(F["mulai"]).normalize() == pd.to_datetime(r["mulai"]) and \
                   pd.to_datetime(F["akhir"]).normalize() == pd.to_datetime(r["akhir"]):
                    st.session_state["cuti_form"]["visible"] = False
                st.success("Baris cuti dihapus 🗑️")
                st.rerun()

    # ====== FORM (muncul hanya jika visible) ======
    if F["visible"]:
        st.markdown("---")
        st.subheader("Form " + ("Edit" if F["mode"] == "edit" else "Tambah") + " Cuti")

        # --- nilai default tergantung mode ---
        default_nama = F.get("nama", "") or ""
        default_mulai = F.get("mulai") or date.today()
        default_akhir = F.get("akhir") or default_mulai

        # ===== Nama (sumber master / manual) — diletakkan di luar st.form agar switch langsung nyala
        names = _hakim_options()
        nama_src = st.radio(
            "Sumber nama hakim",
            ["Pilih dari master", "Ketik manual"],
            horizontal=True,
            index=0 if (names and default_nama in names) else 1,
            key="cuti_form_nama_src"
        )
        if nama_src == "Pilih dari master" and names:
            idx_default = ([""] + names).index(default_nama) if default_nama in names else 0
            nama_val = st.selectbox(
                "Nama hakim",
                [""] + names,
                index=idx_default,
                key="cuti_form_nama_sel"
            ).strip()
        else:
            nama_val = st.text_input(
                "Nama hakim (ketik)",
                value=default_nama,
                key="cuti_form_nama_txt"
            ).strip()

        # ===== Mode tanggal (single/range) — juga di luar st.form supaya switch langsung aktif
        mode_tgl = st.radio(
            "Mode input tanggal",
            ["Satu tanggal", "Rentang tanggal"],
            horizontal=True,
            index=0 if (default_mulai == default_akhir) else 1,
            key="cuti_form_mode_tgl"
        )

        # ===== Input tanggal (render keduanya, aktifkan sesuai pilihan)
        t_single = st.date_input(
            "Tanggal",
            value=default_mulai,
            key="cuti_form_t_single",
            disabled=(mode_tgl != "Satu tanggal")
        )

        col_s, col_e = st.columns(2)
        t_mulai = col_s.date_input(
            "Mulai",
            value=default_mulai,
            key="cuti_form_t_mulai",
            disabled=(mode_tgl != "Rentang tanggal")
        )
        t_akhir = col_e.date_input(
            "Akhir",
            value=default_akhir,
            key="cuti_form_t_akhir",
            disabled=(mode_tgl != "Rentang tanggal")
        )

        # Normalisasi tanggal untuk commit
        if mode_tgl == "Satu tanggal":
            s_val = pd.to_datetime(t_single).normalize()
            e_val = s_val
        else:
            s_val = pd.to_datetime(min(t_mulai, t_akhir)).normalize()
            e_val = pd.to_datetime(max(t_mulai, t_akhir)).normalize()

        # ===== Tombol aksi (tanpa st.form biar simpel dan responsif)
        a1, a2, a3 = st.columns([1, 1, 1])
        if a1.button("💾 Simpan", type="primary", key="cuti_form_save", width='stretch'):
            if not nama_val:
                st.error("Nama wajib diisi.")
            else:
                cur = load_cuti()

                if F["mode"] == "edit":
                    # hapus entri lama yang di-edit (match exact)
                    m = (
                        (cur["nama"].astype(str) == str(default_nama)) &
                        (pd.to_datetime(cur["mulai"]).dt.normalize() == pd.to_datetime(default_mulai)) &
                        (pd.to_datetime(cur["akhir"]).dt.normalize() == pd.to_datetime(default_akhir))
                    )
                    cur = cur[~m].reset_index(drop=True)

                new = pd.DataFrame([{"nama": nama_val, "mulai": s_val, "akhir": e_val}])
                merged = pd.concat([cur, new], ignore_index=True)
                save_cuti(merged)  # fungsi ini tetap auto-merge rentang beririsan

                st.session_state["cuti_form"]["visible"] = False
                st.success("Cuti tersimpan ✅")
                st.rerun()

        if a2.button("Batal", key="cuti_form_cancel", width='stretch'):
            st.session_state["cuti_form"]["visible"] = False
            st.rerun()

        if F["mode"] == "edit":
            if a3.button("🗑️ Hapus", key="cuti_form_delete", width='stretch'):
                base = load_cuti()
                m = (
                    (base["nama"].astype(str) == str(default_nama)) &
                    (pd.to_datetime(base["mulai"]).dt.normalize() == pd.to_datetime(default_mulai)) &
                    (pd.to_datetime(base["akhir"]).dt.normalize() == pd.to_datetime(default_akhir))
                )
                base2 = base[~m].reset_index(drop=True)
                save_cuti(base2)
                st.session_state["cuti_form"]["visible"] = False
                st.success("Cuti dihapus 🗑️")
                st.rerun()
