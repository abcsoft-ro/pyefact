# c:\pyefact\pkcs11_vendored.py
# -*- coding: utf-8 -*-
"""
This file provides a Pkcs11Adapter for the `requests` library, using PyKCS11
to interact with a hardware security token. This approach directly loads the
PKCS#11 library, extracts the certificate, and configures the SSL context,
avoiding the problematic PKCS#11 URI method.
"""

import tempfile
import logging
import os
from requests.adapters import HTTPAdapter

try:
    import PyKCS11
    from cryptography import x509
    from cryptography.hazmat.primitives import serialization
except ImportError as e:
    # Eroare la importurile de bază, care sunt necesare indiferent de metodă.
    raise ImportError(f"Dependințele 'PyKCS11' sau 'cryptography' nu au putut fi importate. Asigurați-vă că sunt instalate corect. Eroare: {e}")

log = logging.getLogger(__name__)

class PinManager:
    """
    Context manager to handle login and logout from a PKCS#11 session.
    """
    def __init__(self, session, pin):
        self.session = session
        self.pin = pin

    def __enter__(self):
        if self.pin:
            self.session.login(self.pin)

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.pin:
            self.session.logout()

class Pkcs11Adapter(HTTPAdapter):
    """
    A Transport Adapter for Requests that uses a PKCS#11-enabled client
    certificate for authentication, using the PyKCS11 library.
    """

    def __init__(self, pkcs11_library, user_pin=None, **kwargs):
        self.pkcs11_library = pkcs11_library
        self.user_pin = user_pin

        self._cert_temp_file = None
        self._key_temp_file = None

        # Inițializăm contextul SSL la crearea adaptorului, *înainte* de a apela super().__init__().
        # Acest lucru este necesar deoarece super().__init__() apelează self.init_poolmanager(),
        # care în versiunea noastră suprascrisă depinde de self.ssl_context.
        self.ssl_context = self._create_ssl_context()
        super(Pkcs11Adapter, self).__init__(**kwargs)

    def __del__(self):
        # Destructor to clean up the temporary certificate file
        if self._cert_temp_file and os.path.exists(self._cert_temp_file):
            try:
                os.remove(self._cert_temp_file)
                log.debug(f"Fișierul temporar de certificat '{self._cert_temp_file}' a fost șters.")
            except OSError as e:
                log.error(f"Eroare la ștergerea fișierului temporar de certificat: {e}")
        if self._key_temp_file and os.path.exists(self._key_temp_file):
            try:
                os.remove(self._key_temp_file)
                log.debug(f"Fișierul temporar de cheie '{self._key_temp_file}' a fost șters.")
            except OSError as e:
                log.error(f"Eroare la ștergerea fișierului temporar de cheie: {e}")

    def init_poolmanager(self, *args, **kwargs):
        # Folosim contextul SSL pre-creat la inițializarea adaptorului.
        log.debug('Using pre-created PKCS#11-enabled SSL context')
        kwargs['ssl_context'] = self.ssl_context
        return super(Pkcs11Adapter, self).init_poolmanager(*args, **kwargs)

    def _create_ssl_context(self):
        """
        Extracts the certificate and key from the token and creates an SSL context.
        """
        try:
            import urllib3.contrib.pyopenssl
            from OpenSSL import SSL, Engine

            # Injectăm pyOpenSSL în urllib3 pentru a putea folosi contexte SSL avansate.
            urllib3.contrib.pyopenssl.inject_into_urllib3()
        except ImportError as e:
            if "cannot import name 'Engine'" in str(e):
                raise RuntimeError(
                    "Versiunea instalată de 'pyOpenSSL' este coruptă sau incompatibilă. "
                    "Vă rugăm urmați pașii de reinstalare a pachetelor."
                ) from e
            raise RuntimeError(f"Dependința 'pyOpenSSL' necesară pentru token-ul USB nu a putut fi importată: {e}") from e

        try:
            lib = PyKCS11.PyKCS11Lib()
            lib.load(self.pkcs11_library)
            slot = lib.getSlotList(tokenPresent=True)[0]
            session = lib.openSession(slot)
            
            with PinManager(session, self.user_pin):
                cert_obj = session.findObjects([(PyKCS11.CKA_CLASS, PyKCS11.CKO_CERTIFICATE)])[0]
                cert_der = bytes(session.getAttributeValue(cert_obj, [PyKCS11.CKA_VALUE])[0])
                key_id_bytes = session.getAttributeValue(cert_obj, [PyKCS11.CKA_ID])[0]
                key_id = "".join(f"{b:02x}" for b in key_id_bytes)
            
            session.closeSession()
            log.debug(f"Certificat extras cu succes. ID cheie: {key_id}")

            engine_path = os.getenv("PKCS11_ENGINE_PATH")
            if not engine_path or not os.path.exists(engine_path):
                raise RuntimeError("Variabila 'PKCS11_ENGINE_PATH' nu este setată sau calea este invalidă. "
                                 "Asigurați-vă că ați instalat OpenSC și ați configurat calea către 'opensc-pkcs11.dll'.")

            log.debug(f"Se încarcă motorul OpenSSL de la: {engine_path}")
            Engine.load_dynamic_engine("pkcs11", engine_path)
            engine = Engine.get_engine("pkcs11")
            
            engine.ctrl_cmd_string("MODULE_PATH", self.pkcs11_library)
            engine.init()
            log.debug("Motorul OpenSSL a fost inițializat cu succes.")

            context = SSL.Context(SSL.TLS_METHOD)
            context.set_options(SSL.OP_NO_SSLv2 | SSL.OP_NO_SSLv3 | SSL.OP_NO_COMPRESSION)

            cert_obj = x509.load_der_x509_certificate(cert_der)
            cert_pem = cert_obj.public_bytes(serialization.Encoding.PEM)
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pem", mode='wb') as f:
                f.write(cert_pem)
                self._cert_temp_file = f.name
            context.use_certificate_file(self._cert_temp_file)
            log.debug(f"Certificatul a fost încărcat în contextul SSL din: {self._cert_temp_file}")

            ui_method = SSL.UI_UTIL_wrap_read_pem_callback(lambda *_: self.user_pin.encode('utf-8'))
            context.set_ui_info(ui_method)
            context.use_privatekey_file(f"id_{key_id}", filetype=SSL.FILETYPE_ENGINE)
            log.debug(f"Contextul SSL a fost configurat să folosească cheia privată cu ID '{key_id}' prin motorul PKCS#11.")
            
            return context

        except (PyKCS11.PyKCS11Error, SSL.Error) as e:
            raise RuntimeError(f"Eroare în timpul configurării PKCS#11: {e}") from e
        finally:
            if 'session' in locals() and 'session_handle' in dir(session) and session.session_handle:
                session.closeSession()
            if 'engine' in locals() and engine:
                engine.finish()

    def __getstate__(self):
        state = self.__dict__.copy()
        state['ssl_context'] = None
        state['_cert_temp_file'] = None
        state['_key_temp_file'] = None
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)
