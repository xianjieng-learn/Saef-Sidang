# app_core/style.py
import streamlit as st
from pathlib import Path

def load_css_text(css: str):
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)

def load_css_file(path: str | Path):
    css = Path(path).read_text(encoding="utf-8")
    load_css_text(css)

def base_tweaks():
    load_css_text("""
    /* contoh: rapikan font & padding global */
    .stApp { font-size: 14.5px; }
    .block-container { padding-top: 1rem; padding-bottom: 2rem; }

    /* auto collapse + sembunyikan toggle sidebar */
    [data-testid="stSidebar"] { min-width: 0; }
    [data-testid="stSidebarCollapseButton"]{ display:none; }

    /* contoh: kartu */
    .mycard {
      border-radius: 14px; padding: 14px; border: 1px solid rgba(255,255,255,.08);
      background: rgba(255,255,255,.03); box-shadow: 0 4px 18px rgba(0,0,0,.08);
    }
    """)
    
def hide_default_sidebar_nav():
    st.markdown("""
    <style>
      [data-testid="stSidebarNav"] { display: none; }
    </style>
    """, unsafe_allow_html=True)
