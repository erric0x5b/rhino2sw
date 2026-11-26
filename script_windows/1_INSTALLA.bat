@echo off
rem Avvio da sorgente (alternativa all'installatore). Crea .venv nella cartella del repository.
cd /d "%~dp0.."
set "PY="
for %%V in (3.14 3.13 3.12 3.11) do (
  if not defined PY (
    py -%%V -c "import sys" >nul 2>nul && set "PY=py -%%V"
  )
)
if not defined PY (
  python -c "import sys; sys.exit(0 if (3,11)<=sys.version_info[:2]<=(3,14) else 1)" >nul 2>nul && set "PY=python"
)
if not defined PY (
  echo ERRORE: serve Python da 3.11 a 3.14, NON la 3.15.
  pause
  exit /b 1
)
echo Uso: %PY%
if exist ".venv" rmdir /s /q ".venv"
%PY% -m venv .venv
if errorlevel 1 ( echo ERRORE nella creazione dell'ambiente Python. & pause & exit /b 1 )
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 ( echo ERRORE: installazione librerie fallita. & pause & exit /b 1 )
echo.
echo Installazione completata. Avvia rhino2sw con "Avvia_rhino2sw.bat" o trascinaci sopra file STEP.
pause
