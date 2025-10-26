@echo off
setlocal

REM --- Descriere ---
REM Acest script este destinat dezvoltatorilor sau utilizatorilor care cloneaza
REM proiectul direct de pe GitHub. El cloneaza repository-ul si apoi configureaza mediul.
REM Pentru o distributie care contine deja fisierele, folositi un alt script (ex: installer_setup.bat).
REM --- Configurare ---
set "REPO_URL=https://github.com/abcsoft-ro/pyefact.git"

REM Extrage numele directorului din URL-ul repo-ului (ex: pyefact.git -> pyefact)
for %%A in ("%REPO_URL%") do set "PROJECT_DIR=%%~nA"

echo ========================================================================
echo      -- Setup py-efactura (Developer / Git) --
echo ========================================================================

echo.
echo --- Pasul 1: Obținerea sau actualizarea proiectului de pe Git ---

REM Scenariul 1: Scriptul este rulat din interiorul unui repository Git existent.
if exist ".git" (
    echo Directorul curent este deja un repository Git. Se incearca actualizarea...
    git pull
    if errorlevel 1 (
        echo.
        echo AVERTISMENT: Actualizarea (git pull) a esuat. Verificati daca aveti modificari locale sau probleme de retea.
        echo Scriptul va continua cu versiunea locala existenta.
    )
REM Scenariul 2: Directorul proiectului exista, dar nu este un repo Git (ex: instalare manuala).
) else if exist "%PROJECT_DIR%" (
    echo Directorul '%PROJECT_DIR%' exista deja, dar nu este un repository Git.
    echo.
    echo AVERTISMENT: Acest script este pentru clonarea de pe GitHub.
    echo Pentru a configura o instalare existenta, rulati 'installer_setup.bat'.
    echo Scriptul se va opri pentru a preveni actiuni neintentionate.
    goto:eof
REM Scenariul 3: Directorul proiectului nu exista, deci il clonam.
) else (
    echo Se cloneaza repository-ul...
    git clone "%REPO_URL%"
    if errorlevel 1 (
        echo.
        echo EROARE: Clonarea de pe Git a esuat. Verificati daca Git este instalat, URL-ul este corect si aveti conexiune la internet.
        goto :eof
    )
    cd /d "%PROJECT_DIR%" || (echo EROARE: Nu s-a putut intra in directorul '%PROJECT_DIR%'. & goto :eof)
    echo Am intrat in directorul: %cd%
)

echo.
echo --- Pasul 2: Crearea mediului virtual Python ---
REM Folosim 'python' care este comanda standard pe Windows.
python -m venv .venv
if errorlevel 1 (
    echo.
    echo EROARE: Crearea mediului virtual a esuat. Asigurati-va ca Python este instalat si adaugat in PATH.
    goto :eof
)
echo Mediul virtual '.venv' a fost creat cu succes.

echo.
echo --- Pasul 3: Activarea mediului virtual ---
REM Folosim 'call' pentru a executa scriptul de activare si a reveni la acest script.
call .venv\Scripts\activate.bat
echo Mediul virtual a fost activat.

echo.
echo --- Pasul 4: Actualizarea pip ---
python -m pip install --upgrade pip
if errorlevel 1 (
    echo.
    echo AVERTISMENT: Actualizarea pip a esuat. Scriptul va continua.
    echo Versiunea existenta de pip este probabil suficient de recenta.
) else (
    echo pip a fost actualizat la cea mai recenta versiune.
)

echo.
echo --- Pasul 5: Instalarea dependentelor din requirements.txt ---
if not exist "requirements.txt" (
    echo.
    echo EROARE: Fisierul 'requirements.txt' nu a fost gasit in directorul proiectului.
    goto :eof
)
pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo EROARE: Instalarea dependentelor a esuat. Verificati fisierul 'requirements.txt' si conexiunea la internet.
    goto:eof
)
echo Toate dependentele Python au fost instalate cu succes.

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
echo.
echo ========================================================================
echo      -- INSTALARE FINALIZATA CU SUCCES --
echo ========================================================================
echo.
echo Proiectul este gata de utilizare.
echo.
echo --- PASII URMATORI ---
echo 1. Creati si configurati fisierul '.env' (puteti redenumi si edita 'env.example').
echo 2. Pentru a porni aplicatia, rulati 'pyefact.bat' sau:
echo    a. Deschideti un terminal nou.
echo    b. Activati mediul virtual: %cd%\.venv\Scripts\activate
echo    c. Rulati comanda: python launcher.py
echo.

endlocal
pause
