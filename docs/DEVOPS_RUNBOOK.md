# Памятка DevOps — GigaAM Speakers 0.2.0

Это отдельное интерактивное Windows x64 приложение. Бот, сервер, Windows Service, meeting API, Docker/Vexa, интеграционные лицензии и виртуальный кабель не нужны. Основной README на английском. Источник GigaAM-Meeting не изменяется.

Команды выполнять по порядку в одной обычной PowerShell-сессии. Ошибка шага останавливает развёртывание. Не менять защиту Windows, Firewall, ExecutionPolicy, long paths и корпоративные политики.

## 1. Передача пользователю

Передайте **GigaAM-Speakers-windows-x64.zip** и matching **.zip.sha256**. Полный ZIP содержит EXE, CPU runtime, GigaAM, две модели диаризации, шрифты, лицензии и curated provenance. Source ZIP предназначен разработчику и не содержит runtime/весов. Старый checksum GigaAM-Meeting 0.1.2 к новому ZIP не подходит.

SHA256 подтверждает целостность относительно опубликованного значения, не является цифровой подписью. EXE не подписан Authenticode; ограничения Windows не обходить.

## 2. Скачать конкретный Release после его публикации

Для локального артефакта пропустите скачивание и вручную задайте пути к ZIP/sidecar в следующем разделе. Публичный GitHub не требует токена.

```powershell
$ErrorActionPreference = 'Stop'
$taskRepo = 'AssylbekGizatov/gigaam-local-speaker-transcriber'
$taskTag = 'v0.2.0'
$taskBase = Join-Path $env:LOCALAPPDATA 'GigaAMSpeakers'
$taskDownload = Join-Path $taskBase ('downloads/' + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $taskDownload | Out-Null
$taskRelease = Invoke-RestMethod -Uri ('https://api.github.com/repos/' + $taskRepo + '/releases/tags/' + $taskTag) -Headers @{'User-Agent'='GigaAMDeployment'}
$taskZipAssets = @($taskRelease.assets | Where-Object {$_.name -eq 'GigaAM-Speakers-windows-x64.zip'})
$taskShaAssets = @($taskRelease.assets | Where-Object {$_.name -eq 'GigaAM-Speakers-windows-x64.zip.sha256'})
if ($taskZipAssets.Count -ne 1 -or $taskShaAssets.Count -ne 1) { throw 'Нет однозначной пары ZIP/SHA' }
$taskZip = Join-Path $taskDownload $taskZipAssets[0].name
$taskSha = Join-Path $taskDownload $taskShaAssets[0].name
Invoke-WebRequest -Uri $taskZipAssets[0].browser_download_url -OutFile $taskZip -UseBasicParsing
Invoke-WebRequest -Uri $taskShaAssets[0].browser_download_url -OutFile $taskSha -UseBasicParsing
```

При сетевом запрете обратиться к администратору. Прерванное скачивание не запускать; повторять в новой папке.

## 3. Проверка SHA и полная распаковка

Если используете локальный ZIP, сначала:

```powershell
$ErrorActionPreference = 'Stop'
$taskZip = Read-Host 'Полный путь к runtime ZIP'
$taskSha = Read-Host 'Полный путь к matching .zip.sha256'
$taskBase = Join-Path $env:LOCALAPPDATA 'GigaAMSpeakers'
```

Затем, для обоих вариантов:

```powershell
$taskExpected = ((Get-Content -LiteralPath $taskSha -Raw).Trim() -split '[ ]+')[0]
if ($taskExpected -notmatch '^[0-9a-fA-F]{64}$') { throw 'Неверный формат SHA256' }
$taskActual = (Get-FileHash -LiteralPath $taskZip -Algorithm SHA256).Hash
if ($taskActual -ne $taskExpected) { throw 'Хеш не совпал: не запускайте архив' }
$taskInstall = Join-Path $taskBase ('apps/v0.2.0-' + [Guid]::NewGuid().ToString('N'))
if (Test-Path -LiteralPath $taskInstall) { throw 'Каталог занят' }
Expand-Archive -LiteralPath $taskZip -DestinationPath $taskInstall
$taskApp = Join-Path $taskInstall 'GigaAM-Speakers'
$taskExe = Join-Path $taskApp 'GigaAM-Speakers.exe'
foreach ($taskRequired in @('GigaAM-Speakers.exe','_internal','models/gigaam','models/diarization','fonts','licenses','provenance','file-manifest.json')) {
    if (-not (Test-Path -LiteralPath (Join-Path $taskApp $taskRequired))) { throw ('Неполная распаковка: ' + $taskRequired) }
}
```

