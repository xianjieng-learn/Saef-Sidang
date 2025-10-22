# pages/3f_🧾_Data_SK_Majelis.py
import streamlit as st
import pandas as pd
from db import get_conn, init_db

st.set_page_config(page_title="Data: SK Majelis", layout="wide")
st.header("🧾 Data SK Majelis")
init_db()

def _is_active_value(v) -> bool:
    s = str(v).strip().upper()
    if s in {"1","YA","Y","TRUE","T","AKTIF","ON"}: return True
    if s in {"0","TIDAK","TDK","NO","N","FALSE","F","NONAKTIF","OFF","NONE","NAN",""}: return False
    try: return float(s) != 0.0
    except Exception: return False

# ---------- DB helpers ----------
def ensure_table():
    con = get_conn()
    try:
        cur = con.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS sk_majelis (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                majelis   TEXT,
                ketua     TEXT,
                anggota1  TEXT,
                anggota2  TEXT,
                pp1       TEXT,
                pp2       TEXT,
                js1       TEXT,
                js2       TEXT,
                aktif     INTEGER DEFAULT 1,
                catatan   TEXT
            );
            """
        )
        con.commit()
    finally:
        con.close()

def migrate_sk_schema():
    con = get_conn()
    try:
        cur = con.cursor()
        cur.execute("PRAGMA table_info(sk_majelis)")
        cols = {row[1] for row in cur.fetchall()}
        targets = [
            ("majelis", "TEXT"),
            ("ketua", "TEXT"),
            ("anggota1", "TEXT"),
            ("anggota2", "TEXT"),
            ("pp1", "TEXT"),
            ("pp2", "TEXT"),
            ("js1", "TEXT"),
            ("js2", "TEXT"),
            ("aktif", "INTEGER DEFAULT 1"),
            ("catatan", "TEXT"),
        ]
        for name, decl in targets:
            if name not in cols:
                cur.execute(f"ALTER TABLE sk_majelis ADD COLUMN {name} {decl};")
        # Migrate legacy columns (pp/js) => pp1/js1
        cur.execute("PRAGMA table_info(sk_majelis)")
        cols = {row[1] for row in cur.fetchall()}
        if "pp" in cols and "pp1" in cols:
            cur.execute("UPDATE sk_majelis SET pp1 = pp WHERE (pp1 IS NULL OR TRIM(pp1)='') AND (pp IS NOT NULL AND TRIM(pp)!='');")
        if "js" in cols and "js1" in cols:
            cur.execute("UPDATE sk_majelis SET js1 = js WHERE (js1 IS NULL OR TRIM(js1)='') AND (js IS NOT NULL AND TRIM(js)!='');")
        con.commit()
    finally:
        con.close()

def load_df(sql: str) -> pd.DataFrame:
    con = get_conn()
    try:
        return pd.read_sql_query(sql, con)
    except Exception:
        return pd.DataFrame()
    finally:
        con.close()

def load_sk() -> pd.DataFrame:
    return load_df("SELECT * FROM sk_majelis")

def upsert_sk(row_id, majelis, ketua, anggota1, anggota2, pp1, pp2, js1, js2, aktif, catatan):
    con = get_conn()
    try:
        cur = con.cursor()
        if row_id:
            cur.execute(
                """UPDATE sk_majelis
                   SET majelis=?, ketua=?, anggota1=?, anggota2=?, pp1=?, pp2=?, js1=?, js2=?, aktif=?, catatan=?
                   WHERE id=?""",
                (majelis.strip(), ketua.strip(), anggota1.strip(), anggota2.strip(),
                 pp1.strip(), pp2.strip(), js1.strip(), js2.strip(), int(bool(aktif)), catatan.strip(), int(row_id))
            )
        else:
            cur.execute(
                """INSERT INTO sk_majelis (majelis, ketua, anggota1, anggota2, pp1, pp2, js1, js2, aktif, catatan)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (majelis.strip(), ketua.strip(), anggota1.strip(), anggota2.strip(),
                 pp1.strip(), pp2.strip(), js1.strip(), js2.strip(), int(bool(aktif)), catatan.strip())
            )
        con.commit()
    finally:
        con.close()

def delete_sk(row_id):
    con = get_conn()
    try:
        cur = con.cursor()
        cur.execute("DELETE FROM sk_majelis WHERE id=?", (int(row_id),))
        con.commit()
    finally:
        con.close()

# ---------- Ensure & migrate ----------
ensure_table()
migrate_sk_schema()

