import streamlit as st
import webbrowser
from auth import login
from data import load_data
from helpers import queue_delta, undo_delete_by_id
#from styles import apply_styles
from ui import sidebar, product_list, deleted_items_history, add_product_form


st.set_page_config(page_title="Lab Magazyn", layout="centered")

# Logowanie
login()

# Inicjalizacja stanów
st.session_state.setdefault("df_cache", None)
st.session_state.setdefault("pending_deltas", {})
st.session_state.setdefault("to_delete", set())
st.session_state.setdefault("require_full_save", False)
st.session_state.setdefault("historia_usuniec", [])
st.session_state.setdefault("page", 1)
st.session_state.setdefault("chat_messages", [])  # historia czatu: [{"role": "...", "content": "..."}]

# Dane
df = st.session_state.df_cache if st.session_state.df_cache is not None else load_data().copy()
st.session_state.df_cache = df

# Styl
#apply_styles()

# Sidebar
filters = sidebar(df)

# Filtrowanie danych
filtered = df.copy()
for col, val in filters.items():
    if val:
        if col in ["Produkt", "Nr seryjny"]:
            filtered = filtered[filtered[col].str.contains(val, case=False, na=False)]
        else:
            filtered = filtered[filtered[col] == val]

# Stronicowanie
page_size = 20
total_pages = max((len(filtered) - 1) // page_size + 1, 1)
page = st.session_state.page
view = filtered.iloc[(page - 1) * page_size: page * page_size]

# Lista produktów
product_list(view, queue_delta)

# Historia usunięć
deleted_items_history(undo_delete_by_id)

# Formularz dodawania
add_product_form(df, queue_delta)



