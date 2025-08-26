import uuid
import pandas as pd
import streamlit as st
from gspread.utils import rowcol_to_a1
from config import ws

@st.cache_data(ttl=60)
def load_data():
    values = ws.get("A1:Z")
    if not values:
        return pd.DataFrame(columns=["ID", "Produkt", "Firma", "Typ", "Nr seryjny", "Lokalizacja", "Stan"])

    headers = [h.strip() for h in values[0]]
    rows = values[1:]
    df = pd.DataFrame(rows, columns=headers)

    if "ID" not in df.columns:
        df.insert(0, "ID", [str(uuid.uuid4()) for _ in range(len(df))])
        ws.clear()
        ws.update([df.columns.tolist()] + df.fillna("").values.tolist())

    for col in ["Produkt", "Firma", "Typ", "Nr seryjny", "Lokalizacja"]:
        if col in df.columns:
            df[col] = df[col].fillna("").astype(str).str.strip()
        else:
            df[col] = ""
    if "Stan" in df.columns:
        df["Stan"] = pd.to_numeric(df["Stan"], errors="coerce").fillna(0).astype(int)
    else:
        df["Stan"] = 0

    desired_cols = ["ID", "Produkt", "Firma", "Typ", "Nr seryjny", "Lokalizacja", "Stan"]
    return df.reindex(columns=desired_cols)

def save_full(df):
    ws.clear()
    ws.update([df.columns.tolist()] + df.fillna("").values.tolist())

def save_deltas(df, deltas):
    updates = []
    stan_idx = df.columns.get_loc("Stan") + 1
    for item_id, _ in deltas.items():
        idx = df.index[df["ID"] == item_id]
        if not idx.empty:
            row_number = idx[0] + 2
            a1 = rowcol_to_a1(row_number, stan_idx)
            updates.append({"range": a1, "values": [[int(df.at[idx[0], "Stan"])]]})
    if updates:
        ws.batch_update(updates, value_input_option="RAW")