# ---------- Dropdown sources ----------
def table_exists(name: str) -> bool:
    df = load_df("SELECT name FROM sqlite_master WHERE type='table'")
    return (not df.empty) and (name in df["name"].tolist())

def get_all_names(table_name: str) -> list[str]:
    """Return ALL names (tanpa filter aktif) untuk dropdown Ketua/Anggota."""
    df = load_df(f"SELECT nama FROM {table_name}") if table_exists(table_name) else pd.DataFrame()
    if df.empty or "nama" not in df.columns: return []
    return sorted([str(x).strip() for x in df["nama"].dropna().unique().tolist()])

def get_active_names(table_name: str) -> list[str]:
    """Return hanya yang aktif (untuk dropdown PP/JS)."""
    df = load_df(f"SELECT nama, aktif FROM {table_name}") if table_exists(table_name) else pd.DataFrame()
    if df.empty or "nama" not in df.columns: return []
    def _is_active(v) -> bool:
        s = str(v).strip().upper()
        if s in {"1","YA","Y","TRUE","T","AKTIF","ON"}: return True
        if s in {"0","TIDAK","TDK","NO","N","FALSE","F","NONAKTIF","OFF","NONE","NAN",""}: return False
        try: return float(s) != 0.0
        except Exception: return False
    if "aktif" in df.columns:
        df["__aktif"] = df["aktif"].apply(_is_active)
        names = df.loc[df["__aktif"], "nama"]
    else:
        names = df["nama"]
    return sorted([str(x).strip() for x in names.dropna().unique().tolist()])

hakim_options = get_all_names("hakim")  # <-- tanpa filter aktif (sesuai permintaan)
pp_options    = get_active_names("pp")  # tetap aktif saja
js_options    = get_active_names("js")  # tetap aktif saja

def _idx(options: list[str], value: str) -> int:
    try:
        return ([""] + options).index(value) if value in options else 0
    except Exception:
        return 0

# ---------- Dialog State ----------
if "sk_dialog" not in st.session_state:
    st.session_state["sk_dialog"] = {"open": False, "mode": "", "title": "", "payload": {}}

def open_dialog(mode: str, title: str, payload: dict | None = None):
    st.session_state["sk_dialog"] = {"open": True, "mode": mode, "title": title, "payload": payload or {}}

def render_dialog(current_df: pd.DataFrame):
    dlg = st.session_state.get("sk_dialog", {"open": False})
    if not dlg.get("open"): return
    mode = dlg.get("mode"); title = dlg.get("title", ""); payload = dlg.get("payload", {}) or {}

    with st.form("sk_form", clear_on_submit=False):
        if mode == "edit" and not current_df.empty:
            i = int(payload.get("index", 0)); row = current_df.reset_index(drop=True).iloc[i]
            row_id = int(row.get("id") or 0)
            majelis_init = str(row.get("majelis",""))
            ketua_init   = str(row.get("ketua",""))
            ang1_init    = str(row.get("anggota1",""))
            ang2_init    = str(row.get("anggota2",""))
            pp1_init     = str(row.get("pp1",""))
            pp2_init     = str(row.get("pp2",""))
            js1_init     = str(row.get("js1",""))
            js2_init     = str(row.get("js2",""))
            aktif_init   = _is_active_value(row.get("aktif",1))
            catatan_init = str(row.get("catatan",""))
        else:
            row_id = None
            majelis_init = ""; ketua_init = ""; ang1_init = ""; ang2_init = ""
            pp1_init = ""; pp2_init = ""; js1_init = ""; js2_init = ""
            aktif_init = True; catatan_init = ""

        st.subheader(title or ("Edit SK Majelis" if row_id else "Tambah SK Majelis"))
        majelis = st.text_input("Nama Majelis", value=majelis_init)

        # Ketua & Anggota dari data hakim (SEMUA nama, tanpa filter aktif)
        cA, cB, cC = st.columns(3)
        if hakim_options:
            ketua = cA.selectbox("Ketua", [""] + hakim_options, index=_idx(hakim_options, ketua_init))
            anggota1 = cB.selectbox("Anggota 1", [""] + hakim_options, index=_idx(hakim_options, ang1_init))
            anggota2 = cC.selectbox("Anggota 2", [""] + hakim_options, index=_idx(hakim_options, ang2_init))
        else:
            ketua = cA.text_input("Ketua", value=ketua_init)
            anggota1 = cB.text_input("Anggota 1", value=ang1_init)
            anggota2 = cC.text_input("Anggota 2", value=ang2_init)

        # PP & JS: dropdown hanya yang aktif
        cD, cE, cF, cG = st.columns(4)
        if pp_options:
            pp1 = cD.selectbox("PP 1", [""] + pp_options, index=_idx(pp_options, pp1_init))
            pp2 = cE.selectbox("PP 2", [""] + pp_options, index=_idx(pp_options, pp2_init))
        else:
            pp1 = cD.text_input("PP 1", value=pp1_init)
            pp2 = cE.text_input("PP 2", value=pp2_init)

        if js_options:
            js1 = cF.selectbox("JS 1", [""] + js_options, index=_idx(js_options, js1_init))
            js2 = cG.selectbox("JS 2", [""] + js_options, index=_idx(js_options, js2_init))
        else:
            js1 = cF.text_input("JS 1", value=js1_init)
            js2 = cG.text_input("JS 2", value=js2_init)

        aktif = st.checkbox("Aktif", value=aktif_init)
        catatan = st.text_area("Catatan (opsional)", value=catatan_init, height=60)

        c1,c2,c3 = st.columns([1,1,1])
        with c1: sbtn = st.form_submit_button("💾 Simpan", use_container_width=True)
        with c2: cbtn = st.form_submit_button("Batal", use_container_width=True)
        with c3: dbtn = st.form_submit_button("🗑️ Hapus", use_container_width=True) if (mode=="edit" and row_id) else None

        if sbtn:
            if not majelis.strip():
                st.error("Nama Majelis wajib diisi.")
            else:
                upsert_sk(row_id, majelis, ketua, anggota1, anggota2, pp1, pp2, js1, js2, aktif, catatan)
                st.session_state["sk_dialog"]["open"] = False
                st.success("Tersimpan ✅"); st.rerun()
        if dbtn and (mode=="edit" and row_id):
            delete_sk(row_id); st.session_state["sk_dialog"]["open"] = False; st.success("Dihapus 🗑️"); st.rerun()
        if cbtn and not sbtn and not dbtn:
            st.session_state["sk_dialog"]["open"] = False; st.info("Dibatalkan"); st.rerun()

