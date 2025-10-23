# app_core/nav.py (potongan penting)
from __future__ import annotations
import inspect
from pathlib import Path
from datetime import datetime, timedelta
import streamlit as st
from app_core.login import is_admin

SESSION_TTL_HOURS = 1

PAGES = [
    {"path": "app.py",                        "label": "Home",          "icon": "🏠"},
    {"path": "pages/1_Input_&_Hasil.py",      "label": "Input & Hasil", "icon": "📥"},
    {"path": "pages/2_Rekap.py",              "label": "Rekap",         "icon": "📊"},
    {"path": "pages/4_BATCH_INSTRUMEN.py",    "label": "Batch",         "icon": "🧰"},
    {"path": "pages/3__Data_Hakim.py",         "label": "Data Hakim",    "icon": "⚖️"},
    {"path": "pages/3__Data_PP.py",            "label": "Data PP",       "icon": "🧑‍💼"},
    {"path": "pages/3_Data_JS.py",            "label": "Data JS",       "icon": "🧑‍💻"},
    {"path": "pages/3_Data_Libur.py",         "label": "Data Libur",    "icon": "📅"},
    {"path": "pages/9_user.py",       "label": "Users",         "icon": "👤", "admin_only": True},
]

CSS = """
/* ===== Matikan sidebar & semua tombol togglenya ===== */
[data-testid="stSidebarNav"]{ display:none; }
[data-testid="stSidebar"]{ min-width:0 !important; width:0 !important; }
/* tombol toggle saat sidebar TERBUKA */
[data-testid="stSidebarCollapseButton"],
button[aria-label="Toggle sidebar"],
button[title="Toggle sidebar"]{
  display:none !important; pointer-events:none !important;
}
/* tombol double-chevron saat sidebar TERTUTUP */
[data-testid="stSidebarCollapsedControl"],
[data-testid="collapsedControl"],
button[aria-label="Open sidebar"],
button[title="Open sidebar"]{
  display:none !important; pointer-events:none !important;
}
/* garis dekorasi tepi kiri (kadang masih bisa diklik) */
[data-testid="stDecoration"]{ display:none !important; }

/* ===== Top bar yang tidak kepotong ===== */
.topbar-shell {
  position: sticky; top: 0; z-index: 99;
  background: var(--background-color);
  padding-top: .10rem; padding-bottom: .10rem;
  border-bottom: 1px solid rgba(255,255,255,.10);
}

/* ===== Konten utama rapi ===== */
.block-container { padding-top: .5rem !important; overflow: visible !important; }
[data-testid="stAppViewContainer"] > .main { overflow: visible !important; }

/* ===== Chip look ===== */
.topchip{
  display:inline-flex; align-items:center; gap:.4rem;
  padding:.40rem .72rem; border-radius:999px;
  border:1px solid rgba(255,255,255,.14);
  background:transparent; font-size:.92rem; white-space:nowrap;
}
.topchip.active{
  background: rgba(99,102,241,.20);
  border-color: rgba(99,102,241,.55);
}
"""

def _logout():
    for k in ("auth_user","auth_role","auth_exp","_redirecting"):
        st.session_state.pop(k, None)
    st.rerun()

def _rel_from_root(abs_path: str) -> str:
    p = Path(abs_path).resolve()
    cwd = Path.cwd().resolve()
    try:
        rel = p.relative_to(cwd).as_posix()
    except Exception:
        rel = p.name
    if rel.endswith(".py"):
        if "/pages/" in rel or "\\pages\\" in rel:
            rel = "pages/" + Path(rel).name
        else:
            rel = "app.py"
    return rel

def _active_page_auto() -> str:
    for fr in inspect.stack():
        fp = fr.filename or ""
        if "app_core" in fp:
            continue
        rel = _rel_from_root(fp)
        if rel.endswith(".py"):
            return rel
    return "app.py"

def render_top_nav(brand: str = "SMART-INPUT", slots:int = 6):
    # refresh TTL (opsional sesuai punyamu)...
    active = _active_page_auto()
    role   = st.session_state.get("auth_role","user")

    items = [p for p in PAGES if not (p.get("admin_only") and role != "admin")]

    # pager state
    key_off = "__topnav_off"
    st.session_state.setdefault(key_off, 0)
    offset = st.session_state[key_off]
    total  = len(items); slots = max(3, int(slots))
    offset = min(max(0, offset), max(0, total - slots))
    st.session_state[key_off] = offset

    st.markdown('<div class="topbar-shell">', unsafe_allow_html=True)
    row = st.columns([1.4, 6.2, 1.2, 1.0])  # brand | nav | user | logout

    # Brand
    with row[0]:
        st.markdown("### " + brand)

    # NAV (horizontal)
    with row[1]:
        c = st.columns([0.6] + [1]*slots + [0.6])
        # ◀
        with c[0]:
            if st.button("◀", key="__topnav_prev", use_container_width=True, disabled=(offset<=0)):
                st.session_state[key_off] = offset-1
                st.rerun()
        # chips
        for idx, it in enumerate(items[offset:offset+slots], start=1):
            with c[idx]:
                label = f'{it["icon"]} {it["label"]}'
                if it["path"] == active:
                    st.markdown(f'<div class="topchip active">{label}</div>', unsafe_allow_html=True)
                else:
                    st.page_link(it["path"], label=label)
        # ▶
        with c[-1]:
            has_next = (offset + slots) < total
            if st.button("▶", key="__topnav_next", use_container_width=True, disabled=not has_next):
                st.session_state[key_off] = offset+1
                st.rerun()

    # User
    with row[2]:
        st.caption(f'👤 Masuk sebagai {st.session_state.get("auth_user","—")} (role: {role})')

    # Logout (HANYA SATU)
    with row[3]:
        if st.button("Logout", key="__top_logout", use_container_width=True):
            for k in ("auth_user","auth_role","auth_exp","_redirecting"):
                st.session_state.pop(k, None)
            st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)