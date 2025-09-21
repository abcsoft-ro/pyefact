import os
import shutil
import json
from xml.etree import ElementTree
from sqlalchemy import text, bindparam, LargeBinary
from datetime import datetime

from anaf_api import ApiANAF, clean_xml_namespaces, find_xml_text


def process_xml_files_from_upload_folder(db_engine, anaf_client: ApiANAF, progress_callback=None):
    """
    Scanează directorul 'xml_upload', procesează fiecare fișier XML,
    generează PDF, inserează datele în tblFacturi și mută fișierul.

    :param db_engine: Un engine SQLAlchemy pentru conexiunea la baza de date.
    :param anaf_client: O instanță a clasei ApiANAF.
    :param progress_callback: O funcție opțională pentru a raporta progresul.
    :return: Un dicționar cu un raport al procesării.
    """
    upload_folder = os.getenv("XML_UPLOAD_FOLDER_PATH")
    report = {"processed": 0, "errors": 0, "details": []}

    if not upload_folder:
        error_msg = "Calea către directorul de upload (`XML_UPLOAD_FOLDER_PATH`) nu este configurată în fișierul .env."
        report["errors"] = 1
        report["details"].append(error_msg)
        if progress_callback:
            progress_callback(1.0, error_msg)
        return report

    base_dir = os.path.dirname(os.path.abspath(__file__))
    processed_folder = os.path.join(base_dir, "xml_processed")
    error_folder = os.path.join(base_dir, "xml_error")

    # Asigură existența directoarelor
    os.makedirs(upload_folder, exist_ok=True)
    os.makedirs(processed_folder, exist_ok=True)
    os.makedirs(error_folder, exist_ok=True)
    
    try:
        xml_files = [f for f in os.listdir(upload_folder) if f.lower().endswith('.xml')]
        if not xml_files:
            report["details"].append("Niciun fișier XML găsit în directorul 'xml_upload'.")
            if progress_callback:
                progress_callback(1.0, "Niciun fișier XML găsit.")
            return report

        total_files = len(xml_files)

        with db_engine.connect() as connection:
            for i, filename in enumerate(xml_files):
                filepath = os.path.join(upload_folder, filename)
                try:
                    if progress_callback:
                        progress_value = (i + 1) / total_files
                        progress_callback(progress_value, f"Se procesează fișierul {i+1}/{total_files}...")

                    # 1. Citește conținutul XML
                    with open(filepath, 'r', encoding='utf-8-sig') as f:
                        fxml_content = f.read()

                    # 2. Validează XML-ul prin API-ul ANAF înainte de a continua
                    validare = anaf_client.validare_xml(xml_content=fxml_content)

                    if validare.get('stare') != 'ok':
                        # Salvează răspunsul de validare ca JSON pentru debug
                        try:
                            # Construim numele fișierului JSON de eroare (ex: error_factura123.json)
                            json_filename = f"error_{os.path.splitext(filename)[0]}.json"
                            json_filepath = os.path.join(error_folder, json_filename)
                            with open(json_filepath, 'w', encoding='utf-8') as json_f:
                                json.dump(validare, json_f, ensure_ascii=False, indent=4)
                            # Adăugăm un mesaj informativ în raport
                            report["details"].append(f"ℹ️ {filename}: Răspunsul de validare a fost salvat în {json_filename}")
                        except Exception as json_err:
                            # Nu oprim procesul dacă salvarea JSON eșuează, doar înregistrăm o avertizare
                            json_error_msg = f"⚠️ {filename}: Nu s-a putut salva fișierul JSON de eroare: {json_err}"
                            report["details"].append(json_error_msg)
                            print(json_error_msg)

                        # Extrage mesajele de eroare. ANAF returnează o listă de dicționare.
                        error_list = validare.get('Messages', []) # Lista de erori
                        formatted_errors = []
                        for error_item in error_list:
                            # Cheia este 'message', nu 'eroare'. Valoarea este un string lung.
                            message_str = error_item.get('message', '')
                            # Parsăm string-ul pentru a extrage detaliile relevante
                            parts = {p.split('=', 1)[0].strip(): p.split('=', 1)[1] for p in message_str.split(';') if '=' in p}
                            
                            cod_eroare = parts.get('codEroare', 'N/A')
                            text_eroare = parts.get('textEroare', 'Descriere indisponibilă.')
                            
                            # Formatăm un mesaj clar pentru fiecare eroare
                            formatted_errors.append(f"({cod_eroare}) {text_eroare}")

                        # Concatenăm mesajele de eroare formatate într-un singur string.
                        error_details = "; ".join(formatted_errors) if formatted_errors else "Eroare de validare neidentificată."
                        # Ridicăm o excepție pentru a întrerupe fluxul și a activa logica de eroare de mai jos.
                        raise ValueError(f"Validare ANAF eșuată: {error_details}")

                    # XML-ul este valid, continuăm procesarea.
                    # Generează PDF (opțional, comentat momentan)
                    pdf_bytes = None
                    # pdf_bytes = anaf_client.xml_to_pdf(xml_content=fxml_content)

                    # 3. Parsează XML pentru date
                    clean_xml = clean_xml_namespaces(fxml_content)
                    root = ElementTree.fromstring(clean_xml)

                    id_factura = find_xml_text(root, './ID', 'N/A')
                    issue_date_str = find_xml_text(root, './IssueDate')
                    # Conversie la formatul de dată corect pentru SQL Server
                    issue_date = datetime.strptime(issue_date_str, '%Y-%m-%d').date() if issue_date_str else None
                    
                    firma = find_xml_text(root, './AccountingSupplierParty/Party/PartyLegalEntity/RegistrationName')
                    cif = find_xml_text(root, './AccountingSupplierParty/Party/PartyTaxScheme/CompanyID')
                    beneficiar = find_xml_text(root, './AccountingCustomerParty/Party/PartyLegalEntity/RegistrationName')
                    valoare = find_xml_text(root, './LegalMonetaryTotal/PayableAmount', '0')

                    # 4. Inserează în tblFacturi
                    insert_sql = text("""
                        INSERT INTO tblFacturi (Firma, cif, Ffilename, IDFactura, IssuDate, Beneficiar, Valoare, fxml, pdf, StareDocument)
                        VALUES (:firma, :cif, :ffilename, :id_factura, :issue_date, :beneficiar, :valoare, :fxml, :pdf, :stare)
                    """).bindparams(bindparam('pdf', type_=LargeBinary))

                    params = {
                        "firma": firma,
                        "cif": cif,
                        "ffilename": filename,
                        "id_factura": id_factura,
                        "issue_date": issue_date,
                        "beneficiar": beneficiar,
                        "valoare": float(valoare),
                        "fxml": fxml_content,
                        "pdf": pdf_bytes,
                        "stare": "Ready to send"
                    }
                    
                    # Folosim o tranzacție pentru a asigura consistența
                    with connection.begin() as transaction:
                        # Verifică dacă factura există deja (în interiorul tranzacției)
                        check_sql = text("SELECT COUNT(*) FROM tblFacturi WHERE IDFactura = :id_factura AND cif = :cif")
                        count = connection.execute(check_sql, {"id_factura": id_factura, "cif": cif}).scalar()

                        if count > 0:
                            raise ValueError(f"Factura cu ID '{id_factura}' și CIF '{cif}' există deja în baza de date.")
                        
                        connection.execute(insert_sql, params)

                    # 5. Mută fișierul în folderul 'processed'
                    shutil.move(filepath, os.path.join(processed_folder, filename))
                    
                    report["processed"] += 1
                    report["details"].append(f"✔️ {filename}: Procesat și inserat cu succes.")
                    print(f"✔️ Factura '{id_factura}' a fost procesată și inserată cu succes.")

                except Exception as e:
                    error_msg = f"❌ {filename}: Eroare la procesare - {e}"
                    report["errors"] += 1
                    report["details"].append(error_msg)
                    print(error_msg)
                    # Mută fișierul în folderul 'error'
                    try:
                        shutil.move(filepath, os.path.join(error_folder, filename))
                    except Exception as move_err:
                        print(f"⚠️ Nu s-a putut muta fișierul {filename} în folderul de erori: {move_err}")

        # Apel final pentru a asigura că bara de progres ajunge la 100%
        if progress_callback:
            progress_callback(1.0, "Procesare finalizată.")

    except Exception as e:
        error_msg = f"❌ Eroare generală în `process_xml_files_from_upload_folder`: {e}"
        report["errors"] += 1
        report["details"].append(error_msg)
        print(error_msg)
        if progress_callback:
            progress_callback(1.0, f"Eroare: {e}")

    return report