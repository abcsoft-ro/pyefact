import streamlit as st
import pandas as pd
from sqlalchemy import text
import xml.etree.ElementTree as ET
import os, base64
from datetime import datetime

from db_utils import get_db_engine
from anaf_utils import get_anaf_client
from xml_processor import process_xml_files_from_upload_folder

st.set_page_config(layout="wide", page_title="Încărcare Facturi XML")

st.title("📤 Încărcare și Procesare Facturi XML")

def _fmt_date(val, fmt='%Y-%m-%d %H:%M:%S'):
    if pd.isna(val):
        return 'N/A'
    if isinstance(val, datetime):
        return val.strftime(fmt)
    if isinstance(val, str):
        try:
            return datetime.fromisoformat(val).strftime(fmt)
        except ValueError:
            try:
                return datetime.strptime(val, '%Y-%m-%d %H:%M:%S').strftime(fmt)
            except ValueError:
                return val
    return str(val)


# --- Inițializare și autentificare ---
try:
    db_engine = get_db_engine()
    anaf_client = get_anaf_client() # Folosim funcția centralizată

    # Citim CIF-ul din .env pentru a-l folosi la trimitere
    anaf_cif = os.getenv("ANAF_CIF")
    if not anaf_cif:
        st.error("CIF-ul ANAF (`ANAF_CIF`) nu este configurat. Verificați fișierul `.env`.")
        st.stop()
except Exception as e:
    st.error(f"Eroare la inițializare: {e}")
    st.stop()

# --- Inițializare stare sesiune ---
if 'processing_log' not in st.session_state:
    st.session_state.processing_log = []
if 'auto_scan_done' not in st.session_state:
    st.session_state.auto_scan_done = False
if 'delete_id' not in st.session_state:
    st.session_state.delete_id = None
if 'selected_id' not in st.session_state:
    st.session_state.selected_id = None
if 'action_type' not in st.session_state:
    st.session_state.action_type = None

# --- Procesare automată la încărcarea paginii (DOAR PASUL 1) ---
if not st.session_state.auto_scan_done:
    st.session_state.auto_scan_done = True # Setăm flag-ul pentru a rula o singură dată per sesiune
    st.session_state.processing_log = [] # Resetăm log-ul pentru această rulare automată
    
    st.session_state.processing_log.append("--- ÎNCEPUT PROCESARE AUTOMATĂ: Scanare fișiere XML ---")
    progress_bar_scan = st.progress(0, text="Se inițializează scanarea automată a fișierelor...")
    
    def update_scan_progress(progress, message):
        progress_bar_scan.progress(progress, text=f"Scanare: {message}")
        
    report_scan = process_xml_files_from_upload_folder(db_engine, anaf_client, update_scan_progress)
    
    # Afișăm un mesaj temporar despre rezultatul scanării
    if report_scan['processed'] > 0 or report_scan['errors'] > 0:
        if report_scan['errors'] > 0:
            st.warning(f"Scanare fișiere finalizată! Rezumat: {report_scan['processed']} succes, {report_scan['errors']} erori.")
        else:
            st.success(f"Scanare fișiere finalizată! Rezumat: {report_scan['processed']} succes, {report_scan['errors']} erori.")
    
    st.session_state.processing_log.extend(report_scan['details'])
    st.session_state.processing_log.append("--- SFÂRȘIT PROCESARE AUTOMATĂ ---\n")
    
    # Reîncărcăm pagina pentru a curăța mesajele de status și a actualiza tabelul
    st.rerun()

# --- Secțiunea de procesare manuală (DOAR PASUL 2) ---
st.header("Trimitere Facturi către ANAF")

# Preluăm calea directorului de upload pentru a o afișa în mesajul informativ
upload_folder_path = os.getenv("XML_UPLOAD_FOLDER_PATH")

if upload_folder_path:
    st.info(
        f"Scanarea directorului configurat (`{upload_folder_path}`) se face automat la încărcarea paginii.\n"
        "Apăsați butonul de mai jos pentru a trimite facturile pregătite către serverul ANAF."
    )
