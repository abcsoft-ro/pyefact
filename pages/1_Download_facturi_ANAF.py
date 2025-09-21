import streamlit as st
import pandas as pd
from sqlalchemy import text, bindparam, LargeBinary, select
from db_utils import get_db_engine
from anaf_utils import get_anaf_client, display_pkcs11_auth_sidebar
import base64, time, os, zipfile  # Pentru a codifica PDF-ul, timestamp, variabile de mediu și arhive ZIP
from datetime import datetime, timedelta # Pentru a lucra cu date
from dotenv import load_dotenv

load_dotenv() # Încarcă variabilele de mediu din fișierul .env

st.set_page_config(page_title="Download Facturi ANAF", layout="wide")

def _build_where_clause(tip: str = "", search_term: str = "") -> tuple[str, dict]:
    """
    Construiește clauza WHERE și dicționarul de parametri pentru interogări.
    Returnează un tuplu (where_clause_string, params_dict).
    """
    params = {}
    where_conditions = []

    if tip:
        where_conditions.append("tip = :tip")
        params["tip"] = tip

    if search_term:
        where_conditions.append("(IDFact LIKE :search_term OR id_descarcare LIKE :search_term)")
        params["search_term"] = f"%{search_term}%"

    where_clause = ""
    if where_conditions:
        where_clause = "WHERE " + " AND ".join(where_conditions)

    return where_clause, params

@st.cache_data(ttl=600)
def get_total_records(table_name: str, tip: str ="T", search_term: str = "") -> int:
    """Returnează numărul total de înregistrări dintr-un tabel, opțional filtrate."""
    engine = get_db_engine()
    where_clause, params = _build_where_clause(tip, search_term)
    query = text(f"SELECT COUNT(*) FROM {table_name} {where_clause}")
    with engine.connect() as connection:
        total_records = connection.execute(query, params).scalar()
    return total_records or 0

@st.cache_data(ttl=600)
def load_paginated_data(table_name: str, page_number: int, page_size: int, tip: str = "T", search_term: str = "") -> pd.DataFrame:
    """Încarcă o singură pagină de date, opțional filtrată, folosind OFFSET-FETCH."""
    engine = get_db_engine()
    where_clause, filter_params = _build_where_clause(tip, search_term)

    # Combinăm parametrii de paginare cu cei de filtrare
    params = {
        "offset": page_number * page_size,
        "page_size": page_size,
        **filter_params
    }

    # Query optimizat pentru paginare în SQL Server
    query = text(f"""
        SELECT Id, Data_creare, IDFact, IssueDate, DueDate, LegalMonetaryTotal, DocumentCurrencyCode, Tip, Den_furnizor, Den_beneficiar, id_solicitare, id_descarcare, subiectm, tipm, continutm,
               (CASE WHEN pdf IS NULL THEN 0 ELSE 1 END) AS is_read
        FROM {table_name}
        {where_clause}
        ORDER BY Data_creare DESC
        OFFSET :offset ROWS
        FETCH NEXT :page_size ROWS ONLY
    """)

    try:
        # Folosim parametrii pentru a preveni SQL Injection
        df = pd.read_sql(query, engine, params=params)
        return df
    except Exception as e:
        st.error(f"Nu am putut încărca datele pentru pagina {page_number + 1}.")
        st.error(e)
        return pd.DataFrame() # Returnează un DataFrame gol în caz de eroare

