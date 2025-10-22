# pages/1_📥_Input_&_Hasil.py — debug + JS Ghoib otomatis
from __future__ import annotations
import pandas as pd
import streamlit as st
from datetime import date, datetime, timedelta

from app_core.data_io import load_with_sk, save_table
from app_core.helpers import (
    NAMA_BULAN, HARI_MAP, format_tanggal_id, compute_nomor_tipe,
    next_judge_day, choose_hakim_auto, choose_anggota_auto, df_display_clean
)

# rotasi PP/JS paket dari SK (langsung DB / noaktif) + debug
try:
    from app_core.helpers_rotate_from_db_noaktif import (
        rotate_pp, rotate_js_cross, debug_sk_for_ketua, refresh_sk_cache
    )
except Exception:
    try:
        from app_core.helpers_rotate_from_db import rotate_pp, rotate_js_cross, set_sk_use_aktif, refresh_sk_cache  # type: ignore
        try: set_sk_use_aktif(False)
        except Exception: pass
        def debug_sk_for_ketua(hakim, rekap_df=None): return {"matched_rows": pd.DataFrame(), "pp_candidates": [], "js_candidates": [], "pp_counts": {}, "js_counts": {}, "pp_pick": None, "js_pick": None}
    except Exception:
        from app_core.helpers import rotate_pp, rotate_js_cross  # type: ignore
        def debug_sk_for_ketua(hakim, rekap_df=None): return {"matched_rows": pd.DataFrame(), "pp_candidates": [], "js_candidates": [], "pp_counts": {}, "js_counts": {}, "pp_pick": None, "js_pick": None}
        def refresh_sk_cache(): pass

# JS Ghoib otomatis dari DB js_ghoib (prioritas saat jenis=GHOIB)
try:
    from app_core.helpers_js_ghoib import choose_js_ghoib_db, debug_js_ghoib
except Exception:
    def choose_js_ghoib_db(rekap_df, use_aktif=True): return ""
    def debug_js_ghoib(rekap_df, use_aktif=True): return {"candidates": [], "counts": {}, "pick": "", "table": pd.DataFrame()}

st.set_page_config(page_title="📥 Input & Hasil (Debug + Ghoib)", page_icon="📥", layout="wide")
st.header("📥 Input & Hasil")

# ==== LOAD semua data ====
hakim_df, pp_df, js_df, js_ghoib_df, libur_df, rekap_df, sk_df = load_with_sk()
if sk_df is None or (isinstance(sk_df, pd.DataFrame) and sk_df.empty):
    sk_df = st.session_state.get("sk_df", pd.DataFrame())

# ==== Form kiri/kanan ====
left, right = st.columns([2, 1])
with left:
    nomor = st.text_input("Nomor Perkara")
    tgl_register_input = st.date_input("Tanggal Register", value=date.today())
    KLASIFIKASI_OPSI = ["CG","CT","VERZET","PAW","WARIS","ISTBAT","HAA","Dispensasi","Poligami","Maqfud","Asal Usul","Perwalian","Harta Bersama","EkSya","Lain-Lain","Lainnya (ketik)"]
    klasifikasi_sel = st.selectbox("Klasifikasi Perkara", KLASIFIKASI_OPSI, index=0)
    klasifikasi_final = st.text_input("Tulis klasifikasi lainnya") if klasifikasi_sel == "Lainnya (ketik)" else klasifikasi_sel
    jenis = st.selectbox("Jenis Perkara (Proses)", ["Biasa","ISTBAT","GHOIB","ROGATORI","MAFQUD"])

with right:
    metode_input = st.selectbox("Metode", ["E-Court","Manual"], index=0)
    semua_nama = []
    if not hakim_df.empty and "nama" in hakim_df.columns:
        df_sorted = hakim_df.copy()
        df_sorted["__aktif_rank"] = (df_sorted.get("aktif","YA").astype(str).str.upper() != "YA").astype(int)
        df_sorted = df_sorted.sort_values(["__aktif_rank","nama"])
        semua_nama = df_sorted["nama"].dropna().astype(str).tolist()
    hakim_manual = st.selectbox("Hakim (kosongkan untuk otomatis)", [""] + semua_nama)
    pp_manual = st.text_input("PP Manual (opsional)")
    js_manual = st.text_input("JS Manual (opsional)")
    tipe_pdt = st.selectbox("Tipe Perkara (Pdt)", ["Otomatis","Pdt.G","Pdt.P","Pdt.Plw"])

# ==== Tentukan Ketua ====
hakim = hakim_manual.strip() if str(hakim_manual).strip() else (choose_hakim_auto(hakim_df, rekap_df, tgl_register_input) if not hakim_df.empty else "")

# ==== Anggota otomatis ====
anggota1, anggota2 = choose_anggota_auto(hakim, rekap_df, hakim_df, n=2)

# ==== PP & JS ====
if pp_manual.strip():
    pp_val = pp_manual.strip()
else:
    pp_val = rotate_pp(hakim, rekap_df)

if js_manual.strip():
    js_val = js_manual.strip()
else:
    if str(jenis).upper() == "GHOIB":
        js_val = choose_js_ghoib_db(rekap_df, use_aktif=True) or rotate_js_cross(hakim, rekap_df)
    else:
        js_val = rotate_js_cross(hakim, rekap_df)

# ==== Jadwal sidang ====
base = tgl_register_input if isinstance(tgl_register_input, (datetime, date)) else date.today()
hari_sidang_num = 0
if not hakim_df.empty and hakim and "nama" in hakim_df.columns and "hari_sidang" in hakim_df.columns:
    try:
        hari_text = hakim_df.set_index("nama").loc[hakim, "hari_sidang"]
        hari_sidang_num = HARI_MAP.get(str(hari_text), 0)
    except Exception:
        pass
