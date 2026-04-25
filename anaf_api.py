import requests
import certifi
import re
from urllib.parse import urlencode
import zipfile
import asyncio
import io
import json
from datetime import datetime
import logging
from xml.etree import ElementTree, ElementTree as ET
import os
from sqlalchemy import text, bindparam, LargeBinary
from typing import Any


class ApiANAF:
    """
    O clasă pentru a interacționa cu API-ul ANAF.
    Include funcționalități pentru autentificare și trimiterea de facturi,
    precum și o metodă utilitară pentru a converti XML-ul e-Factura în PDF.
    """

    def __init__(self, access_token=None):
        """
        Inițializează clientul API cu autentificare OAuth2.

        :param access_token: Un token de acces OAuth2 valid.
        """
        if not access_token:
            raise ValueError("Trebuie furnizat un access_token OAuth2 valid la inițializarea ApiANAF.")

        print("INFO: Se folosește autentificarea OAuth2.")
        self.auth_method = 'oauth'
        self.access_token = access_token
        self.api_base_url = "https://api.anaf.ro"

        debug = os.getenv("DEBUG", "False").lower() in ("true", "1", "yes")
        self.api_prefix = '/test' if debug else '/prod'

        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36'
        })

    def send_invoice(self, xml_content: str, cif: str):
        """
        Trimite o factură în format XML la API-ul ANAF.
        Determină automat dacă este o tranzacție externă pe baza țării clientului.

        :param xml_content: Conținutul XML al facturii.
        :param cif: Codul de Identificare Fiscală al companiei.
        """
        try:
            clean_xml = clean_xml_namespaces(xml_content)
            root = ElementTree.fromstring(clean_xml)

            country_code_path = './AccountingCustomerParty/Party/PostalAddress/Country/IdentificationCode'
            customer_country_code = find_xml_text(root, country_code_path)

            is_external = customer_country_code != 'RO'

            if is_external:
                url = f"{self.api_base_url}{self.api_prefix}/FCTEL/rest/upload?standard=UBL&cif={cif}&extern=DA"
            else:
                url = f"{self.api_base_url}{self.api_prefix}/FCTEL/rest/upload?standard=UBL&cif={cif}"

            request_args = {
                'data': xml_content.encode('utf-8'),
                'headers': {
                    'Content-Type': 'application/xml',
                    'Authorization': f'Bearer {self.access_token}'
                },
                'verify': certifi.where()
            }

            response = self.session.post(url, **request_args)
            response.raise_for_status()
            response_content = response.content

            print(f"✔️ documentul s-a trimis cu succes catre serverul anaf urmeaza procedura de validare.")
            return response_content

        except requests.exceptions.RequestException as e:
            logging.error(f"Eroare la trimiterea facturii către ANAF: {e}")
            if e.response is not None:
                logging.error(f"Răspuns de la server (status {e.response.status_code}): {e.response.text}")
            raise
        except ElementTree.ParseError as e:
            logging.error(f"Eroare la parsarea XML-ului pentru a determina țara clientului: {e}")
            raise ValueError(f"Conținutul XML furnizat este invalid: {e}") from e

    def get_invoice_status(self, IdSolicitare):
        """
        Interoghează statusul unei facturi pe baza IdIncarcare.
        :param IdSolicitare: IdIncarcare returnat de serverul anaf la trimiterea facturii.
        """
        try:
            url = f"{self.api_base_url}{self.api_prefix}/FCTEL/rest/stareMesaj?id_incarcare={IdSolicitare}"

            request_args = {
                'verify': certifi.where(),
                'timeout': 60,
                'headers': {'Authorization': f'Bearer {self.access_token}'}
            }

            response = self.session.get(url, **request_args)
            response.raise_for_status()
            response_content = response.content

            print(f"✔️ documentul a fost procesat cu succes de catre serverul anaf.")
            return response_content

        except requests.exceptions.RequestException as e:
            logging.error(f"Eroare la interogarea statusului mesajului {IdSolicitare}: {e}")
            if e.response is not None:
                logging.error(f"Răspuns de la server (status {e.response.status_code}): {e.response.text}")
            raise

    def lista_mesaje(self, start_time: int, end_time: int, pagina: int, cif: str, filtru: str = None):
        """
        Descarcă lista de mesaje de la ANAF pentru un anumit CIF și interval de timp.

        :param start_time: Timpul de început al intervalului (timestamp în milisecunde).
        :param end_time: Timpul de sfârșit al intervalului (timestamp în milisecunde).
        :param pagina: Numărul paginii pentru paginare.
        :param cif: Codul de Identificare Fiscală al companiei.
        :param filtru: Un filtru opțional pentru mesaje.
        :return: Un dicționar cu răspunsul de la ANAF.
        """
        if not cif:
            raise ValueError("CIF-ul trebuie furnizat.")

        print(f"Se descarcă lista de mesaje pentru CIF {cif}, pagina {pagina}, start {start_time}, end {end_time}, filtru {filtru}...")

        params = {
            'startTime': start_time,
            'endTime': end_time,
            'cif': cif,
            'pagina': pagina
        }
        if filtru:
            params['filtru'] = filtru

        url = f"{self.api_base_url}{self.api_prefix}/FCTEL/rest/listaMesajePaginatieFactura"

        request_args = {
            'params': params,
            'verify': certifi.where(),
            'headers': {'Authorization': f'Bearer {self.access_token}'}
        }

        try:
            response = self.session.get(url, **request_args)
            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            print(f"❌ Eroare la descărcarea listei de mesaje: {e}")
            if e.response is not None:
                print(f"Răspuns de la server: {e.response.text}")
            raise

    def descarca_factura(self, id_descarcare: str) -> bytes:
        """
        Descarcă un fișier (factură/arhivă) de la ANAF folosind ID-ul de descărcare.

        :param id_descarcare: ID-ul unic de descărcare.
        :return: Conținutul fișierului (de obicei un .zip) sub formă de bytes.
        """
        if not id_descarcare:
            raise ValueError("ID-ul de descărcare trebuie furnizat.")

        print(f"Se descarcă fișierul pentru ID: {id_descarcare}...")
        url = f"{self.api_base_url}{self.api_prefix}/FCTEL/rest/descarcare"

        request_args = {
            'params': {'id': id_descarcare},
            'verify': certifi.where(),
            'headers': {'Authorization': f'Bearer {self.access_token}'}
        }

        try:
            response = self.session.get(url, **request_args)
            response.raise_for_status()
            response_content = response.content
            response_headers = response.headers

            content_type = response_headers.get('Content-Type', '').lower()
            is_zip_content = response_content and response_content.startswith(b'PK\x03\x04')

            if 'application/zip' in content_type or is_zip_content:
                print(f"✔️ Fișier ZIP descărcat cu succes pentru ID: {id_descarcare}.")
                return response_content

            try:
                error_data = json.loads(response_content)
                error_message = error_data.get('eroare') or error_data.get('mesaj') or f"Eroare necunoscută la descărcare."
                raise requests.exceptions.HTTPError(error_message)
            except (json.JSONDecodeError, TypeError):
                error_message = f"Răspunsul de la ANAF nu este un fișier ZIP. Content-Type: '{content_type}'."
                response_text = response_content.decode('utf-8', errors='ignore') if response_content else ""
                if response_text:
                    error_message += f" Răspuns primit: '{response_text}'"
                raise ValueError(error_message)
        except requests.exceptions.RequestException as e:
            print(f"❌ Eroare la descărcarea fișierului pentru ID {id_descarcare}: {e}")
            if e.response is not None:
                print(f"Răspuns de la server: {e.response.text}")
            raise

    def validare_xml(self, xml_content: str) -> dict[str, Any]:
        """
        Apel POST, fără autentificare, pentru validarea unui XML e-Factura.
        """
        try:
            tip = 'FCN' if xml_content.strip().endswith('</CreditNote>') else 'FACT1'

            url = f"https://webservicesp.anaf.ro/prod/FCTEL/rest/validare/{tip}"

            response = self.session.post(
                url,
                data=xml_content.encode('utf-8'),
                headers={'Content-Type': 'text/plain'},
                verify=certifi.where()
            )
            response.raise_for_status()
            print(f"✔️ xml validat cu succes.")
            return response.json()

        except requests.exceptions.RequestException as e:
            logging.error(f"Eroare la validarea xml-ului: {e}")
            if e.response is not None:
                logging.error(f"Răspuns de la server (status {e.response.status_code}): {e.response.text}")
            raise

    def xml_to_pdf(self, xml_content: str) -> bytes:
        """
        Trimite un XML la API-ul ANAF pentru transformare în PDF.
        """
        try:
            tip = 'FCN' if xml_content.strip().endswith('</CreditNote>') else 'FACT1'

            url = f"https://webservicesp.anaf.ro/prod/FCTEL/rest/transformare/{tip}"

            response = self.session.post(
                url,
                data=xml_content.encode('utf-8'),
                headers={'Content-Type': 'text/plain'},
                verify=certifi.where()
            )
            response.raise_for_status()
            print(f"✔️ PDF generat cu succes.")
            return response.content

        except requests.exceptions.RequestException as e:
            logging.error(f"Eroare la generarea PDF-ului: {e}")
            if e.response is not None:
                logging.error(f"Răspuns de la server (status {e.response.status_code}): {e.response.text}")
            raise

    def process_unprocessed_messages(self, db_engine, username: str, tip: str = 'P', progress_callback=None):
        """
        Procesează mesajele nepreluate din tblmesaje, descarcă facturile și le inserează în tblSPV.
        """
        report = {"processed": 0, "errors": 0, "details": []}

        try:
            tip_map = {
                'P': 'FACTURA PRIMITA',
                'T': 'FACTURA TRIMISA',
                'M': 'MESAJ',
                'E': 'ERORI FACTURA'
            }
            db_tip_filter = tip_map.get(tip.upper())

            if not db_tip_filter:
                raise ValueError(f"Tipul '{tip}' nu este valid. Tipurile valide sunt P, T, M, E.")

            print(f"\n--- Începe procesarea mesajelor nepreluate de tip '{db_tip_filter}' ---")

            with db_engine.connect() as connection:
                select_query = text("SELECT MesId, id, id_solicitare, data_creare, cif, tip, detalii, eroare FROM tblmesaje "
                                    "WHERE preluat = 0 AND tip = :tip ORDER BY MesId")
                with connection.begin():
                    unprocessed_messages = connection.execute(select_query, {"tip": db_tip_filter}).fetchall()

                if not unprocessed_messages:
                    print("✔️ Nu există mesaje noi de procesat.")
                    return report

                print(f"Am găsit {len(unprocessed_messages)} mesaje de procesat.")

                processed_count = 0
                for message in unprocessed_messages:
                    print(f"\nProcesare MesId: {message.MesId}, ID Descărcare: {message.id}")

                    if progress_callback:
                        progress_callback(processed_count, f"Se procesează mesajul ID: {message.id}...")

                    try:
                        with connection.begin() as transaction:
                            zip_content = self.descarca_factura(id_descarcare=str(message.id))

                            fxml = sxml = None
                            invoice_filename = None
                            signature_filename = None

                            with zipfile.ZipFile(io.BytesIO(zip_content)) as z:
                                filenames = z.namelist()
                                xml_filenames = [f for f in filenames if f.lower().endswith('.xml')]
                                print(f"Fișiere găsite: {filenames}")
                                for fname in xml_filenames:
                                    if 'semnatura' in fname.lower():
                                        signature_filename = fname
                                        sxml = z.read(signature_filename).decode('utf-8-sig')
                                        break

                                for fname in xml_filenames:
                                    if fname != signature_filename:
                                        invoice_filename = fname
                                        fxml = z.read(invoice_filename).decode('utf-8-sig')
                                        break

                            if not fxml:
                                raise ValueError(f"Fișierul XML al facturii nu a fost găsit pentru ID {message.id}. "
                                                 f"Fișiere: {filenames}")

                            if tip in ['T', 'P']:
                                clean_xml = clean_xml_namespaces(fxml)
                                root = ElementTree.fromstring(clean_xml)
                                id_fact = find_xml_text(root, './ID', 'N/A')
                                issue_date = find_xml_text(root, './IssueDate')
                                due_date = find_xml_text(root, './DueDate')
                                den_furnizor = find_xml_text(root, './AccountingSupplierParty/Party/PartyLegalEntity/RegistrationName')
                                cif_furnizor = find_xml_text(root, './AccountingSupplierParty/Party/PartyTaxScheme/CompanyID')
                                den_beneficiar = find_xml_text(root, './AccountingCustomerParty/Party/PartyLegalEntity/RegistrationName')
                                cif_beneficiar = find_xml_text(root, './AccountingCustomerParty/Party/PartyTaxScheme/CompanyID')
                                payable_amount = find_xml_text(root, './LegalMonetaryTotal/PayableAmount', '0')
                                currency_code = find_xml_text(root, './DocumentCurrencyCode', 'RON')

                                pdf_bytes = None
                                subiectm = ''
                                tipm = ''
                                continutm = ''

                                insert_sql = text("""
                                    INSERT INTO tblSPV (Data_creare, id_solicitare, id_descarcare, cif_furnizor, cif_beneficiar,
                                                    den_furnizor, den_beneficiar, tip, f_xml, s_xml, pdf, username, IssueDate,
                                                    LegalMonetaryTotal, DocumentCurrencyCode, IDFact, DueDate, subiectm, tipm, continutm)
                                    VALUES (:data_creare, :id_solicitare, :id_descarcare, :cif_furnizor, :cif_beneficiar,
                                            :den_furnizor, :den_beneficiar, :tip, :f_xml, :s_xml, :pdf, :username, :issue_date,
                                            :payable_amount, :currency_code, :id_fact, :due_date, :subiectm, :tipm, :continutm)
                                """).bindparams(bindparam('pdf', type_=LargeBinary))

                                params = {
                                    "data_creare": message.data_creare, "id_solicitare": message.id_solicitare,
                                    "id_descarcare": message.id, "cif_furnizor": cif_furnizor,
                                    "cif_beneficiar": cif_beneficiar, "den_furnizor": den_furnizor,
                                    "den_beneficiar": den_beneficiar, "tip": tip, "f_xml": fxml, "s_xml": sxml,
                                    "pdf": pdf_bytes, "username": username, "issue_date": issue_date,
                                    "payable_amount": payable_amount, "currency_code": currency_code,
                                    "id_fact": id_fact, "due_date": due_date,
                                    "subiectm": subiectm, "tipm": tipm, "continutm": continutm
                                }

                            if tip in ['R', 'E']:
                                id_fact = None
                                subiectm = message.detalii
                                tipm = message.tip
                                continutm = 'Conținutul mesajului nu a putut fi extras.'

                                try:
                                    if fxml:
                                        clean_xml = clean_xml_namespaces(fxml)
                                        root = ElementTree.fromstring(clean_xml)

                                        if tip == 'R':
                                            continutm = root.get('message', 'Mesaj de tip R neconform.')
                                        elif tip == 'E':
                                            error_element = root.find('Error')
                                            if error_element is not None:
                                                continutm = error_element.get('errorMessage', 'Mesaj de eroare E neconform.')
                                            else:
                                                continutm = 'Tag-ul <Error> nu a fost găsit în mesajul de eroare.'
                                except ElementTree.ParseError as pe:
                                    print(f"Eroare la parsarea XML-ului pentru MesId {message.MesId}: {pe}")
                                    continutm = f"XML invalid: {fxml[:200]}..."

                                insert_sql = text("""
                                    INSERT INTO tblSPV (Data_creare, id_solicitare, id_descarcare, cif_furnizor, cif_beneficiar,
                                                    den_furnizor, den_beneficiar, tip, f_xml, s_xml, pdf, username, IssueDate,
                                                    LegalMonetaryTotal, DocumentCurrencyCode, IDFact, DueDate, subiectm, tipm, continutm)
                                    VALUES (:data_creare, :id_solicitare, :id_descarcare, :cif_furnizor, :cif_beneficiar,
                                            :den_furnizor, :den_beneficiar, :tip, :f_xml, :s_xml, :pdf, :username, NULL,
                                            NULL, NULL, NULL, NULL, :subiectm, :tipm, :continutm)
                                """).bindparams(bindparam('pdf', type_=LargeBinary))

                                params = {
                                    "data_creare": message.data_creare, "id_solicitare": message.id_solicitare,
                                    "id_descarcare": message.id,
                                    "cif_furnizor": '', "cif_beneficiar": '', "den_furnizor": '',
                                    "den_beneficiar": '', "tip": tip, "f_xml": fxml, "s_xml": sxml,
                                    "pdf": None, "username": username,
                                    "subiectm": subiectm, "tipm": tipm, "continutm": continutm
                                }

                            connection.execute(insert_sql, params)
                            if id_fact:
                                print(f"✔️ Inserare cu succes în tblSPV pentru IDFact: {id_fact}.")
                            else:
                                print(f"✔️ Inserare cu succes a mesajului de tip '{tip}' (ID Descărcare: {message.id}).")

                            update_sql = text("UPDATE tblmesaje SET preluat = 1 WHERE MesId = :mesid")
                            connection.execute(update_sql, {"mesid": message.MesId})
                            print(f"✔️ Status actualizat pentru MesId: {message.MesId}.")
                            report["processed"] += 1

                    except Exception as e:
                        error_str = str(e).lower()
                        if "perioada de 60 de zile" in error_str or "10 descarcari" in error_str:
                            if "perioada de 60 de zile" in error_str:
                                print(f"⚠️ Mesajul {message.MesId} este expirat. Se marchează ca preluat cu eroare.")
                            else:
                                print(f"⚠️ Limita de descărcări a fost atinsă pentru {message.MesId}.")
                            with connection.begin():
                                update_sql = text("UPDATE tblmesaje SET preluat = 1, eroare = :error_msg WHERE MesId = :mesid")
                                connection.execute(update_sql, {"mesid": message.MesId, "error_msg": str(e)})
                        else:
                            error_msg = f"Eroare la procesarea mesajului {message.MesId}: {e}"
                            report["errors"] += 1
                            report["details"].append(error_msg)
                            print(f"❌ {error_msg}")

                            if 'fxml' in locals() and fxml:
                                try:
                                    debug_dir = "debug_xmls"
                                    os.makedirs(debug_dir, exist_ok=True)
                                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                                    filepath = os.path.join(debug_dir, f"error_MesId_{message.MesId}_{timestamp}.xml")
                                    with open(filepath, "w", encoding="utf-8-sig") as f:
                                        f.write(fxml)
                                    print(f"ℹ️ Fișierul XML a fost salvat în: {filepath}")
                                except Exception as save_err:
                                    print(f"⚠️ Nu s-a putut salva XML-ul de debug: {save_err}")

                            print("Tranzacția a fost anulată (rollback).")

                    finally:
                        processed_count += 1

            if progress_callback:
                progress_callback(processed_count, "Procesare finalizată.")

            print(f"\n--- Procesare încheiată. Procesate: {report['processed']}, Erori: {report['errors']} ---")
            return report
        except Exception as e:
            error_msg = f"Eroare generală în procesarea mesajelor: {e}"
            print(f"❌ {error_msg}")
            report["errors"] += 1
            report["details"].append(error_msg)
            return report


