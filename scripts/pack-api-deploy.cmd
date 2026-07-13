@echo off
setlocal
powershell -ExecutionPolicy Bypass -File "%~dp0pack-api-deploy.ps1" %*
exit /b %ERRORLEVEL%
