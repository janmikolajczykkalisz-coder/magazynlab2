import streamlit as st
from data import load_data

def queue_delta(df, item_id, delta):
    idx = df.index[df["ID"] == item_id]
    if len(idx) == 0:
        return
    idx = idx[0]
    new_val = int(df.at[idx, "Stan"]) + delta
    if new_val < 0:
        return
    st.session_state.pending_deltas[item_id] = st.session_state.pending_deltas.get(item_id, 0) + delta
    df.at[idx, "Stan"] = new_val
    st.session_state.df_cache = df

def reset_filters():
    for key in ["filter_produkt", "filter_firma", "filter_typ", "filter_nr", "filter_lok"]:
        st.session_state.pop(key, None)
    st.rerun()

def refresh_from_sheet():
    st.session_state.df_cache = load_data().copy()
    st.session_state.pending_deltas.clear()
    st.session_state.to_delete.clear()
    st.session_state.require_full_save = False
    st.rerun()

def undo_delete_by_id(item_id):
    hist = st.session_state["historia_usuniec"]
    pos = next((i for i, it in enumerate(hist) if it.get("ID") == item_id), None)
    if pos is None:
        return
    item = hist.pop(pos)
    st.session_state.df_cache.loc[len(st.session_state.df_cache)] = item
    st.session_state.df_cache.reset_index(drop=True, inplace=True)
    st.session_state.require_full_save = True
    st.success(f"✅ Przywrócono: {item.get('Produkt', 'produkt')}")
    st.rerun()
