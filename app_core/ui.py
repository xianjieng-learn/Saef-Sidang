import streamlit as st

def inject_styles():
    st.markdown("""
    <style>
    .seg {display:flex; flex-wrap:wrap; gap:6px; margin-bottom:8px;}
    .seg button {
      padding:6px 10px; border:1px solid #aaa; background:#f6f6f6; border-radius:8px;
      cursor:pointer; font-weight:600; white-space:nowrap;
    }
    .seg button.active { background:#025bff; color:white; border-color:#025bff; }
    .seg button:hover { filter:brightness(0.97); }
    .right-actions {display:flex; justify-content:flex-end; align-items:center;}
    .add-btn {
      padding:4px 10px; border:1px solid #00a000; color:#00a000; background:#f2fff2; border-radius:8px;
      font-weight:700; cursor:pointer;
    }
    .add-btn:hover { filter:brightness(0.97); }
    .bigdate { font-size: 1.2rem; font-weight: 700; }
    </style>
    """, unsafe_allow_html=True)
