# di setiap pages/*.py
from datetime import datetime, timedelta
import streamlit as st


SESSION_TTL_HOURS = 8  # samakan dengan app.py

def _ensure_auth(redirect="app.py"):
    u = st.session_state.get("auth_user")
    exp = st.session_state.get("auth_exp")
    if not u or not exp or datetime.utcnow() > exp:
        st.switch_page(redirect)     # balik ke login
    else:
        # refresh TTL biar konsisten dengan app.py
        st.session_state["auth_exp"] = datetime.utcnow() + timedelta(hours=SESSION_TTL_HOURS)

_ensure_auth()