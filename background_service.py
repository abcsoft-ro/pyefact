import asyncio
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine

from anaf_api import check_invoice_statuses_periodically, ApiANAF
from db_utils import create_tables_if_not_exist


def run_async_service():
    """
    Punctul de intrare pentru procesul din fundal.
    Configurare proprie (DB, token) și bucla asincronă de verificare.
    """
    load_dotenv()

    print("--- Procesul de fundal pentru verificarea statusului a pornit ---")
    try:
        connection_uri = os.getenv("DATABASE_CONNECTION_URI")
        if not connection_uri:
            print("❌ Eroare: 'DATABASE_CONNECTION_URI' nu a fost găsită în .env.")
            return
        db_engine = create_engine(connection_uri)

        create_tables_if_not_exist(db_engine)

        access_token = os.getenv("ANAF_ACCESS_TOKEN")

        try:
            anaf_client = ApiANAF(access_token=access_token)
        except ValueError as e:
            print(f"❌ Eroare: Nu s-a putut inițializa clientul ANAF. Detalii: {e}")
            return

        asyncio.run(check_invoice_statuses_periodically(db_engine=db_engine, anaf_client=anaf_client))
    except Exception as e:
        print(f"🔥 Serviciul de fundal s-a oprit cu o eroare: {e}")
