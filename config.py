import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

@st.cache_resource
def get_worksheet():
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    client = gspread.authorize(creds)

    sheet_name = st.secrets.get("sheet_name", "Sheet1")
    key = st.secrets.get("spreadsheet_key")
    if key:
        return client.open_by_key(key).worksheet(sheet_name)
    else:
        title = st.secrets.get("spreadsheet_title", "Magazyn")
        return client.open(title).worksheet(sheet_name)

ws = get_worksheet()