def sync_anaf_messages(cif, tip_filtru_anaf, only_count: bool = False) -> int:
    """
    Descarcă mesajele de la ANAF pentru un interval dat și le salvează în baza de date.
    Gestionează paginarea și evită duplicatele.
    """
    anaf_client = get_anaf_client()
    engine = get_db_engine()

    # --- Calculare interval de timp pentru interogare ANAF ---
    # Regula ANAF: intervalul nu poate depăși 60 de zile.
    
    # 1. Obținem data ultimei sincronizări din baza de date
    tip_filtru = {
    "P": "FACTURA PRIMITA",
    "T": "FACTURA TRIMISA",
    "R": "MESAJ",
    "E": "ERORI FACTURA"
    }
    with engine.connect() as connection:
        last_sync_date = connection.execute(
            text("SELECT MAX(data_creare) FROM tblmesaje WHERE tip = :tip_filtru_anaf"),
            {"tip_filtru_anaf": tip_filtru[tip_filtru_anaf]}
        ).scalar()

    # 2. Definim limita de 60 de zile în urmă față de momentul curent
    now_dt = datetime.now()
    sixty_days_ago = now_dt - timedelta(days=60)

    # 3. Stabilim data de început (start_time) conform regulilor
    if last_sync_date is None:
        # Dacă nu există mesaje, pornim de acum 60 de zile
        start_date_dt = sixty_days_ago
    elif last_sync_date < sixty_days_ago:
        # Dacă ultimul mesaj e mai vechi de 60 de zile, pornim de la limita maximă permisă
        start_date_dt = sixty_days_ago
    else:
        # Altfel, pornim de la data ultimului mesaj descărcat
        start_date_dt = last_sync_date

    start_time = int(start_date_dt.timestamp() * 1000)

    # Recalculăm end_time chiar înainte de a face apelurile pentru a fi cât mai precis
    # Folosim un buffer de siguranță pentru a evita erorile de sincronizare a ceasului.
    # Scădem 30 de secunde din timpul curent pentru a garanta că 'endTime' nu este în viitor
    # din perspectiva serverului ANAF, din cauza latenței rețelei sau a desincronizării minore a ceasurilor.
    safe_now_dt = datetime.now() - timedelta(seconds=30)
    end_time = int(safe_now_dt.timestamp() * 1000)

    page = 1
    total_pages = 1 # Inițializăm cu 1 pentru a intra în buclă
    new_messages_count = 0
    
    placeholder = st.empty() # Un container pentru a afișa statusul

    while page <= total_pages:
        #placeholder.info(f"Se descarcă pagina {page} din {total_pages}...")
        try:
            response = anaf_client.lista_mesaje(
                start_time=start_time, end_time=end_time, pagina=page, cif=cif, filtru=tip_filtru_anaf
            )
            #print(response) # Debug: afișăm răspunsul complet pentru a verifica structura
            if not response or 'mesaje' not in response:
                #st.warning(f"Pagina {page} nu a returnat mesaje. Oprire.")
                break

            messages = response.get('mesaje', [])
            total_pages = response.get('numar_total_pagini', page) # Actualizăm numărul total de pagini

            with engine.connect() as connection:
                with connection.begin(): # Pornim o tranzacție pentru întreaga pagină
                    for msg in messages:
                        id_descarcare = msg.get('id')
                        
                        # Verificăm dacă mesajul există deja în tblmesaje pentru a evita duplicatele
                        check_query = text("SELECT MesId FROM tblmesaje WHERE id = :id_descarcare")
                        if connection.execute(check_query, {"id_descarcare": id_descarcare}).fetchone():
                            continue # Trecem la următorul mesaj dacă există deja

                        # Parsăm data
                        data_creare_str = msg.get('data_creare')
                        data_creare_dt = datetime.strptime(data_creare_str, '%Y%m%d%H%M')
                        if only_count:
                            new_messages_count += 1
                            continue
                        # Inserăm mesajul nou în tabela tblmesaje
                        insert_query = text("""
                            INSERT INTO tblmesaje (data_creare, cif, id_solicitare, detalii, tip, id)
                            VALUES (:data_creare, :cif, :id_solicitare, :detalii, :tip, :id_descarcare)
                        """)
                        
                        # Verificăm și standardizăm tipul mesajului
                        tip_mesaj_anaf = msg.get('tip')
                        tip_final = "MESAJ" if tip_mesaj_anaf and tip_mesaj_anaf.startswith("MESAJ") else tip_mesaj_anaf
                        
                        connection.execute(insert_query, {
                            "data_creare": data_creare_dt,
                            "cif": msg.get('cif'),
                            "id_solicitare": msg.get('id_solicitare'),
                            "detalii": msg.get('detalii'),
                            "tip": tip_final,
                            "id_descarcare": id_descarcare
                        })
                        new_messages_count += 1
            page += 1
        except Exception as e:
            placeholder.error(f"Eroare la sincronizarea cu ANAF: {e}")
            return 0 # Returnăm 0 în caz de eroare, nu None
    
    placeholder.empty() # Curățăm mesajul de status
    return new_messages_count

