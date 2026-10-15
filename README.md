# GigaAM Local Speaker Transcriber

A portable Windows x64 desktop application for **local speech recognition and estimated speaker diarization**. The interface is Russian. It listens to explicitly selected WASAPI microphone and playback devices while you are already in a call. It does not join meetings, create a bot, use Teams/Zoom APIs, or require meeting accounts or integration licenses.

Version **0.2.0** is developed in a separate repository from [gigaam-local-meeting-transcriber](https://github.com/AssylbekGizatov/gigaam-local-meeting-transcriber), based on its MIT-licensed code at commit `6f43fdd292f54234e6abbd51b0f97ea0aba93bea`. The original repository is unchanged.

## What changed

- The same **GigaAM Multilingual 220M CTC** recognizes Russian, Kazakh, English, and mixed speech. Its code, weights, CPU float32 path, and checksum pins are retained.
- Local **pyannote segmentation 3.0 ONNX + WeSpeaker ResNet34-LM embeddings**, executed using **ONNX Runtime CPU**, estimate who spoke when. No cloud STT or LLM is used.
- One session registry assigns anonymous `Speaker 1`, `Speaker 2`, etc., across both sources. It survives pauses and audio window boundaries. A microphone can contain several voices; computer audio can contain several voices. Source and speaker are separate fields.
- The echo filter now retains exact CTC word records, including when a late computer-audio result edits the microphone transcript. Word-to-turn alignment splits a fragment into speaker-labelled replies without splitting or duplicating individual words.
- Unknown and overlapping speech remain explicitly labelled. Speaker counts are estimates of distinguishable voices, not meeting attendance.
- TXT, MD, DOCX, and PDF remain available. **JSON** additionally preserves full word timestamps and separate source/speaker metadata.

## Start in three steps

1. Obtain `GigaAM-Speakers-windows-x64.zip` with its matching SHA256, verify it, and extract **the entire archive** into a new local folder.
2. Open `GigaAM-Speakers.exe`. Select the microphone, the output device used by your call, and a local export folder. The optional diarization switch applies to the next session; it is enabled by default in the UI.
3. Obtain the necessary consent, explicitly permit capture, and click **«Начать»**. The level check also requires permission and resets it after checking. At the end click **«Остановить и завершить текст»**, wait for the queue to drain, and export.

End users do not need Python, pip, Git, Docker, virtual audio cables, or a terminal. Headphones work through WASAPI loopback. Do not run the EXE inside the ZIP or copy it alone. Do not bypass Windows security or organizational restrictions.

Computer audio captures **all applications on the selected output device**, including notifications. Per-application capture is unavailable. Device changes require stopping, refreshing, selecting, and starting explicitly. There is no automatic capture, autostart recording, or recording recovery.

## How speaker labels work

This is **incremental processing of bounded audio fragments**, not a sample-by-sample streaming diarization model. The existing ASR worker processes approximately eight-second windows or pause-triggered fragments. Speaker segmentation and embedding inference run in the same worker. Labels appear after fragment processing and are marked provisional during capture.

The registry compares acoustic embeddings, not recognized words or language names. Switching languages does not itself allocate an ID. Acoustic changes, noise, room differences, short utterances, and model bias can nevertheless cause false merges or extra IDs. Cross-language invariance is not guaranteed.

After Stop, pending fragments finish and supported provisional labels are finalized without renumbering the registry. **There is no full-meeting acoustic reanalysis or offline reclustering pass.** Finalized means processing is complete, not that a label is certainly correct. Ambiguous or short turns may stay unknown. Similar voices and remote compression can confuse the model.

Overlap is a speaker-activity estimate. GigaAM CTC does not separate simultaneous voices in one source. A single transcript labelled overlap must not be interpreted as independently decoded text for each overlapping speaker. No real names are inferred.

The segmentation model has three local voice slots and at most two simultaneous voices in its powerset output; the shared session registry is capped at 64 profiles. An overlap label may list only the known IDs while another active voice remains unknown. These limits and estimates must not be interpreted as the number of meeting participants.

The conservative echo filter removes confirmed repeated microphone words after matching text, timing, and PCM. It does not alter model input or optional WAV recordings. Very short or uncertain repeats can remain. Headphones reduce acoustic echo. See [DIARIZATION.md](docs/DIARIZATION.md) and [ECHO.md](docs/ECHO.md).

## Offline operation and privacy

All runtime models load from local disk and are SHA256 checked. Missing or modified files produce a clear error with no hidden download. If diarization is disabled, speech recognition works without loading its models. Model and dependency acquisition are separate build-time actions.

Audio saving is **off by default**. Audio stays in bounded memory queues, recent echo PCM, and the active inference fragment. No full-meeting PCM archive or temporary conversation audio files are created. Speaker embeddings are session-local, bounded, and are not exported or persisted as voice profiles. Transcript text and its metadata grow with session duration in memory.

There is no telemetry, cloud connection, conversation-content diagnostic log, or crash-report upload. Python network operations are blocked in-process. This is not a system-wide firewall guarantee; native libraries and sampled endpoint checks have limits. Windows paging/dumps, backups, and synchronization of your chosen folder remain under your environment's control.

Optional audio saving creates separate source WAV files and a shared timeline. Export is explicit and refuses to overwrite existing files. Participant consent and organizational rules are required separately from Windows microphone permission. See [PRIVACY.md](docs/PRIVACY.md).

## Development, evidence, and limitations

| Document | Purpose |
| --- | --- |
| [DIARIZATION_RESEARCH.md](docs/DIARIZATION_RESEARCH.md) | Comparison of open solutions, code/weight licenses, and the selected runtime |
| [DIARIZATION.md](docs/DIARIZATION.md) | Fragment mode, shared IDs, alignment, overlap, and limitations |
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | Capture → recognition → echo reduction → speaker annotation |
| [TESTING.md](docs/TESTING.md) | Actual tests and unverified scenarios |
| [DEVOPS_RUNBOOK.md](docs/DEVOPS_RUNBOOK.md) | Russian deployment/build/update runbook |
| [BUILD.md](docs/BUILD.md) | Build and packaging commands |
| [CHANGELOG.md](CHANGELOG.md) | Version history |

Build acquisition needs internet access. Normal runtime does not. The source archives contain no model weights or user recordings; the portable runtime ZIP contains the local models and all required notices.

Automated/frozen tests and small public recordings do not certify all microphones, driver combinations, long live meetings, natural Kazakh/code-switching speech, or accurate overlapping speech. The current report distinguishes real inference, deterministic fake tests, and hardware checks. Clean Python-free Windows and physically disconnected-network checks must be reported only when actually performed.

## Licensing

The application remains MIT licensed. Reused baseline authorship and component attribution are retained in [NOTICE.md](NOTICE.md).

| Component | License scope |
| --- | --- |
| GigaAM application/base code | MIT; original notices retained |
| GigaAM Multilingual 220M CTC | Original pinned model notice included |
| ONNX Runtime CPU | MIT plus bundled third-party notices |
| pyannote segmentation 3.0 converted ONNX | Full MIT notice from the official converted model distribution |
| WeSpeaker ResNet34-LM ONNX weights | **CC BY 4.0**; model/dataset attribution and full terms included |
| WeSpeaker upstream code | Apache 2.0; not a replacement for the weights' license |

The official sherpa Windows wheel was investigated but is not bundled: its TTS-enabled binary includes GPLv3 eSpeakNG code. This product executes the selected ONNX models directly, so it does not claim that the wheel is an Apache-only runtime. See the research report for sources and the portable ZIP's `licenses`, inventory, and provenance for the actual supplied components.
