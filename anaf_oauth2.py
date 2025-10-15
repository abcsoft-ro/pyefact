import subprocess
import base64
import json
from urllib.parse import urlencode, quote_plus
import os
import shlex
import requests
import certifi

class Anafgettoken:
    """
    Un client Python pentru a interacționa cu serviciul ANAF OAuth2,
    folosind un utilitar extern Java (PKCS11HttpsClient) pentru cererile HTTPS
    securizate cu un token PKCS#11.
    """
    AUTHORIZE_URL = "https://logincert.anaf.ro/anaf-oauth2/v1/authorize"
    TOKEN_URL = "https://logincert.anaf.ro/anaf-oauth2/v1/token"
    REVOKE_URL = "https://logincert.anaf.ro/anaf-oauth2/v1/revoke"

    def __init__(self, client_id: str, client_secret: str, redirect_uri: str, pin: str, java_class_path: str = ".", java_class_name: str = "PKCS11HttpsClient_Version1"):
        """
        Initializează clientul ANAF.

        :param client_id: Client ID de la ANAF.
        :param client_secret: Client Secret de la ANAF.
        :param redirect_uri: URL-ul de callback.
        :param pin: PIN-ul pentru token-ul hardware (certificatul digital).
        :param java_class_path: Calea către directorul care conține fișierul .class al utilitarului Java.
        :param java_class_name: Numele clasei Java de executat.
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.pin = pin
        self.java_class_path = java_class_path
        self.java_class_name = java_class_name
        self.code = None
        self.debug_info = None

    def get_authorization_link(self) -> str:
        """
        Generează link-ul de autorizare pe care utilizatorul trebuie să-l acceseze.
        """
        params = {
            'response_type': 'code',
            'token_content_type': 'jwt',
            'client_id': self.client_id,
            'redirect_uri': self.redirect_uri,
        }
        return f"{self.AUTHORIZE_URL}?{urlencode(params, quote_via=quote_plus)}"

    def set_code(self, code: str):
        """
        Setează codul de autorizare primit de la ANAF după redirect.
        """
        self.code = code

    def get_token(self) -> dict:
        """
        Schimbă codul de autorizare pentru un token de acces.
        Execută utilitarul Java pentru a face cererea POST securizată.

        :return: Un dicționar cu informațiile token-ului.
        :raises ValueError: Dacă codul de autorizare nu a fost setat.
        :raises RuntimeError: Dacă apelul către utilitarul Java eșuează sau ANAF returnează o eroare.
        """
        if not self.code:
            raise ValueError("Codul de autorizare nu a fost setat. Apelați mai întâi set_code().")

        # 1. Pregătirea datelor pentru cererea POST
        post_data = urlencode({
            'code': self.code,
            'grant_type': 'authorization_code',
            'redirect_uri': self.redirect_uri,
            'token_content_type': 'jwt'
        })

        # 2. Pregătirea header-ului de autorizare
        auth_string = f"{self.client_id}:{self.client_secret}"
        auth_header = f"Authorization: Basic {base64.b64encode(auth_string.encode('utf-8')).decode('utf-8')}"
        content_type_header = "Content-Type: application/x-www-form-urlencoded"

        # 3. Construirea comenzii pentru a apela utilitarul Java
        # Folosim shlex.split pentru a gestiona corect argumentele cu spații
        command = shlex.split(
            f'java -cp "{self.java_class_path}" {self.java_class_name} '
            f'-X POST '
            f'-H "{content_type_header}" '
            f'-H "{auth_header}" '
            f'-d "{post_data}" '
            f'--pin "{self.pin}" '
            f'"{self.TOKEN_URL}"'
        )

        # 4. Executarea comenzii și capturarea rezultatului
        try:
            # Schimbăm directorul de lucru pentru ca Java să găsească config.properties
            # Am adăugat `stderr=subprocess.STDOUT` pentru a captura și ieșirea de eroare în același flux.
            # Am eliminat `check=True` pentru a putea inspecta manual ieșirea chiar dacă procesul eșuează.
            process = subprocess.run(command, capture_output=True, text=True, cwd=self.java_class_path)

            # Extragem corpul răspunsului din stdout
            # Căutăm marker-ul "Response Body:" pentru a izola JSON-ul
            output_lines = process.stdout.splitlines()
            try:
                body_start_index = output_lines.index("Response Body:") + 1
                response_body = "\n".join(output_lines[body_start_index:])
                token_info = json.loads(response_body)
            except (ValueError, IndexError):
                # Mesajul de eroare a fost îmbunătățit pentru a afișa atât stdout, cât și stderr.
                error_output = process.stdout or ""
                if process.stderr:
                    error_output += "\n--- STDERR ---\n" + process.stderr
                raise RuntimeError(f"Nu s-a putut extrage corpul JSON din răspunsul Java. Ieșirea completă de la Java (exit code {process.returncode}) a fost:\n---\n{error_output}\n---")

            if 'error' in token_info:
                error_desc = token_info.get('error_description', 'Eroare necunoscută de la ANAF')
                raise RuntimeError(f"Eroare API ANAF: {error_desc}")

            return token_info

        except subprocess.CalledProcessError as e:
            # Eroare la execuția procesului Java
            error_message = f"Eroare la executarea utilitarului Java (exit code {e.returncode}):\nSTDOUT:\n{e.stdout}\nSTDERR:\n{e.stderr}"
            raise RuntimeError(error_message) from e

    def refresh_token(self, access_token: str, refresh_token: str) -> dict:
        """
        Obține un nou token folosind un refresh_token.
        Această metodă face un apel HTTP direct, fără a folosi utilitarul Java,
        conform specificațiilor fluxului de 'refresh_token'.

        :param access_token: Token-ul de acces curent (chiar dacă a expirat).
        :param refresh_token: Refresh token-ul obținut la autentificarea inițială.
        :return: Un dicționar cu noile informații ale token-ului.
        :raises RuntimeError: Dacă apelul HTTP eșuează sau ANAF returnează o eroare.
        """
        # 1. Pregătirea datelor pentru corpul cererii POST
        post_data = urlencode({
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token,
            'client_id': self.client_id,
            'client_secret': self.client_secret
        })

        # 2. Pregătirea header-elor, conform modelului PHP
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/x-www-form-urlencoded'
        }

        # 3. Executarea cererii POST directe
        try:
            response = requests.post(
                self.TOKEN_URL,
                headers=headers,
                data=post_data,
                verify=certifi.where() # Asigură validarea certificatului SSL
            )
            response.raise_for_status()  # Aruncă o excepție pentru status-uri 4xx/5xx

            token_info = response.json()

            if 'error' in token_info:
                raise RuntimeError(f"Eroare API ANAF (refresh_token): {token_info.get('error_description', 'Eroare necunoscută')}")

            return token_info
        except requests.exceptions.RequestException as e:
            # Am îmbunătățit extragerea detaliilor erorii.
            # În cazul unui 400 Bad Request, ANAF returnează un JSON cu detalii.
            error_details = "Niciun detaliu suplimentar de la server."
            if e.response is not None:
                error_details = e.response.text
            raise RuntimeError(f"Eroare la reîmprospătarea token-ului: {e}\n\nDetalii de la server:\n{error_details}") from e

class Anafgettoken2:
    """
    Un client Python pentru a obține token-uri de la ANAF OAuth2,
    folosind un utilitar extern Java (get_token.class) care gestionează întregul flux de autentificare.
    """

    def __init__(self, java_class_path: str = ".", java_class_name: str = "get_token", java_libs_path: str = None):
        """
        Initializează clientul.

        :param java_class_path: Calea către directorul care conține fișierul .class al utilitarului Java.
        :param java_class_name: Numele clasei Java de executat (fără extensia .class).
        :param java_libs_path: Calea către directorul cu bibliotecile .jar necesare (opțional).
        """
        self.java_libs_path = java_libs_path
        self.java_class_path = java_class_path
        self.java_class_name = java_class_name

    def get_new_token(self) -> dict:
        """
        Obține un nou set de token-uri (access și refresh) prin rularea utilitarului Java.
        Noua logică:
        1. Rulează utilitarul Java, care se ocupă de întregul flux.
        2. Utilitarul Java salvează token-urile în fișierele '.env' și 'token.json'.
        3. Această metodă citește și returnează conținutul din 'token.json' după execuția cu succes a utilitarului.

        :return: Un dicționar cu informațiile token-ului (ex: {'access_token': '...', 'refresh_token': '...'}).
        :raises RuntimeError: Dacă apelul către utilitarul Java eșuează sau fișierul 'token.json' nu poate fi citit.
        """
        # Construirea classpath-ului. Include directorul clasei și, opțional, bibliotecile.
        # Folosim os.pathsep pentru a asigura compatibilitatea între Windows (;) și Linux (:).
        classpath_parts = [self.java_class_path]
        if self.java_libs_path:
            classpath_parts.append(f"{self.java_libs_path}{os.sep}*") # Adaugă toate .jar-urile din director
        classpath = os.pathsep.join(classpath_parts)

        # Construirea comenzii pentru a apela utilitarul Java.
        command = shlex.split(
            f'java -cp "{classpath}" {self.java_class_name}'
        )

        try:
            # Executarea comenzii și capturarea rezultatului.
            # Folosim `cwd` pentru a ne asigura că Java rulează din directorul corect.
            process = subprocess.run(
                command, 
                capture_output=True,
                text=True,
                cwd=self.java_class_path,
                check=True # Aruncă excepție dacă procesul returnează un cod de eroare.
            )
            # Afișăm output-ul standard al procesului Java, care acum conține doar mesaje de log.
            print("--- Log de la utilitarul Java ---")
            print(process.stdout)
            print("---------------------------------")

        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Eroare la executarea utilitarului Java '{self.java_class_name}' (exit code {e.returncode}):\n{e.stderr}") from e

        # După ce procesul Java a rulat cu succes, citim fișierul token.json
        try:
            token_file_path = os.path.join(self.java_class_path, 'token.json')
            with open(token_file_path, 'r') as f:
                token_info = json.load(f)
            
            if 'access_token' not in token_info or 'refresh_token' not in token_info:
                raise RuntimeError(f"Fișierul 'token.json' este invalid. Nu conține 'access_token' sau 'refresh_token'.")

            return token_info
        except FileNotFoundError:
            raise RuntimeError(f"Utilitarul Java a rulat, dar fișierul 'token.json' nu a fost găsit în '{self.java_class_path}'.") from None
        except (json.JSONDecodeError, RuntimeError) as e:
            raise RuntimeError(f"Eroare la citirea sau parsarea fișierului 'token.json': {e}") from e