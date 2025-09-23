@echo off
setlocal

echo ========================================================================
echo      -- Instalare Dependente py-efactura (Installer) --
echo ========================================================================
echo Acest script va configura mediul necesar pentru rularea aplicatiei.
echo Director curent: %cd%

echo.
echo --- Pasul 1: Crearea mediului virtual Python ---
REM Folosim 'python' care este comanda standard pe Windows.
python -m venv .venv
if errorlevel 1 (
    echo.
    echo EROARE: Crearea mediului virtual a esuat. Asigurati-va ca Python este instalat si adaugat in PATH.
    goto:eof
)
echo Mediul virtual '.venv' a fost creat cu succes.

echo.
echo --- Pasul 2: Activarea mediului virtual ---
REM Folosim 'call' pentru a executa scriptul de activare si a reveni la acest script.
call .venv\Scripts\activate.bat
echo Mediul virtual a fost activat.

echo.
echo --- Pasul 3: Actualizarea pip ---
python -m pip install --upgrade pip
if errorlevel 1 (
    echo.
    echo AVERTISMENT: Actualizarea pip a esuat. Scriptul va continua.
    echo Versiunea existenta de pip este probabil suficient de recenta.
) else (
    echo pip a fost actualizat la cea mai recenta versiune.
)

echo.
echo --- Pasul 4: Instalarea dependentelor din requirements.txt ---
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
echo --- Pasul 5: Instalarea browser-elor pentru Playwright ---
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
echo.
echo ========================================================================
echo      -- INSTALARE FINALIZATA CU SUCCES --
echo ========================================================================
echo.
echo Dependentele au fost instalate. Puteti inchide aceasta fereastra.

endlocal
pause