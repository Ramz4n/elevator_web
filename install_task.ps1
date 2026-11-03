# Создаёт задачи проекта в планировщике: сайт (watchdog) и бэкап.
# Запускается из install_task.bat. Повторный запуск заменяет задачи, а не создаёт дубли.
param(
    [Parameter(Mandatory = $true)][string]$ProjectDir,
    [Parameter(Mandatory = $true)][string]$PythonW,
    [int]$BackupEveryHours = 1
)

$ErrorActionPreference = 'Stop'

$User = "$env:USERDOMAIN\$env:USERNAME"
# Только для вошедшего пользователя: так виден диск Google Drive, пароль не нужен
$Principal = New-ScheduledTaskPrincipal -UserId $User -LogonType Interactive -RunLevel Limited

# --- Сайт: при входе в Windows, без лимита времени (по умолчанию Windows снимает задачу через 3 дня) ---
$SiteAction = New-ScheduledTaskAction -Execute $PythonW -Argument "`"$ProjectDir\watchdog.py`"" -WorkingDirectory $ProjectDir
$SiteTrigger = New-ScheduledTaskTrigger -AtLogOn -User $User
$SiteSettings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
Register-ScheduledTask -TaskName 'FlaskTesterApp' -Action $SiteAction -Trigger $SiteTrigger `
    -Settings $SiteSettings -Principal $Principal -Force | Out-Null
Write-Host "Задача 'FlaskTesterApp' создана: запуск при входе в Windows."

# --- Бэкап: каждые $BackupEveryHours ч, начиная со следующего целого часа ---
$Now = Get-Date
$BackupAction = New-ScheduledTaskAction -Execute "$ProjectDir\backup.bat" -WorkingDirectory $ProjectDir
$BackupTrigger = New-ScheduledTaskTrigger -Once -At $Now.Date.AddHours($Now.Hour + 1) `
    -RepetitionInterval (New-TimeSpan -Hours $BackupEveryHours)
$BackupSettings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Hours 2) `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName 'backup' -Action $BackupAction -Trigger $BackupTrigger `
    -Settings $BackupSettings -Principal $Principal -Force | Out-Null
Write-Host "Задача 'backup' создана: каждые $BackupEveryHours ч."

# --- Запуск сайта сейчас, если он ещё не работает (иначе будет два watchdog на одном порту) ---
$Running = Get-CimInstance Win32_Process -Filter "Name LIKE 'python%'" |
    Where-Object { $_.CommandLine -like '*watchdog.py*' }
if ($Running) {
    Write-Host "Сайт уже запущен, перезапуск не нужен."
} else {
    Start-ScheduledTask -TaskName 'FlaskTesterApp'
    Write-Host "Сайт запущен."
}
