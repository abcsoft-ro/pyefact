import asyncio
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine

# Importăm funcția de verificare din anaf_api
from anaf_api import check_invoice_statuses_periodically

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

        # Obținem token-ul de acces din variabilele de mediu
        access_token = os.getenv("ANAF_ACCESS_TOKEN")
        if not access_token:
            print("❌ Eroare în serviciul de fundal: ANAF_ACCESS_TOKEN nu a fost găsit.")
            return

        # Rulăm bucla infinită asincronă
        asyncio.run(check_invoice_statuses_periodically(db_engine=db_engine, access_token=access_token))
    except Exception as e:
        # Înregistrăm orice eroare critică ce ar putea opri serviciul
        print(f"🔥 Serviciul de fundal s-a oprit cu o eroare: {e}")