# pages/2_📊_Rekap_&_Utilitas.py
import streamlit as st
import pandas as pd

from app_core.data_io import load_all, save_table
from app_core.helpers import df_display_clean, compute_nomor_tipe, to_excel_bytes
from app_core.ui import inject_styles

st.set_page_config(page_title="Rekap & Utilitas", layout="wide")
inject_styles()

st.header("📊 Rekap & Utilitas")

# --- Load data
hakim_df, pp_df, js_df, js_ghoib_df, libur_df, rekap_df = load_all()

# --- Rekap Tabel
st.subheader("Rekap Perkara (Lengkap)")
if not rekap_df.empty:
    st.dataframe(df_display_clean(rekap_df), use_container_width=True)
else:
    st.info("Belum ada data rekap.")

st.markdown("---")
st.subheader("Utilitas Rekap")

c1, c2 = st.columns(2)

# === Normalisasi nomor perkara (Pdt.G/P/Plw) ===
with c1:
    if st.button("🔁 Normalisasi Nomor di Rekap (Pdt.G/P/Plw)"):
        try:
            if not rekap_df.empty and "nomor_perkara" in rekap_df.columns:
                fixed_idx = rekap_df["nomor_perkara"].notna() & (rekap_df["nomor_perkara"].astype(str).str.strip() != "")
                fixed = rekap_df.loc[fixed_idx].copy()

                def _normalize_row(row):
                    nfmt, _ = compute_nomor_tipe(
                        row.get("nomor_perkara", ""),
                        row.get("klasifikasi", ""),
                        "Otomatis"
                    )
                    row["nomor_perkara"] = nfmt
                    return row

                fixed = fixed.apply(_normalize_row, axis=1)
                others = rekap_df.loc[~fixed_idx].copy()
                merged = pd.concat([fixed, others], ignore_index=True)

                if "tgl_register" in merged.columns:
                    merged = merged.sort_values("tgl_register").reset_index(drop=True)

                save_table(merged, "rekap")
                st.success("Nomor perkara pada rekap telah dinormalisasi.")
                st.rerun()
            else:
                st.info("Tidak ada data rekap untuk dinormalisasi.")
        except Exception as e:
            st.error(f"Gagal menormalisasi: {e}")

# === Export Excel ===
with c2:
    if not rekap_df.empty:
        try:
            bts = to_excel_bytes(rekap_df)
            st.download_button(
                "⬇️ Export Excel",
                data=bts,
                file_name="rekap_sidang.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        except Exception as e:
            st.error(f"Gagal membuat file Excel: {e}")
    else:
        st.info("Belum ada data untuk diexport.")
