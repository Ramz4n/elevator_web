# Бэкап баз MariaDB: проверка дампа, хранение копий и копирование в папку Google Drive.
# Запускается из backup.bat (задача backup в планировщике, каждый час).
# На компьютере хранятся все бэкапы за $LocalKeepDays дней,
# в Google Drive — первый удачный бэкап каждого дня за $GDriveKeepDays дней.
# backup.bat -Force — сохранить бэкап, даже если он намного меньше прошлого.
param(
    [switch]$Force,
    [string]$MysqlDump = 'D:\mariadb\bin\mysqldump.exe',
    [string]$EnvFile = (Join-Path $PSScriptRoot '.env'),  # DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, имена баз
    [string]$BackupDir = 'D:\backup',
    [string]$GDriveDir = 'G:\Мой диск\backup',  # папка Google Drive для компьютера
    [int]$LocalKeepDays = 14,
    [int]$GDriveKeepDays = 30,
    [double]$MinSizeRatio = 0.5                # дамп меньше 50% прошлого — данные пропали, не сохраняем
)

$LogFile = Join-Path $BackupDir 'backup.log'

# Читает KEY=VALUE из .env (как python-dotenv: без комментариев, кавычки снимаются)
function Read-EnvFile($Path) {
    $vars = @{}
    foreach ($line in Get-Content $Path -Encoding UTF8) {
        if ($line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$') {
            $vars[$Matches[1]] = $Matches[2] -replace '^"(.*)"$', '$1' -replace "^'(.*)'$", '$1'
        }
    }
    return $vars
}

function Write-Log($Message) {
    $line = "[$(Get-Date -Format 'dd.MM.yyyy HH:mm:ss')] $Message"
    Write-Host $line
    Add-Content -Path $LogFile -Value $line -Encoding UTF8
}

# Файл-предупреждение рядом с бэкапами, чтобы проблему было видно в Google Drive
function Get-WarningName($Database) { "ВНИМАНИЕ_бэкап_${Database}_не_сохранён.txt" }

function Set-Warning($Database, $Reason) {
    $text = "Бэкап $Database от $(Get-Date -Format 'dd.MM.yyyy HH:mm') НЕ сохранён.`r`nПричина: $Reason`r`nПодробности: $LogFile"
    foreach ($dir in $BackupDir, $GDriveDir) {
        if (Test-Path $dir) { Set-Content -Path (Join-Path $dir (Get-WarningName $Database)) -Value $text -Encoding UTF8 }
    }
}

function Clear-Warning($Database) {
    foreach ($dir in $BackupDir, $GDriveDir) {
        if (Test-Path $dir) { Remove-Item (Join-Path $dir (Get-WarningName $Database)) -ErrorAction SilentlyContinue }
    }
}

# Бэкапы базы в папке с датой из имени: <база>_yyyy-MM-dd_HH-mm.zip
function Get-Backups($Dir, $Database) {
    $pattern = '^' + [regex]::Escape($Database) + '_(\d{4}-\d{2}-\d{2})_\d{2}-\d{2}\.zip$'
    Get-ChildItem -Path $Dir -Filter "${Database}_*.zip" | ForEach-Object {
        if ($_.Name -match $pattern) {
            [pscustomobject]@{ File = $_; Date = [datetime]::ParseExact($Matches[1], 'yyyy-MM-dd', $null) }
        }
    }
}

# Удаляет бэкапы старше $KeepDays дней. Вызывается только после удачного бэкапа,
# поэтому при сбоях последние хорошие копии не пропадают
function Remove-OldBackups($Dir, $Database, $KeepDays) {
    $cutoff = (Get-Date).Date.AddDays(-$KeepDays)
    Get-Backups $Dir $Database | Where-Object { $_.Date -lt $cutoff } | ForEach-Object {
        Remove-Item $_.File.FullName
        Write-Log "Удалён старый бэкап: $($_.File.FullName)"
    }
}

function Test-Dump($TempSql, $MainTable, $SizeFile) {
    if (-not (Test-Path $TempSql) -or (Get-Item $TempSql).Length -eq 0) {
        return 'файл дампа пустой'
    }
    # mysqldump пишет эту строку последней, только если дамп дошёл до конца
    if (-not (Get-Content $TempSql -Tail 5 | Select-String -SimpleMatch '-- Dump completed' -Quiet)) {
        return 'дамп оборван (нет строки "Dump completed")'
    }
    if (-not (Select-String -Path $TempSql -SimpleMatch "CREATE TABLE ``$MainTable``" -Quiet)) {
        return "в дампе нет таблицы $MainTable"
    }
    if (-not (Select-String -Path $TempSql -SimpleMatch "INSERT INTO ``$MainTable``" -Quiet)) {
        return "таблица $MainTable пустая"
    }
    $size = (Get-Item $TempSql).Length
    if ((Test-Path $SizeFile) -and -not $Force) {
        $lastSize = [long](Get-Content $SizeFile)
        if ($size -lt $lastSize * $MinSizeRatio) {
            return ("дамп {0:N1} МБ, а прошлый был {1:N1} МБ — похоже, данные пропали. " +
                    "Если удаление было намеренным, запустите backup.bat -Force") -f ($size / 1MB), ($lastSize / 1MB)
        }
    }
    return $null
}

