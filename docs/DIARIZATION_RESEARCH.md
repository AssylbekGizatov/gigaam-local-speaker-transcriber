# Diarization selection and implementation

Research date: **2026-10-15**. Target: an interactive Windows x64 desktop with
8 GB RAM and CPU inference alongside the unchanged GigaAM Multilingual 220M CTC.
The original repository is a separate, unchanged application.

## Decision

Use **ONNX Runtime 1.23.2 CPU directly**, the public **pyannote segmentation-3.0
fp32 ONNX**, and **WeSpeaker VoxCeleb ResNet34-LM ONNX**, with a bounded application
speaker registry. All runtime inputs are local arrays and all weights are local
files. This adds approximately 32.5 MB of model files and reuses the CPU runtime
and PyTorch/torchaudio already present for GigaAM. No ASR model is replaced.

This is a practical portable implementation, **not a claim of superior DER**.
Full-recording clustering systems can outperform a bounded window registry,
especially with very short responses, difficult rooms and similar voices.
Publisher benchmarks below use different datasets and metrics; verification EER,
diarization DER and word diarization error cannot be compared as one score.

## Alternatives examined

| Candidate | Code and concrete weight license | Quality and overlap | Windows, offline use and resource/packaging implications | Decision |
| --- | --- | --- | --- | --- |
| pyannote.audio 4 / `speaker-diarization-community-1` | pyannote.audio code MIT; **community-1 weights CC-BY-4.0**, distinct from the code | A mature whole-recording pipeline with overlapping and exclusive diarization; publisher reports improvements in speaker assignment/counting | CPU is the default; local-directory offline loading is documented. Initial model acquisition requires Hugging Face login, accepting contact-sharing conditions and a token. A larger dependency/pipeline bundle and whole-recording processing would need additional Windows/memory testing | Strong reference implementation, not selected for account-free acquisition and a bounded portable live product. [Model card](https://huggingface.co/pyannote/speaker-diarization-community-1), [code license](https://github.com/pyannote/pyannote-audio/blob/main/LICENSE) |
| NVIDIA NeMo Sortformer / `diar_sortformer_4spk-v1`, streaming `diar_streaming_sortformer_4spk-v2.1` | NeMo code Apache-2.0; **v1 weights CC-BY-NC-4.0**; **v2.1 NVIDIA Open Model License** | End-to-end overlap-aware models; streaming v2.1 has arrival-order speaker cache; both have four-speaker output limits | Local saved checkpoints are supported. NeMo/PyTorch and audio tooling increase packaging burden. Published low-latency speed results use an NVIDIA RTX 6000 Ada GPU, not an 8 GB CPU Windows machine. Official examples use Linux package commands | Not selected: v1 noncommercial restriction, v2.1 licensing/dependencies and unmeasured target CPU cost. [v1 card](https://huggingface.co/nvidia/diar_sortformer_4spk-v1), [v2.1 card](https://huggingface.co/nvidia/diar_streaming_sortformer_4spk-v2.1), [NeMo installation](https://docs.nvidia.com/nemo/speech/nightly/starthere/install.html) |
| NVIDIA `Nemotron-3-Diarization` | Concrete weights **OpenMDW 1.1**, not the older Sortformer license; toolkit licenses apply separately | Newer 100M-parameter streaming/offline model, eight ordered speaker channels and speaker cache | Local PyTorch/NeMo/Transformers and a native runtime are offered; published performance uses a Blackwell RTX PRO 5000 in BF16. Windows CPU portability and memory were not established in this task | A useful future comparison; no unsupported CPU latency promise or untested replacement. [Official card](https://huggingface.co/nvidia/Nemotron-3-Diarization) |
| SpeechBrain `spkrec-ecapa-voxceleb` | SpeechBrain code and this exact model card **Apache-2.0** | A speaker-embedding/verification model, **not a complete diarizer**. Its reported 0.80% EER is a VoxCeleb verification result; segmentation and overlap handling must be added | CPU inference and local weights are possible; the toolkit's installation documentation primarily supports Linux/macOS and directs Windows users to workarounds. Adds a toolkit/hyperparameter-loader path | Valid embedding option; direct small ONNX inference is simpler to package. [Model card](https://huggingface.co/speechbrain/spkrec-ecapa-voxceleb), [installation](https://github.com/speechbrain/speechbrain/blob/develop/docs/installation.md) |
| 3D-Speaker ERes2Net / CAM++ | Toolkit **Apache-2.0**; exact weight license must be checked in each ModelScope card. The ERes2Net-base 3D-Speaker ONNX distributed by sherpa is about 39.6 MB; the dynamically rendered original weight-license page was not independently extractable here, so the code license was not treated as proof for weights | Complete recipes combine embeddings, segmentation and clustering. Optional overlap detection introduces a Hugging Face token path | ONNX inference is available, but the full toolkit includes ModelScope and additional processing components; CPU Windows bundle not measured here | Not bundled; selected WeSpeaker has clearer directly readable weight/ONNX licensing. [Toolkit](https://github.com/modelscope/3D-Speaker), [exact source model](https://modelscope.cn/models/iic/speech_eres2net_base_sv_zh-cn_3dspeaker_16k) |
| sherpa-onnx offline diarization with pyannote + WeSpeaker or 3D-Speaker | sherpa source **Apache-2.0**; individual model licenses are separate. pyannote segmentation weights **MIT**; WeSpeaker VoxCeleb weights **CC-BY-4.0** | An established offline segmentation/embedding/clustering implementation with unknown-count threshold and overlap support | Official Windows CPython 3.12 wheels exist (1.13.8 plus sherpa-onnx-core). Its native distribution also includes unrelated TTS/eSpeak components requiring a wider license audit. Offline result speaker numbers belong to an individual processing call, not an application session | **Model distribution reused, native runtime not bundled**. Direct ONNX Runtime avoids the unrelated native/TTS dependency set. [Diarization docs](https://k2-fsa.github.io/sherpa/onnx/speaker-diarization/models.html), [Windows/OS support](https://k2-fsa.github.io/sherpa/intro.html), [release model-license statement](https://github.com/k2-fsa/sherpa-onnx/releases/tag/speaker-recongition-models) |
| Rev `reverb-diarization-v1` | Exact weight license contains a **noncommercial restriction**; do not infer permissions from pyannote code | Publisher reports improved word diarization on its benchmarks | ONNX conversion exists; upstream acquisition is gated; licensing limits a generally reusable desktop distribution | Rejected for this distribution. [Official card](https://huggingface.co/Revai/reverb-diarization-v1), [conversion/license warning](https://k2-fsa.github.io/sherpa/onnx/speaker-diarization/models.html#sherpa-onnx-reverb-diarization-v1) |

## Exact selected artifacts

| Local name | Bytes | SHA256 | Acquisition |
| --- | ---: | --- | --- |
| `segmentation.onnx` | 5,992,913 | `220ad67ca923bef2fa91f2390c786097bf305bceb5e261d4af67b38e938e1079` | `model.onnx` inside [official pyannote segmentation archive](https://github.com/k2-fsa/sherpa-onnx/releases/download/speaker-segmentation-models/sherpa-onnx-pyannote-segmentation-3-0.tar.bz2) |
| `embedding.onnx` | 26,530,550 | `e9848563da86f263117134dfd7ad63c92355b37de492b55e325400c9d9c39012` | [Official WeSpeaker ResNet34-LM ONNX](https://github.com/k2-fsa/sherpa-onnx/releases/download/speaker-recongition-models/wespeaker_en_voxceleb_resnet34_LM.onnx) |

The segmentation archive SHA256 is
`24615ee884c897d9d2ba09bb4d30da6bb1b15e685065962db5b02e76e4996488`.
Its included full MIT license says Copyright (c) 2022 CNRS. The original
segmentation model's Hugging Face acquisition is gated; **the selected official
ONNX distribution is public and needs no token**. This task did not bypass a
gate or extract credentials. The archive does not record an upstream model
commit, so binary SHA256 pins are used rather than an invented revision.
[Original segmentation model and frame semantics](https://huggingface.co/pyannote/segmentation-3.0).

WeSpeaker's exact official model card declares **CC-BY-4.0**. Its source ONNX at
revision `f0c48c298fd835726c27956a5d617bad7115627e` has SHA256
`7bb2f06e9df17cdf1ef14ee8a15ab08ed28e8d0ef5054ee135741560df2ec068`.
The selected sherpa artifact has additional metadata and a different file hash.
Both ONNX graph serializations and opset lists were compared and are identical;
graph SHA256 is `3247a23b25effa9659dde48ed38693dc45e1d89a6f2a922632909f69589ccda3`.
Full licenses, attribution and the artifact provenance accompany the model.
[Pinned model card](https://huggingface.co/Wespeaker/wespeaker-voxceleb-resnet34-LM/blob/f0c48c298fd835726c27956a5d617bad7115627e/README.md),
[upstream weight/ONNX license explanation](https://github.com/wenet-e2e/wespeaker/blob/master/docs/pretrained.md).

## Implemented inference and identity policy

1. The existing bounded capture/ASR worker passes a separate source PCM window,
   rate and absolute session start time to the diarizer. Rates are resampled with
   the existing band-limited torchaudio path. A window is at most nine seconds;
   no full-meeting audio file or PCM history is created for diarization.
2. A ten-second zero-padded input feeds the local segmentation ONNX CPU session.
   Its seven powerset classes represent silence, three local voice slots and
   their two-voice overlaps. **A slot is not a global speaker ID**. Frame centers
   use the artifact's verified geometry: `(991/2 + 270 * index)/16000` seconds.
   Padded frames beyond the real input are ignored.
3. Non-overlapping speech for each local slot feeds WeSpeaker embeddings. The
   official feature recipe is 80-bin Kaldi filterbanks, Hamming windows,
   25 ms/10 ms geometry, zero dither, PCM amplitude scaled by 32768, and mean
   normalization. Mixed overlapping samples do not update speaker profiles.
   [Official inference recipe](https://github.com/wenet-e2e/wespeaker/blob/master/wespeaker/bin/infer_onnx.py).
4. One shared registry holds up to **64** normalized 256-dimensional centroids
   for both sources. Labels remain stable across windows and pauses. Close
   cosine scores, insufficient clean speech and weak evidence return unknown.
   Profiles are not language labels; recognized text and language identifiers
   are not features. This design reduces forced attribution but does not certify
   real cross-language or cross-device invariance. Capacity produces a visible
   warning and unknown attribution; it never renumbers existing profiles.
5. Recent turn evidence is bounded to 120 seconds and 2,048 turns. New window
   ownership replaces previous same-source seam evidence. A failed window masks
   stale evidence with unknown attribution while keeping the recognized text.
6. Echo filtering executes before transcript annotation. Surviving `Word`
   objects keep their identity, start/end times and order; words split into
   adjacent speaker turns exactly once. Ambiguous boundary words are unknown.
   Overlap metadata is separate and keeps the ASR text once: **there is no claim
   to separate or transcribe two simultaneous voices in one mono source**.
7. Labels shown during capture are **windowed provisional estimates**. Stop
   drains the queue and marks completed assignments final without renumbering.
   There is no full-recording reclustering or second audio pass; the application
   does not present this finalization as a more accurate batch diarizer.

ONNX Runtime telemetry events are explicitly disabled before constructing CPU
sessions. Offline hash validation precedes loading. Acquisition code is a
separate build script and is never imported by the desktop runtime. Runtime
network checks have the boundaries described in [PRIVACY.md](PRIVACY.md).

## Evidence and remaining work

Twenty-eight deterministic backend checks cover shared identities, several voices
at one microphone, ambiguity, short speech, overlap, capacity, long-clock gaps,
seam ownership, failed-window masking, exact word conservation, offline missing
or corrupt models, full license hashes and segmentation geometry. Integration
and portable-build evidence are recorded in [TESTING.md](TESTING.md).

Actual local CPU checks used permitted public Russian and LibriSpeech English
read speech. Russian repeats across sources and a synthetic 900-second pause
kept Speaker 1; the distinct English sample received Speaker 2. A gain-scaled
Russian repeat retained Speaker 1. All word objects/times were retained. Some
boundary words stayed unknown (Russian 21 assigned/5 unknown, English 16/1),
which is preferable to inventing an identity. Diarization-only work for these
clips was about **0.49–1.52 seconds** on this machine. These are tiny fixture
checks, not a hardware SLA, DER benchmark or proof of full-meeting accuracy.

A further synthetic composition placed four seconds of each public recording
and a 250 ms silent gap in one 8.25-second microphone window. It detected two
voice profiles and split all 24 ASR words into corresponding turns without
changing their objects, timing or order. Mixing the two four-second recordings
instead detected about 3.488 seconds of overlap and kept the four words GigaAM
could recognize exactly once, with unknown/overlap attribution and no invented
speaker profiles. This demonstrates overlap handling **and the ASR limitation**:
the mixed mono input did not produce two complete transcripts. Splice intervals
are construction metadata, not human-annotated frame-level speaker ground truth.

Not certified: real simultaneous-voice transcription, real acoustic echo and
double-talk diarization, many similar voices, same person switching among
Russian/Kazakh/English, Kazakh diarization audio quality, hour-long hardware
capture, or a clean offline Windows VM without installed Python. Segmentation
has three local slots and at most two concurrent voices in one ten-second
window; more crowded speech can be missed or confused. Quiet local speech under
loud speakers, changed microphones, clipped audio, language/domain shifts and
short acknowledgments can leave unknown labels or split one person. Headphones
remain useful. The displayed count is an estimate of voice profiles, never a
count of meeting participants or proof of identity.
