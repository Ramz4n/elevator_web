@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
call venv\Scripts\activate

:retry
echo Сайт со статистикой запущен. НЕ ЗАКРЫВАЙТЕ ЭТО ОКНО, СВЕРНИТЕ ЕГО!
python tester.py > app.log 2>&1

if %errorlevel% neq 0 (
    echo Ошибка при выполнении tester.py, возможно, нет интернета.
    echo Повторная попытка через 10 секунд...
    timeout /t 10 /nobreak >nul
    goto retry
)

echo Скрипт успешно завершён.
pause
