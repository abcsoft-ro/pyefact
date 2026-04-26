# py-efactura

**py-efactura** is a Python desktop application built with Streamlit that simplifies interaction with the Romanian national electronic invoicing system (ANAF e-Factura). It provides an intuitive graphical interface for sending, verifying, and downloading invoices.

![Application screenshot](https://github.com/abcsoft-ro/pyefact/blob/main/assets/Incarcare_Facturi_XML.png)

## ✨ Key Features

- **Modern Web UI** — Built with Streamlit for a clean and efficient user experience.
- **Send Invoices** — Upload and submit XML invoices to ANAF.
- **Download Messages** — Automatically sync received/sent invoices, messages, and error reports from ANAF.
- **Status Verification** — Background service that periodically checks the status of submitted invoices.
- **PDF Conversion** — Generate a PDF version of any invoice XML.
- **OAuth2 Authentication** — Secure JWT-based token authentication with automatic renewal.
- **Debug Mode** — Toggle between ANAF test and production endpoints via `DEBUG=True/False` in `.env`.
- **Local SQLite Database** — Zero configuration — the database is created automatically on first launch.

## 📋 Requirements

- **Python:** 3.12+ recommended.
- **Git:** For cloning the repository.

## 🚀 Installation

### 🪟 Windows 10+ (Installer)

Download and run the installer package: **[pyefactura-setup-v1.1.exe](installer/output/pyefactura-setup-v1.1.exe)**

The installer automatically sets up the application and all required dependencies.

### Source installation (any platform)

#### Windows:
1. Run `setup.bat`.

#### Linux / macOS:
1. `chmod +x setup.sh && ./setup.sh`

### Manual installation

```bash
git clone https://github.com/abcsoft-ro/pyefact.git
cd pyefact
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt
playwright install
```

## ⚙️ Configuration

The application is configured through the `.env` file in the project root directory:

```env
# ========== General Settings ==========
DEBUG=False
XML_UPLOAD_FOLDER_PATH=C:\pyefact\xml_upload

# ========== ANAF Configuration ==========
ANAF_CIF="RO123456"

# ========== OAuth2 Authentication ==========
ANAF_ACCESS_TOKEN="..."
ANAF_REFRESH_TOKEN="..."
ANAF_CLIENT_ID="..."
ANAF_CLIENT_SECRET="..."
ANAF_REDIRECT_URI="https://..."

# ========== Database (SQLite) ==========
DATABASE_CONNECTION_URI="sqlite:///efact.db"
```

**`DEBUG=False`** — uses ANAF production endpoints (`/prod/FCTEL/...`).  
**`DEBUG=True`** — uses ANAF test endpoints (`/test/FCTEL/...`), with a visible warning banner in the app.

## ▶️ Usage

```bash
pyefact.bat          # Windows
python launcher.py   # Any platform
```

The app starts a local web server and opens a browser tab.

### Token Renewal

ANAF OAuth2 tokens expire periodically. From the **Settings** page:
- **Refresh Access Token** — extends the current token validity by 3 months.
- **Get a New Token** — opens the browser for a full authentication flow.

## 🏗️ Project Structure

```
pyefact/
├── pages/                # Streamlit pages
├── data_sql/             # Database schema (SQLite)
├── installer/output/     # Windows installer executable
├── anaf_api.py           # ANAF API client (OAuth2)
├── anaf_oauth2.py        # OAuth2 token management
├── anaf_utils.py         # ANAF client factory
├── background_service.py # Background invoice status checker
├── db_utils.py           # SQLAlchemy engine + table creation
├── efact.py              # Main page
├── get_token.py          # Token acquisition script (Playwright)
├── launcher.py           # Entry point
├── xml_processor.py      # XML file processing
├── .env                  # Configuration (gitignored)
├── requirements.txt      # Python dependencies
├── setup.bat / setup.sh  # Setup scripts
└── pyefact.bat           # Windows launcher
```

## 📄 License

This project is distributed under the MIT License.
