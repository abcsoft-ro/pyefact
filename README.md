# py-efactura

`py-efactura` is a web application developed in Python with Streamlit, designed to simplify interaction with the romanian national electronic invoicing system, ANAF e-Factura. The application provides an intuitive graphical interface for sending, verifying, and downloading invoices directly from your own system. The application is also built to be easily integrated into ERP systems or other systems to securely and efficiently manage interaction with the ANAF e-Factura endpoints.

![Screenshot al aplicației py-efactura incarcare facturi XML](https://github.com/abcsoft-ro/pyefact/blob/main/assets/Incarcare_Facturi_XML.png)

## ✨ Funcționalități Principale

*   **Interfață Web Modernă:** Construită cu Streamlit pentru o experiență de utilizare simplă și eficientă.
*   **Trimitere Facturi:** Permite încărcarea și trimiterea facturilor în format XML către ANAF.
*   **Descărcare Mesaje:** Sincronizează și descarcă automat facturile primite, facturile trimise, mesajele și erorile de la ANAF.
*   **Verificare Status:** Un serviciu de fundal verifică periodic starea facturilor trimise și actualizează statusul acestora (ex: validat, eroare).
*   **Conversie PDF:** Generează o versiune PDF a oricărei facturi XML pentru vizualizare și arhivare.
*   **Metode Multiple de Autentificare:**
    *   **OAuth2:** Folosind un token de acces.
    *   **Certificat Digital:** Folosind fișiere de tip `.pem`.
    *   **Token USB (PKCS#11):** Suport pentru autentificare securizată cu token-uri fizice (ex: SafeNet) - **în curs de implementare**.
*   **Reînnoire Token Automatizată:** Click pe butonul Refresh token sau Click pe butonul Obtine token nou
*   **Bază de Date SQL Server:** Stochează toate facturile și mesajele descărcate pentru acces rapid și istoric.

## 📋 Cerințe

*   **Python:** Versiunea **3.12** este recomandată pentru compatibilitate maximă (versiunile 3.13+ pot avea probleme cu anumite dependențe).
*   **Git:** Pentru a clona repository-ul.
*   **Microsoft SQL Server:** O instanță locală sau de rețea (inclusiv versiunea gratuită Express).
*   **(Opțional) Driver Token USB:** Dacă se folosește autentificarea PKCS#11, driverul specific token-ului (ex: SafeNet Authentication Client) trebuie instalat.

## 🚀 Instalare

Cel mai simplu mod de a instala proiectul este folosind scripturile de setup.

#### Pe Windows:
1.  Descărcați și rulați `setup.bat`.

#### Pe Linux/macOS:
1.  Deschideți un terminal și rulați: `chmod +x setup.sh`
2.  Rulați scriptul: `./setup.sh`

Aceste scripturi vor clona automat repository-ul, vor crea un mediu virtual, vor instala dependențele Python și vor descărca browserele necesare pentru Playwright.

### Instalare Manuală

1.  Clonează repository-ul:
    ```bash
    git clone https://github.com/abcsoft-ro/pyefact.git
    ```
2.  Navighează în directorul proiectului:
    ```bash
    cd pyefact
    ```
3.  Creează și activează un mediu virtual:
    ```bash
    # Creează mediul
    python -m venv .venv
    
    # Activează mediul (Windows)
    .venv\Scripts\activate
    
    # Activează mediul (Linux/macOS)
    source .venv/bin/activate
    ```
4.  Instalează dependențele:
    ```bash
    pip install -r requirements.txt
    ```
5.  Instalează browserele pentru Playwright:
    ```bash
    playwright install
    ```

## ⚙️ Configurare

Aplicația se configurează folosind un fișier `.env` în directorul rădăcină. Creați acest fișier pornind de la exemplul de mai jos.

```env
# === Configurare Bază de Date (Exemplu pentru SQL Server Express local) ===
DATABASE_CONNECTION_URI="mssql+pyodbc:///?odbc_connect=DRIVER={ODBC Driver 17 for SQL Server};SERVER=localhost\SQLEXPRESS;DATABASE=efact;Trusted_Connection=yes"

# === Configurare Generală ANAF ===
ANAF_CIF="RO123456"

# === Metoda 1: Autentificare cu Token OAuth2 (Recomandat) ===
ANAF_ACCESS_TOKEN="token_de_acces_aici..."
ANAF_REFRESH_TOKEN="token_de_refresh_aici..."

# === Metoda 2: Autentificare cu fișiere certificat (.pem) - Funcțional ===
# Lăsați goale dacă nu se folosește
CERT_PATH=""
KEY_PATH=""

# === Metoda 3: Autentificare cu Token USB (PKCS#11) - Experimental / În curs de implementare ===
# ATENȚIE: Această metodă nu este complet funcțională în versiunea curentă.
# PIN-ul NU se stochează aici. Va fi solicitat în interfața aplicației.
PKCS11_LIBRARY_PATH="C:\Windows\System32\eToken.dll"
```

**Notă:** Aplicația va alege metoda de autentificare în următoarea ordine de prioritate:
1.  Token OAuth2 (`ANAF_ACCESS_TOKEN`)
2.  Fișiere certificat (`CERT_PATH` și `KEY_PATH`)
2.  Token USB (`PKCS11_LIBRARY_PATH` și `PKCS11_PIN`)

## ▶️ Utilizare

1.  **Activare mediu virtual:**
    *   Windows: `.venv\Scripts\activate`
    *   Linux/macOS: `source .venv/bin/activate`
2.  **Pornire aplicație:**
    ```bash
    python launcher.py
    ```
    Sau, pe Windows, puteți rula direct `pyefact.bat`.

Aplicația va porni un server local și va deschide o pagină în browser.

### Reînnoirea Token-ului de Acces

Token-urile de acces ANAF expiră. Click pe butonul Refresh token pentru a prelungi cu 3 luni durata de valabilitate a tokenului existent sau Click pe butonul Obtine token nou pentru a primi un nou token.
In acest fin urma caz aplicatia va deschide o fereastră de browser. Autentificați-vă cu tokenul criptografic, iar scriptul va extrage automat noile token-uri și le va salva în fișierul `.env`.

![Screenshot al aplicației py-efactura Setari variabile de mediu](https://github.com/abcsoft-ro/pyefact/blob/main/assets/Setari_variabile_de_mediu.png)

## 🏗️ Structura Proiectului

```
pyefact/
├── data/                 # Fișierele bazei de date (ignorate de Git)
├── pages/                # Paginile secundare ale aplicației Streamlit
├── .venv/                # Mediul virtual Python (ignorat de Git)
├── anaf_api.py           # Clasa principală pentru interacțiunea cu API-ul ANAF
├── background_service.py # Logica pentru serviciul de fundal
├── db_utils.py           # Utilitare pentru conexiunea la baza de date
├── efact.py              # Pagina principală a aplicației Streamlit
├── get_token.py          # Script pentru reînnoirea token-ului OAuth2
├── launcher.py           # Punct de intrare: pornește serviciul de fundal și UI-ul
├── pkcs11_vendored.py    # Adaptor pentru autentificarea cu token USB
├── .env                  # Fișier de configurare (ignorat de Git)
├── .gitignore            # Fișiere și directoare ignorate de Git
├── requirements.txt      # Dependențele Python ale proiectului
├── setup.bat             # Script de instalare pentru Windows
└── setup.sh              # Script de instalare pentru Linux/macOS
```

## 📄 Licență

Acest proiect este distribuit sub licența MIT. Vezi fișierul `LICENSE` pentru mai multe detalii.

## 📄 Screenshots

![Screenshot al aplicației py-efactura incarcare facturi XML](https://github.com/abcsoft-ro/pyefact/blob/main/assets/Incarcare_Facturi_XML.png)

