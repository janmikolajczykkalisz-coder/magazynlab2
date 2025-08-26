import streamlit as st
from helpers import reset_filters, refresh_from_sheet
from data import save_full, save_deltas

def sidebar(df):
    with st.sidebar:
        st.markdown(f"{st.session_state.username}")
        st.divider()

        st.header("Filtruj")
        produkt_filter = st.text_input("Nazwa produktu", key="filter_produkt")
        firma_filter = st.text_input("Firma", key="filter_firma")
        typ_filter = st.text_input("Typ", key="filter_typ")
        nr_ser_filter = st.text_input("Numer seryjny", key="filter_nr")
        lokalizacja_filter = st.text_input("Lokalizacja", key="filter_lok")

        cols = st.columns(2)
        if cols[0].button("Wyczyść filtry"):
            reset_filters()
        if cols[1].button("Odśwież z arkusza"):
            refresh_from_sheet()

        st.divider()
        st.caption(f" Oczekujące zmiany: {len(st.session_state.pending_deltas)}  ️ | Usunięcia: {len(st.session_state.to_delete)}")
        if st.button(" Zapisz zmiany"):
            if st.session_state.require_full_save or st.session_state.to_delete:
                save_full(st.session_state.df_cache)
                st.session_state.pending_deltas.clear()
                st.session_state.to_delete.clear()
                st.session_state.require_full_save = False
                st.success("Zapisano wszystkie zmiany.")
            else:
                save_deltas(st.session_state.df_cache, st.session_state.pending_deltas)
                st.session_state.pending_deltas.clear()
                st.success("Zapisano zmiany stanów.")
            st.rerun()

        if st.button("Anuluj zmiany lokalne"):
            refresh_from_sheet()

        st.divider()
        if st.button(" Wyloguj"):
            st.session_state.logged_in = False
            st.session_state.username = ""
            st.rerun()

    return {
        "Produkt": produkt_filter,
        "Firma": firma_filter,
        "Typ": typ_filter,
        "Nr seryjny": nr_ser_filter,
        "Lokalizacja": lokalizacja_filter
    }

def product_list(view, queue_delta):
    st.markdown('<h2 class="fade-in"> Magazyn</h2>', unsafe_allow_html=True)
    for idx, (_, row) in enumerate(view.iterrows()):
        # Dodajemy niewidoczny znak, żeby tytuł był unikalny, ale wyglądał tak samo
        expander_title = f"{row['Produkt']} — {row['Firma']}\u00A0" * 1 + ""  # niewidoczna spacja
        expander_title = expander_title + ("\u200B" * idx)  # zero-width space zależny od idx

        with st.expander(expander_title, expanded=False):
            st.markdown(f"**Typ:** {row['Typ']}")
            st.markdown(f"**Nr seryjny:** {row['Nr seryjny']}")
            st.markdown(f"**Lokalizacja:** {row['Lokalizacja']}")
            st.markdown(f"**Stan:** {int(row['Stan'])}")

            c1, c2, c3 = st.columns(3)
            if c1.button("➕", key=f"plus_{row['ID']}_{idx}"):
                queue_delta(st.session_state.df_cache, row["ID"], +1)
                st.rerun()
            if c2.button("➖", key=f"minus_{row['ID']}_{idx}"):
                if int(row["Stan"]) > 0:
                    queue_delta(st.session_state.df_cache, row["ID"], -1)
                    st.rerun()
            if c3.button("❌", key=f"del_{row['ID']}_{idx}"):
                st.session_state["historia_usuniec"].append(row.to_dict())
                st.session_state["to_delete"].add(row["ID"])
                st.session_state.df_cache = st.session_state.df_cache[st.session_state.df_cache["ID"] != row["ID"]]
                st.session_state.require_full_save = True
                st.success(f"🗑️ Usunięto: {row['Produkt']}")
                st.rerun()


def deleted_items_history(undo_delete_by_id):
    st.subheader(" Historia usunięć")
    if st.session_state["historia_usuniec"]:
        for hist_item in reversed(st.session_state["historia_usuniec"]):
            col1, col2 = st.columns([4, 1])
            with col1:
                st.write(f"**{hist_item.get('Produkt','')}** — {hist_item.get('Firma','')} ({hist_item.get('Typ','')})")
            with col2:
                if st.button("↩️ Cofnij", key=f"undo_{hist_item['ID']}"):
                    undo_delete_by_id(hist_item["ID"])
    else:
        st.info("Brak usuniętych produktów.")

def add_product_form(df, queue_delta):
    import uuid
    st.subheader("➕ Dodaj nowy produkt")
    with st.form("add_form"):
        nowy = {
            "Produkt": st.text_input("Nazwa produktu").strip(),
            "Firma": st.text_input("Firma").strip(),
            "Typ": st.text_input("Typ").strip(),
            "Nr seryjny": st.text_input("Numer seryjny").strip(),
            "Lokalizacja": st.text_input("Lokalizacja").strip(),
            "Stan": st.number_input("Stan", min_value=0, step=1)
        }
        submitted = st.form_submit_button("✅ Dodaj produkt")

        if submitted:
            if not nowy["Produkt"]:
                st.warning("⚠️ Podaj przynajmniej nazwę produktu.")
            else:
                istnieje = (
                    (df["Produkt"].fillna("") == nowy["Produkt"]) &
                    (df["Firma"].fillna("") == nowy["Firma"]) &
                    (df["Typ"].fillna("") == nowy["Typ"]) &
                    (df["Nr seryjny"].fillna("") == nowy["Nr seryjny"]) &
                    (df["Lokalizacja"].fillna("") == nowy["Lokalizacja"])
                )
                if istnieje.any():
                    idx = df[istnieje].index[0]
                    queue_delta(df, df.at[idx, "ID"], int(nowy["Stan"]))
                    st.success(f"✅ Zwiększono stan produktu '{nowy['Produkt']}' o {int(nowy['Stan'])} szt.")
                    st.rerun()
                else:
                    nowy["ID"] = str(uuid.uuid4())
                    for col in ["Produkt", "Firma", "Typ", "Nr seryjny", "Lokalizacja"]:
                        nowy[col] = str(nowy[col]).strip()
                    nowy["Stan"] = int(nowy["Stan"])
                    st.session_state.df_cache.loc[len(st.session_state.df_cache)] = nowy
                    st.session_state.df_cache.reset_index(drop=True, inplace=True)
                    st.session_state.require_full_save = True
                    st.success("✅ Dodano nowy produkt (zapisz zmiany aby utrwalić w arkuszu).")
                    st.rerun()
#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