Не использовать -Force, не устанавливать поверх работающей программы, не запускать EXE из виртуальной папки ZIP.

## 4. Проверка всех файлов

```powershell
$taskManifest = Get-Content -LiteralPath (Join-Path $taskApp 'file-manifest.json') -Raw | ConvertFrom-Json
$taskRoot = [IO.Path]::GetFullPath($taskApp).TrimEnd([IO.Path]::DirectorySeparatorChar)
$taskPrefix = $taskRoot + [IO.Path]::DirectorySeparatorChar
foreach ($taskEntry in $taskManifest) {
    if ([IO.Path]::IsPathRooted($taskEntry.file)) { throw 'Абсолютный путь в manifest' }
    $taskPath = [IO.Path]::GetFullPath((Join-Path $taskRoot $taskEntry.file))
    if (-not $taskPath.StartsWith($taskPrefix,[StringComparison]::OrdinalIgnoreCase)) { throw 'Путь выходит за установку' }
    $taskFile = Get-Item -LiteralPath $taskPath
    if ($taskFile.PSIsContainer -or $taskFile.Length -ne $taskEntry.size) { throw ('Неверный размер: ' + $taskEntry.file) }
    if ((Get-FileHash -LiteralPath $taskPath -Algorithm SHA256).Hash -ne $taskEntry.sha256) { throw ('Неверный хеш: ' + $taskEntry.file) }
}
Write-Output ('Проверено файлов: ' + @($taskManifest).Count)
```

Manifest сам покрыт SHA исходного ZIP. Сохранить полный licenses/NOTICE/provenance.

## 5. Запуск без автоматической записи

```powershell
$taskData = Join-Path $taskBase 'transcripts'
if (-not (Test-Path -LiteralPath $taskData)) { New-Item -ItemType Directory -Path $taskData | Out-Null }
Start-Process -FilePath $taskExe -WorkingDirectory $taskApp -WindowStyle Normal
```

В окне выбрать микрофон, loopback выхода звонка и папку данных. Loopback слышит **все приложения выбранного выхода**, включая уведомления; захвата только Teams/Zoom нет. Наушники работают без кабеля.

Диаризация включена в UI по умолчанию; toggle применяется до следующего сеанса. WAV выключен по умолчанию. Получить согласия участников и учесть правила организации. Перед проверкой уровней отметить permission; трёхсекундная проверка сбрасывает его. Снова разрешить захват и **самостоятельно нажать «Начать»**.

Метки предварительные, count — оценка голосов. Unknown/overlap не скрываются. Pause выключает потоки, resume явное. Stop завершает остаток очереди без перенумерации, но без full-meeting acoustic reanalysis. После drain сохранить TXT/MD/DOCX/PDF или **JSON для точных Word timestamps/source/speaker metadata**.

## 6. Диагностика без живого захвата

```powershell
$taskReports = Join-Path $taskBase ('reports/' + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $taskReports | Out-Null
$taskSelfReport = Join-Path $taskReports 'selftest.json'
$taskProc = Start-Process -FilePath $taskExe -WorkingDirectory $taskApp -WindowStyle Hidden -Wait -PassThru -ArgumentList @('--self-test',('"' + $taskSelfReport + '"'))
if ($taskProc.ExitCode -ne 0) { throw 'Self-test failed' }
$taskSelf = Get-Content -LiteralPath $taskSelfReport -Raw | ConvertFrom-Json
if ($taskSelf.status -ne 'passed' -or $taskSelf.diarization.status -ne 'passed') { throw 'Проверка не прошла' }
$taskSelf | Select-Object status,elapsed_seconds,diarization,blocked_python_network_attempts
```

Self-test использует публичный WAV, реальные локальные CPU модели, synthetic format exports. Живые устройства не открываются. Явные тестовые файлы появляются рядом в selftest-artifacts. Новое имя обязательно: existing report не перезаписывается.

Метаданные устройств:

```powershell
$taskDevices = Join-Path $taskReports 'devices.json'
$taskDevicesProc = Start-Process -FilePath $taskExe -WorkingDirectory $taskApp -WindowStyle Hidden -Wait -PassThru -ArgumentList @('--list-devices',('"' + $taskDevices + '"'))
if ($taskDevicesProc.ExitCode -ne 0) { throw 'Enumeration failed' }
```

Список устройств хранить локально. CLI не поддерживает автоматический Start, meeting URL или токен.

