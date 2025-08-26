import streamlit as st

def apply_styles():
    st.markdown("""
    <style>
    .stButton > button {
        background-color: #f0f0f0;
        color: #333;
        border: 1px solid #ccc;
        padding: 0.4em 1em;
        border-radius: 6px;
        transition: 0.2s ease;
    }
    .stButton > button:hover {
        background-color: #e0e0e0;
        color: #000;
    }
    .streamlit-expander {
        border-radius: 8px;
        border: 1px solid #ddd;
        padding: 0.5em;
    }
    .fade-in {
        animation: fadeIn 0.5s ease-in-out;
    }
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(6px); }
        to { opacity: 1; transform: translateY(0); }
    }
    </style>
    """, unsafe_allow_html=True)