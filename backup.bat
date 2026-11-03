@echo off
REM Бэкап базы. Настройки — в начале backup.ps1, логин и пароль — из .env (DB_USER, DB_PASSWORD).
REM backup.bat -Force — сохранить, даже если дамп намного меньше прошлого.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0backup.ps1" %*
exit /b %errorlevel%