# Делает дамп одной базы, проверяет и сохраняет в zip. Возвращает путь к zip.
function Backup-Database($Database, $MainTable, $Connection) {
    $tempSql = Join-Path $BackupDir "_tmp_$Database.sql"
    $sizeFile = Join-Path $BackupDir "last_size_$Database.txt"
    try {
        Write-Log "Начало бэкапа $Database"

        # Пароль через переменную окружения, чтобы его не было видно в командной строке процесса
        $env:MYSQL_PWD = $Connection.Password
        try {
            $output = & $MysqlDump "--host=$($Connection.Host)" "--port=$($Connection.Port)" "--user=$($Connection.User)" `
                --single-transaction --triggers --default-character-set=utf8mb4 `
                "--result-file=$tempSql" $Database 2>&1 | ForEach-Object { "$_" } | Out-String
        }
        finally {
            Remove-Item Env:MYSQL_PWD -ErrorAction SilentlyContinue
        }
        if ($LASTEXITCODE -ne 0) {
            throw "mysqldump завершился с ошибкой (код $LASTEXITCODE): $($output.Trim())"
        }

        $problem = Test-Dump $tempSql $MainTable $sizeFile
        if ($problem) { throw $problem }

        $size = (Get-Item $tempSql).Length
        $name = "{0}_{1}" -f $Database, (Get-Date -Format 'yyyy-MM-dd_HH-mm')
        $sql = Join-Path $BackupDir "$name.sql"
        $zip = Join-Path $BackupDir "$name.zip"
        Move-Item $tempSql $sql -Force
        Compress-Archive -Path $sql -DestinationPath $zip -Force
        Remove-Item $sql
        Set-Content -Path $sizeFile -Value $size
        Write-Log ("Бэкап сохранён: {0} (дамп {1:N1} МБ)" -f $zip, ($size / 1MB))
        Clear-Warning $Database
        Remove-OldBackups $BackupDir $Database $LocalKeepDays
        return $zip
    }
    catch {
        Remove-Item $tempSql -ErrorAction SilentlyContinue
        Write-Log "ОШИБКА ($Database): $_"
        Set-Warning $Database $_
        return $null
    }
}

New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null

if (-not (Test-Path $EnvFile)) {
    Write-Log "ОШИБКА: не найден файл $EnvFile"
    exit 1
}
$envVars = Read-EnvFile $EnvFile
foreach ($key in 'DB_USER', 'DB_PASSWORD', 'DB_NAME_JOURNAL', 'DB_NAME_SITE') {
    if (-not $envVars[$key]) {
        Write-Log "ОШИБКА: в $EnvFile нет $key"
        exit 1
    }
}
$connection = @{
    Host     = if ($envVars['DB_HOST']) { $envVars['DB_HOST'] } else { 'localhost' }
    Port     = if ($envVars['DB_PORT']) { $envVars['DB_PORT'] } else { '3306' }
    User     = $envVars['DB_USER']
    Password = $envVars['DB_PASSWORD']
}

# База => таблица, без данных в которой бэкап считается битым
$databases = [ordered]@{
    $envVars['DB_NAME_JOURNAL'] = if ($envVars['DB_TABLE']) { $envVars['DB_TABLE'] } else { 'zayavki' }
    $envVars['DB_NAME_SITE']    = 'users'
}

$exitCode = 0
$zips = @()
foreach ($db in $databases.Keys) {
    $zip = Backup-Database $db $databases[$db] $connection
    if ($zip) { $zips += , @($db, $zip) } else { $exitCode = 1 }
}

# Google Drive: локальные бэкапы уже сохранены, поэтому ошибка здесь их не отменяет
if ($zips.Count -gt 0) {
    try {
        if (-not (Test-Path (Split-Path $GDriveDir -Qualifier))) {
            throw "диск Google Drive ($(Split-Path $GDriveDir -Qualifier)) не найден — запущен ли Google Drive?"
        }
        New-Item -ItemType Directory -Force -Path $GDriveDir | Out-Null
        foreach ($item in $zips) {
            # В Google Drive — только первый удачный бэкап за день
            $today = (Get-Date).Date
            if (Get-Backups $GDriveDir $item[0] | Where-Object { $_.Date -eq $today }) { continue }
            Copy-Item $item[1] $GDriveDir
            Write-Log "Скопирован в Google Drive: $(Join-Path $GDriveDir (Split-Path $item[1] -Leaf))"
            Remove-OldBackups $GDriveDir $item[0] $GDriveKeepDays
        }
    }
    catch {
        Write-Log "ОШИБКА копирования в Google Drive: $_"
        if ($exitCode -eq 0) { $exitCode = 2 }
    }
}

exit $exitCode
