import streamlit as st
import pandas as pd
from typing import Dict, Optional, List
from db_io import load_table, save_table, upsert, delete_by_id

def render_editor_with_row_actions(
    table_name: str,
    column_config: Optional[Dict] = None,
    unique_col: str = "nama",
    add_form_fields: Optional[List[str]] = None,
    add_form_labels: Optional[Dict[str, str]] = None,
):
    if add_form_fields:
        with st.expander("➕ Tambah Data", expanded=False):
            with st.form(f"form_add_{table_name}"):
                new_values = {}
                for col in add_form_fields:
                    label = (add_form_labels or {}).get(col, col)
                    if col.lower() in ("aktif", "max_per_hari", "total_ghoib"):
                        val = st.number_input(label, min_value=0, step=1, key=f"add_{table_name}_{col}")
                    elif col.lower() == "tanggal":
                        val = st.date_input(label, key=f"add_{table_name}_{col}")
                        val = val.strftime("%Y-%m-%d")
                    else:
                        val = st.text_input(label, key=f"add_{table_name}_{col}")
                    new_values[col] = val
                submitted = st.form_submit_button("Tambah")
                if submitted:
                    if not new_values.get(unique_col, ""):
                        st.error(f"Kolom unik '{unique_col}' wajib diisi.")
                    else:
                        cols = list(new_values.keys())
                        vals = tuple(new_values[c] for c in cols)
                        upsert(table_name, cols, vals, unique_col=unique_col)
                        st.success("Baris baru ditambahkan / di-update ✅")
                        st.rerun()

    df = load_table(table_name)
    st.subheader("Editor Tabel (Simpan Semua)")
    edited = st.data_editor(
        df,
        num_rows="dynamic",
        use_container_width=True,
        key=f"editor_{table_name}",
        column_config=column_config or {},
    )

    c1, c2 = st.columns(2)
    with c1:
        if st.button("💾 Simpan Semua ke SQLite", type="primary", key=f"save_all_{table_name}"):
            save_table(table_name, edited)
            st.success("Semua perubahan tersimpan ✅")
            st.rerun()
    with c2:
        if st.button("🔄 Muat ulang", key=f"reload_{table_name}"):
            st.rerun()

    st.markdown("---")
    st.subheader("Aksi Per-baris")
    if edited.empty:
        st.info("Belum ada data.")
        return

    for idx, row in edited.iterrows():
        row_id = int(row.get("id", 0)) if "id" in edited.columns and pd.notna(row.get("id")) else None
        cols = [c for c in edited.columns if c != "id"]
        vals = tuple(row[c] if c in row else None for c in cols)
        with st.container(border=True):
            st.write(f"**#{idx+1}**", {k: row[k] for k in row.index if k != "id"})
            cc1, cc2, cc3 = st.columns([1,1,6])
            with cc1:
                if st.button("💾 Simpan baris", key=f"save_row_{table_name}_{idx}"):
                    upsert(table_name, cols, vals, unique_col=unique_col)
                    st.success("Baris tersimpan ✅")
                    st.rerun()
            with cc2:
                disabled = row_id is None
                if st.button("🗑️ Hapus", key=f"del_row_{table_name}_{idx}", disabled=disabled):
                    delete_by_id(table_name, row_id)
                    st.success("Baris dihapus 🗑️")
                    st.rerun()
            with cc3:
                st.caption(f"id={row_id} • {unique_col}={row.get(unique_col)}")
