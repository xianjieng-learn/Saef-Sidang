# app_core/login.py
from __future__ import annotations
from datetime import datetime, timedelta
import streamlit as st

SESSION_TTL_HOURS = 1  # samakan dengan app.py

def _ensure_auth(redirect="app.py"):
    """Guard ringan untuk dipanggil di setiap pages/*.py"""
    u = st.session_state.get("auth_user")
    exp = st.session_state.get("auth_exp")
    if u and exp and datetime.utcnow() <= exp:
        # refresh TTL biar konsisten
        st.session_state["auth_exp"] = datetime.utcnow() + timedelta(hours=SESSION_TTL_HOURS)
        return
    # cegah loop redirect
    if not st.session_state.get("_redirecting"):
        st.session_state["_redirecting"] = True
        try:
            st.switch_page(redirect)
        except Exception:
            st.page_link(redirect, label="Kembali ke Halaman Login", icon="🔐")
        st.stop()
    else:
        st.page_link(redirect, label="Kembali ke Halaman Login", icon="🔐")
        st.stop()

def ensure_auth_and_topbar(require_admin: bool = False, show_user: bool = True):
    """
    - Pastikan user sudah login & sesi belum expired (kalau tidak → balik ke app.py)
    - Refresh TTL
    - Tampilkan tombol Logout di header dan di sidebar
    - Jika require_admin=True → non-admin ditolak
    """
    u = st.session_state.get("auth_user")
    exp = st.session_state.get("auth_exp")
    if not u or not exp or datetime.utcnow() > exp:
        st.switch_page("app.py")

    # refresh TTL setiap interaksi
    st.session_state["auth_exp"] = datetime.utcnow() + timedelta(hours=SESSION_TTL_HOURS)

    # admin gate (opsional)
    if require_admin and st.session_state.get("auth_role") != "admin":
        st.error("Halaman ini khusus admin.")
        st.page_link("app.py", label="⬅️ Kembali ke Home", icon="🏠")
        st.stop()

    # ===== Topbar dengan Logout =====
    l, m, r = st.columns([5, 3, 1])
    with l:
        if show_user:
            st.caption(
                f"👤 **{st.session_state.get('auth_user','?')}** "
                f"(role: {st.session_state.get('auth_role','user')})"
            )
    with r:
        if st.button("Logout", key="__logout_hdr", use_container_width=True):
            for k in ("auth_user","auth_role","auth_exp","_redirecting"):
                st.session_state.pop(k, None)
            st.rerun()

    # ===== Sidebar Logout (duplikat, biar selalu kelihatan) =====
    with st.sidebar:
        if st.button("Logout", key="__logout_sidebar", use_container_width=True):
            for k in ("auth_user","auth_role","auth_exp","_redirecting"):
                st.session_state.pop(k, None)
            st.rerun()
