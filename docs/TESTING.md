# Проверки GigaAM Speakers v0.2.0

Локальные проверки ниже выполнены **15 октября 2026**; результат финального опубликованного CI указан отдельно. Исходный GigaAM-Meeting v0.1.2 не изменён. Старые файлы verification/v0.1.x — только историческая основа, не доказательство новой диаризации.

## Исходники и контракты

Историческая локальная проверка перед исправлением Windows checkout: **220 pytest passed за 29,63 с**, Ruff без ошибок. Это исходный локальный отчёт, а не число тестов финального CI. Проверки охватывают прежний WASAPI/streaming/echo/export/lifecycle и новые speaker contracts, точные Word records, источник отдельно от говорящего, speaker registry, unknown/overlap, source/time boundary ownership, паузы, bounded history/capacity и JSON.

Финальный CI [38791679693](https://github.com/AssylbekGizatov/gigaam-local-speaker-transcriber/actions/runs/38791679693) на Windows 2022/Python 3.12.10 завершился успешно: **222 pytest passed за 11,41 с**, Ruff без ошибок. Его source commit и опубликованный tag `v0.2.0` — `5074258caf7639b503bc0efe92cc57a9e852beaa`. Добавленные два теста проверяют включение `.gitattributes` в исходники и реальный свежий Git checkout с `autocrlf=true`: все pinned license/binary/core bytes сохранены. Отрицательный контроль без атрибутов воспроизводит изменение LF→CRLF и прежнюю ошибку SHA256 лицензии.

[Отчёт об опубликованном Release](verification/v0.2.0/published-release.json) связывает окончательные CI, tag и конкретные опубликованные артефакты. Существующие tag и assets не заменяются последующими обновлениями документации.

Новый backend: 28 детерминированных тестов. Проверяются shared IDs независимо от канала/текста языка, несколько голосов у одного mic, short/uncertain embedding, max64profiles, история120sec/2048turns, temporal gaps, failed-window masking и exactWord conservation. Это правила и regression tests, не DER-бенчмарк.

Интеграция: реальные StreamProcessor/SessionManager с fake PCM/model/capture и controlled diarizer. Проверяются split внутри фрагмента, delayed echo edits удаления всех display parts, pause/stop/finalization порядок, missing models до capture, ASR без диаризации и ошибки анализа/annotation/finalization. Семь malformed annotation cases сохраняют первоначальные слова/времена и unknown label. На 320 параграфах служебная карта остаётся ограниченной текущей историей эха, а текст сохраняется. Длинный fake clock gap не равен длинному аппаратному сеансу.

## Настоящие CPU модели и разрешённые записи

[Public RU/EN report](verification/v0.2.0/public-fixture-report.json) и [two-voice/overlap report](verification/v0.2.0/multi-speaker-window-report.json) относятся к финальному SHA256 diarization.py. Никакие записи пользователя, meeting URLs, устройства и private paths не публикуются.

- Публичный пример GigaAM: русский, 11,29 с, 26 распознанных слов. Пример LibriSpeech: английский, 5,855 с, 17 слов; CC BY4.0, Vassil Panayotov et al./OpenSLR12. Exact fixture SHA/source/attribution в отчёте; английский WAV не входит в ZIP.
- Повтор RU через другой источник и смоделированную паузу900sec сохранил Спикера1; другой голос EN получил Спикера2; gain0,3 RU повтор сохранил Спикера1. Word object identity/order/text/times сохранены. При методе report некоторые boundary words unknown: RU21assigned/5unknown, EN16/1. Это не потеря текста.
- Диаризация этих отдельных клипов заняла около0,49–1,52с на CPU. Это небольшие примеры, не аппаратный SLA и не установленный DER.
- Один источник в одном окне: RU4s + silence0,25s + EN4s → **два профиля, 24 слова**, внутрифрагментный split, exact Word records. 11слов первого/12второго/1unknown; intervals end>start, chronological numbering.
- Искусственное одновременное смешивание этих голосов → **3,488с обнаруженного overlap**, только **4 ASR слова** сохранены один раз с unknown/overlap. Чистых embeddings недостаточно, фиктивных speaker profiles не создано. Это поддержка отметки перекрытия, **не разделение двух голосов или полнота обоих текстов**.
- Python network guard:0attempts. Эти тесты не открывали микрофон/loopback и не являются независимой OS network certification.

## Локальная сборка: исторический self-test

Историческая локальная Windows x64 сборка использовала Python runtime3.12.3; успешно выполненный canonical CI использовал3.12.10. Поставляется самостоятельный runtime, а не вызов системного Python. Точный installed supplier graph и readonly reuse source в provenance соответствующей сборки. Побайтная воспроизводимость ZIP не заявляется; времена и выборки локального self-test ниже не приписываются архиву CI.

Локальный GigaAM-Speakers.exe, проверенный до выпуска CI:

- frozen source attestation: **15 модулей** совпали с финальными исходниками;
- actual offline self-test: **passed, 37,138с**;
- CPU speaker inference: **4,734с**, локальные hash-pinned модели, CPUExecutionProvider,26Wordrecords exact, один голос сохранил ID между источниками/gain и900sec gap;
- настоящий GigaAM/public PCM, консервативный synthetic echo check и пять экспортов TXT/MD/DOCX/PDF/JSON прошли; existingfiles сохранены;
- child PATH толькоWindows, PYTHONHOME/PYTHONPATH очищены. Это runtime search independence, не удаление Python с хоста;
- сеть: **66 endpoint snapshots,0TCP,0UDP,0queryfailures, exit0**, Pythonguard0. При ошибках queries обновлённый аудит не выдаёт ложный успешный нулевой результат;
- захват hardware в self-test не запускался.

Эти локальные отчёты сохранены в текущем verification/v0.2.0. Они не подменяют результаты self-test другого архива. PE audit, ZIP SHA/CRC/manifest проверяются отдельно для каждого конкретного архива.

## Опубликованный канонический ZIP: CI и проверка скачанных байтов

Каноническая [сборка v0.2.0](https://github.com/AssylbekGizatov/gigaam-local-speaker-transcriber/releases/tag/v0.2.0) создана успешным CI `38791679693` на commit `5074258caf7639b503bc0efe92cc57a9e852beaa`. Полностью скачанный `GigaAM-Speakers-windows-x64.zip` имеет **1 033 476 178 байт** и SHA256:

```text
711f904a89f312eed3256624fcec6ccc2954bdb92ff898a43166262f2b4b91bf
```

Проверены совпадение SHA256 с опубликованным checksum и GitHub asset digest, CRC всего ZIP, **4 055** записей manifest, соответствие хешей **130** нативных файлов сохранённому PE audit CI и контрольные суммы четырёх опубликованных Release assets. Архитектура PE и imports этим проверяющим архива повторно не вычислялись; они проверены CI. Исходный архив tag содержит **130** разрешённых файлов и отдельно проверен по байтам; модели и runtime в исходный архив не входят.

Следующие значения взяты из встроенного evidence именно этого канонического CI ZIP:

- Python runtime **3.12.10**, frozen self-test **passed за 8,336 с**;
- настоящий GigaAM/Public PCM: inference включая загрузку **4,52 с**;
- локальная CPU-диаризация **0,91 с**, **26 exact Word records**, сохранение ID между источниками/gain и gap900sec;
- frozen-source attestation: **15 модулей**, совпадают с исходниками опубликованного tag;
- сеть при self-test CI: **30 endpoint snapshots, 0 TCP, 0 UDP, 0 query failures**;
- полный pytest: **222 passed за 11,41 с**, Ruff без ошибок.

Дополнительно этот скачанный архив полностью извлечён в новую папку: проверены SHA256 всех **4 055** файлов, без лишних или отсутствующих файлов. Именно извлечённый канонический EXE запущен локально с public PCM, без открытия микрофона/loopback:

- self-test **passed за 25,333 с**, bundled Python **3.12.10**;
- настоящий GigaAM inference включая загрузку **13,873 с**, 26 слов с правильными временными метками;
- CPU-диаризация **1,884 с**, сохранены exact Word records и ID между источниками/gain и gap900sec;
- synthetic echo: 26 повторных microphone слов удалены, system text и Word timestamps сохранены;
- TXT/MD/DOCX/PDF/JSON exports и отказ от перезаписи прошли;
- локальная frozen-source attestation: **15 модулей** совпадают с исходниками опубликованной версии;
- отдельный локальный network audit: **passed, 46 snapshots, 0 TCP, 0 UDP, 0 query failures**, exit0; Python network attempts0.

Все эти проверки и их границы отражены в [published-release.json](verification/v0.2.0/published-release.json). Числа CI и локального запуска не являются гарантией задержки на другом компьютере, качеством диаризации реальной встречи или проверкой физических аудиоустройств. Sampled endpoints не доказывают отсутствие всех возможных native/system сетевых путей; чистая Windows без Python и физическое отключение сети по-прежнему не проверены.

## Что не проверено и ограничения

Не выполнены: новый ручной microphone+WASAPIloopback acceptance, реальные наушники/комната/эхо/тихий double-talk, перезапуск/смена headset на hardware, часовая запись с inference+GUI, естественная казахская речь и один реальный голос при смене RU/KK/EN, полный diarization dataset с human speaker ground truth, чистая Windows без Python и физически отключённой сетью.

Успешная прежняя v0.1.2 ручная проверка не подтверждает автоматически новое speaker поведение. Windows есть, устройства не захватывались без нового явного действия пользователя. Offline self-test с guard и выборками не доказывает абсолютно все native/system network paths.

Модель сегментации имеет три локальных voice slots и максимум два одновременных голоса powerset; global registry до64. Similar voices/codec/room shifts могут давать false merges/splits; языковой переход не является правилом нового ID, но acoustic cross-language invariance не сертифицирована. Count — estimate, не attendance. После Stop нет full-meeting acoustic reanalysis или глобальной перенумерации.

Микрофон/компьютерный звук — отдельные source fields. Короткие слова и неубедительное эхо могут сохраняться; WAV не очищаются. JSON сохраняет exact Word timestamps, readable formats — интервалы реплик. Политики paging/dumps/backup/sync остаются внешними.

## Приёмка пользователем

Сначала выбрать источники/папку/toggle, явно разрешить levelcheck, затем заново разрешить Start. Проверить mic отдельно, loopback отдельно, вместе; несколько голосов у одного mic; short turns/overlap; наушники/динамики; Pause/Stop/drain; новый сеанс; headset change; RU/KK/EN/естественная смешанная речь; длительность и память; пять exports/nooverwrite. Записать конфигурацию и фактические результаты без приватной записи в публичных reports.

Тесты синтетического Unicode проверяют только форматы, не ASR казахского языка. Сравнение решений/лицензий: [DIARIZATION_RESEARCH.md](DIARIZATION_RESEARCH.md). Режим: [DIARIZATION.md](DIARIZATION.md). Метод приватности: [PRIVACY.md](PRIVACY.md). Развёртывание: [DEVOPS_RUNBOOK.md](DEVOPS_RUNBOOK.md).
