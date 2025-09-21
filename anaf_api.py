import requests  # Va fi necesar pentru apelurile API reale
import pyodbc  # Pentru conexiunea la MS SQL Server
import certifi # Pentru a oferi un pachet de certificate SSL/TLS
import re
import zipfile
import asyncio
import io
from datetime import datetime
import logging
from xml.etree import ElementTree
import os

from sqlalchemy import text, bindparam, LargeBinary
from typing import Any

# Import direct din fișierul local, eliminând complexitatea.
try:
    from pkcs11_vendored import Pkcs11Adapter
except ImportError as e:
    raise ImportError(f"Fișierul 'pkcs11_vendored.py' lipsește sau este corupt. Eroare: {e}") from e


class ApiANAF:
    """
    O clasă pentru a interacționa cu API-ul ANAF.
    Include funcționalități pentru autentificare și trimiterea de facturi,
    precum și o metodă utilitară pentru a converti XML-ul e-Factura în PDF.
    """

    def __init__(self, access_token=None, cert_path=None, key_path=None, pkcs11_lib=None, pkcs11_pin=None):
        """
        Inițializează clientul API.

        Poate fi inițializat în trei moduri:
        1. Cu un token de acces OAuth2: `ApiANAF(access_token="...")`
        2. Cu certificate digitale (fișiere): `ApiANAF(cert_path="...", key_path="...")`
        3. Cu token USB (PKCS#11): `ApiANAF(pkcs11_lib="...", pkcs11_pin="...")`

        :param access_token: Un token de acces OAuth2 valid.
        :param cert_path: Calea către fișierul certificatului (.pem).
        :param key_path: Calea către fișierul cheii private (.pem).
        :param pkcs11_lib: Calea către biblioteca PKCS#11 (.dll pe Windows).
        :param pkcs11_pin: PIN-ul token-ului USB.
        """
        self.auth_method = None
        self.access_token = None
        self.cert = None
        self.api_base_url = None

        # Creăm un obiect de sesiune care va persista cookie-urile
        self.session = requests.Session()
        # Setăm un User-Agent pentru a simula un browser, o practică bună
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36'
        })

        if access_token: # Metoda 1: OAuth2
            print("INFO: Se folosește autentificarea OAuth2.")
            self.auth_method = 'oauth'
            self.access_token = access_token
            self.api_base_url = "https://api.anaf.ro"
        elif cert_path and key_path: # Metoda 2: Fișiere certificat
            print("INFO: Se folosește autentificarea cu fișiere certificat.")
            self.auth_method = 'cert'
            self.cert = (cert_path, key_path)
            self.api_base_url = "https://webserviceapl.anaf.ro"
        elif pkcs11_lib and pkcs11_pin: # Metoda 3: Token USB (PKCS#11)
            print("INFO: Se folosește autentificarea cu token USB (PKCS#11).")
            self.auth_method = 'pkcs11'
            self.api_base_url = "https://webserviceapl.anaf.ro"
            
            try:
                pkcs11_adapter = Pkcs11Adapter(
                    pkcs11_library=pkcs11_lib,
                    user_pin=pkcs11_pin
                )
                self.session.mount(self.api_base_url, pkcs11_adapter)
                print("✔️ Adaptorul PKCS#11 a fost montat cu succes pe sesiune.")
            except Exception as e:
                error_message = str(e)
                if "[Errno 2]" in error_message or "No such file or directory" in error_message:
                    detailed_error = (f"**Eroare la încărcarea bibliotecii PKCS#11: {e}**\n\n"
                                      "Cauza este probabil o dependință lipsă a fișierului `.dll`.\n\n"
                                      "Asigurați-vă că driverul SafeNet pe 64-bit este instalat în `C:\\Program Files\\SafeNet\\...`")
                    raise RuntimeError(detailed_error) from e
                raise RuntimeError(f"Eroare la inițializarea adaptorului PKCS#11: {e}. Verificați PIN-ul și dacă token-ul este conectat.")
        else:
            raise ValueError("Trebuie furnizată o metodă de autentificare validă la inițializarea ApiANAF (token, certificat sau pkcs11).")
        
    def get_access_token(self):
        """
        Obține un token de acces OAuth2 de la ANAF.
        ATENȚIE: Fluxul real de autentificare este complex și implică un token fizic.
        Această funcție este un placeholder și nu trebuie utilizată în forma actuală.
        """
        raise NotImplementedError("Autentificarea automată nu este implementată. "
                                "Vă rugăm să furnizați un 'access_token' valid la inițializarea clasei ApiANAF.")

    def send_invoice(self, xml_content:str, cif: str):
        """
        Trimite o factură în format XML la API-ul ANAF.
        Determină automat dacă este o tranzacție externă pe baza țării clientului.

        :param xml_content: Conținutul XML al facturii.
        :param cif: Codul de Identificare Fiscală al companiei.
        """
        try:
            # Determinăm dacă factura este externă pe baza codului țării clientului
            clean_xml = clean_xml_namespaces(xml_content)
            root = ElementTree.fromstring(clean_xml)
            
            # Calea către codul țării clientului
            country_code_path = './AccountingCustomerParty/Party/PostalAddress/Country/IdentificationCode'
            customer_country_code = find_xml_text(root, country_code_path)

            # Dacă codul țării este 'RO', nu este externă. Altfel (sau dacă nu e găsit), este.
            is_external = customer_country_code != 'RO'

            # 1. Pregătește și execută apelul API către ANAF
            if is_external:
                url = f"{self.api_base_url}/prod/FCTEL/rest/upload?standard=UBL&cif={cif}&extern=DA"
                #url = f"{self.api_base_url}/test/FCTEL/rest/upload?standard=UBL&cif={cif}&extern=DA"
            else:
                url = f"{self.api_base_url}/prod/FCTEL/rest/upload?standard=UBL&cif={cif}"
                #url = f"{self.api_base_url}/test/FCTEL/rest/upload?standard=UBL&cif={cif}"
            
            request_args = {
                'data': xml_content.encode('utf-8'),
                'headers': {'Content-Type': 'application/xml'},
                'verify': certifi.where()
            }

            if self.auth_method == 'oauth':
                request_args['headers']['Authorization'] = f'Bearer {self.access_token}'
            elif self.auth_method == 'cert':
                request_args['cert'] = self.cert
            # Pentru PKCS#11, autentificarea este gestionată automat de adaptorul montat pe sesiune


            response = self.session.post(url, **request_args)

            # Verifică dacă request-ul a avut succes (status code 2xx)
            response.raise_for_status()

            # 2. Returnează un xml cu informatii despre solicitarea facturii
            print(f"✔️ documentul s-a trimis cu succes catre serverul anaf urmeaza procedura de validare.")
            return response.content
        
        except requests.exceptions.RequestException as e:
            # Prindem erori specifice de rețea sau de la API (ex: 4xx, 5xx, timeout)
            # Folosim logging.error pentru o practică mai bună în producție decât print()
            logging.error(f"Eroare la trimiterea facturii către ANAF: {e}")
            if e.response is not None:
                # Dacă avem un răspuns de la server, îl afișăm pentru debug
                logging.error(f"Răspuns de la server (status {e.response.status_code}): {e.response.text}")
            # Re-ridicăm excepția pentru ca funcția apelantă să știe că a apărut o eroare
            # și să o poată gestiona (ex: afișarea unui mesaj către utilizator).
            raise
        except ElementTree.ParseError as e:
            logging.error(f"Eroare la parsarea XML-ului pentru a determina țara clientului: {e}")
            # Ridicăm o eroare mai specifică pentru a fi gestionată de apelant
            raise ValueError(f"Conținutul XML furnizat este invalid: {e}") from e

    def get_invoice_status(self, IdSolicitare):
        """
        Trimite o cerere de interogare catre serverul anaf pentru a returna statusul unei facturi pe baza Idincarcare.
        :param IdSolicitare: Idincarcare returnat de serverul anaf la trimiterea facturii.
        """
        try:
            # 1. Pregătește și execută apelul API către ANAF
            url = f"{self.api_base_url}/prod/FCTEL/rest/stareMesaj?id_incarcare={IdSolicitare}"
            #url = f"{self.api_base_url}/test/FCTEL/rest/stareMesaj?id_incarcare={IdSolicitare}"
            
            request_args = {
                'verify': certifi.where()
            }
            if self.auth_method == 'oauth':
                request_args['headers'] = {'Authorization': f'Bearer {self.access_token}'}
            elif self.auth_method == 'cert':
                request_args['cert'] = self.cert
            # Pentru PKCS#11, autentificarea este gestionată automat de adaptorul montat pe sesiune

            response = self.session.get(url, **request_args)

            # Verifică dacă request-ul a avut succes (status code 2xx)
            response.raise_for_status()

            # 2. Returnează un xml IdDescarcare in caz de succes
            print(f"✔️ documentul a fost procesat cu succes de catre serverul anaf.")
            return response.content

        except requests.exceptions.RequestException as e:
            # Prindem erori specifice de rețea sau de la API
            logging.error(f"Eroare la interogarea statusului mesajului {IdSolicitare}: {e}")
            if e.response is not None:
                logging.error(f"Răspuns de la server (status {e.response.status_code}): {e.response.text}")
            # Re-ridicăm excepția
            raise

    def lista_mesaje(self, start_time: int, end_time: int, pagina: int, cif: str, filtru: str = None):
        """
        Descarcă lista de mesaje de la ANAF pentru un anumit CIF și interval de timp.
        Replică funcționalitatea din exemplul PHP.

        :param start_time: Timpul de început al intervalului (timestamp în milisecunde).
        :param end_time: Timpul de sfârșit al intervalului (timestamp în milisecunde).
        :param pagina: Numărul paginii pentru paginare.
        :param cif: Codul de Identificare Fiscală al companiei.
        :param filtru: Un filtru opțional pentru mesaje (ex: 'FACTURA_TRIMISA').
        :return: Un dicționar cu răspunsul de la ANAF.
        :raises ValueError: Dacă CIF-ul nu este furnizat.
        :raises requests.exceptions.RequestException: Pentru erori de rețea sau de la API.
        """
        if not cif:
            raise ValueError("CIF-ul trebuie furnizat.")

        print(f"Se descarcă lista de mesaje pentru CIF {cif}, pagina {pagina}, start {start_time}, end {end_time}, filtru {filtru}...")

        # Construim parametrii pentru URL
        params = {
            'startTime': start_time,
            'endTime': end_time,
            'cif': cif,
            'pagina': pagina
        }
        if filtru:
            params['filtru'] = filtru

        url = f"{self.api_base_url}/prod/FCTEL/rest/listaMesajePaginatieFactura"

        request_args = {
            'params': params,
            'verify': certifi.where()
        }
        if self.auth_method == 'oauth':
            request_args['headers'] = {'Authorization': f'Bearer {self.access_token}'}
        elif self.auth_method == 'cert':
            request_args['cert'] = self.cert
        # Pentru PKCS#11, autentificarea este gestionată automat de adaptorul montat pe sesiune

        try:
            response = self.session.get(url, **request_args)
            response.raise_for_status()  # Va arunca o excepție pentru status-uri 4xx/5xx
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"❌ Eroare la descărcarea listei de mesaje: {e}")
            if e.response is not None:
                print(f"Răspuns de la server: {e.response.text}")
            raise

    def descarca_factura(self, id_descarcare: str,test: bool=False) -> bytes:
        """
        Descarcă un fișier (factură/arhivă) de la ANAF folosind ID-ul de descărcare.
        Acesta este echivalentul Python pentru funcția `descarca2` din exemplul PHP.

        :param id_descarcare: ID-ul unic de descărcare obținut din lista de mesaje.
        :return: Conținutul fișierului (de obicei un .zip) sub formă de bytes.
        :raises ValueError: Dacă id_descarcare nu este furnizat.
        :raises requests.exceptions.RequestException: Pentru erori de rețea sau de la API.
        """
        if not id_descarcare:
            raise ValueError("ID-ul de descărcare ('id_descarcare') trebuie furnizat.")

        print(f"Se descarcă fișierul pentru ID: {id_descarcare}...")
        if test:
            url = f"{self.api_base_url}/test/FCTEL/rest/descarcare"
        else:    
            url = f"{self.api_base_url}/prod/FCTEL/rest/descarcare"
        
        request_args = {
            'params': {'id': id_descarcare},
            'verify': certifi.where()
        }
        if self.auth_method == 'oauth':
            request_args['headers'] = {'Authorization': f'Bearer {self.access_token}'}
        elif self.auth_method == 'cert':
            request_args['cert'] = self.cert
        # Pentru PKCS#11, autentificarea este gestionată automat de adaptorul montat pe sesiune

        try:
            response = self.session.get(url, **request_args)
            response.raise_for_status()  # Aruncă excepție pentru status-uri 4xx/5xx

            # Verificare primară: este un fișier ZIP? Ne bazăm atât pe Content-Type, cât și pe "magic number".
            content_type = response.headers.get('Content-Type', '').lower()
            is_zip_header = 'application/zip' in content_type
            is_zip_content = response.content.startswith(b'PK\x03\x04')

            if is_zip_header or is_zip_content:
                print(f"✔️ Fișier ZIP descărcat cu succes pentru ID: {id_descarcare}.")
                return response.content

            # Dacă nu e ZIP, tratăm ca o eroare. Încercăm să parsăm ca JSON, indiferent de Content-Type.
            try:
                error_data = response.json()
                # ANAF returnează chei diferite: 'mesaj' la listaMesaje, 'eroare' la descarcare
                error_message = error_data.get('eroare') or error_data.get('mesaj') or f"Eroare necunoscută la descărcarea fișierului cu ID {id_descarcare}."
                # Folosim HTTPError pentru a fi consistent cu alte erori API
                raise requests.exceptions.HTTPError(error_message, response=response)
            except requests.exceptions.JSONDecodeError:
                # Dacă nu e JSON, tratăm ca text simplu/HTML
                error_message = f"Răspunsul de la ANAF nu este un fișier ZIP. Content-Type: '{content_type}'."
                response_text = response.text
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
            Apel de tip POST, ce nu necesita autentificare, pentru validarea unui XML in format e-Factura.

            :param xml_content: Conținutul XML al facturii sau notei de credit.
            :return: Un dicționar cu starea validării. Ex: {'stare': 'ok', 'trace_id': '...'} sau 
                     {'stare': 'nok', 'Messages': [...], 'trace_id': '...'} în caz de eroare.
            :raises requests.exceptions.RequestException: Pentru erori de rețea sau de la API.
            """
            try:
                # 1. Determină tipul documentului (FACT1 sau FCN)
                # Echivalentul Python pentru: substr(trim((string)$xml), -13,13)=='</CreditNote>'
                if xml_content.strip().endswith('</CreditNote>'):
                    tip = 'FCN'
                else:
                    tip = 'FACT1'

                # 2. Pregătește și execută apelul API către ANAF
                # ATENȚIE: Endpoint-ul de transformare folosește un alt domeniu (webservicesp) și nu necesită token.
                url = f"https://webservicesp.anaf.ro/prod/FCTEL/rest/validare/{tip}"

                # Conform exemplului funcțional, acest endpoint necesită Content-Type: text/plain și nu folosește token.
                headers = {
                    'Content-Type': 'text/plain'
                }

                response = self.session.post(
                    url,
                    data=xml_content.encode('utf-8'), # Trimitem XML-ul ca bytes
                    headers=headers,
                    verify=certifi.where()
                )

                # Verifică dacă request-ul a avut succes (status code 2xx)
                response.raise_for_status()

                # 3. Returnează răspunsul JSON ca dicționar Python
                print(f"✔️ xml validat cu succes.")
                return response.json()

            except requests.exceptions.RequestException as e:
                # Prindem erori specifice de rețea sau de la API
                logging.error(f"Eroare la validarea xml-ului prin intermediul API-ul ANAF: {e}")
                if e.response is not None:
                    logging.error(f"Răspuns de la server (status {e.response.status_code}): {e.response.text}")
                # Re-ridicăm excepția
                raise

    def xml_to_pdf(self, xml_content: str) -> bytes:
        """
        Trimite un XML la API-ul ANAF pentru a-l transforma în PDF și returnează conținutul PDF-ului.
        Această metodă este acum generică și nu mai depinde de baza de date.

        :param xml_content: Conținutul XML al facturii sau notei de credit.
        :return: Conținutul PDF sub formă de bytes.
        :raises requests.exceptions.RequestException: Pentru erori de rețea sau de la API.
        """
        try:
            # 1. Determină tipul documentului (FACT1 sau FCN)
            # Echivalentul Python pentru: substr(trim((string)$xml), -13,13)=='</CreditNote>'
            if xml_content.strip().endswith('</CreditNote>'):
                tip = 'FCN'
            else:
                tip = 'FACT1'

            # 2. Pregătește și execută apelul API către ANAF
            # ATENȚIE: Endpoint-ul de transformare folosește un alt domeniu (webservicesp) și nu necesită token.
            url = f"https://webservicesp.anaf.ro/prod/FCTEL/rest/transformare/{tip}"

            # Conform exemplului funcțional, acest endpoint necesită Content-Type: text/plain și nu folosește token.
            headers = {
                'Content-Type': 'text/plain'
            }

            response = self.session.post(
                url,
                data=xml_content.encode('utf-8'), # Trimitem XML-ul ca bytes
                headers=headers,
                verify=certifi.where()
            )

            # Verifică dacă request-ul a avut succes (status code 2xx)
            response.raise_for_status()

            # 3. Returnează conținutul PDF (bytes)
            print(f"✔️ PDF generat cu succes.")
            return response.content

        except requests.exceptions.RequestException as e:
            # Prindem erori specifice de rețea sau de la API
            logging.error(f"Eroare la generarea PDF-ului prin API-ul ANAF: {e}")
            if e.response is not None:
                logging.error(f"Răspuns de la server (status {e.response.status_code}): {e.response.text}")
            # Re-ridicăm excepția
            raise

    def process_unprocessed_messages(self, db_engine, username: str, tip: str='P', progress_callback=None):
        """
        Procesează mesajele nepreluate din `tblmesaje`, descarcă facturile,
        extrage datele și le inserează în `tblSPV`.

        :param db_engine: Un engine SQLAlchemy pentru conexiunea la baza de date.
        :param username: Numele utilizatorului care rulează procesul.
        :param tip: Tipul mesajelor de procesat (ex: 'P', 'T', 'M', 'E').
        :param progress_callback: O funcție opțională care primește (număr_procesat, mesaj_status).
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
            
            # Folosim o singură conexiune pentru toate operațiunile
            with db_engine.connect() as connection:
                # 1. Selectăm mesajele nepreluate într-o tranzacție separată, care se închide imediat.
                select_query = text("SELECT MesId, id, id_solicitare, data_creare, cif, tip, detalii, eroare FROM tblmesaje "
                                    "WHERE preluat = 0 AND tip = :tip ORDER BY MesId")
                with connection.begin():
                    unprocessed_messages = connection.execute(select_query, {"tip": db_tip_filter}).fetchall()

                if not unprocessed_messages:
                    print("✔️ Nu există mesaje noi de procesat.")
                    return report

                print(f"Am găsit {len(unprocessed_messages)} mesaje de procesat.")

                processed_count = 0 # Inițializăm contorul
                for message in unprocessed_messages:
                    print(f"\nProcesare MesId: {message.MesId}, ID Descărcare: {message.id}")

                    # Apelăm callback-ul de progres, dacă a fost furnizat
                    if progress_callback:
                        # Folosim message.id (id_descarcare) care este mai relevant pentru utilizator
                        progress_callback(processed_count, f"Se procesează mesajul ID: {message.id}...")

                    try:
                        # Începem o tranzacție pentru fluxul principal de procesare
                        with connection.begin() as transaction:
                            # 2. Descarcă arhiva ZIP de la ANAF
                            zip_content = self.descarca_factura(id_descarcare=str(message.id))
                            
                            # 3. Extrage fișierele XML din arhiva ZIP
                            # Logica a fost modificată pentru a nu mai depinde de un nume fix (ex: {id}.xml)
                            fxml = sxml = None
                            invoice_filename = None
                            signature_filename = None

                            with zipfile.ZipFile(io.BytesIO(zip_content)) as z:
                                filenames = z.namelist()
                                xml_filenames = [f for f in filenames if f.lower().endswith('.xml')]
                                print(f"Fișiere găsite: {filenames}")
                                # Caută fișierul de semnătură
                                for fname in xml_filenames:
                                    if 'semnatura' in fname.lower():
                                        signature_filename = fname
                                        sxml = z.read(signature_filename).decode('utf-8-sig')
                                        break
                                
                                # Caută fișierul facturii (primul XML care nu e semnătura)
                                for fname in xml_filenames:
                                    if fname != signature_filename:
                                        invoice_filename = fname
                                        fxml = z.read(invoice_filename).decode('utf-8-sig')
                                        break
                            
                            if not fxml:
                                raise ValueError(f"Fișierul XML al facturii nu a fost găsit în arhiva ZIP pentru ID {message.id}. "
                                                 f"Fișiere găsite: {filenames}")
                            # 4. prelucreaza datele in vederea inserarii in tblSPV
                            if tip in ['T', 'P']:
                                # Parsează XML-ul facturii pentru a extrage datele necesare
                                clean_xml = clean_xml_namespaces(fxml)
                                root = ElementTree.fromstring(clean_xml)
                                # Extragere date conform modelului PHP
                                id_fact = find_xml_text(root, './ID', 'N/A')
                                issue_date = find_xml_text(root, './IssueDate')
                                due_date = find_xml_text(root, './DueDate')
                                den_furnizor = find_xml_text(root, './AccountingSupplierParty/Party/PartyLegalEntity/RegistrationName')
                                cif_furnizor = find_xml_text(root, './AccountingSupplierParty/Party/PartyTaxScheme/CompanyID')
                                den_beneficiar = find_xml_text(root, './AccountingCustomerParty/Party/PartyLegalEntity/RegistrationName')
                                cif_beneficiar = find_xml_text(root, './AccountingCustomerParty/Party/PartyTaxScheme/CompanyID')
                                payable_amount = find_xml_text(root, './LegalMonetaryTotal/PayableAmount', '0')
                                currency_code = find_xml_text(root, './DocumentCurrencyCode', 'RON')
                                tip_document = 'FCN' if fxml.strip().endswith('</CreditNote>') else 'FACT1'

                                # Generează PDF-ul folosind metoda refactorizată
                                pdf_bytes=None
                                #pdf_bytes = self.xml_to_pdf(xml_content=fxml)
                                subiectm=''
                                tipm=''
                                continutm=''

                                # Inserează datele în tblSPV
                                insert_sql = text("""
                                    INSERT INTO tblSPV (Data_creare, id_solicitare, id_descarcare, cif_furnizor, cif_beneficiar, 
                                                    den_furnizor, den_beneficiar, tip, f_xml, s_xml, pdf, username, IssueDate, 
                                                    LegalMonetaryTotal, DocumentCurrencyCode, IDFact, DueDate, subiectm, tipm, continutm)
                                    VALUES (:data_creare, :id_solicitare, :id_descarcare, :cif_furnizor, :cif_beneficiar, 
                                            :den_furnizor, :den_beneficiar, :tip, :f_xml, :s_xml, :pdf, :username, :issue_date, 
                                            :payable_amount, :currency_code, :id_fact, :due_date, :subiectm, :tipm, :continutm)
                                """).bindparams(bindparam('pdf', type_=LargeBinary))
                                
                                params = {
                                    "data_creare": message.data_creare, "id_solicitare": message.id_solicitare, "id_descarcare": message.id,
                                    "cif_furnizor": cif_furnizor, "cif_beneficiar": cif_beneficiar, "den_furnizor": den_furnizor,
                                    "den_beneficiar": den_beneficiar, "tip": tip, "f_xml": fxml, "s_xml": sxml,
                                    "pdf": pdf_bytes, "username": username, "issue_date": issue_date, "payable_amount": payable_amount,
                                    "currency_code": currency_code, "id_fact": id_fact, "due_date": due_date,
                                    "subiectm": subiectm, "tipm": tipm, "continutm": continutm
                                }
                                
                            if tip in ['R', 'E']:
                                id_fact = None # Nu avem ID de factură pentru mesaje
                                subiectm=message.detalii
                                tipm=message.tip
                                continutm = 'Conținutul mesajului nu a putut fi extras.' # Valoare implicită

                                try:
                                    if fxml:
                                        clean_xml = clean_xml_namespaces(fxml)
                                        root = ElementTree.fromstring(clean_xml)

                                        if tip == 'R':
                                            # Extrage atributul 'message' din tag-ul 'header'
                                            # XML: <header message="ok" ... />
                                            continutm = root.get('message', 'Mesaj de tip R neconform.')
                                        
                                        elif tip == 'E':
                                            # Extrage atributul 'errorMessage' din tag-ul 'Error'
                                            # XML: <header><Error errorMessage="..."/></header>
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
                                    "data_creare": message.data_creare, "id_solicitare": message.id_solicitare, "id_descarcare": message.id,
                                    "cif_furnizor": '', "cif_beneficiar": '', "den_furnizor": '',
                                    "den_beneficiar": '', "tip": tip, "f_xml": fxml, "s_xml": sxml,
                                    "pdf": None, "username": username,
                                    "subiectm": subiectm, "tipm": tipm, "continutm": continutm
                                }    
                            connection.execute(insert_sql, params)   
                            if id_fact:
                                print(f"✔️ Inserare cu succes în tblSPV pentru IDFact: {id_fact}.")
                            else:
                                print(f"✔️ Inserare cu succes a mesajului de tip '{tip}' în tblSPV (ID Descărcare: {message.id}).")

                            # 5. Actualizează statusul în tblmesaje
                            update_sql = text("UPDATE tblmesaje SET preluat = 1 WHERE MesId = :mesid")
                            connection.execute(update_sql, {"mesid": message.MesId})
                            print(f"✔️ Actualizare cu succes a statusului pentru MesId: {message.MesId}.")
                            report["processed"] += 1

                            # Tranzacția se va comite automat la ieșirea din blocul `with`

                    except Exception as e:
                        # Tranzacția din blocul 'try' a fost deja anulată (rollback) automat la ieșirea din 'with'.
                        
                        # Verificăm cazul specific al erorii de 60 de zile
                        if "perioada de 60 de zile" in str(e):
                            print(f"⚠️ Mesajul {message.MesId} este expirat. Se marchează ca preluat cu eroare.")
                            # Pornim o nouă tranzacție, separată, doar pentru a actualiza statusul.
                            with connection.begin():
                                update_sql = text("UPDATE tblmesaje SET preluat = 1, eroare = :error_msg WHERE MesId = :mesid")
                                connection.execute(update_sql, {"mesid": message.MesId, "error_msg": str(e)})
                        else:
                            error_msg = f"Eroare la procesarea mesajului {message.MesId}: {e}"
                            report["errors"] += 1
                            report["details"].append(error_msg)
                            # Pentru orice altă eroare, doar afișăm mesajul. Rollback-ul s-a făcut deja.
                            print(f"❌ {error_msg}")

                            # --- NOU: Salvarea XML-ului pentru debug ---
                            # Verificăm dacă variabila fxml a fost definită înainte de a apărea eroarea
                            if 'fxml' in locals() and fxml:
                                try:
                                    debug_dir = "debug_xmls"
                                    os.makedirs(debug_dir, exist_ok=True)
                                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                                    filename = f"error_MesId_{message.MesId}_{timestamp}.xml"
                                    filepath = os.path.join(debug_dir, filename)
                                    with open(filepath, "w", encoding="utf-8-sig") as f:
                                        f.write(fxml)
                                    print(f"ℹ️ Fișierul XML problematic a fost salvat pentru analiză în: {filepath}")
                                except Exception as save_err:
                                    print(f"⚠️ Nu s-a putut salva fișierul XML de debug: {save_err}")

                            print("Tranzacția a fost anulată (rollback). Se continuă cu următorul mesaj.")

                    finally:
                        # Incrementăm contorul indiferent de succes sau eroare, pentru a avansa bara de progres
                        processed_count += 1

            # Apel final către callback pentru a afișa 100% și mesajul final
            if progress_callback:
                progress_callback(processed_count, "Procesare finalizată.")

            print(f"\n--- Procesarea mesajelor s-a încheiat. Procesate: {report['processed']}, Erori: {report['errors']} ---")
            return report
        except Exception as e:
            # Prindem orice eroare care ar putea apărea înainte de bucla de procesare
            # (ex: eroare de conexiune la DB, eroare la selectarea mesajelor)
            error_msg = f"Eroare generală în timpul procesării mesajelor: {e}"
            print(f"❌ {error_msg}")
            report["errors"] += 1
            report["details"].append(error_msg)
            # Returnăm raportul cu eroarea, în loc să lăsăm funcția să crape
            return report

