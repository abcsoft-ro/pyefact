# py-efactura

`py-efactura` este o aplicație web dezvoltată în Python cu Streamlit, concepută pentru a simplifica interacțiunea cu sistemul național de facturare electronică, ANAF e-Factura. Oferă o interfață grafică intuitivă pentru trimiterea, verificarea și descărcarea facturilor direct din sistemul propriu.

![Screenshot aplicație](https://github.com/abcsoft-ro/pyefact/blob/main/assets/Incarcare_Facturi_XML.png)

## ✨ Funcționalități Principale

*   **Interfață Web Modernă:** Construită cu Streamlit pentru o experiență simplă și eficientă.
*   **Trimitere Facturi:** Încărcare și trimitere facturi în format XML către ANAF.
*   **Descărcare Mesaje:** Sincronizare și descărcare automată a facturilor primite/trimise, mesajelor și erorilor de la ANAF.
*   **Verificare Status:** Serviciu de fundal care verifică periodic starea facturilor trimise.
*   **Conversie PDF:** Generare PDF din orice factură XML.
*   **Autentificare OAuth2:** Autentificare securizată cu token de acces JWT + reînnoire automată.
*   **Mod Debug:** Comutare simplă între endpoint-urile de test și producție ANAF (`DEBUG=True/False` în `.env`).
*   **Bază de Date Locală SQLite:** Zero configurare — baza de date se creează automat la prima pornire.

## 📋 Cerințe

*   **Python:** 3.12+ recomandat.
*   **Git:** Pentru clonarea repository-ului.

## 🚀 Instalare

### 🪟 Windows 10+ (Installer)

Descărcați și rulați programul de instalare: **[pyefactura-setup-v1.1.exe](installer/output/pyefactura-setup-v1.1.exe)**

Installerul instalează automat aplicația și dependențele necesare.

### Instalare din sursă (orice platformă)

#### Pe Windows:
1.  Rulați `setup.bat`.

#### Pe Linux/macOS:
1.  `chmod +x setup.sh && ./setup.sh`

### Instalare Manuală

```bash
git clone https://github.com/abcsoft-ro/pyefact.git
cd pyefact
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
playwright install
```

## ⚙️ Configurare

Aplicația se configurează prin fișierul `.env` din directorul rădăcină:

```env
# ========== Setări Generale ==========
DEBUG=False
XML_UPLOAD_FOLDER_PATH=C:\pyefact\xml_upload

# ========== Configurare ANAF ==========
ANAF_CIF="RO123456"

# ========== Autentificare OAuth2 ==========
ANAF_ACCESS_TOKEN="..."
ANAF_REFRESH_TOKEN="..."
ANAF_CLIENT_ID="..."
ANAF_CLIENT_SECRET="..."
ANAF_REDIRECT_URI="https://..."

# ========== Bază de Date (SQLite) ==========
DATABASE_CONNECTION_URI="sqlite:///efact.db"
```

**DEBUG=False** - se folosesc endpoint-urile de producție ANAF (`/prod/FCTEL/...`).  
**DEBUG=True** - se folosesc endpoint-urile de test (`/test/FCTEL/...`), cu avertisment vizibil în aplicație.

## ▶️ Utilizare

```bash
pyefact.bat          # Windows
python launcher.py   # Orice platformă
```

Aplicația pornește un server local și deschide o pagină în browser.

### Reînnoire Token OAuth2

Token-urile ANAF expiră. Din pagina **Setări**:
- **Refresh Access Token** → prelungește valabilitatea cu 3 luni
- **Obține un Token Nou** → deschide browserul pentru autentificare completă

## 🏗️ Structura Proiectului

```
pyefact/
├── pages/                # Paginile aplicației Streamlit
├── data_sql/             # Schema bazei de date SQLite
├── anaf_api.py           # Client API ANAF (OAuth2)
├── anaf_oauth2.py        # Gestionare token-uri OAuth2
├── anaf_utils.py         # Factory pentru clientul ANAF
├── background_service.py # Serviciu fundal verificare status
├── db_utils.py           # Conexiune SQLAlchemy + creare tabele
├── efact.py              # Pagina principală
├── get_token.py          # Script achiziție token (Playwright)
├── launcher.py           # Punct de intrare
├── xml_processor.py      # Procesare fișiere XML
├── .env                  # Configurație (ignorat de Git)
├── requirements.txt      # Dependențe
├── setup.bat / setup.sh  # Scripturi instalare
└── pyefact.bat           # Lansator Windows
```

## 📄 Licență

Acest proiect este distribuit sub licența MIT.
