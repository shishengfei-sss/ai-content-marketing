@echo off
setlocal
set PORT=8000
if not "%~1"=="" set PORT=%~1

echo Stopping listeners on port %PORT% ...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%PORT% " ^| findstr LISTENING') do (
  echo   taskkill PID %%a
  taskkill /F /PID %%a >nul 2>&1
)

cd /d "%~dp0..\apps\api"
call .venv\Scripts\python.exe -m alembic upgrade head
echo Starting API on http://127.0.0.1:%PORT% ...
call .venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port %PORT% --reload
