# Происхождение и лицензии

## Основа нового приложения v0.2.0

WASAPI-захват, общая временная шкала, GigaAM CPU, безопасный экспорт, UI, echo filter и упаковка переиспользованы из MIT-проекта [AssylbekGizatov/gigaam-local-meeting-transcriber](https://github.com/AssylbekGizatov/gigaam-local-meeting-transcriber), commit `6f43fdd292f54234e6abbd51b0f97ea0aba93bea`. Авторство Assylbek Gizatov и MIT уведомление сохранены. Исходный проект не изменён. Новые изменения: word timing conservation, локальная диаризация и session registry, раздельные source/speaker metadata и JSON.

CPU ONNX Runtime 1.23.2: MIT и полные ThirdPartyNotices. Сегментация pyannote-3.0: полный MIT notice Copyright (c) 2022 CNRS из официального ONNX-distribution. Embedding WeSpeaker ResNet34-LM: веса **CC BY 4.0**, авторы проекта WeSpeaker, VoxCeleb dataset attribution и условия доступны в `assets/licenses/diarization/NOTICE.md`, полном тексте CC BY и runtime `licenses/diarization-models`. Код WeSpeaker Apache 2.0 не заменяет лицензию его весов. Модели не изменены; metadata конверсии и pinned hashes зафиксированы. Sherpa-onnx указан как автор официальной ONNX-конверсии/распространения моделей; его TTS/eSpeak/нативный runtime не включён. Алгоритм признаков реализован через уже поставляемый Torchaudio.

Публичные English тесты используют один LibriSpeech/OpenSLR12 sample (CC BY 4.0, Vassil Panayotov et al.), только как разрешённый тестовый материал. Его audio не включено в runtime/source ZIP; публичный отчёт содержит технические метрики и атрибуцию. Источники и сравнение решений: `docs/DIARIZATION_RESEARCH.md`.

## Сохранённые уведомления исходной основы

Движок локального CPU-распознавания, проверки закреплённых весов и идеи упаковки адаптированы из `AssylbekGizatov/teams-local-transcriber`, компонента `desktop-microphone` (MIT). Автор исходного приложения — Assylbek Gizatov; исходное уведомление сохранено в LICENSE. Новый проект не зависит от его серверов и не изменяет старый репозиторий.

GigaAM: [salute-developers/GigaAM](https://github.com/salute-developers/GigaAM/tree/7447938d791c4f3e643386ee22c33777004293a5), MIT, закреплённый commit. Модель: [ai-sage/GigaAM-Multilingual](https://huggingface.co/ai-sage/GigaAM-Multilingual/tree/2f8a57144e6ec3adfd32fe0484d9ea9913305bc8), MIT согласно опубликованной model card; полный текст лицензии включён рядом с весами. Патч отложенного импорта неиспользуемого soundfile описан в provenance сборки; веса не изменены.

PyAudioWPatch предоставляет WASAPI loopback через PortAudio. Его условия и условия включённого нативного кода сохраняются отдельно. Экспорт DOCX: python-docx/lxml; PDF: ReportLab и DejaVu Sans. Лицензия приложения не заменяет лицензий этих компонентов. Полные тексты и версии доступны в `licenses/` и `dependency-inventory.json` каждого ZIP.

Публичный русский тестовый WAV получен из официального примера GigaAM. Это тестовый материал, не запись пользователя. Его URL и SHA256 приведены в тестах и отчёте самопроверки.
