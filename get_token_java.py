# exemplu_utilizare.py
from anaf_oauth2 import Anafgettoken
import os
import json

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from urllib.parse import urlparse, parse_qs
from dotenv import set_key, find_dotenv, load_dotenv
# --- Pasul 1: Inițializarea ---

# Încărcăm variabilele din fișierul .env
load_dotenv()

# Citim configurația din variabilele de mediu
CLIENT_ID = os.getenv("ANAF_CLIENT_ID")
CLIENT_SECRET = os.getenv("ANAF_CLIENT_SECRET")
REDIRECT_URI = os.getenv("ANAF_REDIRECT_URI")
TOKEN_PIN = os.getenv("ANAF_TOKEN_PIN")
JAVA_PROJECT_PATH = os.path.dirname(os.path.abspath(__file__)) # Presupunem că totul e în același folder

# Validăm că toate variabilele necesare au fost încărcate
required_vars = [CLIENT_ID, CLIENT_SECRET, REDIRECT_URI, TOKEN_PIN]
if not all(required_vars):
    print("EROARE: Asigurați-vă că variabilele ANAF_CLIENT_ID, ANAF_CLIENT_SECRET, ANAF_REDIRECT_URI și ANAF_TOKEN_PIN sunt setate în fișierul .env.")
    exit()

# Creează o instanță a clientului
anaf = Anafgettoken(
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    redirect_uri=REDIRECT_URI,
    pin=TOKEN_PIN,
    java_class_path=JAVA_PROJECT_PATH
)

def update_env_file(access_token: str, refresh_token: str):
    """
    Actualizează variabilele ANAF_ACCESS_TOKEN și ANAF_REFRESH_TOKEN în fișierul .env.
    Creează fișierul .env dacă nu există.
    """
    env_file = find_dotenv()
    if not env_file:
        # Dacă nu există un fișier .env, îl creăm în directorul curent.
        env_file = os.path.join(os.getcwd(), '.env')
        print(f"Fișierul .env nu a fost găsit. Se creează unul nou: {env_file}")
        open(env_file, 'a').close()

    set_key(env_file, "ANAF_ACCESS_TOKEN", access_token)
    print(f"OK: 'ANAF_ACCESS_TOKEN' a fost salvat în fișierul '{os.path.basename(env_file)}'.")
    
    set_key(env_file, "ANAF_REFRESH_TOKEN", refresh_token)
    print(f"OK: 'ANAF_REFRESH_TOKEN' a fost salvat în fișierul '{os.path.basename(env_file)}'.")

    # Salvăm și credențialele, dacă nu există deja, pentru a fi folosite de alte scripturi (ex: refresh)
    set_key(env_file, "ANAF_CLIENT_ID", CLIENT_ID)
    set_key(env_file, "ANAF_CLIENT_SECRET", CLIENT_SECRET)
    set_key(env_file, "ANAF_REDIRECT_URI", REDIRECT_URI)
    set_key(env_file, "ANAF_TOKEN_PIN", TOKEN_PIN)

def get_auth_code_automatically(auth_link: str, redirect_uri_start: str) -> str | None:
    """
    Lansează un browser cu Playwright, așteaptă autentificarea utilizatorului
    și extrage automat parametrul 'code' din URL-ul de redirect.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=50)
        page = browser.new_page()
        try:
            print("--- Automatizare Browser ---")
            print("1. Se deschide fereastra de autentificare ANAF...")
            page.goto(auth_link, timeout=60000)

            print("\n>>> ACȚIUNE NECESARĂ <<<")
            print("Vă rugăm să vă autentificați în fereastra de browser deschisă folosind certificatul digital.")
            print("Scriptul va continua automat după finalizarea autentificării.")
            print("-" * 28)

            # Așteaptă până când URL-ul paginii începe cu URI-ul de redirect.
            # Timeout de 3 minute pentru a oferi timp suficient pentru autentificare.
            page.wait_for_url(f"{redirect_uri_start}**", timeout=180000)
            
            final_url = page.url
            print("2. Autentificare detectată. Se extrage codul de autorizare...")

            # Parsează URL-ul pentru a extrage parametrul 'code'
            parsed_url = urlparse(final_url)
            query_params = parse_qs(parsed_url.query)
            auth_code = query_params.get('code', [None])[0]

            if auth_code:
                print("3. Cod de autorizare extras cu succes. Se închide browser-ul.")
                return auth_code
            else:
                print("EROARE: Redirecționare detectată, dar parametrul 'code' lipsește din URL.")
                return None

        except PlaywrightTimeoutError:
            print("EROARE: Timpul pentru autentificare a expirat (3 minute).")
            return None
        finally:
            browser.close()

auth_link = anaf.get_authorization_link()
auth_code = get_auth_code_automatically(auth_link, REDIRECT_URI)

if auth_code:
    anaf.set_code(auth_code)
    try:
        print("\nSe încearcă obținerea token-ului...")
        token_data = anaf.get_token()
        print("SUCCES! Token obținut.")

        access_token = token_data.get('access_token')
        refresh_token = token_data.get('refresh_token')

        if access_token and refresh_token:
            update_env_file(access_token, refresh_token)
        else:
            print("\nEROARE: Răspunsul de la ANAF nu conține 'access_token' sau 'refresh_token'.")
            print("Răspuns primit:", json.dumps(token_data, indent=2))
    except (ValueError, RuntimeError) as e:
        print(f"\nEROARE: {e}")
else:
    print("\nProcesul de obținere a token-ului a fost anulat deoarece codul de autorizare nu a putut fi obținut.")