else:
    st.warning(
        "**Atenție:** Directorul pentru upload XML (`XML_UPLOAD_FOLDER_PATH`) nu este configurat în fișierul `.env`.\nScanarea automată nu va funcționa. Vă rugăm configurați calea în pagina de Setări."
    )

if st.button("🚀 Trimite facturile către ANAF", type="primary"):
    # Resetăm log-ul pentru acțiunea de trimitere
    st.session_state.processing_log = []
    
    st.session_state.processing_log.append("--- ÎNCEPUT TRIMITERE: Trimitere facturi către ANAF ---")
    progress_bar = st.progress(0, text="Se pregătește trimiterea...")

    try:
        with db_engine.connect() as connection:
            query = text("""
                SELECT Id, fxml
                FROM tblFacturi
                WHERE (ExecutionStatus <> 0 OR ExecutionStatus IS NULL) AND fxml IS NOT NULL AND LENGTH(fxml) > 0
                ORDER BY Id
                LIMIT 100
            """)
            invoices_to_send = connection.execute(query).fetchall()

            if not invoices_to_send:
                st.session_state.processing_log.append("✔️ Nu există facturi noi de trimis.")
                progress_bar.progress(100, "Procesare finalizată.")
            else:
                total_invoices = len(invoices_to_send)
                st.session_state.processing_log.append(f"ℹ️ S-au găsit {total_invoices} facturi pentru trimitere.")
                
                for i, invoice in enumerate(invoices_to_send):
                    progress = (i + 1) / total_invoices
                    progress_bar.progress(progress, text=f"Se trimite factura Id: {invoice.Id} ({i+1}/{total_invoices})...")
                    
                    try:
                        response_content = anaf_client.send_invoice(xml_content=invoice.fxml, cif=anaf_cif)
                        
                        root = ET.fromstring(response_content)
                        header = root
                        
                        date_response_str = header.attrib.get('dateResponse')
                        execution_status = header.attrib.get('ExecutionStatus')
                        index_incarcare = header.attrib.get('index_incarcare')
                        error_message = None
                        
                        date_response_obj = None
                        if date_response_str:
                            try:
                                date_response_obj = datetime.strptime(date_response_str, '%Y%m%d%H%M')
                            except ValueError:
                                st.session_state.processing_log.append(f"⚠️ Avertisment pentru factura Id: {invoice.Id} - format dată invalid: {date_response_str}")
                                date_response_obj = None

                        errors_node = header.find('{*}Errors')
                        if errors_node is not None:
                            error_message = errors_node.attrib.get('errorMessage')

                        update_query = text("""
                            UPDATE tblFacturi 
                            SET SolicitareID = :index, IndexIncarcare = :index, DateResponse = :date_resp, 
                                ExecutionStatus = :status, ErrorMessage = :error_msg, StareDocument = 'Trimis, se asteapta validarea anaf' 
                            WHERE Id = :id
                        """)
                        connection.execute(update_query, {"index": index_incarcare, "date_resp": date_response_obj, "status": execution_status, "error_msg": error_message, "id": invoice.Id})
                        connection.commit()
                        st.session_state.processing_log.append(f"✔️ Factura Id: {invoice.Id} trimisă. Status: {execution_status}, Index: {index_incarcare}")

                    except Exception as e:
                        st.session_state.processing_log.append(f"❌ Eroare la trimiterea facturii Id: {invoice.Id} - {e}")
    except Exception as e:
        st.session_state.processing_log.append(f"🔥 Eroare generală în procesul de trimitere: {e}")

    st.rerun()

# --- Afișare după procesare ---

# Afișează log-ul combinat
if 'processing_log' in st.session_state and st.session_state.processing_log:
    with st.expander("Jurnal detaliat procesare și trimitere", expanded=True):
        st.code("\n".join(st.session_state.processing_log), language="log")

# --- Secțiunea de vizualizare tabel ---
st.header("Vizualizare facturi")

