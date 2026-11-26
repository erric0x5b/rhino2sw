@echo off
cd /d "%~dp0"
echo ============================================
echo  rhino2sw - installazione (una volta sola)
echo ============================================
echo.
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
  echo Scaricalo da https://www.python.org/downloads/windows/
  echo e durante l'installazione spunta "Add python.exe to PATH".
  echo Poi rilancia questo file.
  pause
  exit /b 1
)
echo Uso: %PY%
if exist ".venv" rmdir /s /q ".venv"
%PY% -m venv .venv
if errorlevel 1 ( echo ERRORE nella creazione dell'ambiente Python. & pause & exit /b 1 )
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install cadquery-ocp==8.0.1.1.0
if errorlevel 1 ( echo ERRORE: installazione libreria fallita. Serve connessione internet. & pause & exit /b 1 )
".venv\Scripts\python.exe" -c "import OCP; print('Libreria geometrica OK')"
echo.
echo Installazione completata. Ora trascina file o cartelle STEP su "Converti_per_SolidWorks.bat".
pause
