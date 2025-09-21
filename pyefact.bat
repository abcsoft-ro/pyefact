@echo off
:: Salvează directorul curent
set "WORKDIR=%~dp0"
cd /d "%WORKDIR%"

:: Activează mediul virtual
call "%WORKDIR%.venv\Scripts\activate.bat"

:: Rulează scriptul Python

python launcher.py

:: Dezactivarea nu este necesară aici într-un .bat
echo Script Python finalizat.

pause