# ---------- UI ----------
_, c2 = st.columns([1,1])
with c2:
    if st.button("➕ Tambah SK Majelis"): open_dialog("add","Tambah SK Majelis")

sk_df = load_sk()
if sk_df.empty:
    st.info("Belum ada data SK Majelis. Klik ➕ Tambah SK Majelis untuk membuat data pertama.")
else:
    view = sk_df.copy()
    view["Aktif?"] = view.get("aktif",0).apply(lambda v: "YA" if _is_active_value(v) else "TIDAK")

    COLS = [1.2, 1.5, 1.5, 1.5, 1.3, 1.3, 1.3, 1.3, 0.9, 2.0, 0.8, 0.8]
    h = st.columns(COLS)
    h[0].markdown("**Majelis**"); h[1].markdown("**Ketua**"); h[2].markdown("**Anggota 1**"); h[3].markdown("**Anggota 2**")
    h[4].markdown("**PP 1**"); h[5].markdown("**PP 2**"); h[6].markdown("**JS 1**"); h[7].markdown("**JS 2**")
    h[8].markdown("**Aktif?**"); h[9].markdown("**Catatan**"); h[10].markdown("**Edit**"); h[11].markdown("**Hapus**")
    st.markdown("<hr/>", unsafe_allow_html=True)

    for i, row in view.reset_index(drop=True).iterrows():
        cols = st.columns(COLS)
        cols[0].write(str(row.get("majelis","") or "-"))
        cols[1].write(str(row.get("ketua","") or ""))
        cols[2].write(str(row.get("anggota1","") or ""))
        cols[3].write(str(row.get("anggota2","") or ""))
        cols[4].write(str(row.get("pp1","") or ""))
        cols[5].write(str(row.get("pp2","") or ""))
        cols[6].write(str(row.get("js1","") or ""))
        cols[7].write(str(row.get("js2","") or ""))
        cols[8].write(str(view.loc[i,"Aktif?"]))
        cols[9].write(str(row.get("catatan","") or ""))
        with cols[10]:
            if st.button("✏️", key=f"edit_sk_{i}"): open_dialog("edit", f"Edit SK: {row.get('majelis','')}", {"index": int(i)})
        with cols[11]:
            row_id = int(view.reset_index(drop=True).loc[i].get("id") or 0)
            if row_id and st.button("🗑️", key=f"del_sk_{row_id}"):
                delete_sk(row_id); st.success("Dihapus 🗑️"); st.rerun()

render_dialog(sk_df)
