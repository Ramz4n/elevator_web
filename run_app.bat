@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
call venv\Scripts\activate

:retry
echo [%date% %time%] Проверка соединения с БД...

REM Проверка соединения с сервером БД (замени DB_HOST на свой хост)
ping -n 1 localhost >nul 2>&1
if %errorlevel% neq 0 (
    echo [%date% %time%] Нет соединения. Повтор через 10 сек...
    timeout /t 10 /nobreak >nul
    goto retry
)

echo [%date% %time%] Сайт запущен. НЕ ЗАКРЫВАЙТЕ ЭТО ОКНО!
echo [%date% %time%] Запуск сервера >> app.log
python tester.py >> app.log 2>&1

echo [%date% %time%] Сервер остановлен (код: %errorlevel%). Перезапуск через 5 сек...
echo [%date% %time%] Сервер остановлен (код: %errorlevel%) >> app.log
timeout /t 5 /nobreak >nul
goto retry