# Container pentru a afișa link-ul PDF, similar cu pagina de download
pdf_link_container = st.empty()
if st.session_state.get('pdf_success_message'):
    pdf_link_container.success(st.session_state.get('pdf_success_message', ''), icon="📄")

# Inițializare stare paginare
if 'page_number' not in st.session_state:
    st.session_state.page_number = 0

# --- Logică ștergere ---
if st.session_state.delete_id is not None:
    try:
        with db_engine.connect() as connection:
            with connection.begin(): # Folosim o tranzacție
                delete_query = text("""
                    DELETE FROM tblFacturi 
                    WHERE Id = :id AND (IndexIncarcare IS NULL OR IndexIncarcare = 0)
                """)
                connection.execute(delete_query, {"id": st.session_state.delete_id})
        st.success(f"Factura cu ID intern {st.session_state.delete_id} a fost ștearsă cu succes.")
    except Exception as e:
        st.error(f"A apărut o eroare la ștergerea facturii: {e}")
    finally:
        st.session_state.delete_id = None # Resetăm starea
        st.rerun()

def style_stare_document(val):
    """Colorează textul în funcție de valoare pentru coloana StareDocument."""
    val_lower = str(val).lower()
    if val_lower == 'ok':
        color = 'green'
    elif val_lower == 'nok':
        color = 'red'
    else:
        color = 'black' # Culoare implicită
    return f'color: {color}'

