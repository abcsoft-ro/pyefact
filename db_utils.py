import streamlit as st
from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

load_dotenv()

@st.cache_resource
def get_db_engine():
    """
    Creează și returnează un engine SQLAlchemy pentru conexiunea la baza de date.
    Folosește st.cache_resource pentru a se asigura că engine-ul este creat o singură dată per sesiune.
    Creează automat tabelele la prima rulare (SQLite).
    """
    try:
        connection_uri = os.getenv("DATABASE_CONNECTION_URI")
        if not connection_uri:
            st.error("Variabila de mediu 'DATABASE_CONNECTION_URI' nu este setată în fișierul .env!")
            st.stop()

        engine = create_engine(connection_uri)

        with engine.connect() as connection:
            pass

        create_tables_if_not_exist(engine)

        return engine
    except Exception as ex:
        st.error("Eroare la crearea engine-ului de conexiune SQLAlchemy.")
        st.error(ex)
        st.stop()


def create_tables_if_not_exist(engine):
    """Creează tabelele în baza de date dacă nu există deja."""
    with engine.connect() as connection:
        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS tblFacturi (
                Id INTEGER PRIMARY KEY AUTOINCREMENT,
                Firma TEXT,
                cif TEXT,
                Ffilename TEXT,
                IDFactura TEXT,
                IssuDate TEXT,
                Beneficiar TEXT,
                Valoare REAL,
                fxml TEXT,
                sxml TEXT,
                pdf BLOB,
                Solicitareid TEXT,
                StareDocument TEXT,
                IDdescarcare TEXT,
                IndexIncarcare TEXT,
                ExecutionStatus TEXT,
                ErrorMessage TEXT,
                DateResponse TEXT,
                Data TEXT
            )
        """))
        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS tblSPV (
                Id INTEGER PRIMARY KEY AUTOINCREMENT,
                Data_creare TEXT,
                id_solicitare TEXT,
                id_descarcare TEXT,
                IDFact TEXT,
                IssueDate TEXT,
                DueDate TEXT,
                LegalMonetaryTotal TEXT,
                DocumentCurrencyCode TEXT,
                Tip TEXT,
                cif_furnizor TEXT,
                cif_beneficiar TEXT,
                Den_furnizor TEXT,
                Den_beneficiar TEXT,
                f_xml TEXT,
                s_xml TEXT,
                pdf BLOB,
                username TEXT,
                subiectm TEXT,
                tipm TEXT,
                continutm TEXT
            )
        """))
        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS tblmesaje (
                MesId INTEGER PRIMARY KEY AUTOINCREMENT,
                data_creare TEXT,
                cif TEXT,
                id_solicitare TEXT,
                detalii TEXT,
                tip TEXT,
                id TEXT,
                preluat INTEGER DEFAULT 0,
                eroare TEXT
            )
        """))
        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS tblSetari (
                Id INTEGER PRIMARY KEY AUTOINCREMENT,
                cif TEXT,
                Cheie TEXT,
                Valoare TEXT
            )
        """))
        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS tblUtilizatori (
                UserID INTEGER PRIMARY KEY AUTOINCREMENT,
                Nume TEXT,
                Blocat INTEGER DEFAULT 0,
                Functia TEXT,
                CNP TEXT,
                SPV TEXT
            )
        """))
        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS trelIdspvUserID (
                Id INTEGER PRIMARY KEY AUTOINCREMENT,
                IdSPV INTEGER,
                UserID INTEGER
            )
        """))
        connection.commit()
