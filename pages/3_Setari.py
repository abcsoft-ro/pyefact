import streamlit as st
import os
from dotenv import load_dotenv, set_key, find_dotenv
import base64
import json
from datetime import datetime
from sqlalchemy import create_engine
import time
import sys
import subprocess

# Adăugăm calea proiectului pentru a putea importa clasa Anafgettoken
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from anaf_oauth2 import Anafgettoken

# Este o practică bună să încărcăm .env și aici, pentru a asigura funcționarea
# paginii în diverse contexte de rulare.
load_dotenv()

st.set_page_config(page_title="Setări", layout="wide")

st.title("⚙️ Setări Aplicație și Variabile de Mediu")

st.info(
    "Această pagină afișează starea variabilelor de mediu esențiale, citite din fișierul `.env`. "
    "Valorile sensibile, cum ar fi token-urile sau string-urile de conexiune, sunt afișate parțial din motive de securitate."
)

def test_db_connection():
    """
    Testează conexiunea la baza de date folosind URI-ul din .env.
    Returnează un tuplu (success: bool, message: str).
    """
    connection_uri = os.getenv("DATABASE_CONNECTION_URI")
    if not connection_uri:
        return False, "Variabila 'DATABASE_CONNECTION_URI' nu este setată în fișierul .env."

    try:
        # Creăm un engine nou pentru test, fără a folosi cache-ul global
        engine = create_engine(connection_uri)
        with engine.connect() as connection:
            # Conexiunea este reușită dacă acest bloc se execută fără excepții
            return True, "✅ Conexiunea la baza de date a fost realizată cu succes!"
    except Exception as e:
        return False, f"🔥 Eroare la conectare: {e}"

def get_jwt_expiry(token: str) -> datetime | None:
    """
    Parsează un token JWT și returnează data de expirare ca obiect datetime.
    Returnează None dacă token-ul este invalid sau nu are un claim 'exp'.
    """
    try:
        # JWT este compus din trei părți separate prin puncte. Payload-ul este a doua parte.
        _, payload_b64, _ = token.split('.')
        
        # Payload-ul este codat Base64Url. Trebuie să adăugăm padding dacă lipsește.
        payload_b64 += '=' * (-len(payload_b64) % 4)
        
        # Decodăm payload-ul
        payload_json = base64.urlsafe_b64decode(payload_b64).decode('utf-8')
        
        # Parsăm payload-ul JSON
        payload = json.loads(payload_json)
        
        # Obținem claim-ul 'exp', care este un timestamp Unix
        exp_timestamp = payload.get('exp')
        return datetime.fromtimestamp(exp_timestamp) if exp_timestamp else None
    except Exception:
        return None

def display_env_var(var_name: str, sensitive: bool = False):
    """
    Afișează o variabilă de mediu și statusul ei într-un mod structurat.
    """
    value = os.getenv(var_name)
    
    col1, col2 = st.columns([1, 3])
    
    with col1:
        st.code(var_name, language=None)
        
    with col2:
        if value:
            if sensitive and len(value) > 8:
                # Afișează o valoare mascată pentru variabilele sensibile
                masked_value = f"{value[:4]}...{value[-4:]}"
                st.success(f"Încărcat: `{masked_value}`")
            else:
                # Afișează valoarea completă pentru variabilele non-sensibile sau scurte
                st.success(f"Încărcat: `{value}`")
        else:
            st.error(f"Neconfigurat. Vă rugăm adăugați `{var_name}` în fișierul `.env`.")

def display_file_path_var(var_name: str):
    """
    Afișează o variabilă de mediu care conține o cale către un fișier
    și validează existența fișierului.
    """
    path = os.getenv(var_name)
    
    col1, col2 = st.columns([1, 3])
    
    with col1:
        st.code(var_name, language=None)
        
    with col2:
        if path:
            st.success(f"Configurat: `{path}`")
            if os.path.exists(path):
                st.info("✔️ Fișierul a fost găsit pe disc.")
            else:
                st.error("🔥 Fișierul NU a fost găsit la calea specificată!")
        else:
            st.warning(f"Opțional. Adăugați `{var_name}` în fișierul `.env` pentru a folosi autentificarea cu certificat.")

