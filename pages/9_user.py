# pages/9_👤_Kelola_Users.py
from __future__ import annotations
from datetime import datetime, timedelta
import streamlit as st
import pandas as pd
from app_core.nav import render_top_nav
render_top_nav()  # tampilkan top bar

# --- auth guard (sesuaikan dengan proyekmu) ---
try:
    # kalau kamu pakai modul guard sendiri
    from app_core.login import _ensure_auth  # pastikan modul ini ada
    _ensure_auth("app.py")
except Exception:
    # fallback ringan: hanya cek session
    if not st.session_state.get("auth_user") or datetime.utcnow() > st.session_state.get("auth_exp", datetime.min):
        st.switch_page("app.py")
    else:
        st.session_state["auth_exp"] = datetime.utcnow() + timedelta(hours=8)

# --- hanya admin ---
if st.session_state.get("auth_role") != "admin":
    st.set_page_config(page_title="👤 Users", layout="wide")
    st.error("Halaman ini khusus admin.")
    st.page_link("app.py", label="⬅️ Kembali ke Home", icon="🏠")
    st.stop()

# --- deps store & hashing ---
import user_store                           # CRUD ke data/users.json
from auth_utils import hash_new_password    # PBKDF2 (salt_hex, hash_hex)

st.set_page_config(page_title="👤 Kelola Users", layout="wide", initial_sidebar_state="collapsed")
st.header("👤 Kelola Pengguna (users.json)")

# -------------------- State dialog --------------------
if "user_dialog" not in st.session_state:
    st.session_state["user_dialog"] = {
        "open": False,     # True | False
        "mode": "",        # "add" | "edit"
        "username": "",    # target username saat edit
        "title": ""
    }

def open_user_dialog(mode: str, title: str, username: str = ""):
    st.session_state["user_dialog"] = {"open": True, "mode": mode, "username": username or "", "title": title}

def close_user_dialog():
    st.session_state["user_dialog"]["open"] = False

# -------------------- Data --------------------
users = user_store.list_users()  # dict: username -> {salt_hex, hash_hex, role}
st.caption("Sumber: `data/users.json`")

# -------------------- Toolbar --------------------
topL, topR = st.columns([1, 1])
with topL:
    if st.button("➕ Tambah User", use_container_width=True, key="btn_add_user"):
        open_user_dialog("add", "Tambah User")

with topR:
    q = st.text_input("🔎 Cari username (opsional)", key="user_filter")

# -------------------- Tabel Users --------------------
view = pd.DataFrame([{"username": u, "role": rec.get("role", "user")}
                     for u, rec in users.items()])

if q:
    view = view[view["username"].str.contains(q, case=False, na=False)]

view = view.sort_values(["role", "username"], ascending=[True, True], kind="stable").reset_index(drop=True)

# Header grid
COLS = [2.4, 1.0, 0.8, 0.8]
h = st.columns(COLS)
h[0].markdown("**Username**")
h[1].markdown("**Role**")
h[2].markdown("**Edit**")
h[3].markdown("**Hapus**")
st.markdown("<hr/>", unsafe_allow_html=True)

for i, row in view.iterrows():
    cols = st.columns(COLS)
    uname = str(row["username"])
    urole = str(row["role"] or "user")
    cols[0].write(uname)
    cols[1].write(urole)
    with cols[2]:
        if st.button("✏️", key=f"usr_edit_{uname}"):
            open_user_dialog("edit", f"Edit User: {uname}", uname)
            st.rerun()
    with cols[3]:
        if st.button("🗑️", key=f"usr_del_{uname}"):
            # Cegah hapus diri sendiri; sisanya dilewatkan ke store (yang juga cegah admin terakhir)
            if uname == st.session_state.get("auth_user"):
                st.error("Tidak boleh menghapus akun yang sedang login.")
            else:
                ok, msg = user_store.delete_user(uname)
                (st.success if ok else st.error)(msg)
                st.rerun()

# -------------------- Dialog (Tambah / Edit) --------------------
dlg = st.session_state["user_dialog"]
if dlg.get("open"):
    st.markdown("---")
    st.subheader(dlg.get("title") or ("Tambah User" if dlg.get("mode") == "add" else "Edit User"))

    mode = dlg.get("mode")
    target = dlg.get("username", "")

    if mode == "add":
        c1, c2, c3 = st.columns([1.2, 1.2, 0.8])
        with c1:
            in_user = st.text_input("Username *", key="dlg_add_username")
        with c2:
            in_pass = st.text_input("Password *", type="password", key="dlg_add_password")
        with c3:
            in_role = st.selectbox("Role", ["user", "admin"], index=0, key="dlg_add_role")

        a1, a2 = st.columns([1, 1])
        do_save = a1.button("💾 Simpan", type="primary", use_container_width=True, key="dlg_add_save")
        do_cancel = a2.button("Batal", use_container_width=True, key="dlg_add_cancel")

        if do_save:
            u = (in_user or "").strip()
            p = in_pass or ""
            if not u or not p:
                st.error("Username dan password wajib diisi.")
            elif u in users:
                st.error("Username sudah ada.")
            else:
                salt_hex, hash_hex = hash_new_password(p)
                user_store.upsert_user(u, salt_hex, hash_hex, in_role)
                close_user_dialog()
                st.success(f"User '{u}' ditambahkan (role={in_role}).")
                st.rerun()

        if do_cancel and not do_save:
            close_user_dialog()
            st.info("Dibatalkan.")
            st.rerun()

    elif mode == "edit":
        rec = users.get(target, {})
        if not rec:
            st.error("User tidak ditemukan."); close_user_dialog()
        else:
            c1, c2, c3 = st.columns([1.2, 1.2, 0.8])
            with c1:
                st.text_input("Username", value=target, disabled=True, key="dlg_edit_username")
            with c2:
                in_pass_new = st.text_input("Password baru (opsional)", type="password", key="dlg_edit_password")
                st.caption("Kosongkan jika tidak ingin mengubah password.")
            with c3:
                in_role = st.selectbox("Role", ["user", "admin"],
                                       index=(0 if rec.get("role", "user") == "user" else 1),
                                       key="dlg_edit_role")

            b1, b2, b3 = st.columns([1, 1, 1])
            do_save = b1.button("💾 Simpan Perubahan", type="primary", use_container_width=True, key="dlg_edit_save")
            do_cancel = b2.button("Batal", use_container_width=True, key="dlg_edit_cancel")
            do_delete = b3.button("🗑️ Hapus User", use_container_width=True, key="dlg_edit_delete")

            if do_save:
                # Jika password baru diisi → buat salt/hash baru, kalau kosong pakai yang lama
                if in_pass_new:
                    salt_hex, hash_hex = hash_new_password(in_pass_new)
                else:
                    salt_hex, hash_hex = rec["salt_hex"], rec["hash_hex"]
                user_store.upsert_user(target, salt_hex, hash_hex, in_role)
                close_user_dialog()
                st.success(f"User '{target}' diperbarui (role={in_role}{', password direset' if in_pass_new else ''}).")
                st.rerun()

            if do_delete:
                if target == st.session_state.get("auth_user"):
                    st.error("Tidak boleh menghapus akun yang sedang login.")
                else:
                    ok, msg = user_store.delete_user(target)
                    if ok:
                        close_user_dialog()
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)

            if do_cancel and not (do_save or do_delete):
                close_user_dialog()
                st.info("Dibatalkan.")
                st.rerun()

# Footer
st.markdown("---")
st.page_link("app.py", label="⬅️ Kembali ke Home", icon="🏠")