## 7. Сборка разработчиком

Нужны Windows x64, PowerShell7, Git, официальный Python3.12.10 x64 с Tcl/Tk. [BUILD.md](BUILD.md) объясняет pipeline и лицензии.

```powershell
$taskSource = 'C:/gigaam-speakers-src-01'
if (Test-Path -LiteralPath $taskSource) { throw 'Выберите новый путь' }
git clone https://github.com/AssylbekGizatov/gigaam-local-speaker-transcriber.git $taskSource
if ($LASTEXITCODE -ne 0) { throw 'Clone failed' }
Set-Location -LiteralPath $taskSource
git rev-parse HEAD
$taskBuild = 'C:/gigaam-speakers-build-01'
if (Test-Path -LiteralPath $taskBuild) { throw 'Выберите новый build path' }
New-Item -ItemType Directory -Path $taskBuild | Out-Null
py -3.12 -c "import sys,struct,tkinter; assert sys.version_info[:3]==(3,12,10); assert struct.calcsize('P')==8"
if ($LASTEXITCODE -ne 0) { throw 'Python x64/version/Tcl mismatch' }
py -3.12 -m venv (Join-Path $taskBuild 'v')
if ($LASTEXITCODE -ne 0) { throw 'Venv failed' }
$taskPython = Join-Path $taskBuild 'v/Scripts/python.exe'
./build/build.ps1 -Python $taskPython -Output (Join-Path $taskBuild 'release')
```

При ограничении доступа к C:/ выбрать другой короткий разрешённый путь, не менять политики. Activation.ps1 не нужен. Dependency/model acquisition выполняется только на build-time; уже изменённые веса не заменяются скрыто.

Порядок: pinned packages → GigaAM/диаризация acquire → минимальный проверяемый upstream patch → pytest/Ruff → PyInstaller → source match → local models/fonts/docs/licenses → frozen test/network sampling → current curated evidence → PE audit → ZIP/SHA/manifest. Не публиковать сырые pip reports и пользовательские данные.

Проверка CRC:

```powershell
$taskBuiltZip = Join-Path $taskBuild 'release/GigaAM-Speakers-windows-x64.zip'
& $taskPython -c "import sys,zipfile; z=zipfile.ZipFile(sys.argv[1]); bad=z.testzip(); z.close(); assert bad is None" $taskBuiltZip
if ($LASTEXITCODE -ne 0) { throw 'CRC failed' }
Get-FileHash -LiteralPath $taskBuiltZip -Algorithm SHA256
```

Повторно распаковать новый ZIP и проверить разделы4/6. Локальный Python3.12.3 используется только для честно обозначенных local evidence; canonical CI —3.12.10. Побайтная воспроизводимость ZIP не заявляется.

Source archive после завершения/ревью документов:

```powershell
$taskSnapshot = Join-Path $taskBuild ('snapshot-' + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $taskSnapshot | Out-Null
& $taskPython build/source_package.py --root . --audit (Join-Path $taskSnapshot 'audit.json') --zip (Join-Path $taskSnapshot 'GigaAM-Speakers-source-v0.2.0.zip') --finalized-docs
if ($LASTEXITCODE -ne 0) { throw 'Source audit failed' }
```

Не архивировать весь workspace с credentials, venv, private recordings и raw reports.

## 8. GitHub CI и Release

Workflow windows.yml ручной, Windows2022/Python3.12.10. Для build-only:

В JSON для `gh workflow run --json` параметр `publish` передаётся строкой
`'false'` или `'true'`: GitHub CLI читает значения inputs как строки, а GitHub
Actions преобразует их по объявленному в workflow типу `boolean`.

```powershell
$taskRepo = 'AssylbekGizatov/gigaam-local-speaker-transcriber'
gh auth status
if ($LASTEXITCODE -ne 0) { throw 'Нужна разрешённая авторизация GitHub CLI' }
@{publish='false';tag='v0.2.0'} | ConvertTo-Json -Compress | gh workflow run windows.yml --repo $taskRepo --ref main --json
if ($LASTEXITCODE -ne 0) { throw 'Dispatch failed' }
gh run list --repo $taskRepo --workflow windows.yml --limit 10 --json databaseId,headSha,status,conclusion,url
$taskRunId = Read-Host 'ID вашего run; сверьте время и headSha'
gh run watch $taskRunId --repo $taskRepo --exit-status
if ($LASTEXITCODE -ne 0) { throw 'Gates failed; не публиковать' }
```