def handle_filter_change():
    """Resetează paginarea și selecția la schimbarea filtrelor."""
    st.session_state.page_number = 0
    st.session_state.selected_id = None

DOWNLOAD_DIR = "xml_download"

# --- Interfața aplicației ---
# Folosim un selector CSS specific pentru a ținti butonul din a doua coloană.
# Acest lucru asigură că doar acest buton este afectat.
st.markdown("""
<style>
/* Reduce spațiul (padding) de deasupra conținutului paginii, inclusiv titlul */
div.block-container {
    padding-top: 1rem; /* Valoarea implicită este ~5rem */
}
</style>
""", unsafe_allow_html=True)
# --- Logica de paginare ---
nume_tabel = 'tblSPV' 
RECORDS_PER_PAGE = 10

# Inițializare session state pentru numărul paginii
if 'page_number' not in st.session_state:
    st.session_state.page_number = 0
# Inițializare session state pentru ID-ul selectat
if 'selected_id' not in st.session_state:
    st.session_state.selected_id = None
if 'action_type' not in st.session_state:
    st.session_state.action_type = None
if 'search_term' not in st.session_state:
    st.session_state.search_term = ""
if 'tip' not in st.session_state:
    st.session_state.tip = "P" # Valoare inițială: Facturi primite

st.title("📥 Download Facturi ANAF")

# Afișăm UI-ul pentru PIN dacă este necesar și oprim execuția paginii
# până când PIN-ul este introdus.
if display_pkcs11_auth_sidebar():
    st.stop()

col_info, col_dl = st.columns([3, 1])

with col_info:
    message_number=sync_anaf_messages(os.getenv("ANAF_CIF", ""), st.session_state.tip, only_count=True)
    st.info(f"Există {message_number} mesaje noi disponibile pe serverul ANAF.")  

with col_dl:
    if st.button("🚀 Sincronizare ANAF", help="Apasă pentru a descărca și procesa mesajele de la ANAF", use_container_width=True):
        cif = os.getenv("ANAF_CIF", "")
        st.info(f"CIF-ul implicit este: {cif if cif else 'nu este setat'}")

        with st.spinner("Pasul 1/2: Se descarcă lista de mesaje noi..."):
            new_count = sync_anaf_messages(cif, st.session_state.tip)
        st.success(f"✔️ S-au găsit {new_count} mesaje noi.")

        engine = get_db_engine()
        with engine.connect() as conn:
            total_to_process_query = text("SELECT COUNT(*) FROM tblmesaje WHERE preluat = 0 AND tip LIKE :tip")
            total_to_process = conn.execute(total_to_process_query, {"tip": f"%{st.session_state.tip}%"}).scalar() or 0

        if total_to_process > 0:
            st.info(f"Pasul 2/2: Se vor procesa {total_to_process} mesaje...")
            progress_bar = st.progress(0)
            status_text = st.empty()

            def update_progress(processed_count, message):
                progress = processed_count / total_to_process if total_to_process > 0 else 0
                progress_bar.progress(min(progress, 1.0))
                status_text.info(f"Procesat {processed_count}/{total_to_process}: {message}")

            try:
                anaf_client = get_anaf_client()
                db_engine = get_db_engine()
                report = anaf_client.process_unprocessed_messages(
                    db_engine=db_engine, username='web_user', tip=st.session_state.tip, progress_callback=update_progress
                )

                progress_bar.empty()
                status_text.empty()

                if report["errors"] > 0:
                    st.warning(f"{report['processed']} mesaje procesate cu succes.")
                    st.error(f"{report['errors']} mesaje au eșuat la procesare:")
                    for error_detail in report["details"]: st.code(error_detail, language=None)
                elif report["processed"] > 0:
                    st.success(f"✔️ Procesare finalizată! {report['processed']} mesaje au fost procesate cu succes.")
                else:
                    st.info("Nu au fost găsite mesaje noi sau neprocesate în baza de date.")
            except Exception as e:
                progress_bar.empty(); status_text.empty()
                st.error(f"A apărut o eroare critică în timpul procesării: {e}")
        else: st.info("Nu există mesaje noi sau neprocesate care să necesite procesare.")
        st.cache_data.clear(); st.info("Se reîmprospătează tabelul..."); time.sleep(2); st.rerun()