def display_folder_path_var(var_name: str):
    """
    Afișează o variabilă de mediu care conține o cale către un director
    și validează existența acestuia.
    """
    path = os.getenv(var_name)
    
    col1, col2 = st.columns([1, 3])
    
    with col1:
        st.code(var_name, language=None)
        
    with col2:
        if path:
            st.success(f"Configurat: `{path}`")
            if os.path.isdir(path):
                st.info("✔️ Directorul a fost găsit pe disc.")
            else:
                st.error("🔥 Directorul NU a fost găsit la calea specificată!")
        else:
            st.error(f"Neconfigurat. Vă rugăm adăugați `{var_name}` în fișierul `.env`.")

def display_optional_env_var(var_name: str, sensitive: bool = False, purpose_text: str = ""):
    """
    Afișează o variabilă de mediu opțională, cu opțiune de mascare.
    """
    value = os.getenv(var_name)
    
    col1, col2 = st.columns([1, 3])
    
    with col1:
        st.code(var_name, language=None)
        
    with col2:
        if value:
            if sensitive and len(value) > 0:
                # Afișează o valoare mascată pentru variabilele sensibile
                masked_value = f"{value[0]}...{value[-1]}" if len(value) > 1 else "*"
                st.success(f"Configurat: `{masked_value}`")
            else:
                st.success(f"Configurat: `{value}`")
        else:
            st.warning(f"Opțional. Adăugați `{var_name}` în fișierul `.env` {purpose_text}.")


