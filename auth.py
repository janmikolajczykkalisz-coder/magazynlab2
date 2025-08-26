import streamlit as st

def login():
    AUTHORIZED_USERS = st.secrets["users"]
    st.session_state.setdefault("logged_in", False)
    st.session_state.setdefault("username", "")

    if not st.session_state.logged_in:
        st.title(" Logowanie")
        with st.form("login_form"):
            username = st.text_input("Login")
            password = st.text_input("Hasło", type="password")
            if st.form_submit_button("Zaloguj"):
                if AUTHORIZED_USERS.get(username) == password:
                    st.session_state.logged_in = True
                    st.session_state.username = username
                    st.rerun()
                else:
                    st.error("❌ Niepoprawny login lub hasło.")
        st.stop()
