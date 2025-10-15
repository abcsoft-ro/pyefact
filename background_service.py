import asyncio
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine

# Importăm funcțiile necesare din anaf_api și anaf_utils
from anaf_api import check_invoice_statuses_periodically, ApiANAF

def run_async_service():
    """
    Punctul de intrare pentru procesul din fundal.
    Acesta își configurează propriul mediu (conexiune la DB, token)
    și pornește bucla asincronă de verificare.
    """
    # Este important să încărcăm variabilele de mediu din nou,
    # deoarece acest cod rulează într-un proces complet separat.
    load_dotenv()
    
    print("--- Procesul de fundal pentru verificarea statusului a pornit ---")
    try:
        # Creăm un nou DB engine special pentru acest proces
        connection_uri = os.getenv("DATABASE_CONNECTION_URI")
        if not connection_uri:
            print("❌ Eroare în serviciul de fundal: Variabila 'DATABASE_CONNECTION_URI' nu a fost găsită în fișierul .env.")
            return
        db_engine = create_engine(connection_uri)

        # --- NOU: Inițializare flexibilă a clientului ANAF ---
        # Serviciul de fundal va folosi metoda de autentificare configurată în .env
        # (OAuth, certificat sau PKCS#11).
        pkcs11_lib = os.getenv("PKCS11_LIB_PATH")
        pkcs11_pin = os.getenv("PKCS11_PIN") # PIN-ul trebuie să fie în .env pentru serviciu
        cert_path = os.getenv("CERT_PATH")
        key_path = os.getenv("KEY_PATH")
        access_token = os.getenv("ANAF_ACCESS_TOKEN")

        try:
            anaf_client = ApiANAF(
                access_token=access_token,
                cert_path=cert_path,
                key_path=key_path,
                pkcs11_lib=pkcs11_lib,
                pkcs11_pin=pkcs11_pin
            )
        except ValueError as e:
            print(f"❌ Eroare în serviciul de fundal: Nu s-a putut inițializa clientul ANAF. Verificați configurația din .env. Detalii: {e}")
            return

        # Rulăm bucla infinită asincronă
        asyncio.run(check_invoice_statuses_periodically(db_engine=db_engine, anaf_client=anaf_client))
    except Exception as e:
        # Înregistrăm orice eroare critică ce ar putea opri serviciul
        print(f"🔥 Serviciul de fundal s-a oprit cu o eroare: {e}")