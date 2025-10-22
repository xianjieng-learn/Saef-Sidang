# app_core/dialogs.py
import streamlit as st
import pandas as pd
from datetime import date

# ======================================================
# Global state for SINGLE dialog (avoid "Only one dialog")
# ======================================================
if "dlg" not in st.session_state:
    st.session_state["dlg"] = None  # {"type": str, "title": str, "payload": dict}

def open_dialog(dlg_type: str, title: str, payload: dict | None = None):
    """Set state to open a single dialog on next rerun."""
    st.session_state["dlg"] = {"type": dlg_type, "title": title, "payload": payload or {}}
    st.rerun()

def close_dialog():
    st.session_state["dlg"] = None
    st.rerun()

# ======================================================
# Compatibility modal/dialog context manager (SAFE)
# ======================================================
def _is_ctxmgr(obj) -> bool:
    return hasattr(obj, "__enter__") and hasattr(obj, "__exit__")

def _dialog_context(title: str):
    """
    SAFE floating dialog:
    - Coba st.modal / st.dialog / st.experimental_dialog
      HANYA jika mereka mengembalikan *context manager* yang valid.
    - Jika tidak ada CM valid → fallback ke container biasa (non-floating),
      sehingga aplikasi tidak error di semua versi Streamlit.
    """
    # 1) st.modal
    if hasattr(st, "modal"):
        try:
            cm = st.modal(title)
            if _is_ctxmgr(cm):
                return cm
        except Exception:
            pass

    # 2) st.dialog
    if hasattr(st, "dialog"):
        try:
            cm = st.dialog(title)
            if _is_ctxmgr(cm):
                return cm
        except Exception:
            pass

    # 3) experimental_dialog
    if hasattr(st, "experimental_dialog"):
        try:
            cm = st.experimental_dialog(title)
            if _is_ctxmgr(cm):
                return cm
        except Exception:
            pass

    # 4) fallback container (tidak floating tapi aman)
    class _ContainerCM:
        def __enter__(self_in):
            st.markdown(f"### {title}")
            st.caption("(*Mode kompatibilitas: dialog tidak floating. "
                       "Jika ingin mengambang, gunakan Streamlit versi yang mendukung context manager.*)")
            return st.container()
        def __exit__(self_in, exc_type, exc, tb):
            return False
    return _ContainerCM()

