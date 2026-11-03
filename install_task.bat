@echo off
chcp 65001 >nul
REM Запускать от имени Администратора!
REM Создаёт задачи FlaskTesterApp (сайт) и backup. Повторный запуск заменяет их.
set BACKUP_EVERY_HOURS=1

set PROJECT_DIR=%~dp0
set PROJECT_DIR=%PROJECT_DIR:~0,-1%

REM Используем venv если есть, иначе системный pythonw
if exist "%PROJECT_DIR%\.venv\Scripts\pythonw.exe" (
    set PYTHONW=%PROJECT_DIR%\.venv\Scripts\pythonw.exe
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

echo Python: %PYTHONW%
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%PROJECT_DIR%\install_task.ps1" -ProjectDir "%PROJECT_DIR%" -PythonW "%PYTHONW%" -BackupEveryHours %BACKUP_EVERY_HOURS%
if errorlevel 1 (
    echo.
    echo ОШИБКА при создании задач.
    pause
    exit /b 1
)

echo.
echo Готово! Сайт запускается при входе в Windows, бэкап — каждые %BACKUP_EVERY_HOURS% ч.
echo Для запуска без ручного входа нужен автовход в Windows (netplwiz).
echo.
echo Управление: taskschd.msc
pause