async def check_invoice_statuses_periodically(db_engine, access_token: str):
    """
    Rulează în fundal, verificând periodic statusul facturilor trimise la ANAF
    care nu au încă un ID de descărcare.

    :param db_engine: Un engine SQLAlchemy pentru conexiunea la baza de date.
    :param access_token: Token-ul de acces pentru API-ul ANAF.
    """
    if not access_token:
        print("❌ Eroare fatală: Token-ul de acces ANAF nu a fost furnizat serviciului de verificare.")
        return

    anaf_client = ApiANAF(access_token=access_token)
    print("🚀 Serviciul de verificare a statusului facturilor a pornit.")

    while True:
        print(f"\n[{datetime.now()}] Se caută facturi de procesat...")
        try:
            with db_engine.connect() as connection:
                # 1. Selectăm facturile
                # Folosim o tranzacție pentru a asigura consistența citirii
                with connection.begin():
                    query = text("""
                        SELECT TOP 100 Id, IndexIncarcare 
                        FROM tblFacturi 
                        WHERE IndexIncarcare > 0 AND (IDdescarcare = 0 OR IDdescarcare IS NULL)
                        ORDER BY Id
                    """)
                    invoices_to_check = connection.execute(query).fetchall()

                if not invoices_to_check:
                    print("✔️ Nu există facturi noi de verificat.")
                else:
                    print(f"Am găsit {len(invoices_to_check)} facturi de verificat.")
                    
                    for invoice in invoices_to_check:
                        print(f"--- Verificare factură cu Id: {invoice.Id}, IndexIncarcare: {invoice.IndexIncarcare} ---")
                        try:
                            # 2. Apelăm ANAF pentru status
                            # Rulăm funcția sincronă într-un thread separat pentru a nu bloca bucla asyncio
                            status_xml_content = await asyncio.to_thread(
                                anaf_client.get_invoice_status,
                                IdSolicitare=str(invoice.IndexIncarcare)
                            )
                            
                            # 3. Parsăm XML-ul de răspuns
                            clean_xml = clean_xml_namespaces(status_xml_content.decode('utf-8'))
                            root = ElementTree.fromstring(clean_xml)

                            stare = root.get('stare')
                            id_descarcare = root.get('id_descarcare')
                            error_message = None
                            # Căutăm mesajul de eroare
                            error_element = root.find('Errors')
                            if error_element is not None:
                                error_message = error_element.get('errorMessage')    
                                                                                            
                            if stare == 'nok':
                                print(f"ℹ️ Răspuns non-OK de la ANAF. Se descarcă detaliile erorii pentru id_descarcare: {id_descarcare}")
                                if id_descarcare and id_descarcare != '0':
                                    try:
                                        # Descarcă arhiva ZIP cu detaliile erorii
                                        zip_content = await asyncio.to_thread(
                                            anaf_client.descarca_factura,
                                            id_descarcare=str(id_descarcare)
                                        )
                                        # Extrage XML-ul de eroare din arhivă
                                        error_xml_str = None
                                        with zipfile.ZipFile(io.BytesIO(zip_content)) as z:
                                            for filename in z.namelist():
                                                # Ignorăm fișierul de semnătură
                                                if not filename.lower().startswith('semnatura'):
                                                    error_xml_str = z.read(filename).decode('utf-8-sig')
                                                    break
                                        
                                        if error_xml_str:
                                            # Parsează XML-ul de eroare pentru a extrage mesajul
                                            clean_error_xml = clean_xml_namespaces(error_xml_str)
                                            error_root = ElementTree.fromstring(clean_error_xml)
                                            error_element_from_zip = error_root.find('Error')
                                            if error_element_from_zip is not None:
                                                # Suprascriem mesajul de eroare cu cel detaliat
                                                error_message = error_element_from_zip.get('errorMessage')
                                                print(f"✔️ Mesaj de eroare detaliat extras: {error_message}")
                                    except requests.exceptions.HTTPError as http_err:
                                        # Cazul în care ANAF returnează o eroare JSON în loc de ZIP
                                        # (ex: "Pentru id=... nu exista inregistrata nici o factura")
                                        error_message = str(http_err)
                                        print(f"ℹ️ Detaliu eroare obținut din răspunsul API: {error_message}")
                                    except Exception as download_err:
                                        # Alte erori la descărcare (network, fișier corupt etc.)
                                        print(f"⚠️ Eroare la descărcarea/procesarea detaliilor erorii: {download_err}")
                                        # Păstrăm mesajul de eroare inițial dacă descărcarea eșuează
                                else:
                                    print("⚠️ Stare 'nok', dar nu există un ID de descărcare valid pentru a obține detalii.")

                            # 4. Actualizăm în baza de date într-o tranzacție separată per factură
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
                                print(f"✔️ Baza de date a fost actualizată pentru factura cu Id: {invoice.Id}.")

                        except Exception as e:
                            print(f"❌ Eroare la procesarea facturii cu Id {invoice.Id}: {e}")
                            # Continuăm cu următoarea factură
        except Exception as e:
            print(f"❌ A apărut o eroare generală în bucla de verificare: {e}")
        
        print(f"--- Ciclul de verificare s-a încheiat. Următoarea verificare în 5 de minute. ---")
        await asyncio.sleep(5 * 60) # Pauză de 5 de minute

def clean_xml_namespaces(xml_string: str) -> str:
    """Elimină namespace-urile și prefixele dintr-un string XML pentru a facilita parsarea."""
    # 1. Elimină atributele xmlns="..." (atât cele cu prefix, cât și cele default)
    xml_string = re.sub(r'\sxmlns(:\w+)?="[^"]+"', '', xml_string)
    # 2. Elimină atributele cu prefix, cum ar fi xsi:schemaLocation, pentru a preveni erorile "unbound prefix"
    xml_string = re.sub(r'\s[a-zA-Z0-9_.-]+:[a-zA-Z0-9_.-]+\s*=\s*"[^"]*"', '', xml_string)
    # 3. Elimină prefixele din tag-uri (ex: <cbc:ID> -> <ID>).
    xml_string = re.sub(r'<(/?)[a-zA-Z0-9_.-]+:', r'<\1', xml_string)
    return xml_string

def find_xml_text(element: ElementTree.Element, path: str, default=None):
    """Găsește textul unui element XML după cale, returnând o valoare implicită dacă nu este găsit."""
    found_element = element.find(path)
    return found_element.text if found_element is not None else default
