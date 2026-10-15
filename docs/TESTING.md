# Проверки GigaAM Speakers v0.2.0

Дата: **15 октября 2026**. Исходный GigaAM-Meeting v0.1.2 не изменён. Старые файлы verification/v0.1.x — только историческая основа, не доказательство новой диаризации.

## Исходники и контракты

Финальный набор: **220 pytest passed за 29,63 с**, Ruff без ошибок. Проверки охватывают прежний WASAPI/streaming/echo/export/lifecycle и новые speaker contracts, точные Word records, источник отдельно от говорящего, speaker registry, unknown/overlap, source/time boundary ownership, паузы, bounded history/capacity и JSON.

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

## Собранный EXE: выполнено

Локальная Windows x64 сборка с Python runtime3.12.3; canonical CI настроен3.12.10. Поставляется самостоятельный runtime, а не вызов системного Python. Точный installed supplier graph и readonly reuse source в provenance сборки. Побайтная воспроизводимость ZIP не заявляется.

Финальный GigaAM-Speakers.exe:

- frozen source attestation: **15 модулей** совпали с финальными исходниками;
- actual offline self-test: **passed, 37,138с**;
- CPU speaker inference: **4,734с**, локальные hash-pinned модели, CPUExecutionProvider,26Wordrecords exact, один голос сохранил ID между источниками/gain и900sec gap;
- настоящий GigaAM/public PCM, консервативный synthetic echo check и пять экспортов TXT/MD/DOCX/PDF/JSON прошли; existingfiles сохранены;
- child PATH толькоWindows, PYTHONHOME/PYTHONPATH очищены. Это runtime search independence, не удаление Python с хоста;
- сеть: **66 endpoint snapshots,0TCP,0UDP,0queryfailures, exit0**, Pythonguard0. При ошибках queries обновлённый аудит не выдаёт ложный успешный нулевой результат;
- захват hardware в self-test не запускался.

Отчёты внутри ZIP provenance и текущего verification/v0.2.0. PE audit, ZIP SHA/CRC/manifest проверяются отдельным шагом упаковки каждого конкретного архива; финальные asset значения не выводятся из отчёта другого ZIP.

## Что не проверено и ограничения

Не выполнены: новый ручной microphone+WASAPIloopback acceptance, реальные наушники/комната/эхо/тихий double-talk, перезапуск/смена headset на hardware, часовая запись с inference+GUI, естественная казахская речь и один реальный голос при смене RU/KK/EN, полный diarization dataset с human speaker ground truth, чистая Windows без Python и физически отключённой сетью.

Успешная прежняя v0.1.2 ручная проверка не подтверждает автоматически новое speaker поведение. Windows есть, устройства не захватывались без нового явного действия пользователя. Offline self-test с guard и выборками не доказывает абсолютно все native/system network paths.

Модель сегментации имеет три локальных voice slots и максимум два одновременных голоса powerset; global registry до64. Similar voices/codec/room shifts могут давать false merges/splits; языковой переход не является правилом нового ID, но acoustic cross-language invariance не сертифицирована. Count — estimate, не attendance. После Stop нет full-meeting acoustic reanalysis или глобальной перенумерации.

Микрофон/компьютерный звук — отдельные source fields. Короткие слова и неубедительное эхо могут сохраняться; WAV не очищаются. JSON сохраняет exact Word timestamps, readable formats — интервалы реплик. Политики paging/dumps/backup/sync остаются внешними.

## Приёмка пользователем

Сначала выбрать источники/папку/toggle, явно разрешить levelcheck, затем заново разрешить Start. Проверить mic отдельно, loopback отдельно, вместе; несколько голосов у одного mic; short turns/overlap; наушники/динамики; Pause/Stop/drain; новый сеанс; headset change; RU/KK/EN/естественная смешанная речь; длительность и память; пять exports/nooverwrite. Записать конфигурацию и фактические результаты без приватной записи в публичных reports.

Тесты синтетического Unicode проверяют только форматы, не ASR казахского языка. Сравнение решений/лицензий: [DIARIZATION_RESEARCH.md](DIARIZATION_RESEARCH.md). Режим: [DIARIZATION.md](DIARIZATION.md). Метод приватности: [PRIVACY.md](PRIVACY.md). Развёртывание: [DEVOPS_RUNBOOK.md](DEVOPS_RUNBOOK.md).
