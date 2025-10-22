# pages/2b_Input_Hasil_Perkara.py
import streamlit as st
import pandas as pd
from datetime import date
from pathlib import Path
from db import get_conn, init_db

# Optional helpers (fallback-safe)
try:
    from app_core.ui import inject_styles  # type: ignore
except Exception:
    def inject_styles(): pass

try:
    from app_core.exports import export_csv as _export_csv_fn  # type: ignore
except Exception:
    _export_csv_fn = None

st.set_page_config(page_title="Form Perkara • Input & Hasil", layout="wide")
inject_styles()
st.header("🧾 Form Perkara — Input & Hasil")
init_db()

# ================= DB helpers =================
def load_table(name: str) -> pd.DataFrame:
    con = get_conn()
    try:
        return pd.read_sql_query(f"SELECT * FROM {name}", con)
    except Exception:
        return pd.DataFrame()
    finally:
        con.close()

def insert_rekap_row(row: dict):
    con = get_conn()
    try:
        cur = con.cursor()
        cur.execute(
            """INSERT INTO rekap
               (nomor_perkara, tgl_register, klasifikasi, jenis_perkara, metode,
                hakim, anggota1, anggota2, pp, js, tgl_sidang)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                row.get("nomor_perkara","").strip(),
                row.get("tgl_register",""),
                row.get("klasifikasi","").strip(),
                row.get("jenis_perkara","").strip(),
                row.get("metode","").strip().lower(),
                row.get("hakim","").strip(),
                row.get("anggota1","").strip(),
                row.get("anggota2","").strip(),
                row.get("pp","").strip(),
                row.get("js","").strip(),
                row.get("tgl_sidang",""),
            )
        )
        con.commit()
    finally:
        con.close()

# ================= CSV export =================
def _export_rekap_csv(df: pd.DataFrame | None = None):
    """Tuliskan rekap_df.csv ke lokasi standar app atau ke folder data/ (UTF-8-SIG)."""
    try:
        out = df.copy() if isinstance(df, pd.DataFrame) else load_table("rekap").copy()
        if _export_csv_fn:
            _export_csv_fn(out, "rekap_df.csv")
        else:
            data_dir = Path("data"); data_dir.mkdir(parents=True, exist_ok=True)
            out.to_csv(data_dir / "rekap_df.csv", index=False, encoding="utf-8-sig")
        st.toast("rekap_df.csv diperbarui ✅", icon="✅")
    except Exception as e:
        st.warning(f"Gagal auto-generate rekap_df.csv: {e}")

# ================= Utilities =================
def _indo_dayname(d) -> str | None:
    """Kembalikan nama hari Indonesia untuk tanggal (Senin, Selasa, ...)"""
    if d is None or d == "":
        return None
    if isinstance(d, str):
        dt = pd.to_datetime(d, errors="coerce")
    else:
        dt = pd.to_datetime(d, errors="coerce")
    if pd.isna(dt):
        return None
    days = ["Senin","Selasa","Rabu","Kamis","Jumat","Sabtu","Minggu"]
    return days[dt.weekday()]

def _to_iso(d) -> str:
    if d is None or d == "":
        return ""
    dt = pd.to_datetime(d, errors="coerce")
    if pd.isna(dt): 
        return ""
    return dt.date().isoformat()

# ================= Load master tables =================
sk_df = load_table("sk_majelis")
hakim_df = load_table("hakim")
pp_df = load_table("pp")
js_df = load_table("js")
rekap_df = load_table("rekap")

active_sk = sk_df.copy()
if not active_sk.empty and "aktif" in active_sk.columns:
    active_sk = active_sk[active_sk["aktif"].fillna(1).astype(int) != 0].reset_index(drop=True)

# ================= Session state (form model) =================
DEFAULT_FORM = {
    "nomor_perkara": "",
    "tgl_register": "",
    "tgl_sidang": "",
    "klasifikasi": "",
    "jenis_perkara": "",
    "metode": "e-court",
    "hakim": "",
    "anggota1": "",
    "anggota2": "",
    "pp": "",
    "js": "",
    "sk_selected": None,
}
if "form_perkara" not in st.session_state:
    st.session_state["form_perkara"] = DEFAULT_FORM.copy()

fm = st.session_state["form_perkara"]

# ================= Layout =================
top_l, top_r = st.columns([1.2, 1.0], gap="large")

# ---- Left: Data perkara ----
with top_l:
    st.subheader("📝 Data Perkara")
    fm["nomor_perkara"] = st.text_input("Nomor Perkara", value=fm.get("nomor_perkara",""), placeholder="Contoh: 123/Pdt.G/2025/PA.XYZ")
    dcol1, dcol2 = st.columns(2)
    init_reg = pd.to_datetime(fm.get("tgl_register") or "today", errors="coerce")
    init_sid = pd.to_datetime(fm.get("tgl_sidang") or "today", errors="coerce")
    fm["tgl_register"] = _to_iso(dcol1.date_input("Tanggal Register", value=init_reg.date() if not pd.isna(init_reg) else None))
    fm["tgl_sidang"]   = _to_iso(dcol2.date_input("Tanggal Sidang", value=init_sid.date() if not pd.isna(init_sid) else None))
    w1, w2, w3 = st.columns([1,1,1])
    fm["klasifikasi"] = w1.text_input("Klasifikasi", value=fm.get("klasifikasi",""), placeholder="Contoh: Cerai Gugat / Hadhanah / ...")
    fm["jenis_perkara"] = w2.text_input("Jenis Perkara", value=fm.get("jenis_perkara",""), placeholder="Contoh: Pdt.G / P / Plw / GHOIB")
    fm["metode"] = w3.selectbox("Metode", options=["e-court","manual"], index=0 if (fm.get("metode","e-court").lower()!="manual") else 1)

# ---- Right: SK selector + auto fill ----
with top_r:
    st.subheader("🏛️ Ambil dari SK Majelis")
    if active_sk.empty:
        st.info("Belum ada SK Majelis aktif.")
        fm["sk_selected"] = None
    else:
        # Filter by hari (auto dari tanggal sidang)
        hari_hint = _indo_dayname(fm.get("tgl_sidang") or "today")
        f1, f2 = st.columns([1,1])
        by_day_only = f1.checkbox(f"Filter Hari = {hari_hint or '-'}", value=bool(hari_hint))
        query = f2.text_input("Cari (majelis/nama)", value="", placeholder="ketik sebagian nama…").strip().lower()

        options = active_sk.copy()
        if by_day_only and "hari" in options.columns and hari_hint:
            options = options[options["hari"].astype(str).str.strip().str.lower() == str(hari_hint).lower()]
        if query:
            def _contains(df, col):
                return df[col].astype(str).str.lower().str.contains(query, na=False)
            cols = ["majelis","ketua","anggota1","anggota2","pp1","pp2","js1","js2"]
            mask = None
            for c in cols:
                if c in options.columns:
                    m = _contains(options, c)
                    mask = m if mask is None else (mask | m)
            options = options[mask] if mask is not None else options

        display_opts = []
        idx_map = {}
        for i, r in options.reset_index(drop=True).iterrows():
            label = f"{r.get('majelis','-')} • {r.get('hari','-')} • K: {r.get('ketua','-')} • A1: {r.get('anggota1','-')} • A2: {r.get('anggota2','-')}"
            display_opts.append(label)
            idx_map[label] = i

        sel = st.selectbox("Pilih SK", options=(display_opts or ["(Tidak ada SK tersedia)"]), index=0)
        can_apply = bool(display_opts)
        if st.button("Gunakan SK ini → Isi Otomatis", use_container_width=True, disabled=not can_apply):
            i = idx_map.get(sel, None)
            if i is not None:
                row = options.reset_index(drop=True).iloc[i]
                fm["hakim"] = str(row.get("ketua","") or "")
                fm["anggota1"] = str(row.get("anggota1","") or "")
                fm["anggota2"] = str(row.get("anggota2","") or "")
                fm["pp"] = str(row.get("pp1","") or "")
                fm["js"] = str(row.get("js1","") or "")
                fm["sk_selected"] = str(row.get("majelis","") or "")
                st.success("Bidang Hakim/Anggota/PP/JS diisi dari SK.")
                st.rerun()

# ---- Assignment fields (editable) ----
st.subheader("👥 Penugasan (bisa disunting)")
c1, c2, c3, c4, c5 = st.columns([1.4, 1.4, 1.4, 1.2, 1.2])
fm["hakim"]    = c1.text_input("Hakim Ketua", value=fm.get("hakim",""))
fm["anggota1"] = c2.text_input("Anggota 1", value=fm.get("anggota1",""))
fm["anggota2"] = c3.text_input("Anggota 2", value=fm.get("anggota2",""))
fm["pp"]       = c4.text_input("PP", value=fm.get("pp",""))
fm["js"]       = c5.text_input("JS", value=fm.get("js",""))

tool1, tool2, _ = st.columns([1,1,3])
if tool1.button("🔁 Tukar PP ↔️ (pp1/pp2) / JS ↔️ (js1/js2)", use_container_width=True):
    if active_sk is not None and fm.get("sk_selected"):
        row = active_sk[active_sk["majelis"].astype(str) == fm["sk_selected"]]
        if not row.empty:
            r = row.iloc[0]
            new_pp = str(r.get("pp2","") or "")
            new_js = str(r.get("js2","") or "")
            if new_pp or new_js:
                if new_pp: fm["pp"] = new_pp
                if new_js: fm["js"] = new_js
                st.success("PP/JS ditukar ke opsi kedua dari SK.")
                st.rerun()
            else:
                st.info("SK tidak memiliki pp2/js2. Tidak ada yang ditukar.")
        else:
            st.info("SK terpilih tidak ditemukan lagi.")
    else:
        st.info("Belum ada SK terpilih untuk ditukar.")

if tool2.button("🧹 Kosongkan Penugasan", use_container_width=True):
    for k in ["hakim","anggota1","anggota2","pp","js"]:
        fm[k] = ""
    st.rerun()

# ---- Submit / Reset ----
st.markdown("---")
btnL, btnR = st.columns([1,1])
submit = btnL.button("💾 Simpan ke Rekap", type="primary", use_container_width=True)
reset  = btnR.button("↺ Reset Form", use_container_width=True)

# Validation + Save
def _validate(fm) -> list[str]:
    errs = []
    if not (fm.get("nomor_perkara","").strip()):
        errs.append("Nomor perkara wajib diisi.")
    if not fm.get("tgl_register"):
        errs.append("Tanggal register wajib diisi.")
    if not fm.get("tgl_sidang"):
        errs.append("Tanggal sidang wajib diisi.")
    if not (fm.get("hakim","").strip()):
        errs.append("Nama Hakim Ketua wajib diisi (bisa otomatis dari SK).")
    if not (fm.get("pp","").strip()):
        errs.append("Nama PP wajib diisi (bisa otomatis dari SK).")
    if not (fm.get("js","").strip()):
        errs.append("Nama JS wajib diisi (bisa otomatis dari SK).")
    if fm.get("metode","").lower() not in {"e-court","manual"}:
        errs.append("Metode harus e-court atau manual.")
    return errs

if submit:
    errors = _validate(fm)
    if errors:
        for e in errors: st.error(e)
    else:
        rec = {k: fm.get(k) for k in ["nomor_perkara","tgl_register","klasifikasi","jenis_perkara","metode",
                                      "hakim","anggota1","anggota2","pp","js","tgl_sidang"]}
        insert_rekap_row(rec)
        _export_rekap_csv()
        st.success("Tersimpan ke rekap ✅")

        with st.expander("🔎 Hasil Otomatis (ringkas)", expanded=True):
            info = {
                "Nomor": fm.get("nomor_perkara",""),
                "Tanggal Register": fm.get("tgl_register",""),
                "Tanggal Sidang": fm.get("tgl_sidang",""),
                "Hari (dari tgl sidang)": _indo_dayname(fm.get("tgl_sidang","")),
                "SK Dipakai": fm.get("sk_selected","(manual)"),
                "Hakim": fm.get("hakim",""),
                "Anggota 1": fm.get("anggota1",""),
                "Anggota 2": fm.get("anggota2",""),
                "PP": fm.get("pp",""),
                "JS": fm.get("js",""),
                "Metode": fm.get("metode",""),
                "Klasifikasi": fm.get("klasifikasi",""),
                "Jenis Perkara": fm.get("jenis_perkara",""),
            }
            st.table(pd.DataFrame(info.items(), columns=["Field","Nilai"]))

            if (fm.get("js","").strip() == "") and not active_sk.empty:
                st.warning("JS dari SK kosong / tidak ditemukan. Isi manual ya.")

        keep = ["tgl_register","tgl_sidang","sk_selected","metode"]
        new_state = {k: (fm[k] if k in keep else "") for k in DEFAULT_FORM.keys()}
        st.session_state["form_perkara"] = new_state
        st.rerun()

if reset:
    st.session_state["form_perkara"] = DEFAULT_FORM.copy()
    st.rerun()

# ================= Recent entries =================
st.markdown("---")
st.subheader("🗂️ Entri Terbaru")
latest = load_table("rekap")
if latest.empty:
    st.info("Belum ada data di rekap.")
else:
    if "id" in latest.columns:
        latest = latest.sort_values("id", ascending=False)
    elif "tgl_register" in latest.columns:
        latest = latest.sort_values("tgl_register", ascending=False)
    st.dataframe(latest.head(100), use_container_width=True)