# --- Controale de filtrare în coloane ---
tip_options = ["P", "T", "R", "E"]
tip_labels = {
    "P": "Facturi primite",
    "T": "Facturi trimise",
    "R": "Mesaje",
    "E": "Erori"
}
# Calculăm indexul opțiunii curente pentru a-l pasa widget-ului
current_tip_index = tip_options.index(st.session_state.tip) if st.session_state.tip in tip_options else 0

# Afișăm widget-ul și citim valoarea selectată
selected_tip = st.radio(
    "Afișează:",
    options=tip_options,
    format_func=lambda x: tip_labels.get(x, x),
    horizontal=True,
    index=current_tip_index
)
# Verificăm manual dacă selecția s-a schimbat și forțăm un rerun
if selected_tip != st.session_state.tip:
    st.session_state.tip = selected_tip
    handle_filter_change()
    st.rerun()

# --- Casetă de căutare ---
# Am refactorizat și caseta de căutare pentru a folosi același model
st.text_input(
    "Caută după ID Factură (serie și număr), ID descarcare:",
    placeholder="ex: ABC 123",
    key='search_term', # Legăm direct starea de session_state.search_term
    on_change=handle_filter_change # Folosim aceeași funcție de callback
)

# Container pentru a afișa link-ul PDF, mutat aici pentru o vizibilitate mai bună
pdf_link_container = st.empty()
if st.session_state.get('pdf_success_message'):
    pdf_link_container.success(st.session_state.get('pdf_success_message', ''), icon="📄")

#st.divider()

# Obține numărul total de înregistrări pentru a calcula numărul de pagini
total_records = get_total_records(nume_tabel, tip=st.session_state.tip, search_term=st.session_state.search_term)

