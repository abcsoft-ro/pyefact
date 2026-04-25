import base64
import json
from urllib.parse import urlencode, quote_plus
import requests
import certifi


class Anafgettoken:
    """
    Un client Python pentru a interacționa cu serviciul ANAF OAuth2.
    Suportă refresh token prin HTTP direct.
    """

    AUTHORIZE_URL = "https://logincert.anaf.ro/anaf-oauth2/v1/authorize"
    TOKEN_URL = "https://logincert.anaf.ro/anaf-oauth2/v1/token"
    REVOKE_URL = "https://logincert.anaf.ro/anaf-oauth2/v1/revoke"

    def __init__(self, client_id: str, client_secret: str, redirect_uri: str = ""):
        """
        Initializează clientul ANAF.

        :param client_id: Client ID de la ANAF.
        :param client_secret: Client Secret de la ANAF.
        :param redirect_uri: URL-ul de callback.
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri

    def get_authorization_link(self) -> str:
        """Generează link-ul de autorizare pe care utilizatorul trebuie să-l acceseze."""
        params = {
            'response_type': 'code',
            'token_content_type': 'jwt',
            'client_id': self.client_id,
            'redirect_uri': self.redirect_uri,
        }
        return f"{self.AUTHORIZE_URL}?{urlencode(params, quote_via=quote_plus)}"

    def refresh_token(self, access_token: str, refresh_token: str) -> dict:
        """
        Obține un nou token folosind un refresh_token.
        Apel HTTP direct, fără utilitar Java.

        :param access_token: Token-ul de acces curent.
        :param refresh_token: Refresh token-ul obținut la autentificarea inițială.
        :return: Un dicționar cu noile informații ale token-ului.
        """
        post_data = urlencode({
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token,
            'client_id': self.client_id,
            'client_secret': self.client_secret
        })

        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/x-www-form-urlencoded'
        }

        try:
            response = requests.post(
                self.TOKEN_URL,
                headers=headers,
                data=post_data,
                verify=certifi.where()
            )
            response.raise_for_status()

            token_info = response.json()

            if 'error' in token_info:
                raise RuntimeError(f"Eroare API ANAF (refresh_token): {token_info.get('error_description', 'Eroare necunoscută')}")

            return token_info
        except requests.exceptions.RequestException as e:
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

        :param java_class_path: Calea către directorul care conține fișierul .class.
        :param java_class_name: Numele clasei Java de executat.
        :param java_libs_path: Calea către directorul cu bibliotecile .jar.
        """
        import os
        self.java_libs_path = java_libs_path
        self.java_class_path = java_class_path
        self.java_class_name = java_class_name

    def get_new_token(self) -> dict:
        """
        Obține un nou set de token-uri prin rularea utilitarului Java.
        """
        import subprocess
        import shlex
        import os

        classpath_parts = [self.java_class_path]
        if self.java_libs_path:
            classpath_parts.append(f"{self.java_libs_path}{os.sep}*")
        classpath = os.pathsep.join(classpath_parts)

        command = shlex.split(
            f'java -cp "{classpath}" {self.java_class_name}'
        )

        try:
            process = subprocess.run(
                command,
                capture_output=True,
                text=True,
                cwd=self.java_class_path,
                check=True
            )
            print("--- Log de la utilitarul Java ---")
            print(process.stdout)
            print("---------------------------------")

        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Eroare la executarea utilitarului Java '{self.java_class_name}' (exit code {e.returncode}):\n{e.stderr}") from e

        try:
            import json
            token_file_path = os.path.join(self.java_class_path, 'token.json')
            with open(token_file_path, 'r') as f:
                token_info = json.load(f)

            if 'access_token' not in token_info or 'refresh_token' not in token_info:
                raise RuntimeError(f"Fișierul 'token.json' este invalid.")

            return token_info
        except FileNotFoundError:
            raise RuntimeError(f"Utilitarul Java a rulat, dar fișierul 'token.json' nu a fost găsit.")
        except (json.JSONDecodeError, RuntimeError) as e:
            raise RuntimeError(f"Eroare la citirea fișierului 'token.json': {e}") from e
