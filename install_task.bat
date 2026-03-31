@echo off
REM Запускать от имени Администратора!
set TASK_NAME=FlaskTesterApp
set PROJECT_DIR=%~dp0
REM Используем venv если есть, иначе системный pythonw
if exist "%PROJECT_DIR%.venv\Scripts\pythonw.exe" (
    set PYTHONW=%PROJECT_DIR%.venv\Scripts\pythonw.exe
) else (
    for /f "delims=" %%i in ('where pythonw 2^>nul') do set PYTHONW=%%i
    if not defined PYTHONW (
        for /f "delims=" %%i in ('where python 2^>nul') do set PYTHONW=%%i
    )
)

if not defined PYTHONW (
    echo ОШИБКА: pythonw.exe не найден. Установите Python.
    pause
    exit /b 1
)
set WATCHDOG=%PROJECT_DIR%watchdog.py

echo Удаление старой задачи...
schtasks /delete /tn "%TASK_NAME%" /f >nul 2>&1

echo Создание задачи для пользователя %USERNAME%...
schtasks /create /tn "%TASK_NAME%" /tr "\"%PYTHONW%\" \"%WATCHDOG%\"" /sc onlogon /ru "%USERNAME%" /f

echo.
echo Готово! Сайт будет запускаться при входе в Windows (без окна CMD).
echo.
echo Запустить сейчас:
start "" "%PYTHONW%" "%WATCHDOG%"
echo.
echo Управление: taskschd.msc
echo Удалить задачу: schtasks /delete /tn "%TASK_NAME%" /f
pause