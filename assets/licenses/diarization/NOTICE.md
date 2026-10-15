# Diarization model and runtime attribution

The desktop application retains the original GigaAM recognizer. Diarization is
an additional local process. It is not affiliated with or endorsed by the
following projects or their authors.

- **pyannote segmentation-3.0**: model by Séverin Baroudi and the pyannote team,
  Copyright (c) 2022 CNRS, MIT. The unmodified fp32 ONNX conversion is distributed
  by k2-fsa/sherpa-onnx. Original model: https://huggingface.co/pyannote/segmentation-3.0
  Conversion/distribution: https://github.com/k2-fsa/sherpa-onnx/releases/tag/speaker-segmentation-models
  Full model license: `LICENSE-pyannote-MIT.txt`.
- **WeSpeaker VoxCeleb ResNet34-LM**: model by the WeSpeaker project authors,
  trained on VoxCeleb2. The **weights/ONNX model** use Creative Commons Attribution
  4.0 International (CC-BY-4.0); the separate WeSpeaker source code uses Apache-2.0.
  We bundle the unmodified official sherpa-onnx ONNX conversion, including its
  original model metadata. Model: https://huggingface.co/Wespeaker/wespeaker-voxceleb-resnet34-LM
  Model license/provenance statement: https://github.com/wenet-e2e/wespeaker/blob/master/docs/pretrained.md
  Full terms: `LICENSE-WeSpeaker-CC-BY-4.0.txt` and https://creativecommons.org/licenses/by/4.0/ .
- **sherpa-onnx**, k2-fsa project and contributors, Apache License 2.0.
  The project distributed the model conversions; its native runtime is NOT
  bundled. Project: https://github.com/k2-fsa/sherpa-onnx . Full code terms:
  `LICENSE-sherpa-onnx-APACHE-2.0.txt`.
- **ONNX Runtime 1.23.2**, Microsoft and contributors, MIT. The application uses
  its CPU provider directly. Complete runtime and third-party terms are in the
  bundle-wide licenses inventory. No eSpeak/TTS or sherpa native binary is used.

No new training, weight modification or quantization was performed by this
application. Local speaker centroids are session-only data, not model weight
changes. Model file hashes and source URLs are recorded in `provenance.json`.

References: Alexis Plaquet and Hervé Bredin, “Powerset multi-class cross entropy
loss for neural speaker diarization”, INTERSPEECH 2023; Hongji Wang et al.,
“Wespeaker: A research and production oriented speaker embedding learning
toolkit”, ICASSP 2023; Hossein Zeinali et al., “But system description to
voxceleb speaker recognition challenge 2019”.