try:
    with db_engine.connect() as connection:
        # Selectăm coloanele relevante pentru afișare
        query = text("""
            SELECT Id, IndexIncarcare, DateResponse, ExecutionStatus,IDdescarcare, ErrorMessage, IDFactura, IssuDate, Firma, cif, Beneficiar, Valoare, StareDocument, Data 
            FROM tblFacturi
            ORDER BY Data DESC
        """)
        df = pd.read_sql(query, connection)
        
        if df.empty:
            st.warning("Nicio factură procesată nu a fost găsită în baza de date.")
        else:
            # --- Logica de paginare ---
            ITEMS_PER_PAGE = 10
            total_items = len(df)
            total_pages = max(1, (total_items - 1) // ITEMS_PER_PAGE + 1)

            # Asigură-te că numărul paginii este valid
            if st.session_state.page_number >= total_pages:
                st.session_state.page_number = total_pages - 1
            if st.session_state.page_number < 0:
                st.session_state.page_number = 0

            start_idx = st.session_state.page_number * ITEMS_PER_PAGE
            end_idx = start_idx + ITEMS_PER_PAGE
            
            df_paginated = df.iloc[start_idx:end_idx]

            # --- Header tabel custom ---
            header_cols = st.columns((2, 2, 3, 2, 2, 2, 3, 1))
            fields = ["ID Factură", "Data Facturii", "Beneficiar", "Valoare", "Stare Document", "Index Încărcare", "Mesaj Eroare", "Acțiuni"]
            for col, field_name in zip(header_cols, fields):
                if field_name == "Valoare":
                    col.markdown(f"<div style='text-align: right;'><strong>{field_name}</strong></div>", unsafe_allow_html=True)
                else:
                    col.markdown(f"**{field_name}**")

            st.divider()

            # --- Linii tabel custom ---
            for index, row in df_paginated.iterrows():
                row_cols = st.columns((2, 2, 3, 2, 2, 2, 3, 1))
                row_cols[0].write(row['IDFactura'])
                row_cols[1].write(_fmt_date(row['IssuDate'], '%d.%m.%Y'))
                row_cols[2].write(row['Beneficiar'])
                row_cols[3].markdown(f"<div style='text-align: right;'>{float(row['Valoare']):.2f} RON</div>", unsafe_allow_html=True)
                
                # Aplicăm stilul pentru StareDocument
                stare_doc = row['StareDocument']
                stare_color = style_stare_document(stare_doc).split(': ')[1]
                row_cols[4].markdown(f"<span style='color:{stare_color}'>{stare_doc if pd.notna(stare_doc) else 'N/A'}</span>", unsafe_allow_html=True)
                
                idx = int(row['IndexIncarcare']) if pd.notna(row['IndexIncarcare']) and row['IndexIncarcare'] != '' else 0
                row_cols[5].write(str(idx) if idx != 0 else "")
                row_cols[6].write(row['ErrorMessage'])

                # Coloana de acțiuni
                with row_cols[7]:
                    action_cols = st.columns(2) # Două coloane pentru butoane
                    # Butonul de ștergere este vizibil doar dacă factura nu a fost trimisă
                    if pd.isna(row['IndexIncarcare']) or idx == 0:
                        if action_cols[0].button("🗑️", key=f"delete_{row['Id']}", help="Șterge această înregistrare"):
                            st.session_state.delete_id = row['Id']
                            st.rerun()
                    # Butonul PDF este vizibil doar dacă starea este 'ok'
                    if row['StareDocument'] == 'ok':
                        if action_cols[1].button("📄", key=f"pdf_{row['Id']}", help="Generează și descarcă PDF"):
                            st.session_state.selected_id = row['Id']
                            st.session_state.action_type = 'pdf'
                            st.rerun()

            # --- Controale de navigare ---
            st.divider()
            col1, col2, col3 = st.columns([2, 3, 2])

            with col1:
                if st.button("⬅️ Pagina anterioară", width="stretch", disabled=(st.session_state.page_number == 0)):
                    st.session_state.page_number -= 1
                    st.rerun()
            with col3:
                if st.button("Pagina următoare ➡️", width="stretch", disabled=(st.session_state.page_number >= total_pages - 1)):
                    st.session_state.page_number += 1
                    st.rerun()

            col2.markdown(f"<p style='text-align: center; margin-top: 0.7em;'>Pagina {st.session_state.page_number + 1} din {total_pages}</p>", unsafe_allow_html=True)

    # --- Secțiunea de procesare acțiune PDF ---
    if st.session_state.get('selected_id') and st.session_state.get('action_type') == 'pdf':
        selected_id = st.session_state.selected_id
        pdf_content = None
        id_factura = None
        issue_date = None

        with st.spinner(f"Se generează PDF-ul pentru factura cu ID intern: {selected_id}..."):
            try:
                # Preluăm XML-ul din baza de date
                with db_engine.connect() as connection:
                    select_query = text("SELECT fxml, IDFactura, IssuDate FROM tblFacturi WHERE Id = :id")
                    result = connection.execute(select_query, {"id": selected_id}).fetchone()

                if result and result.fxml:
                    # Generăm PDF-ul folosind clientul ANAF
                    pdf_content = anaf_client.xml_to_pdf(xml_content=result.fxml)
                    id_factura = result.IDFactura
                    issue_date = result.IssuDate
                else:
                    st.error(f"Nu s-a găsit conținutul XML pentru factura cu ID {selected_id}.")

            except Exception as e:
                st.error(f"A apărut o eroare la generarea PDF-ului: {e}")

        if pdf_content:
            # Construim link-ul de descărcare
            base64_pdf = base64.b64encode(pdf_content).decode('utf-8')
            data_uri = f"data:application/pdf;base64,{base64_pdf}"

            # Construim un nume de fișier relevant
            if id_factura and issue_date:
                if isinstance(issue_date, str):
                    issue_date = datetime.fromisoformat(issue_date)
                date_str = issue_date.strftime('%Y-%m-%d')
                safe_id_factura = str(id_factura).replace('/', '_').replace('\\', '_')
                file_name = f"factura_{safe_id_factura}_{date_str}.pdf"
            else:
                file_name = f"factura_{selected_id}.pdf"

            # Setăm mesajul de succes pentru a fi afișat în containerul de sus
            success_message = f'PDF-ul a fost generat. [Click aici pentru a deschide/salva **{file_name}**]({data_uri})'
            st.session_state['pdf_success_message'] = success_message

            # Resetăm starea și forțăm un rerun pentru a afișa link-ul
            st.session_state.selected_id = None
            st.session_state.action_type = None
            st.rerun()

except Exception as e:
    st.error(f"A apărut o eroare la citirea datelor din `tblFacturi`: {e}")