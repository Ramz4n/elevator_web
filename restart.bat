@echo off
echo Перезапуск сервера...
wmic process where "commandline like '%%tester.py%%'" call terminate >nul 2>&1
echo Готово. Watchdog поднимет сервер через 5 секунд.
timeout /t 6 /nobreak >nul
echo Сервер запущен.