if total_records > 0:
    total_pages = (total_records // RECORDS_PER_PAGE) + (1 if total_records % RECORDS_PER_PAGE > 0 else 0)
    col1, col2, col3 = st.columns([2, 3, 2])

    with col1:
        if st.button("⬅️ Pagina Anterioară", width='stretch', disabled=(st.session_state.page_number < 1)):
            st.session_state.page_number -= 1
            st.session_state.selected_id = None # Resetăm selecția
            st.rerun()

    with col2:
        st.markdown(f"<p style='text-align: center; font-weight: bold;'>Pagina {st.session_state.page_number + 1} din {total_pages} ({total_records} înregistrări)</p>", unsafe_allow_html=True)

    with col3:
        if st.button("Pagina Următoare ➡️", width='stretch', disabled=(st.session_state.page_number >= total_pages - 1)):
            st.session_state.page_number += 1
            st.session_state.selected_id = None # Resetăm selecția
            st.rerun()


    data_df = load_paginated_data(nume_tabel, st.session_state.page_number, RECORDS_PER_PAGE, st.session_state.tip, search_term=st.session_state.search_term)

    if not data_df.empty:
        # --- Afișare condiționată a tabelului în funcție de tip ---
        if st.session_state.tip in ["P", "T"]:
            # --- Afișare Header Tabel Custom pentru Facturi (P/T) ---
            header_cols = st.columns((1, 2, 2, 2, 2, 4, 2, 1, 2, 3)) # Adăugat coloană pentru status
            header_beneficiar = "Furnizor" if st.session_state.tip == "P" else "Beneficiar"
            fields = ["", "Data creare spv", "ID Factură", "Data Factura", "Data Scadenta", header_beneficiar, "Total de plata", "Moneda", "ID Descarcare", "Acțiune"]
            for col, field_name in zip(header_cols, fields):
                if field_name == "Total de plata":
                    # Aliniem la dreapta și îngroșăm textul, similar cu conținutul coloanei
                    col.markdown(f"<div style='text-align: right; font-weight: bold;'>{field_name}</div>", unsafe_allow_html=True)
                elif field_name: # Nu afișăm titlu pentru coloana de status
                    col.write(f"**{field_name}**")

            # --- Afișare Linii Tabel cu Butoane pentru Facturi (P/T) ---
            for index, row in data_df.iterrows():
                row_cols = st.columns((1, 2, 2, 2, 2, 4, 2, 1, 2, 3)) # Adăugat coloană pentru status

                # Coloana 0: Iconiță status (citit/necitit)
                status_icon = "📨" if row['is_read'] else "✉️"
                row_cols[0].markdown(f"<p style='text-align: center; font-size: 1.2em;' title='{'Citit' if row['is_read'] else 'Necitit'}'>{status_icon}</p>", unsafe_allow_html=True)

                # Restul coloanelor
                row_cols[1].write(row['Data_creare'].strftime('%Y-%m-%d %H:%M:%S') if pd.notna(row['Data_creare']) else 'N/A')
                row_cols[2].write(row['IDFact'])
                row_cols[3].write(row['IssueDate'].strftime('%Y-%m-%d') if pd.notna(row['IssueDate']) else 'N/A')
                row_cols[4].write(row['DueDate'].strftime('%Y-%m-%d') if pd.notna(row['DueDate']) else 'N/A')
                row_cols[5].write(row['Den_beneficiar'] if st.session_state.tip == "T" else row['Den_furnizor'])
                row_cols[6].markdown(f"<div style='text-align: right; font-weight: bold; color: black'>{row['LegalMonetaryTotal']:,.2f}</div>", unsafe_allow_html=True)
                row_cols[7].write(row['DocumentCurrencyCode'])
                row_cols[8].write(row['id_descarcare'])
                
                # Coloana de acțiuni cu 3 butoane
                with row_cols[9]:
                    action_cols = st.columns(3, gap="small")
                    if action_cols[0].button("PDF", key=f"pdf_{row['Id']}", help="Vizualizează PDF"):
                        st.session_state.selected_id = row['Id']
                        st.session_state.action_type = 'pdf'
                        st.rerun() # Forțăm un rerun pentru a actualiza iconița imediat
                    if action_cols[1].button("XML", key=f"xml_{row['Id']}", help="Descarcă XML"):
                        st.session_state.selected_id = row['Id']
                        st.session_state.action_type = 'xml'
                        st.rerun()
                    if action_cols[2].button("ZIP", key=f"zip_{row['Id']}", help="Descarcă ZIP"):
                        st.session_state.selected_id = row['Id']
                        st.session_state.action_type = 'zip'

        elif st.session_state.tip in ["M", "E"]:
            # --- Afișare Header Tabel Custom pentru Mesaje/Erori (M/E) ---
            header_cols = st.columns((2, 3, 2, 5))
            fields = ["Data creare spv", "Subiect", "Tip Mesaj", "Continut"]
            for col, field_name in zip(header_cols, fields):
                col.write(f"**{field_name}**")

            # --- Afișare Linii Tabel pentru Mesaje/Erori (M/E) ---
            for index, row in data_df.iterrows():
                row_cols = st.columns((2, 3, 2, 5))
                row_cols[0].write(row['Data_creare'].strftime('%Y-%m-%d %H:%M:%S') if pd.notna(row['Data_creare']) else 'N/A')
                row_cols[1].write(row['subiectm'])
                row_cols[2].write(row['tipm'])
                row_cols[3].write(row['continutm'])

    else:
        st.warning("Nu s-au putut afișa datele pentru această pagină.")

    # --- Secțiunea de procesare acțiuni (PDF, XML, ZIP) ---
    # Această secțiune se afișează doar dacă un ID a fost selectat
    if st.session_state.get('selected_id'):
        action = st.session_state.get('action_type')
        selected_id = st.session_state.selected_id

        # Flag pentru a forța o reîncărcare a paginii și a actualiza iconița de status
        # de la necitit la citit, după ce PDF-ul a fost vizualizat.
        rerun_for_ui_update = False

        if action == 'pdf':
            pdf_content = None
            # Inițializăm variabilele pentru numele fișierului
            id_factura = None
            issue_date = None
            with st.spinner(f"Se pregătește PDF-ul pentru factura cu ID intern: {selected_id}..."):
                try:
                    db_engine = get_db_engine()
                    with db_engine.begin() as connection:
                        # Modificăm query-ul pentru a prelua și IDFact și IssueDate
                        select_query = text("SELECT pdf, f_xml, IDFact, IssueDate FROM tblSPV WHERE Id = :id")
                        result = connection.execute(select_query, {"id": selected_id}).fetchone()
                        
                        if result and result.pdf:
                            pdf_content = result.pdf
                        elif result and result.f_xml:
                            anaf_client = get_anaf_client()
                            xml_content = result.f_xml
                            pdf_content = anaf_client.xml_to_pdf(xml_content=xml_content)
                            if pdf_content:
                                update_query = text("UPDATE tblSPV SET pdf = :pdf WHERE Id = :id").bindparams(bindparam('pdf', type_=LargeBinary))
                                connection.execute(update_query, {"pdf": pdf_content, "id": selected_id})
                        else:
                            st.error(f"Nu s-a găsit niciun fișier XML pentru a genera PDF-ul pentru ID {selected_id}.")
                        
                        # Salvăm valorile necesare pentru numele fișierului, indiferent de sursa PDF-ului
                        if result:
                            id_factura = result.IDFact
                            issue_date = result.IssueDate
                except Exception as e:
                    st.error(f"A apărut o eroare la generarea PDF-ului: {e}")
            
            if pdf_content:
                base64_pdf = base64.b64encode(pdf_content).decode('utf-8')
                data_uri = f"data:application/pdf;base64,{base64_pdf}"
                # Construim noul nume de fișier
                if id_factura and issue_date:
                    date_str = issue_date.strftime('%Y-%m-%d')
                    # Înlocuim caracterele invalide din IDFactura (ex: /) cu _
                    safe_id_factura = str(id_factura).replace('/', '_').replace('\\', '_')
                    file_name = f"factura_{safe_id_factura}_{date_str}.pdf"
                else:
                    file_name = f"factura_{selected_id}.pdf" # Fallback la vechiul format
                # Creăm un mesaj de succes care conține un link de descărcare, similar cu cel de la XML
                success_message = f'PDF-ul a fost generat. [Click aici pentru a deschide/salva **{file_name}**]({data_uri})'
                st.session_state['pdf_success_message'] = success_message
                
                st.cache_data.clear()
                rerun_for_ui_update = True

        elif action in ['xml', 'zip']:
            with st.spinner(f"Se pregătește fișierul..."):
                try:
                    db_engine = get_db_engine()
                    with db_engine.connect() as connection:
                        query = text("SELECT f_xml, s_xml, id_descarcare FROM tblSPV WHERE Id = :id")
                        result = connection.execute(query, {"id": selected_id}).fetchone()

                    if not result or not result.id_descarcare:
                        st.error(f"Nu s-au găsit datele necesare (id_descarcare) pentru ID {selected_id}.")
                    else:
                        # Asigură existența directorului de descărcări
                        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
                        file_basename = result.id_descarcare

                        if action == 'xml':
                            if not result.f_xml:
                                st.error(f"Nu există conținut XML (f_xml) pentru ID {selected_id}.")
                            else:
                                file_path = os.path.join(DOWNLOAD_DIR, f"{file_basename}.xml")
                                with open(file_path, "w", encoding="utf-8") as f:
                                    f.write(result.f_xml)
                                st.success(f"Fișierul XML a fost generat cu succes în: `{file_path}`")

                        elif action == 'zip':
                            if not result.f_xml or not result.s_xml:
                                st.error(f"Lipsesc datele necesare (f_xml sau s_xml) pentru a crea arhiva ZIP pentru ID {selected_id}.")
                            else:
                                zip_path = os.path.join(DOWNLOAD_DIR, f"{file_basename}.zip")
                                with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                                    zipf.writestr("factura.xml", result.f_xml)
                                    zipf.writestr("semnatura.xml", result.s_xml)
                                
                                st.success(f"Arhiva ZIP a fost generată cu succes în: `{zip_path}`")

                except Exception as e:
                    st.error(f"A apărut o eroare la crearea fișierului: {e}")

        # Resetăm starea pentru a nu mai rula acest bloc la următoarea interacțiune
        if action in ['xml', 'zip']:
            st.session_state.selected_id = None
            st.session_state.action_type = None

        # Dacă este necesar, forțăm o re-execuție a scriptului pentru a afișa starea actualizată
        if rerun_for_ui_update and action == 'pdf':
            # Resetăm starea doar înainte de rerun, pentru a permite afișarea link-ului
            st.session_state.selected_id = None
            st.rerun()

elif st.session_state.search_term:
    st.warning(f"Nu s-au găsit înregistrări care să corespundă termenului de căutare: '{st.session_state.search_term}'")
else:
    st.warning(f"Tabelul `{nume_tabel}` nu conține nicio înregistrare.")
