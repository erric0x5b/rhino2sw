@echo off
set "ROOT=%~dp0.."
if not exist "%ROOT%\.venv\Scripts\pythonw.exe" (
  echo Prima esegui 1_INSTALLA.bat
  pause
  exit /b 1
)
start "" "%ROOT%\.venv\Scripts\pythonw.exe" "%ROOT%\run_rhino2sw.py" %*
