# app_core/ui_nav.py
import streamlit as st

# mapping halamanmu (path -> label & ikon)
PAGES = [
    ("1_Input_&_Hasil.py",  "Input & Hasil", "📋"),
    ("2_Rekap.py",          "Rekap",                    "📊"),
    ("3_Data_Hakim.py",     "Data Hakim",               "⚖️"),
    ("3_Data_PP.py",        "Data PP",                  "🧑‍💼"),
    ("3_Data_JS.py",        "Data JS",                  "📨"),
    ("3_Data_Libur.py",     "Data Libur",               "🏖️"),
    ("3_Data_SK_Majelis.py","Data SK Majelis",          "📑"),
    ("4_BATCH_INSTRUMEN.py","Batch Instrumen",          "🧰"),
]

def _css():
    st.markdown("""
    <style>
    :root{
      --nav-w:260px; --nav-w-c:74px;
      --nav-bg:#1d3a55; --nav-bg-2:#163043;
      --nav-active:#0ea5e9; --nav-t:#e6edf3; --nav-m:#a8b3bf;
    }
    ._nav{position:fixed;left:0;top:0;height:100vh;width:var(--nav-w);
      background:var(--nav-bg);color:var(--nav-t);z-index:100;
      display:flex;flex-direction:column;border-right:1px solid #0a2536;transition:width .18s;}
    ._nav.c{width:var(--nav-w-c);}
    ._hdr{display:flex;gap:.6rem;align-items:center;padding:12px 14px;border-bottom:1px solid #0a2536}
    ._logo{width:34px;height:34px;border-radius:50%;background:#0ea5e9;display:grid;place-items:center;font-weight:700}
    ._ttl{font-weight:700;letter-spacing:.4px}
    .c ._ttl{display:none}
    ._tgl{margin-left:auto;padding:6px 10px;border-radius:10px;background:rgba(255,255,255,.06);cursor:pointer}
    ._sc{overflow:auto;padding:10px 8px 14px 8px;flex:1}
    ._item{display:flex;align-items:center;gap:.8rem;padding:10px 12px;margin:6px;border-radius:12px;cursor:pointer;
      white-space:nowrap;overflow:hidden;text-overflow:ellipsis;border:1px solid transparent}
    ._item:hover{background:var(--nav-bg-2)}
    ._item.a{background:rgba(14,165,233,.16);border-color:rgba(14,165,233,.45)}
    ._ico{width:26px;min-width:26px;text-align:center}
    .c ._lbl{display:none}
    ._main{margin-left:var(--nav-w);transition:margin-left .18s}
    ._main.c{margin-left:var(--nav-w-c)}
    </style>
    """, unsafe_allow_html=True)

def render_sidebar(active_filename: str):
    """Gambar sidebar & kembalikan kelas margin untuk konten utama."""
    if "_collapsed" not in st.session_state: st.session_state._collapsed = False
    _css()
    collapsed = "c" if st.session_state._collapsed else ""
    st.markdown(f"""
    <div class="_nav {collapsed}">
      <div class="_hdr">
        <div class="_logo">PT</div>
        <div class="_ttl">PTSP</div>
        <div class="_tgl" onclick="window.parent.postMessage({{isStreamlitMessage:true,type:'streamlit:rerun'}}, '*')">☰</div>
      </div>
      <div class="_sc">
    """, unsafe_allow_html=True)

    # tombol toggle versi Streamlit (fallback dari div di atas)
    if st.button("☰", key="__nav_toggle", help="Collapse/Expand"):
        st.session_state._collapsed = not st.session_state._collapsed

    # items
    for path, label, icon in PAGES:
        is_active = ("a" if path == active_filename else "")
        # tombol yang berpindah halaman
        if st.button(f"{icon}  {label}", key=f"nav-{path}", help=label):
            try:
                st.switch_page(f"pages/{path}")   # Streamlit 1.25+
            except Exception:
                pass
        st.markdown(
            f'<div class="_item {is_active}"><div class="_ico">{icon}</div><div class="_lbl">{label}</div></div>',
            unsafe_allow_html=True
        )

    st.markdown("</div></div>", unsafe_allow_html=True)
    return collapsed  # untuk kelas konten

def main_container(collapsed_flag: str):
    """Bungkus konten utama agar tergeser dari sidebar."""
    st.markdown(f'<div class="_main {collapsed_flag}">', unsafe_allow_html=True)

def end_container():
    st.markdown("</div>", unsafe_allow_html=True)