# ======================================================
# RENDER a SINGLE dialog per rerun
# Call: render_dialog(hakim_df, pp_df, js_df, js_ghoib_df, libur_df)
# ======================================================
def render_dialog(hakim_df: pd.DataFrame,
                  pp_df: pd.DataFrame,
                  js_df: pd.DataFrame,
                  js_ghoib_df: pd.DataFrame,
                  libur_df: pd.DataFrame):
    dlg = st.session_state.get("dlg")
    if not dlg:
        return

    t = dlg.get("type")
    p = dlg.get("payload", {})
    title = dlg.get("title", "Dialog")

    # ---------------------------------
    # HAKIM: ADD
    # ---------------------------------
    if t == "add_hakim":
        from app_core.data_io import save_table
        with _dialog_context(title):
            with st.form("form_add_hakim"):
                nama = st.text_input("Nama")
                hari = st.selectbox("Hari Sidang", ["Senin","Selasa","Rabu","Kamis","Jumat"], index=0)
                aktif = st.selectbox("Aktif", ["YA","TIDAK"], index=0)
                max_per = st.number_input("Max Perkara per Hari (0 = tak terbatas)", min_value=0, value=0)
                catatan = st.text_input("Catatan (opsional)", "")
                pasangan1 = st.text_input("Pasangan 1 (opsional)", "")
                pasangan2 = st.text_input("Pasangan 2 (opsional)", "")
                if st.form_submit_button("Simpan"):
                    try:
                        row = {
                            "nama": nama, "hari_sidang": hari, "aktif": aktif,
                            "max_per_hari": int(max_per), "catatan": catatan,
                            "pasangan1": pasangan1, "pasangan2": pasangan2
                        }
                        newdf = pd.concat([hakim_df, pd.DataFrame([row])], ignore_index=True)
                        save_table(newdf, "hakim")
                        st.success("Tersimpan.")
                        close_dialog()
                    except Exception as e:
                        st.error(f"Gagal menyimpan: {e}")
            st.button("Tutup", on_click=close_dialog)

    # ---------------------------------
    # HAKIM: EDIT
    # ---------------------------------
    elif t == "edit_hakim":
        from app_core.data_io import save_table
        i = int(p["index"])
        row0 = hakim_df.iloc[i]
        with _dialog_context(title):
            with st.form(f"form_edit_hakim_{i}"):
                hari_list = ["Senin","Selasa","Rabu","Kamis","Jumat"]
                nama = st.text_input("Nama", str(row0.get("nama","")))
                hv = str(row0.get("hari_sidang","Senin"))
                hari = st.selectbox("Hari Sidang", hari_list, index=hari_list.index(hv) if hv in hari_list else 0)
                aktif = st.selectbox("Aktif", ["YA","TIDAK"], index=0 if str(row0.get("aktif","YA"))=="YA" else 1)
                max_per = st.number_input("Max Perkara per Hari", min_value=0, value=int(row0.get("max_per_hari",0)))
                catatan = st.text_input("Catatan", str(row0.get("catatan","")))
                alias = st.text_area(
            "Alias",
            value=row.get("alias",""),
            placeholder="Pisahkan dengan koma, titik koma, atau baris baru.\nContoh: Syahrani; Syakrani; Syachrani"
        )
                if st.form_submit_button("Simpan Perubahan"):
                    try:
                        df = hakim_df.copy()
                        df.loc[df.index[i], ["nama","hari_sidang","aktif","max_per_hari","catatan","Alias"]] = [
                            nama, hari, aktif, int(max_per), catatan, alias
                        ]
                        save_table(df, "hakim")
                        st.success("Perubahan disimpan.")
                        close_dialog()
                    except Exception as e:
                        st.error(f"Gagal menyimpan: {e}")
            st.button("Tutup", on_click=close_dialog)

    # ---------------------------------
    # PP: ADD
    # ---------------------------------
    elif t == "add_pp":
        from app_core.data_io import save_table
        with _dialog_context(title):
            with st.form("form_add_pp"):
                hakim_n = st.text_input("Hakim (Ketua Majelis)")
                pp1 = st.text_input("PP 1")
                pp2 = st.text_input("PP 2")
                if st.form_submit_button("Simpan"):
                    try:
                        row = {"hakim": hakim_n, "pp1": pp1, "pp2": pp2}
                        newdf = pd.concat([pp_df, pd.DataFrame([row])], ignore_index=True)
                        save_table(newdf, "pp")
                        st.success("Tersimpan.")
                        close_dialog()
                    except Exception as e:
                        st.error(f"Gagal menyimpan: {e}")
            st.button("Tutup", on_click=close_dialog)

    # ---------------------------------
    # PP: EDIT
    # ---------------------------------
    elif t == "edit_pp":
        from app_core.data_io import save_table
        i = int(p["index"])
        row0 = pp_df.iloc[i]
        with _dialog_context(title):
            with st.form(f"form_edit_pp_{i}"):
                hakim_n = st.text_input("Hakim (Ketua Majelis)", str(row0.get("hakim","")))
                pp1 = st.text_input("PP 1", str(row0.get("pp1","")))
                pp2 = st.text_input("PP 2", str(row0.get("pp2","")))
                if st.form_submit_button("Simpan Perubahan"):
                    try:
                        df = pp_df.copy()
                        df.loc[df.index[i], ["hakim","pp1","pp2"]] = [hakim_n, pp1, pp2]
                        save_table(df, "pp")
                        st.success("Perubahan disimpan.")
                        close_dialog()
                    except Exception as e:
                        st.error(f"Gagal menyimpan: {e}")
            st.button("Tutup", on_click=close_dialog)

    # ---------------------------------
    # JS: ADD
    # ---------------------------------
    elif t == "add_js":
        from app_core.data_io import save_table
        with _dialog_context(title):
            with st.form("form_add_js"):
                hakim_n = st.text_input("Hakim (Ketua Majelis)")
                js1 = st.text_input("JS 1")
                js2 = st.text_input("JS 2")
                if st.form_submit_button("Simpan"):
                    try:
                        row = {"hakim": hakim_n, "js1": js1, "js2": js2}
                        newdf = pd.concat([js_df, pd.DataFrame([row])], ignore_index=True)
                        save_table(newdf, "js")
                        st.success("Tersimpan.")
                        close_dialog()
                    except Exception as e:
                        st.error(f"Gagal menyimpan: {e}")
            st.button("Tutup", on_click=close_dialog)

    # ---------------------------------
    # JS: EDIT
    # ---------------------------------
    elif t == "edit_js":
        from app_core.data_io import save_table
        i = int(p["index"])
        row0 = js_df.iloc[i]
        with _dialog_context(title):
            with st.form(f"form_edit_js_{i}"):
                hakim_n = st.text_input("Hakim (Ketua Majelis)", str(row0.get("hakim","")))
                js1 = st.text_input("JS 1", str(row0.get("js1","")))
                js2 = st.text_input("JS 2", str(row0.get("js2","")))
                if st.form_submit_button("Simpan Perubahan"):
                    try:
                        df = js_df.copy()
                        df.loc[df.index[i], ["hakim","js1","js2"]] = [hakim_n, js1, js2]
                        save_table(df, "js")
                        st.success("Perubahan disimpan.")
                        close_dialog()
                    except Exception as e:
                        st.error(f"Gagal menyimpan: {e}")
            st.button("Tutup", on_click=close_dialog)

    # ---------------------------------
    # JS GHOIB: ADD
    # ---------------------------------
    elif t == "add_js_ghoib":
        from app_core.data_io import save_table
        with _dialog_context(title):
            with st.form("form_add_js_ghoib"):
                nama = st.text_input("Nama JS")
                aktif = st.selectbox("Aktif", ["YA","TIDAK"], index=0)
                exclude = st.selectbox("Exclude", ["NO","YES"], index=0)
                total_gh = st.number_input("Total Ghoib (history)", min_value=0, value=0)
                if st.form_submit_button("Simpan"):
                    try:
                        row = {"js": nama, "aktif": aktif, "exclude": exclude, "total_ghoib": int(total_gh)}
                        newdf = pd.concat([js_ghoib_df, pd.DataFrame([row])], ignore_index=True)
                        save_table(newdf, "js_ghoib_pool")
                        st.success("Tersimpan.")
                        close_dialog()
                    except Exception as e:
                        st.error(f"Gagal menyimpan: {e}")
            st.button("Tutup", on_click=close_dialog)

    # ---------------------------------
    # JS GHOIB: EDIT
    # ---------------------------------
    elif t == "edit_js_ghoib":
        from app_core.data_io import save_table
        i = int(p["index"])
        row0 = js_ghoib_df.iloc[i]
        with _dialog_context(title):
            with st.form(f"form_edit_jsgh_{i}"):
                nama = st.text_input("Nama JS", str(row0.get("js","")))
                aktif = st.selectbox("Aktif", ["YA","TIDAK"], index=0 if str(row0.get("aktif","YA"))=="YA" else 1)
                exclude = st.selectbox("Exclude", ["NO","YES"], index=1 if str(row0.get("exclude","NO"))=="YES" else 0)
                total_gh = st.number_input("Total Ghoib", min_value=0, value=int(row0.get("total_ghoib",0)))
                if st.form_submit_button("Simpan Perubahan"):
                    try:
                        df = js_ghoib_df.copy()
                        df.loc[df.index[i], ["js","aktif","exclude","total_ghoib"]] = [nama, aktif, exclude, int(total_gh)]
                        save_table(df, "js_ghoib_pool")
                        st.success("Perubahan disimpan.")
                        close_dialog()
                    except Exception as e:
                        st.error(f"Gagal menyimpan: {e}")
            st.button("Tutup", on_click=close_dialog)

    # ---------------------------------
    # LIBUR: ADD
    # ---------------------------------
    elif t == "add_libur":
        from app_core.data_io import save_table
        with _dialog_context(title):
            with st.form("form_add_libur"):
                tgl = st.date_input("Tanggal Libur", value=date.today())
                if st.form_submit_button("Simpan"):
                    try:
                        row = {"tanggal": pd.to_datetime(tgl).strftime("%Y-%m-%d")}
                        newdf = pd.concat([libur_df, pd.DataFrame([row])], ignore_index=True)
                        save_table(newdf, "libur")
                        st.success("Tersimpan.")
                        close_dialog()
                    except Exception as e:
                        st.error(f"Gagal menyimpan: {e}")
            st.button("Tutup", on_click=close_dialog)

    # ---------------------------------
    # LIBUR: EDIT
    # ---------------------------------
    elif t == "edit_libur":
        from app_core.data_io import save_table
        i = int(p["index"])
        try:
            d0 = pd.to_datetime(libur_df.iloc[i]["tanggal"]).date()
        except Exception:
            d0 = date.today()
        with _dialog_context(title):
            with st.form(f"form_edit_libur_{i}"):
                tgl = st.date_input("Tanggal Libur", value=d0)
                if st.form_submit_button("Simpan Perubahan"):
                    try:
                        df = libur_df.copy()
                        df.loc[df.index[i], "tanggal"] = pd.to_datetime(tgl).strftime("%Y-%m-%d")
                        save_table(df, "libur")
                        st.success("Perubahan disimpan.")
                        close_dialog()
                    except Exception as e:
                        st.error(f"Gagal menyimpan: {e}")
            st.button("Tutup", on_click=close_dialog)

    # ---------------------------------
    # SK MAJELIS & PP: ADD
    # ---------------------------------
    elif t == "add_sk":
        from app_core.data_io import load_sk, save_table
        sk_now = load_sk()
        with _dialog_context(title):
            with st.form("form_add_sk"):
                majelis = st.text_input("Nama Majelis (mis. Majelis I / Rabu - Taslimah)")
                hari = st.selectbox("Hari Sidang", ["Senin","Selasa","Rabu","Kamis","Jumat"], index=0)
                hakim_ketua = st.text_input("Hakim Ketua")
                anggota1 = st.text_input("Anggota 1")
                anggota2 = st.text_input("Anggota 2")
                pp1 = st.text_input("PP 1")
                pp2 = st.text_input("PP 2")
                js1 = st.text_input("JS 1")
                js2 = st.text_input("JS 2")
                aktif = st.selectbox("Aktif", ["YA","TIDAK"], index=0)

                if st.form_submit_button("Simpan"):
                    try:
                        row = {
                            "majelis": majelis, "hari_sidang": hari, "hakim_ketua": hakim_ketua,
                            "anggota1": anggota1, "anggota2": anggota2,
                            "pp1": pp1, "pp2": pp2, "js1": js1, "js2": js2,
                            "aktif": aktif
                        }
                        newdf = pd.concat([sk_now, pd.DataFrame([row])], ignore_index=True)
                        save_table(newdf, "sk_majelis")
                        st.success("Tersimpan.")
                        close_dialog()
                    except Exception as e:
                        st.error(f"Gagal menyimpan: {e}")
            st.button("Tutup", on_click=close_dialog)

    # ---------------------------------
    # SK MAJELIS & PP: EDIT
    # ---------------------------------
    elif t == "edit_sk":
        from app_core.data_io import load_sk, save_table
        sk_now = load_sk()
        i = int(p["index"])
        row0 = sk_now.iloc[i] if not sk_now.empty else pd.Series()
        with _dialog_context(title):
            with st.form(f"form_edit_sk_{i}"):
                hari_list = ["Senin","Selasa","Rabu","Kamis","Jumat"]
                majelis = st.text_input("Nama Majelis", str(row0.get("majelis","")))
                hari_val = str(row0.get("hari_sidang","Senin"))
                hari = st.selectbox("Hari Sidang", hari_list, index=hari_list.index(hari_val) if hari_val in hari_list else 0)
                hakim_ketua = st.text_input("Hakim Ketua", str(row0.get("hakim_ketua","")))
                anggota1 = st.text_input("Anggota 1", str(row0.get("anggota1","")))
                anggota2 = st.text_input("Anggota 2", str(row0.get("anggota2","")))
                pp1 = st.text_input("PP 1", str(row0.get("pp1","")))
                pp2 = st.text_input("PP 2", str(row0.get("pp2","")))
                js1 = st.text_input("JS 1", str(row0.get("js1","")))
                js2 = st.text_input("JS 2", str(row0.get("js2","")))
                aktif = st.selectbox("Aktif", ["YA","TIDAK"], index=0 if str(row0.get("aktif","YA"))=="YA" else 1)

                if st.form_submit_button("Simpan Perubahan"):
                    try:
                        df = sk_now.copy()
                        df.loc[df.index[i], ["majelis","hari_sidang","hakim_ketua","anggota1","anggota2",
                                             "pp1","pp2","js1","js2","aktif"]] = [
                            majelis, hari, hakim_ketua, anggota1, anggota2, pp1, pp2, js1, js2, aktif
                        ]
                        save_table(df, "sk_majelis")
                        st.success("Perubahan disimpan.")
                        close_dialog()
                    except Exception as e:
                        st.error(f"Gagal menyimpan: {e}")
            st.button("Tutup", on_click=close_dialog)

    else:
        with _dialog_context(title):
            st.info("Dialog tidak dikenal.")
            st.button("Tutup", on_click=close_dialog)