def display_anaf_token_status():
    """
    Afișează statusul token-ului ANAF, al refresh token-ului și un buton de refresh.
    """
    # --- Access Token ---
    access_token_var = "ANAF_ACCESS_TOKEN"
    access_token = os.getenv(access_token_var)
    
    col1, col2 = st.columns([1, 3])
    with col1:
        st.code(access_token_var, language=None)
    with col2:
        if not access_token:
            st.error(f"Neconfigurat. Vă rugăm adăugați `{access_token_var}` în fișierul `.env`.")
        else:
            masked_value = f"{access_token[:4]}...{access_token[-4:]}" if len(access_token) > 8 else access_token
            st.success(f"Încărcat: `{masked_value}`")
            expiry_date = get_jwt_expiry(access_token)
            if expiry_date:
                formatted_date = expiry_date.strftime('%d %B %Y, %H:%M:%S')
                if expiry_date > datetime.now():
                    st.info(f"🔑 **Token valabil până la:** {formatted_date}")
                else:
                    st.error(f"🔑 **Token expirat la:** {formatted_date}")
            else:
                st.warning("Nu s-a putut determina data de expirare a token-ului. Format invalid?")

    # --- Refresh Token ---
    refresh_token_var = "ANAF_REFRESH_TOKEN"
    refresh_token = os.getenv(refresh_token_var)
    
    col3, col4 = st.columns([1, 3])
    with col3:
        st.code(refresh_token_var, language=None)
    with col4:
        if not refresh_token:
            st.error(f"Neconfigurat. Vă rugăm adăugați `{refresh_token_var}` în fișierul `.env`.")
        else:
            masked_value = f"{refresh_token[:4]}...{refresh_token[-4:]}" if len(refresh_token) > 8 else refresh_token
            st.success(f"Încărcat: `{masked_value}`")

        # Reorganizăm butoanele pe 3 coloane pentru a adăuga butonul de revocare
        btn_col1, btn_col2, btn_col3 = st.columns(3)

        with btn_col1:
            if st.button("Refresh Access Token"):
                with st.spinner("Se reîmprospătează token-ul..."):
                    # --- PAS CRITIC ---
                    # Forțăm reîncărcarea variabilelor din .env pentru a ne asigura că folosim cele mai recente token-uri.
                    load_dotenv(override=True)

                    # Citim toate variabilele necesare
                    access_token = os.getenv("ANAF_ACCESS_TOKEN")
                    refresh_token = os.getenv("ANAF_REFRESH_TOKEN")
                    client_id = os.getenv("ANAF_CLIENT_ID")
                    client_secret = os.getenv("ANAF_CLIENT_SECRET")

                    if not all([access_token, refresh_token, client_id, client_secret]):
                        st.error("Eroare: Asigurați-vă că variabilele ANAF_ACCESS_TOKEN, ANAF_REFRESH_TOKEN, ANAF_CLIENT_ID și ANAF_CLIENT_SECRET sunt setate în fișierul .env.")
                    else:
                        try:
                            # Inițiem clientul. PIN-ul și redirect_uri nu sunt necesare pentru refresh.
                            anaf_client = Anafgettoken(
                                client_id=client_id,
                                client_secret=client_secret,
                                redirect_uri="", # Nu este necesar pentru acest flux
                                pin="" # Nu este necesar pentru acest flux
                            )
                            
                            new_token_data = anaf_client.refresh_token(access_token, refresh_token)
                            
                            new_access_token = new_token_data.get("access_token")
                            # Fluxul de refresh returnează doar un nou access_token.
                            # Refresh token-ul rămâne același.

                            if new_access_token:
                                env_file = find_dotenv()
                                set_key(env_file, "ANAF_ACCESS_TOKEN", new_access_token)
                                
                                st.success("Token-ul de acces a fost reîmprospătat cu succes! Se reîncarcă pagina...")
                                time.sleep(2)
                                st.rerun()
                            else:
                                st.error("Răspunsul de la ANAF nu conține noul 'access_token'.")
                                st.json(new_token_data)

                        except Exception as e:
                            st.error(f"A apărut o eroare la reîmprospătarea token-ului:")
                            st.exception(e)

        with btn_col2:
            if st.button("Revoca Tokenul", help="Invalidează permanent token-ul de acces și cel de refresh. Va fi necesară o nouă autentificare."):
                # Folosim session_state pentru a afișa un dialog de confirmare
                st.session_state['show_revoke_confirmation'] = True

            if st.session_state.get('show_revoke_confirmation'):
                st.warning("**Sunteți sigur că doriți să revocați token-ul?** Această acțiune este ireversibilă și va necesita o nouă autentificare completă.")
                
                # Creăm coloane pentru butoanele de confirmare
                # Am mărit lățimea relativă a coloanelor pentru a se potrivi cu textul butoanelor.
                confirm_col1, confirm_col2, _ = st.columns([2, 2, 3])
                with confirm_col1:
                    if st.button("DA, revocă", type="primary", use_container_width=True):
                        st.session_state['show_revoke_inprogress_message'] = True
                        st.session_state['show_revoke_confirmation'] = False # Ascundem dialogul
                        st.rerun()
                
                with confirm_col2:
                    if st.button("Cancel", use_container_width=True):
                        st.session_state['show_revoke_confirmation'] = False # Ascundem dialogul
                        st.rerun()

            if st.session_state.pop('show_revoke_inprogress_message', False):
                st.info("Funcționalitate în curs de implementare.")
        with btn_col3:
            if st.button("Obține un Token Nou", type="primary", help="Lansează o fereastră de browser pentru a vă autentifica și a obține un nou set de token-uri."):
                with st.spinner("Se lansează procesul de autentificare... Vă rugăm urmați instrucțiunile din terminal și fereastra de browser."):
                    try:
                        # Folosim sys.executable pentru a ne asigura că rulăm cu același interpretor Python
                        # ca și aplicația Streamlit, care are acces la mediul virtual.
                        process = subprocess.run(
                            [sys.executable, "get_token.py"],
                            capture_output=True, text=True, check=True, encoding='utf-8'
                        )
                        st.success("Procesul de obținere a token-ului s-a încheiat cu succes!")
                        st.code(process.stdout, language="log")

                        # --- NOU: Forțăm reîncărcarea variabilelor și golirea cache-ului ---
                        # Această secțiune este esențială pentru a asigura că aplicația Streamlit,
                        # care rulează într-un proces separat, preia noile variabile de mediu.
                        st.info("Se reîncarcă configurația și se golește cache-ul...")
                        
                        # 1. Suprascriem variabilele de mediu din procesul curent cu cele noi din fișierul .env
                        load_dotenv(override=True)
                        
                        # 2. Golim cache-ul pentru resurse (ex: clientul ANAF) și date
                        st.cache_resource.clear()
                        st.cache_data.clear()
                        
                        st.success("Configurația a fost actualizată. Se reîncarcă pagina...")
                        time.sleep(2) # O mică pauză pentru ca utilizatorul să citească mesajul

                        st.rerun() # Acum, rerun-ul va folosi noile variabile
                    except subprocess.CalledProcessError as e:
                        st.error("A apărut o eroare la rularea scriptului de obținere a token-ului:")
                        st.code(e.stderr or e.stdout, language="log")
                    except FileNotFoundError:
                        st.error("Eroare: Scriptul 'get_token.py' nu a fost găsit. Asigurați-vă că se află în directorul principal al aplicației.")

