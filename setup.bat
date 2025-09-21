@echo off
setlocal

REM --- Configurare ---
REM !!! IMPORTANT: Inlocuiti cu URL-ul real al repository-ului dumneavoastra Git.
set "REPO_URL=https://github.com/utilizator/pyefact.git"
set "PROJECT_DIR=pyefact"

echo --- Pasul 1: Clonarea proiectului de pe Git ---

REM Verificam daca directorul exista deja pentru a evita erori la rulari multiple.
if exist "%PROJECT_DIR%" (
    echo Directorul '%PROJECT_DIR%' exista deja. Se omite clonarea.
) else (
    echo Se cloneaza repository-ul...
    git clone "%REPO_URL%"
    if errorlevel 1 (
        echo.
        echo EROARE: Clonarea de pe Git a esuat. Verificati daca Git este instalat, URL-ul este corect si aveti conexiune la internet.
        goto:eof
    )
)

REM Intram in directorul proiectului. /d este necesar in caz ca proiectul e pe alt drive.
cd /d "%PROJECT_DIR%"
echo Am intrat in directorul: %cd%

echo.
echo --- Pasul 2: Crearea mediului virtual Python ---
REM Folosim 'python' care este comanda standard pe Windows.
python -m venv venv
if errorlevel 1 (
    echo.
    echo EROARE: Crearea mediului virtual a esuat. Asigurati-va ca Python este instalat si adaugat in PATH.
    goto:eof
)
echo Mediul virtual 'venv' a fost creat cu succes.

echo.
echo --- Pasul 3: Activarea mediului virtual ---
REM Folosim 'call' pentru a executa scriptul de activare si a reveni la acest script.
call venv\Scripts\activate.bat
echo Mediul virtual a fost activat.

echo.
echo --- Pasul 4: Actualizarea pip ---
pip install --upgrade pip
if errorlevel 1 (
    echo.
    echo EROARE: Actualizarea pip a esuat.
    goto:eof
)
echo pip a fost actualizat la cea mai recenta versiune.

echo.
echo --- Pasul 5: Instalarea dependentelor din requirements.txt ---
if not exist "requirements.txt" (
    echo.
    echo EROARE: Fisierul 'requirements.txt' nu a fost gasit in directorul proiectului.
    goto:eof
)
pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo EROARE: Instalarea dependentelor a esuat. Verificati fisierul 'requirements.txt' si conexiunea la internet.
    goto:eof
)
echo Toate dependentele au fost instalate cu succes.

echo.
echo --- Pasul 6: Instalarea browser-elor pentru Playwright ---
echo Aceasta comanda descarca browserele necesare (Chromium, etc.) pentru obtinerea token-ului.
playwright install
if errorlevel 1 (
    echo.
    echo AVERTISMENT: Instalarea browser-elor pentru Playwright a esuat.
    echo Acest lucru va cauza erori la obtinerea unui nou token ANAF.
    echo Puteti incerca sa rulati manual comanda 'playwright install' dupa finalizarea scriptului.
) else (
    echo Browser-ele pentru Playwright au fost instalate cu succes.
)

echo.
echo.
echo ========================================================================
echo      -- INSTALARE FINALIZATA CU SUCCES --
echo ========================================================================
echo.
echo Proiectul este gata de utilizare.
echo.
echo PASII URMATORI:
echo 1. Creati si configurati fisierul '.env' conform exemplului din pagina de Setari.
echo 2. Pentru a porni aplicatia, deschideti un terminal nou, activati mediul virtual
echo    (cu comanda: %PROJECT_DIR%\venv\Scripts\activate) si apoi rulati: python launcher.py
echo.

endlocal
pause
