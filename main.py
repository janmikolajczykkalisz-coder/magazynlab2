# # app.py
# # Wymagane sekrety:
# # st.secrets["gcp_service_account"] = {...}
# # st.secrets["users"] = {"login": "haslo", ...}
# # st.secrets["spreadsheet_key"] = "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"  # (zalecane)
# # opcjonalnie: st.secrets["spreadsheet_title"] = "Magazyn"
# # opcjonalnie: st.secrets["sheet_name"] = "Sheet1"
#
# import uuid
# import pandas as pd
# import streamlit as st
# import gspread
# from gspread.utils import rowcol_to_a1
# from google.oauth2.service_account import Credentials
#
# # ------------------------------- Konfiguracja strony -------------------------------
# st.set_page_config(page_title="Lab Magazyn", layout="centered")
#
# # ------------------------------- Połączenie z Google Sheets -------------------------------
# @st.cache_resource
# def get_worksheet():
#     scopes = ["https://www.googleapis.com/auth/spreadsheets"]
#     creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
#     client = gspread.authorize(creds)
#
#     sheet_name = st.secrets.get("sheet_name", "Sheet1")
#     ws = None
#     # Najpierw spróbuj po kluczu
#     key = st.secrets.get("spreadsheet_key")
#     if key:
#         ws = client.open_by_key(key).worksheet(sheet_name)
#     else:
#         # Fallback po tytule (mniej niezawodne)
#         title = st.secrets.get("spreadsheet_title", "Magazyn")
#         ws = client.open_by_key(st.secrets["spreadsheet_key"]).worksheet(sheet_name)
#
#     return ws
#
# ws = get_worksheet()
#
# # ------------------------------- Ładowanie danych -------------------------------
# @st.cache_data(ttl=60)
# def load_data():
#     values = ws.get("A1:Z")  # dopasuj zakres szerokości kolumn, jeśli potrzeba
#     if not values:
#         return pd.DataFrame(columns=["ID", "Produkt", "Firma", "Typ", "Nr seryjny", "Lokalizacja", "Stan"])
#
#     headers = [h.strip() for h in values[0]]
#     rows = values[1:]
#     df = pd.DataFrame(rows, columns=headers)
#
#     # Migracja: dodaj ID jeśli brak
#     if "ID" not in df.columns:
#         df.insert(0, "ID", [str(uuid.uuid4()) for _ in range(len(df))])
#         # Jednorazowe nadpisanie arkusza z nową kolumną
#         ws.clear()
#         ws.update([df.columns.tolist()] + df.fillna("").values.tolist())
#
#     # Typy i czyszczenie
#     for col in ["Produkt", "Firma", "Typ", "Nr seryjny", "Lokalizacja"]:
#         if col in df.columns:
#             df[col] = df[col].fillna("").astype(str).str.strip()
#         else:
#             df[col] = ""
#     if "Stan" in df.columns:
#         df["Stan"] = pd.to_numeric(df["Stan"], errors="coerce").fillna(0).astype(int)
#     else:
#         df["Stan"] = 0
#
#     # Upewnij się o właściwej kolejności kolumn
#     desired_cols = ["ID", "Produkt", "Firma", "Typ", "Nr seryjny", "Lokalizacja", "Stan"]
#     df = df.reindex(columns=desired_cols)
#     return df
#
# # ------------------------------- Autoryzacja użytkowników -------------------------------
# AUTHORIZED_USERS = st.secrets["users"]
# st.session_state.setdefault("logged_in", False)
# st.session_state.setdefault("username", "")
#
# if not st.session_state.logged_in:
#     st.title(" Logowanie")
#     with st.form("login_form"):
#         username = st.text_input("Login")
#         password = st.text_input("Hasło", type="password")
#         if st.form_submit_button("Zaloguj"):
#             if AUTHORIZED_USERS.get(username) == password:
#                 st.session_state.logged_in = True
#                 st.session_state.username = username
#                 st.rerun()
#             else:
#                 st.error("❌ Niepoprawny login lub hasło.")
#     st.stop()
#
# # ------------------------------- Stan aplikacji -------------------------------
# st.session_state.setdefault("df_cache", None)           # lokalna, spójna kopia danych
# st.session_state.setdefault("pending_deltas", {})       # ID -> delta int (zmiany stanu)
# st.session_state.setdefault("to_delete", set())         # ID oznaczone do usunięcia
# st.session_state.setdefault("require_full_save", False) # czy potrzebny pełny zapis (dodania/usunięcia)
# st.session_state.setdefault("historia_usuniec", [])     # lista słowników z usuniętymi rekordami
#
# # Załaduj lub użyj lokalnej kopii
# df = st.session_state.df_cache if st.session_state.df_cache is not None else load_data().copy()
# st.session_state.df_cache = df
#
# # ------------------------------- Funkcje pomocnicze -------------------------------
# def stan_col_index(df_: pd.DataFrame) -> int:
#     # 1-based index kolumny "Stan" w arkuszu (kolumny w df odpowiadają arkuszowi)
#     return df_.columns.get_loc("Stan") + 1
#
# def queue_delta(item_id: str, delta: int):
#     # Zabezpieczenie przed zejściem poniżej 0
#     idx = df.index[df["ID"] == item_id]
#     if len(idx) == 0:
#         return
#     idx = idx[0]
#     new_val = int(df.at[idx, "Stan"]) + delta
#     if new_val < 0:
#         return
#     # Buforuj zmianę i optymistycznie aktualizuj UI
#     st.session_state.pending_deltas[item_id] = st.session_state.pending_deltas.get(item_id, 0) + delta
#     df.at[idx, "Stan"] = new_val
#     st.session_state.df_cache = df
#
# def flush_changes():
#     # Jeśli są usunięcia lub dodania, wykonaj pełny zapis
#     if st.session_state.require_full_save or st.session_state.to_delete:
#         new_df = st.session_state.df_cache.copy()
#
#         # Wykonaj pełny rewrite arkusza
#         ws.clear()
#         ws.update([new_df.columns.tolist()] + new_df.fillna("").values.tolist())
#
#         # Po pełnym zapisie wyczyść bufory
#         st.session_state.pending_deltas.clear()
#         st.session_state.to_delete.clear()
#         st.session_state.require_full_save = False
#         st.success("Zapisano wszystkie zmiany (pełna aktualizacja arkusza).")
#         return
#
#     # Seletywne aktualizacje kolumny "Stan"
#     if not st.session_state.pending_deltas:
#         st.info("Brak zmian do zapisania.")
#         return
#
#     updates = []
#     stan_idx = stan_col_index(df)
#     # Dla każdego ID z deltą policz docelową wartość i zaktualizuj odpowiednią komórkę
#     for item_id, _delta in st.session_state.pending_deltas.items():
#         idx = df.index[df["ID"] == item_id]
#         if len(idx) == 0:
#             continue
#         idx = idx[0]
#         row_number = idx + 2  # +1 nagłówek, +1 1-based
#         a1 = rowcol_to_a1(row_number, stan_idx)
#         new_val = int(df.at[idx, "Stan"])
#         updates.append({"range": a1, "values": [[new_val]]})
#
#     if updates:
#         ws.batch_update(updates, value_input_option="RAW")
#         st.session_state.pending_deltas.clear()
#         st.success("Zapisano zmiany stanów (szybka aktualizacja).")
#     else:
#         st.info("Brak zmian do zapisania.")
#
# def reset_filters():
#     for key in ["filter_produkt", "filter_firma", "filter_typ", "filter_nr", "filter_lok"]:
#         if key in st.session_state:
#             if key in st.session_state:
#                 del st.session_state[key]
#
#     st.rerun()
#
# def refresh_from_sheet():
#     # Porzuć lokalne zmiany i wczytaj ponownie
#     st.session_state.df_cache = load_data().copy()
#     st.session_state.pending_deltas.clear()
#     st.session_state.to_delete.clear()
#     st.session_state.require_full_save = False
#     st.rerun()
#
# def undo_delete_by_id(item_id: str):
#     # Znajdź element w historii i przywróć
#     hist = st.session_state["historia_usuniec"]
#     pos = next((i for i, it in enumerate(hist) if it.get("ID") == item_id), None)
#     if pos is None:
#         return
#     item = hist.pop(pos)
#     # Dodaj wiersz z powrotem do df
#     st.session_state.df_cache.loc[len(st.session_state.df_cache)] = item
#     st.session_state.df_cache.reset_index(drop=True, inplace=True)
#     st.session_state.require_full_save = True
#     st.success(f"✅ Przywrócono: {item.get('Produkt', 'produkt')}")
#     st.rerun()
#
# # ------------------------------- Sidebar: user & akcje -------------------------------
# with st.sidebar:
#     st.markdown(f"👋 Witaj, **{st.session_state.username}**!")
#     st.divider()
#
#     # Filtry
#     st.header("🔍 Filtry")
#     produkt_filter = st.text_input("Nazwa produktu", key="filter_produkt", value=st.session_state.get("filter_produkt", ""))
#     firma_filter = st.text_input("Firma", key="filter_firma", value=st.session_state.get("filter_firma", ""))
#     typ_filter = st.text_input("Typ", key="filter_typ", value=st.session_state.get("filter_typ", ""))
#     nr_ser_filter = st.text_input("Numer seryjny", key="filter_nr", value=st.session_state.get("filter_nr", ""))
#     lokalizacja_filter = st.text_input("Lokalizacja", key="filter_lok", value=st.session_state.get("filter_lok", ""))
#
#     cols = st.columns(2)
#     if cols[0].button("🔄 Wyczyść filtry"):
#         reset_filters()
#     if cols[1].button("🔁 Odśwież z arkusza"):
#         refresh_from_sheet()
#
#     st.divider()
#     st.caption(f"📝 Oczekujące zmiany: {len(st.session_state.pending_deltas)} | 🗑️ Usunięcia: {len(st.session_state.to_delete)}")
#     if st.button("💾 Zapisz zmiany"):
#         flush_changes()
#         st.rerun()
#
#     if st.button("🧹 Anuluj zmiany lokalne"):
#         refresh_from_sheet()
#
#     st.divider()
#     if st.button("🚪 Wyloguj"):
#         st.session_state.logged_in = False
#         st.session_state.username = ""
#         st.rerun()
#
# # ------------------------------- Filtrowanie & paginacja -------------------------------
# filtered = df.copy()
# mapping = {
#     "Produkt": produkt_filter,
#     "Firma": firma_filter,
#     "Typ": typ_filter,
#     "Nr seryjny": nr_ser_filter,
#     "Lokalizacja": lokalizacja_filter
# }
# for col, val in mapping.items():
#     if val:
#         if col in ["Produkt", "Nr seryjny"]:
#             filtered = filtered[filtered[col].str.contains(val, case=False, na=False)]
#         else:
#             filtered = filtered[filtered[col] == val]
#
# # Paginacja (wcześnie, żeby nie renderować nadmiaru UI)
# page_size = 20
# total_pages = max((len(filtered) - 1) // page_size + 1, 1)
# if "page" not in st.session_state:
#     st.session_state.page = 1
#
# max_page = total_pages
#
# # trzy kolumny w sidebarze: przyciski i wyświetlenie numeru strony
# col1, col2, col3 = st.sidebar.columns([1, 2, 1])
# with col1:
#     if st.button("⬅", key="prev"):
#         if st.session_state.page > 1:
#             st.session_state.page -= 1
#             st.rerun()
#
# with col3:
#     if st.button("➡", key="next"):
#         if st.session_state.page < max_page:
#             st.session_state.page += 1
#             st.rerun()
#
# col2.markdown(
#     f"<div style='text-align:center;'>📄 Strona {st.session_state.page} z {max_page}</div>",
#     unsafe_allow_html=True
# )
#
# page = st.session_state.page
# # ————————————————————————————————————————————————————————————————
#
# # Teraz już tylko wycinasz odpowiedni fragment danych:
# view = filtered.iloc[(page - 1) * page_size : page * page_size]
#
# # ------------------------------- Interfejs główny -------------------------------
# st.markdown('<h2 class="fade-in">📦 Stan magazynu</h2>', unsafe_allow_html=True)
#
# for _, row in view.iterrows():
#     with st.expander(f"{row['Produkt']} — {row['Firma']}", expanded=False):
#         st.markdown(f"**Typ:** {row['Typ']}")
#         st.markdown(f"**Nr seryjny:** {row['Nr seryjny']}")
#         st.markdown(f"**Lokalizacja:** {row['Lokalizacja']}")
#         st.markdown(f"**Stan:** {int(row['Stan'])}")
#
#         c1, c2, c3 = st.columns(3)
#         if c1.button("➕", key=f"plus_{row['ID']}"):
#             queue_delta(row["ID"], +1)
#             st.rerun()
#         if c2.button("➖", key=f"minus_{row['ID']}"):
#             if int(row["Stan"]) > 0:
#                 queue_delta(row["ID"], -1)
#                 st.rerun()
#         if c3.button("❌", key=f"del_{row['ID']}"):
#             # Zapisz do historii i oznacz do usunięcia
#             st.session_state["historia_usuniec"].append(row.to_dict())
#             st.session_state["to_delete"].add(row["ID"])
#             # Usuń lokalnie i zaznacz pełny zapis
#             st.session_state.df_cache = st.session_state.df_cache[st.session_state.df_cache["ID"] != row["ID"]]
#             st.session_state.require_full_save = True
#             st.success(f"🗑️ Usunięto: {row['Produkt']}")
#             st.rerun()
#
# # ------------------------------- Historia usunięć -------------------------------
# st.subheader(" Historia usunięć")
# if st.session_state["historia_usuniec"]:
#     for hist_item in reversed(st.session_state["historia_usuniec"]):
#         col1, col2 = st.columns([4, 1])
#         with col1:
#             st.write(f"**{hist_item.get('Produkt','')}** — {hist_item.get('Firma','')} ({hist_item.get('Typ','')})")
#         with col2:
#             if st.button("↩️ Cofnij", key=f"undo_{hist_item['ID']}"):
#                 undo_delete_by_id(hist_item["ID"])
# else:
#     st.info("Brak usuniętych produktów.")
#
# # ------------------------------- Dodawanie nowego produktu -------------------------------
# st.subheader("➕ Dodaj nowy produkt")
# with st.form("add_form"):
#     nowy = {
#         "Produkt": st.text_input("Nazwa produktu").strip(),
#         "Firma": st.text_input("Firma").strip(),
#         "Typ": st.text_input("Typ").strip(),
#         "Nr seryjny": st.text_input("Numer seryjny").strip(),
#         "Lokalizacja": st.text_input("Lokalizacja").strip(),
#         "Stan": st.number_input("Stan", min_value=0, step=1)
#     }
#     submitted = st.form_submit_button("✅ Dodaj produkt")
#
#     if submitted:
#         if not nowy["Produkt"]:
#             st.warning("⚠️ Podaj przynajmniej nazwę produktu.")
#         else:
#             # Sprawdź czy istnieje identyczny rekord (po 5 kolumnach)
#             istnieje = (
#                 (df["Produkt"].fillna("") == nowy["Produkt"]) &
#                 (df["Firma"].fillna("") == nowy["Firma"]) &
#                 (df["Typ"].fillna("") == nowy["Typ"]) &
#                 (df["Nr seryjny"].fillna("") == nowy["Nr seryjny"]) &
#                 (df["Lokalizacja"].fillna("") == nowy["Lokalizacja"])
#             )
#             if istnieje.any():
#                 idx = df[istnieje].index[0]
#                 # Buforuj zwiększenie stanu jako delta
#                 queue_delta(df.at[idx, "ID"], int(nowy["Stan"]))
#                 st.success(f"✅ Zwiększono stan produktu '{nowy['Produkt']}' o {int(nowy['Stan'])} szt.")
#                 st.rerun()
#             else:
#                 # Dodaj nowy wiersz lokalnie i oznacz pełny zapis
#                 nowy["ID"] = str(uuid.uuid4())
#                 # Upewnij się o typach/kolumnach
#                 for col in ["Produkt", "Firma", "Typ", "Nr seryjny", "Lokalizacja"]:
#                     nowy[col] = str(nowy[col]).strip()
#                 nowy["Stan"] = int(nowy["Stan"])
#                 st.session_state.df_cache.loc[len(st.session_state.df_cache)] = nowy
#                 st.session_state.df_cache.reset_index(drop=True, inplace=True)
#                 st.session_state.require_full_save = True
#                 st.success("✅ Dodano nowy produkt (zapisz zmiany aby utrwalić w arkuszu).")
#                 st.rerun()
#
# # ------------------------------- Stylizacja -------------------------------
# st.markdown("""
# <style>
# .stButton > button {
#     background-color: #f0f0f0;
#     color: #333;
#     border: 1px solid #ccc;
#     padding: 0.4em 1em;
#     border-radius: 6px;
#     transition: 0.2s ease;
# }
# .stButton > button:hover {
#     background-color: #e0e0e0;
#     color: #000;
# }
# .streamlit-expander {
#     border-radius: 8px;
#     border: 1px solid #ddd;
#     padding: 0.5em;
# }
# .fade-in {
#     animation: fadeIn 0.5s ease-in-out;
# }
# @keyframes fadeIn {
#     from { opacity: 0; transform: translateY(6px); }
#     to { opacity: 1; transform: translateY(0); }
# }
# </style>
# """, unsafe_allow_html=True)
