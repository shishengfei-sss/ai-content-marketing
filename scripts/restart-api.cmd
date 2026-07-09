@echo off
setlocal
set PORT=8003
if not "%~1"=="" set PORT=%~1

powershell -ExecutionPolicy Bypass -File "%~dp0restart-api.ps1" -Port %PORT%
exit /b %ERRORLEVEL%
