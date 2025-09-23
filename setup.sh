#!/bin/bash

# Oprește scriptul dacă o comandă eșuează, pentru a preveni erori în cascadă.
set -e

# --- Configurare ---
# !!! IMPORTANT: Înlocuiți cu URL-ul real al repository-ului dumneavoastră Git.
REPO_URL="https://github.com/abcsoft-ro/pyefact.git"
PROJECT_DIR="pyefact"

echo "--- Pasul 1: Clonarea proiectului de pe Git ---"

# Verificăm dacă directorul există deja pentru a evita erori la rulări multiple.
if [ -d "$PROJECT_DIR" ]; then
    echo "Directorul '$PROJECT_DIR' există deja. Se omite clonarea."
else
    git clone "$REPO_URL"
fi

# Intrăm în directorul proiectului. Toate comenzile următoare se vor executa de aici.
cd "$PROJECT_DIR"
echo "Am intrat în directorul: $(pwd)"

echo ""
echo "--- Pasul 2: Crearea mediului virtual Python ---"
# Folosim 'python3' care este standard pe majoritatea sistemelor Linux/macOS.
# Dacă comanda implicită este 'python', puteți modifica mai jos.
python3 -m venv .venv
echo "Mediul virtual '.venv' a fost creat cu succes."

echo ""
echo "--- Pasul 3: Activarea mediului virtual ---"
source .venv/bin/activate
echo "Mediul virtual a fost activat."
echo "(Notă: Pentru Windows, comanda de activare este: .venv\Scripts\activate)"

echo ""
echo "--- Pasul 4: Actualizarea pip ---"
python -m pip install --upgrade pip
echo "pip a fost actualizat la cea mai recentă versiune."

echo ""
echo "--- Pasul 5: Instalarea dependențelor din requirements.txt ---"
pip install -r requirements.txt
echo "Toate dependențele au fost instalate cu succes."

echo ""
echo "--- Pasul 6: Instalarea browser-elor pentru Playwright ---"
echo "Aceasta comanda descarca browserele necesare (Chromium, etc.)."
playwright install

echo ""
echo "✅ --- INSTALARE FINALIZATĂ --- ✅"
echo "Proiectul este gata de utilizare."
echo "Nu uitați să creați și să configurați fișierul '.env' conform exemplului din pagina de Setări."
echo "Pentru a porni aplicația, rulați comanda: python launcher.py"