Сохранять run и source commit. Не брать «самый последний» при совместной работе. При ошибке посмотреть gh run view RUN_ID --repo REPO --log-failed локально.

Для нового кода: version/CHANGELOG/README/RELEASE/test report → review выбранных файлов → commit/PR по branch policy → build-only → приёмка. Пример будущего номера v0.2.1:

```powershell
$taskNewTag = 'v0.2.1'
$taskTags = @(git ls-remote --tags origin ('refs/tags/' + $taskNewTag))
if ($LASTEXITCODE -ne 0 -or $taskTags.Count -ne 0) { throw 'Tag не проверен или занят' }
$taskReleaseTags = gh api --paginate ('repos/' + $taskRepo + '/releases') --jq '.[].tag_name'
if ($LASTEXITCODE -ne 0 -or @($taskReleaseTags) -contains $taskNewTag) { throw 'Release не проверен или занят' }
@{publish='true';tag=$taskNewTag} | ConvertTo-Json -Compress | gh workflow run windows.yml --repo $taskRepo --ref main --json
if ($LASTEXITCODE -ne 0) { throw 'Publish dispatch failed' }
```

Existing tag/asset не заменять. Workflow заново собирает ZIP, checksum может отличаться от build-only. После Release заново скачать и проверить опубликованный ZIP, manifest, self-test, run headSha/tag. Для docs-only обновлений новый binary release не нужен.

## 9. Сеть и ручная приёмка

Guard запрещает Python network operations, ORT telemetry отключена. Endpoint sampling PID во время self-test не гарантирует отсутствие коротких/native/system-broker обращений. При сбоях доступа «0 наблюдений» не доказательство.

С разрешённым доступом к таблицам endpoints, из исходников:

```powershell
Get-NetTCPConnection -ErrorAction Stop | Out-Null
Get-NetUDPEndpoint -ErrorAction Stop | Out-Null
$taskAudit = Join-Path $taskBuild ('net-' + [Guid]::NewGuid().ToString('N'))
./build/audit_runtime.ps1 -Exe $taskExe -ReportDirectory $taskAudit
```

Скрипт меняет только child runtime search environment и возвращает его, не Firewall. Clean Windows без Python и с отключённым интернетом проверяется отдельно на разрешённой VM/машине; не заявлять без фактического прогона.

Приёмка пользователем: mic, loopback, вместе, несколько людей у одного mic, наушники, динамики/echo/свой ответ, short turns, overlap, Pause/Stop/new session/headset change, реальная длинная сессия, RU/KK/EN и один голос с переключением языков. Fake900sec clock gap не равен 15-минутному живому тесту. Фиксировать длительность, параметры и известный текст.

## 10. Обновление и откат

Stop → drain → export → close. Новый ZIP — в новый каталог с проверкой SHA/manifest/self-test. Старую полную папку сохранять до приёмки. Для rollback вручную открыть предыдущий EXE с его полным runtime; не смешивать DLL/models. Выбрать устройства/permission заново. Данные хранить отдельно; ничего автоматически не удалять.

| Проблема | Действие |
| --- | --- |
| Missing/corrupt speaker model | Полный проверенный ZIP или явно выключить диаризацию; нет runtime download |
| Нет собеседников | Выход звонка и loopback должны совпадать |
| Unknown/короткая реплика | Не хватает чистой речи; ID не выдумывается |
| Один голос получил другой ID | Возможны комнатные/codec/noise false splits; это оценка |
| Overlap с одним ID | Второй голос может быть неизвестен; нет двух независимых текстов |
| CPU lag/drop | Дождаться drain, уменьшить нагрузку/источники следующего сеанса |
| Headset changed | Stop/refresh/новый явный выбор, без fallback |
| Security block | Остановиться и обратиться к администратору |
| Export failed | Доступная локальная папка/новое имя, existing files не заменяются |

Передача сопровождения: version/tag/source commit, ZIP SHA/size, run, source/frozen results, сеть/границы метода, manual tests/duration/languages, known limitations, data retention (держать локально), сохранённая версия rollback. Embeddings не публиковать. Windows paging/dumps/backups/sync имеют отдельные ограничения.

Результаты: [TESTING.md](TESTING.md). Диаризация: [DIARIZATION.md](DIARIZATION.md). Приватность: [PRIVACY.md](PRIVACY.md). Модели/лицензии: [DIARIZATION_RESEARCH.md](DIARIZATION_RESEARCH.md). Синтаксическая проверка команд не означает полного повторного развёртывания на чистой машине.