libur_set = set(libur_df["tanggal"].astype(str).tolist()) if isinstance(libur_df, pd.DataFrame) and "tanggal" in libur_df.columns else set()
if jenis == "Biasa":
    calon_min8 = base + timedelta(days=8)
    d1 = next_judge_day(calon_min8, hari_sidang_num, libur_set) if hari_sidang_num else calon_min8
    tgl_sidang = d1 if (d1 - base).days <= 14 else (next_judge_day(base + timedelta(days=14), hari_sidang_num, libur_set) if hari_sidang_num else base + timedelta(days=14))
elif jenis == "ISTBAT":
    calon = base + timedelta(days=21); tgl_sidang = next_judge_day(calon, hari_sidang_num, libur_set) if hari_sidang_num else calon
elif jenis == "GHOIB":
    offset = 124 if str(klasifikasi_final).upper() in ("CT","CG") else 31
    calon = base + timedelta(days=offset); tgl_sidang = next_judge_day(calon, hari_sidang_num, libur_set) if hari_sidang_num else calon
elif jenis == "ROGATORI":
    calon = base + timedelta(days=124); tgl_sidang = next_judge_day(calon, hari_sidang_num, libur_set) if hari_sidang_num else calon
elif jenis == "MAFQUD":
    calon = base + timedelta(days=246); tgl_sidang = next_judge_day(calon, hari_sidang_num, libur_set) if hari_sidang_num else calon
else:
    tgl_sidang = base

# ==== Output ringkas ====
nomor_fmt, tipe_final = compute_nomor_tipe(nomor, klasifikasi_final, tipe_pdt)
st.subheader("Hasil Otomatis")
resL, resR = st.columns(2)
with resL:
    st.write("**Hakim**:", hakim or "-")
    st.write("**Anggota 1**:", anggota1 or "-")
    st.write("**Anggota 2**:", anggota2 or "-")
with resR:
    st.write("**PP**:", pp_val or "-")
    st.write("**JS**:", js_val or "-")
    st.markdown("**Tanggal Sidang**")
    st.markdown(f"<div style='font-size:1.4rem;font-weight:600'>{format_tanggal_id(tgl_sidang)}</div>", unsafe_allow_html=True)

# ==== Simpan ke rekap ====
if st.button("💾 Simpan ke Rekap", use_container_width=True):
    new_row = {
        "nomor_perkara": nomor_fmt,
        "tgl_register": pd.to_datetime(base),
        "klasifikasi": klasifikasi_final,
        "jenis_perkara": jenis,
        "metode": metode_input,
        "hakim": hakim, "anggota1": anggota1, "anggota2": anggota2,
        "pp": pp_val, "js": js_val,
        "tgl_sidang": pd.to_datetime(tgl_sidang)
    }
    tmp_df = pd.concat([rekap_df, pd.DataFrame([new_row])], ignore_index=True)
    save_table(tmp_df, "rekap")
    st.success("Tersimpan!"); st.rerun()

# ==== Rekap harian ====
st.markdown("---")
st.subheader("Rekap Hari Ini (berdasarkan Tanggal Register)")
filter_date = st.date_input("Filter tanggal", value=base, key="filter_rekap_input")
if not rekap_df.empty and "tgl_register" in rekap_df.columns:
    mask = rekap_df["tgl_register"].dt.date == filter_date
    view = rekap_df.loc[mask].copy()
    view = df_display_clean(view)
    st.dataframe(view, use_container_width=True)
else:
    st.info("Belum ada data rekap.")

# ==== Debug: SK paket + JS Ghoib ====
with st.expander("🔍 Debug Auto-Assign"):
    colA, colB = st.columns([1,1])
    with colA:
        if st.button("🔄 Reload SK dari DB (clear cache)", use_container_width=True):
            try:
                refresh_sk_cache()
            finally:
                st.rerun()
    # debug SK paket
    try:
        info = debug_sk_for_ketua(hakim, rekap_df)
        st.write("**[SK Paket] PP candidates:**", info.get("pp_candidates", []))
        st.write("**[SK Paket] JS candidates:**", info.get("js_candidates", []))
        st.write("**[SK Paket] PP pick:**", info.get("pp_pick"), " | **JS pick:**", info.get("js_pick"))
        rows = info.get("matched_rows")
        st.markdown("**Baris SK yang cocok dengan Ketua:**")
        if isinstance(rows, pd.DataFrame) and not rows.empty:
            st.dataframe(rows, use_container_width=True)
        else:
            st.info("Tidak ada baris SK yang cocok. Cek nama Ketua & kolom pp/js di SK.")
    except Exception as e:
        st.warning(f"Debug SK tidak tersedia: {e}")
    # debug JS ghoib
    try:
        dbg = debug_js_ghoib(rekap_df, use_aktif=True)
        st.write("**[JS Ghoib] Kandidat:**", dbg.get("candidates", []))
        st.write("**[JS Ghoib] Beban (rekap GHOIB):**", dbg.get("counts", {}))
        st.write("**[JS Ghoib] Pick:**", dbg.get("pick", ""))
        tbl = dbg.get("table")
        if isinstance(tbl, pd.DataFrame) and not tbl.empty:
            st.dataframe(tbl, use_container_width=True)
    except Exception as e:
        st.warning(f"Debug JS Ghoib tidak tersedia: {e}")
