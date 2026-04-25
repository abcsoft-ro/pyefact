import streamlit as st
import os
from anaf_api import ApiANAF


@st.cache_resource
def get_anaf_client():
    """
    Creează și returnează un client pentru API-ul ANAF folosind autentificare OAuth2.
    Folosește st.cache_resource pentru a menține clientul pe durata sesiunii.
    """
    access_token = os.getenv("ANAF_ACCESS_TOKEN")

    if not access_token:
        st.error("Variabila 'ANAF_ACCESS_TOKEN' nu este configurată în fișierul .env. "
                 "Verificați pagina de Setări pentru detalii.")
        st.stop()

    try:
        client = ApiANAF(access_token=access_token)
        return client
    except Exception as e:
        st.error(f"Eroare la inițializarea clientului ANAF: {e}")
        st.stop()
