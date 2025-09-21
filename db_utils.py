import streamlit as st
from sqlalchemy import create_engine
import os
from dotenv import load_dotenv

# Încărcăm variabilele de mediu din fișierul .env
# Este o practică bună să o facem aici pentru a ne asigura că sunt disponibile
load_dotenv()

@st.cache_resource
def get_db_engine():
    """
    Creează și returnează un engine SQLAlchemy pentru conexiunea la baza de date.
    Folosește st.cache_resource pentru a se asigura că engine-ul este creat o singură dată per sesiune.
    """
    try:
        connection_uri = os.getenv("DATABASE_CONNECTION_URI")
        if not connection_uri:
            st.error("Variabila de mediu 'DATABASE_CONNECTION_URI' nu este setată în fișierul .env!")
            st.stop()

        engine = create_engine(connection_uri)

        # Testează conexiunea
        with engine.connect() as connection:
            pass

        return engine
    except Exception as ex:
        st.error("Eroare la crearea engine-ului de conexiune SQLAlchemy.")
        st.error(ex)
        st.stop()