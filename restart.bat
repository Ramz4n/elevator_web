@echo off
chcp 65001 >nul
echo Перезапуск сервера...
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name LIKE 'python%%'\" | Where-Object { $_.CommandLine -like '*tester.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"

REM Сайт поднимает watchdog. Если он не работает — запускаем задачу автозапуска
powershell -NoProfile -Command "if (Get-CimInstance Win32_Process -Filter \"Name LIKE 'python%%'\" | Where-Object { $_.CommandLine -like '*watchdog.py*' }) { exit 0 } else { exit 1 }"
if errorlevel 1 (
    echo Watchdog не запущен, запускаю задачу FlaskTesterApp...
    schtasks /run /tn "FlaskTesterApp" >nul 2>&1
    if errorlevel 1 (
        echo ОШИБКА: задача FlaskTesterApp не найдена. Запустите install_task.bat от имени Администратора.
        pause
        exit /b 1
    )
)

echo Готово. Watchdog поднимет сервер через 5 секунд.
timeout /t 6 /nobreak >nul
echo Сервер запущен.
