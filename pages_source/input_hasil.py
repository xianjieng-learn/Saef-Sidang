# 📥 Input & Hasil — versi pakai SK Majelis untuk rotasi PP/JS
from __future__ import annotations
import io
import pandas as pd
import streamlit as st
from datetime import date, datetime, timedelta

# ambil data + SK
from app_core.data_io import load_with_sk, save_table
from app_core.helpers import (
    NAMA_BULAN, HARI_MAP, format_tanggal_id, compute_nomor_tipe,
    next_judge_day, choose_hakim_auto, rotate_pp, rotate_js_cross,
    choose_js_ghoib, choose_anggota_auto, df_display_clean
)
from app_core.ui import inject_styles
from app_core.dialogs import render_dialog

def run():
    st.set_page_config(page_title="Input & Hasil", layout="wide")
    inject_styles()
    st.header("📥 Input & Hasil")

    # ====== LOAD semuata + SK ======
    hakim_df, pp_df, js_df, js_ghoib_df, libur_df, rekap_df, sk_df = load_with_sk()
    # kalau load_with_sk belum ada sk_df, coba ambil dari session
    if (sk_df is None) or (isinstance(sk_df, pd.DataFrame) and sk_df.empty):
        sk_df = st.session_state.get("sk_df", pd.DataFrame())

    left, right = st.columns([2, 1])
    with left:
        nomor = st.text_input("Nomor Perkara")
        tgl_register_input = st.date_input("Tanggal Register", value=date.today())
        st.caption(f"Tanggal Register (ID): **{format_tanggal_id(tgl_register_input)}**")
        KLASIFIKASI_OPSI = [
            "CG", "CT", "VERZET", "PAW", "WARIS", "ISTBAT", "HAA",
            "Dispensasi", "Poligami", "Maqfud", "Asal Usul", "Perwalian",
            "Harta Bersama", "EkSya", "Lain-Lain", "Lainnya (ketik)"
        ]
        klasifikasi_sel = st.selectbox("Klasifikasi Perkara", KLASIFIKASI_OPSI, index=0)
        if klasifikasi_sel == "Lainnya (ketik)":
            klasifikasi_custom = st.text_input("Tulis klasifikasi lainnya")
            klasifikasi_final = klasifikasi_custom.strip()
        else:
            klasifikasi_final = klasifikasi_sel
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

    # ====== Tentukan Ketua (manual → otomatis by beban) ======
    hakim = hakim_manual.strip() if str(hakim_manual).strip() else (
        choose_hakim_auto(hakim_df, rekap_df, tgl_register_input) if not hakim_df.empty else ""
    )

    # ====== Ambil hari sidang ketua ======
    hari_sidang_num = 0
    if not hakim_df.empty and hakim and "nama" in hakim_df.columns and "hari_sidang" in hakim_df.columns:
        try:
            hari_text = hakim_df.set_index("nama").loc[hakim, "hari_sidang"]
            hari_sidang_num = HARI_MAP.get(str(hari_text), 0)
        except Exception:
            pass

    # ====== Anggota otomatis (tetap pakai helper lama) ======
    anggota1, anggota2 = choose_anggota_auto(hakim, rekap_df, hakim_df, n=2)

    # ====== PP & JS ======
    # prioritas: manual → kalau kosong: rotasi via SK (kirim sk_df=sk_df)
    # fallback tanpa SK: helper lama (tetap aman, tidak KeyError)
    if pp_manual.strip():
        pp_val = pp_manual.strip()
    else:
        pp_val = rotate_pp(hakim, rekap_df, pp_df, sk_df=sk_df, seed_pp="pp1")

    if js_manual.strip():
        js_val = js_manual.strip()
    else:
        if str(jenis).upper() == "GHOIB":
            js_val = choose_js_ghoib(js_ghoib_df)
        else:
            js_val = rotate_js_cross(hakim, rekap_df, js_df, sk_df=sk_df, seed_js="js1")

    # ====== Jadwal sidang otomatis ======
    base = tgl_register_input if isinstance(tgl_register_input, (datetime, date)) else date.today()
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

    # ====== Output ringkas ======
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
        st.markdown(f"<div class='bigdate'>{format_tanggal_id(tgl_sidang)}</div>", unsafe_allow_html=True)

    st.caption(f"Nomor (format akhir): **{nomor_fmt}**")

    # ====== Simpan ke rekap ======
    if st.button("💾 Simpan ke Rekap"):
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

    # ====== Rekap harian ======
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

    # ====== Debug singkat ======
    with st.expander("🔧 Debug SK"):
        st.caption("Potongan SK (dipakai untuk rotasi PP/JS):")
        st.dataframe(sk_df.head(20) if isinstance(sk_df, pd.DataFrame) else pd.DataFrame(), use_container_width=True)

    render_dialog(hakim_df, pp_df, js_df, js_ghoib_df, libur_df)

# Jalankan halaman bila file ini dieksekusi sebagai modul
if __name__ == "__main__":
    run()
