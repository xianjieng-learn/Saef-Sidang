from __future__ import annotations
import streamlit as st
import pandas as pd
from pathlib import Path

def _normalize_for_csv(df: pd.DataFrame) -> pd.DataFrame:
    if df is None:
        return pd.DataFrame()
    out = df.copy()
    if "aktif" in out.columns:
        def _norm_aktif(v):
            s = str(v).strip().upper()
            if s in {"1","YA","Y","TRUE","T","AKTIF","ON"}:    return "YA"
            if s in {"0","TIDAK","TDK","NO","N","FALSE","F","NONAKTIF","OFF","NONE","NAN",""}: 
                return "TIDAK"
            return s
        out["aktif"] = out["aktif"].map(_norm_aktif)
    for c in out.columns:
        lc = c.lower()
        if ("tgl" in lc) or ("tanggal" in lc):
            out[c] = pd.to_datetime(out[c], errors="coerce").dt.date.astype(str).replace("NaT","")
    return out

def get_data_dir() -> Path:
    default_dir = Path(__file__).resolve().parents[1] / "data"
    data_dir = Path(st.session_state.get("DATA_DIR", str(default_dir)))
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir

def export_csv(df: pd.DataFrame, filename: str, with_bom: bool = True) -> Path:
    out = _normalize_for_csv(df)
    data_dir = get_data_dir()
    path = data_dir / filename
    encoding = "utf-8-sig" if with_bom else "utf-8"
    out.to_csv(path, index=False, encoding=encoding)
    return path

def export_toolbar(df: pd.DataFrame, filename: str, title: str | None = None):
    if title:
        st.subheader(title)
    c1, c2 = st.columns([0.65, 0.35])
    with c1:
        data_dir_text = st.text_input(
            "Folder penyimpanan (default: data/ di root proyek)",
            value=str(get_data_dir()),
            help="Ganti bila mau simpan ke lokasi lain. Hasil otomatis tetap membaca folder default kecuali kamu juga mengubahnya di sana."
        )
        st.session_state["DATA_DIR"] = data_dir_text
    with c2:
        clicked = st.button("💾 Generate CSV", use_container_width=True)
        if clicked:
            if df is None or len(df) == 0:
                st.warning("DataFrame kosong—tidak ada yang diekspor.")
                return
            try:
                path = export_csv(df, filename)
                st.success(f"✅ Disimpan: {path}")
                st.toast(f"CSV diperbarui: {path.name}", icon="✅")
            except Exception as e:
                st.error(f"Gagal menyimpan: {e}")
    st.download_button(
        "⬇️ Download CSV (UTF-8-SIG)",
        data=_normalize_for_csv(df).to_csv(index=False, encoding="utf-8-sig"),
        file_name=filename,
        mime="text/csv",
        use_container_width=True
    )

def export_all(named_dfs: dict[str, pd.DataFrame]):
    results = []
    for fname, _df in named_dfs.items():
        results.append(str(export_csv(_df, fname)))
    return results
