import streamlit as st
import os
from anaf_api import ApiANAF

def display_pkcs11_auth_sidebar():
    """
    Afișează în bara laterală câmpurile necesare pentru autentificarea PKCS#11.
    Această funcție NU este cache-uită și trebuie apelată pe fiecare pagină.

    Returnează:
        bool: True dacă este necesară introducerea PIN-ului și execuția trebuie oprită,
              False în caz contrar.
    """
    pkcs11_lib = os.getenv("PKCS11_LIB_PATH")
    
    # Afișăm câmpul pentru PIN doar dacă metoda PKCS#11 este configurată și PIN-ul nu este deja în sesiune
    if pkcs11_lib and 'pkcs11_pin' not in st.session_state:
        st.sidebar.subheader("🔐 Autentificare Token USB")
        pin_input = st.sidebar.text_input(
            "Introduceți PIN-ul token-ului", 
            type="password", 
            help="PIN-ul este necesar pentru a comunica cu serverul ANAF folosind token-ul USB."
        )
        if st.sidebar.button("Salvează PIN"):
            if pin_input:
                st.session_state['pkcs11_pin'] = pin_input
                st.rerun()
            else:
                st.sidebar.warning("PIN-ul nu poate fi gol.")
        # Returnăm True pentru a semnala paginii să se oprească până la introducerea PIN-ului
        return True
    # Returnăm False dacă nu este nevoie de PIN sau dacă a fost deja introdus
    return False

@st.cache_resource
def get_anaf_client():
    """
    Creează și returnează un client pentru API-ul ANAF, gestionând toate metodele de autentificare.
    Folosește st.cache_resource pentru a menține clientul pe durata sesiunii.
    Solicită PIN-ul interactiv pentru autentificarea PKCS#11.
    """
    # Detectează metoda de autentificare pe baza variabilelor de mediu
    auth_method = None
    access_token = os.getenv("ANAF_ACCESS_TOKEN")
    cert_path = os.getenv("ANAF_CERT_PATH")
    key_path = os.getenv("ANAF_KEY_PATH")
    pkcs11_lib = os.getenv("PKCS11_LIB_PATH")
    client_args = {}

    if access_token:
        auth_method = "OAuth2"
        client_args = {"access_token": access_token}
    elif cert_path and key_path:
        auth_method = "Certificat"
        client_args = {"cert_path": cert_path, "key_path": key_path}
    elif pkcs11_lib:
        auth_method = "PKCS#11"
        
        # --- NOU: Verificare explicită a existenței fișierului .dll ---
        if not os.path.exists(pkcs11_lib):
            st.error(f"**Fișierul bibliotecii PKCS#11 nu a fost găsit!**\n\n"
                     f"Calea configurată în `.env` este:\n`{pkcs11_lib}`\n\n"
                     "Verificați următoarele:\n"
                     "1. Calea este corectă și nu conține greșeli de scriere.\n"
                     "2. Ați folosit double backslash (`\\\\`) în fișierul `.env` (ex: `C:\\\\Windows\\\\...`).\n"
                     "3. Fișierul `.dll` există la locația specificată.")
            st.stop()

        # Pentru PKCS#11, PIN-ul este citit din session_state.
        # Funcția UI `display_pkcs11_auth_sidebar` trebuie apelată pe pagină înainte de acest apel.
        client_args = {"pkcs11_lib": pkcs11_lib, "pkcs11_pin": st.session_state.get('pkcs11_pin')}
    
    if not auth_method:
        st.error("Nicio metodă de autentificare ANAF nu este configurată corect în fișierul .env. "
                 "Verificați pagina de Setări pentru detalii.")
        st.stop()
    
    try:
        # Inițializăm clientul API cu argumentele determinate
        client = ApiANAF(**client_args)
        return client
    except Exception as e:
        st.error(f"Eroare la inițializarea clientului ANAF: {e}")
        # Dacă eroarea este legată de PKCS#11, ar putea fi din cauza unui PIN greșit.
        # Oferim utilizatorului o modalitate de a reintroduce PIN-ul.
        if auth_method == "PKCS#11" and 'pkcs11_pin' in st.session_state:
            del st.session_state['pkcs11_pin']
            st.warning("A apărut o eroare, posibil din cauza unui PIN incorect. Vă rugăm reîncercați.")
        st.stop()