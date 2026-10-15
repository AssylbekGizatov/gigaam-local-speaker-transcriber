# Changelog

## 0.2.0 — separate speaker-transcriber application

- Retains pinned GigaAM Multilingual 220M CTC and the local WASAPI capture/export foundation.
- Adds optional fragment-based speaker segmentation and acoustic embedding comparison using local ONNX Runtime CPU models.
- Uses a shared session speaker registry across microphone/system, pauses, and window boundaries; explicitly marks preliminary, unknown, and overlapping speech.
- Fixes exact word timing/metadata loss in both echo pass-through and microphone reduction.
- Splits ASR fragments into speaker replies while retaining each surviving Word exactly once; late echo edits remove all corresponding display parts.
- Finalizes queued fragments after Stop without renumbering; no hidden full-meeting PCM retention/reclustering.
- Adds JSON export with separate source/speaker fields and full word timestamps.
- Retains MIT attribution for the baseline and adds model/runtime license/provenance requirements.
- The original repository and v0.1.2 release are unchanged.

Historical baseline: [gigaam-local-meeting-transcriber v0.1.2](https://github.com/AssylbekGizatov/gigaam-local-meeting-transcriber/releases/tag/v0.1.2). New test reports supersede inherited baseline reports for this application's behavior.