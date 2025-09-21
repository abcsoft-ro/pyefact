import json
import time
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from dotenv import set_key, find_dotenv
import os

# --- Configurare ---
URL_TOKEN = "https://efactura.abcsoft.ro/admin/get_anaf_token.php?action=new"

def update_env_file(access_token, refresh_token):
    """
    Actualizează variabilele ANAF_ACCESS_TOKEN și ANAF_REFRESH_TOKEN în fișierul .env.
    """
    env_file = find_dotenv()
    if not env_file:
        # Dacă nu există un fișier .env, îl creăm.
        env_file = os.path.join(os.getcwd(), '.env')
        print(f"Fisierul .env nu a fost gasit. Se creeaza unul nou: {env_file}")
        open(env_file, 'a').close()

    set_key(env_file, "ANAF_ACCESS_TOKEN", access_token)
    print(f"OK: 'ANAF_ACCESS_TOKEN' a fost actualizat in fisierul '{env_file}'.")
    
    set_key(env_file, "ANAF_REFRESH_TOKEN", refresh_token)
    print(f"OK: 'ANAF_REFRESH_TOKEN' a fost actualizat in fisierul '{env_file}'.")

def get_new_anaf_token():
    """
    Folosește Playwright pentru a deschide o pagină web, a permite utilizatorului
    să se autentifice și a extrage noile token-uri ANAF.
    Token-urile extrase sunt apoi salvate în fișierul .env.
    """
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=False, slow_mo=50)
            page = browser.new_page()
            
            print(f"Navighez catre: {URL_TOKEN}")
            # Mărim timeout-ul pentru navigare la 60 de secunde, deoarece pagina de login se poate încărca lent.
            page.goto(URL_TOKEN, timeout=60000)

            print("\n" + "="*80)
            print(">>> ACTIUNE NECESARA <<<")
            print("O fereastra de browser a fost deschisa.")
            print("Va rugam sa va autentificati in portalul ABC Soft.")
            print("Scriptul va astepta automat aparitia token-ului dupa autentificare.")
            print("="*80 + "\n")

            # Așteptăm apariția elementului care conține token-ul.
            # Selectorul CSS 'input#token[value]' așteaptă un input cu id='token' care are atributul 'value' setat.
            # Timeout-ul este setat la 5 minute (300,000 ms) pentru a oferi timp suficient pentru login.
            try:
                # Așteptăm ca input-ul #token să aibă o valoare.
                # Folosim o funcție JavaScript pentru a ne asigura că elementul există ȘI are o valoare non-goală.
                # Acest lucru previne erorile în care scriptul citește valoarea înainte ca aceasta să fie populată.
                page.wait_for_function(
                    "document.querySelector('input#token') && document.querySelector('input#token').value !== ''",
                    timeout=180000
                )
            except PlaywrightTimeoutError:
                print("EROARE: Timeout: Nu s-a detectat niciun token in 3 minute. Se inchide.")
                return

            print("OK: Elementele cu token-uri au fost detectate. Se extrag datele...")
            
            # Extragem valorile din atributele 'value' ale celor două input-uri.
            access_token = page.locator("input#token").get_attribute("value")
            refresh_token = page.locator("input#refreshtoken").get_attribute("value")

            if not access_token or not refresh_token:
                print("EROARE: Nu am putut extrage 'access_token' sau 'refresh_token' din input-urile ascunse.")
                print(f"Date primite: access_token='{access_token}', refresh_token='{refresh_token}'")
                return

            update_env_file(access_token, refresh_token)
            
            print("\n>> Proces finalizat cu succes! Puteti inchide fereastra browser-ului.")
            time.sleep(10) # Asteptam putin pentru ca utilizatorul sa vada mesajul
        finally:
            if 'browser' in locals() and browser.is_connected():
                browser.close()

if __name__ == "__main__":
    get_new_anaf_token()