async def check_invoice_statuses_periodically(db_engine, anaf_client: ApiANAF):
    """
    Rulează în fundal, verificând periodic statusul facturilor trimise la ANAF.
    """
    print("🚀 Serviciul de verificare a statusului facturilor a pornit.")

    while True:
        print(f"\n[{datetime.now()}] Se caută facturi de procesat...")
        try:
            with db_engine.connect() as connection:
                with connection.begin():
                    query = text("""
                        SELECT Id, IndexIncarcare
                        FROM tblFacturi
                        WHERE IndexIncarcare > 0 AND (IDdescarcare = 0 OR IDdescarcare IS NULL)
                        ORDER BY Id
                        LIMIT 100
                    """)
                    invoices_to_check = connection.execute(query).fetchall()

                if not invoices_to_check:
                    print("✔️ Nu există facturi noi de verificat.")
                else:
                    print(f"Am găsit {len(invoices_to_check)} facturi de verificat.")

                    for invoice in invoices_to_check:
                        print(f"--- Verificare factură Id: {invoice.Id}, IndexIncarcare: {invoice.IndexIncarcare} ---")
                        try:
                            status_xml_content = await asyncio.to_thread(
                                anaf_client.get_invoice_status,
                                IdSolicitare=str(invoice.IndexIncarcare)
                            )

                            clean_xml = clean_xml_namespaces(status_xml_content.decode('utf-8'))
                            root = ElementTree.fromstring(clean_xml)

                            stare = root.get('stare')
                            id_descarcare = root.get('id_descarcare')
                            error_message = None
                            error_element = root.find('Errors')
                            if error_element is not None:
                                error_message = error_element.get('errorMessage')

                            if stare == 'nok':
                                print(f"ℹ️ Răspuns non-OK. Se descarcă detalii eroare pentru id_descarcare: {id_descarcare}")
                                if id_descarcare and id_descarcare != '0':
                                    try:
                                        zip_content = await asyncio.to_thread(
                                            anaf_client.descarca_factura,
                                            id_descarcare=str(id_descarcare)
                                        )
                                        error_xml_str = None
                                        with zipfile.ZipFile(io.BytesIO(zip_content)) as z:
                                            for filename in z.namelist():
                                                if not filename.lower().startswith('semnatura'):
                                                    error_xml_str = z.read(filename).decode('utf-8-sig')
                                                    break

                                        if error_xml_str:
                                            clean_error_xml = clean_xml_namespaces(error_xml_str)
                                            error_root = ElementTree.fromstring(clean_error_xml)
                                            error_element_from_zip = error_root.find('Error')
                                            if error_element_from_zip is not None:
                                                error_message = error_element_from_zip.get('errorMessage')
                                                print(f"✔️ Mesaj de eroare detaliat: {error_message}")
                                    except requests.exceptions.HTTPError as http_err:
                                        error_message = str(http_err)
                                        print(f"ℹ️ Detaliu eroare din API: {error_message}")
                                    except Exception as download_err:
                                        print(f"⚠️ Eroare la descărcarea detaliilor: {download_err}")
                                else:
                                    print("⚠️ Stare 'nok' fără ID de descărcare valid.")

                            with connection.begin():
                                update_query = text("""
                                    UPDATE tblFacturi
                                    SET StareDocument = :stare, IDdescarcare = :id_descarcare, ErrorMessage = :error_message
                                    WHERE Id = :id
                                """)
                                connection.execute(update_query, {
                                    "stare": stare,
                                    "id_descarcare": id_descarcare,
                                    "error_message": error_message,
                                    "id": invoice.Id
                                })
                                print(f"✔️ BD actualizată pentru factura Id: {invoice.Id}.")

                        except Exception as e:
                            print(f"❌ Eroare la procesarea facturii Id {invoice.Id}: {e}")
        except Exception as e:
            print(f"❌ Eroare generală în bucla de verificare: {e}")

        print(f"--- Ciclu încheiat. Următoarea verificare în 5 minute. ---")
        await asyncio.sleep(5 * 60)


def clean_xml_namespaces(xml_string: str) -> str:
    """Elimină namespace-urile și prefixele dintr-un string XML pentru a facilita parsarea."""
    xml_string = re.sub(r'\sxmlns(:\w+)?="[^"]+"', '', xml_string)
    xml_string = re.sub(r'\s[a-zA-Z0-9_.-]+:[a-zA-Z0-9_.-]+\s*=\s*"[^"]*"', '', xml_string)
    xml_string = re.sub(r'<(/?)[a-zA-Z0-9_.-]+:', r'<\1', xml_string)
    return xml_string


def find_xml_text(element: ElementTree.Element, path: str, default=None):
    """Găsește textul unui element XML după cale, returnând o valoare implicită dacă nu e găsit."""
    found_element = element.find(path)
    return found_element.text if found_element is not None else default