st.header("Configurație ANAF")
st.markdown("Aplicația poate folosi una din cele trei metode de autentificare. Asigurați-vă că ați configurat corect variabilele pentru metoda dorită.")
display_env_var("ANAF_CIF")

st.subheader("Metoda 1: Autentificare OAuth2")
st.info("Această metodă folosește un `access_token` și un `refresh_token` pentru autentificare.")
display_anaf_token_status()

st.markdown("##### Credențiale Client OAuth2")
st.info("Aceste credențiale sunt necesare pentru a reîmprospăta token-ul.")
display_env_var("ANAF_CLIENT_ID", sensitive=True)
display_env_var("ANAF_CLIENT_SECRET", sensitive=True)

st.subheader("Metoda 2: Autentificare cu Certificat Digital")
st.info("Această metodă folosește un certificat digital calificat, salvat în fișiere de tip .pem.")
display_file_path_var("ANAF_CERT_PATH")
display_file_path_var("ANAF_KEY_PATH")

st.subheader("Metoda 3: Autentificare cu Token USB (PKCS#11)")
st.warning("Notă: Această metodă de autentificare este experimentală și în curs de implementare.")
st.info("Această metodă folosește un token criptografic USB. Necesită calea către driverul PKCS#11 (.dll) al token-ului.")
st.info("**Notă de securitate:** Din motive de securitate, PIN-ul **nu** se stochează în fișierul `.env`. Aplicația vă va solicita PIN-ul într-un câmp securizat atunci când este necesar.")
display_file_path_var("PKCS11_LIB_PATH")


st.header("Configurație Directoare")
st.markdown("Căile către directoarele folosite de aplicație.")
display_folder_path_var("XML_UPLOAD_FOLDER_PATH")

st.header("Configurație Bază de Date")
display_env_var("DATABASE_CONNECTION_URI", sensitive=True)

if st.button("Testează Conexiunea la Baza de Date"):
    with st.spinner("Se testează conexiunea..."):
        success, message = test_db_connection()
        if success:
            st.success(message)
        else:
            st.error(message)

st.markdown("---")
st.write("Exemplu de conținut pentru fișierul `.env`:")
st.code("""# --- Setări Generale ANAF ---
# Calea către directorul unde se vor plasa fișierele XML pentru a fi încărcate în ANAF
XML_UPLOAD_FOLDER_PATH=C:\\pyefact\\xml_upload

ANAF_CIF=...

# --- Metoda 1: Autentificare OAuth2 ---
ANAF_ACCESS_TOKEN=...
ANAF_REFRESH_TOKEN=...

# --- Credențiale Client OAuth2 (necesare pentru refresh token) ---
ANAF_CLIENT_ID=...
ANAF_CLIENT_SECRET=...

# --- Metoda 2: Autentificare cu Certificat Digital (căi absolute recomandate) ---
ANAF_CERT_PATH=C:\\path\\to\\certificat.pem
ANAF_KEY_PATH=C:\\path\\to\\cheie_privata.pem

# --- Metoda 3: Autentificare cu Token USB (PKCS#11) - Experimental ---
# Calea către fișierul .dll al driverului token-ului (ex: "C:\\Windows\\System32\\eTPKCS11.dll")
PKCS11_LIB_PATH=C:\\Windows\\System32\\eTPKCS11.dll

# --- Setări Bază de Date (alegeți una din opțiuni) ---

# Opțiunea A: Autentificare SQL Server (cu utilizator și parolă)
# Asigurați-vă că parola nu conține caractere speciale sau, dacă da, că este encodată (URL-encoded).
DATABASE_CONNECTION_URI="mssql+pyodbc://user:password@server_name\\SQLEXPRESS/database_name?driver=ODBC+Driver+17+for+SQL+Server"

# Opțiunea B: Autentificare Windows (Trusted Connection)
# DATABASE_CONNECTION_URI="mssql+pyodbc:///?odbc_connect=DRIVER={ODBC Driver 17 for SQL Server};SERVER=server_name\\SQLEXPRESS;DATABASE=database_name;Trusted_Connection=yes"
""", language="ini")