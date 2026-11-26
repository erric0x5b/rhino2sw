@echo off
set "DIR=%~dp0"
set "SCRIPT=%DIR%rhino2sw.py"
if not exist "%SCRIPT%" set "SCRIPT=%DIR%..\rhino2sw.py"
if not exist "%DIR%.venv\Scripts\python.exe" (
  echo Prima esegui 1_INSTALLA.bat
  pause
  exit /b 1
)
"%DIR%.venv\Scripts\python.exe" -I "%SCRIPT%" %*
echo.
pause
