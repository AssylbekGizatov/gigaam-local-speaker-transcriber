# Build Windows x64 — GigaAM Speakers 0.2.0

End users use the complete portable ZIP. This document is for developers. Runtime capture remains interactive and explicit; builds never capture microphone/system audio.

Canonical environment: Windows x64, PowerShell 7, official Python **3.12.10 x64 with Tcl/Tk**, Git, a fresh short-path virtual environment. Local development/frozen evidence on this machine uses **3.12.3**; this difference is recorded, not hidden. No byte-for-byte archive reproducibility is promised.

## Commands

From a fresh source checkout in a permitted short directory:

```powershell
$ErrorActionPreference = 'Stop'
$taskPythonBase = 'C:/Path/To/Python312/python.exe'
$taskBuildRoot = 'C:/gigaam-speakers-build-01'
if (Test-Path -LiteralPath $taskBuildRoot) { throw 'Choose a new build folder' }
New-Item -ItemType Directory -Path $taskBuildRoot | Out-Null
& $taskPythonBase -c "import sys,struct,tkinter; assert sys.version_info[:3]==(3,12,10); assert struct.calcsize('P')==8"
if ($LASTEXITCODE -ne 0) { throw 'Need official Python 3.12.10 x64 and Tcl/Tk' }
& $taskPythonBase -m venv (Join-Path $taskBuildRoot 'v')
if ($LASTEXITCODE -ne 0) { throw 'Venv creation failed' }
$taskPython = Join-Path $taskBuildRoot 'v/Scripts/python.exe'
./build/build.ps1 -Python $taskPython -Output (Join-Path $taskBuildRoot 'release')
```

Replace the interpreter placeholder with its actual approved path. No activation script, ExecutionPolicy change, antivirus change, virtual cable, or system PATH modification is required.

## Pipeline

The pipeline installs pinned build/runtime dependencies and Torch/Torchaudio CPU, pinned GigaAM code, obtains hash-checked GigaAM and diarization weights, records the minimal soundfile lazy-import patch, runs tests and Ruff, builds the onedir EXE, attests frozen source modules, copies local models/fonts/docs/licenses, executes actual frozen offline self-test and endpoint sampling, curates current public evidence, audits native DLL dependencies, and packages ZIP/SHA256/manifest.

GigaAM ASR continues through native Torch CPU. **ONNX Runtime CPU 1.23.2 is deliberately included only for speaker models.** Python ONNX tooling, unused GigaAM ONNX/VAD paths, CUDA, soundfile/libsndfile/FFmpeg, and Sherpa/TTS/eSpeak runtime are excluded. The exact supplied files are established by file manifest and PE audit, not by a broad build-environment inventory.

Model acquisition is build-time only:

```powershell
& $taskPython build/acquire_model.py
if ($LASTEXITCODE -ne 0) { throw 'GigaAM acquisition failed' }
& $taskPython build/acquire_diarization.py --directory models/diarization
if ($LASTEXITCODE -ne 0) { throw 'Speaker model acquisition failed' }
```

Ordinary GUI startup never calls these scripts. Already present corrupt weights are refused rather than silently replaced. Exact model hashes, sources, and full MIT/CC-BY-4.0/Apache conversion notices are recorded by `models/diarization/provenance.json`. Full notices are versioned in `assets/licenses/diarization`; source publication includes them but excludes model weights.

Each build uses fresh private reports. The curator requires current source attestation, passing JUnit, frozen real speaker inference, and matching model hashes. It excludes private paths, hostname, raw pip environment metadata, signed transport URLs, selected devices, and user audio. Historical baseline reports in `docs/verification` are labelled separately from current v0.2.0 evidence.

## Packaging checks

Archive: `GigaAM-Speakers-windows-x64.zip`; root folder: `GigaAM-Speakers`; executable: `GigaAM-Speakers.exe`. The existing spec filename `GigaAM-Meeting.spec` is retained as a build filename only.

Check archive CRC on the build machine:

```powershell
$taskZip = Join-Path $taskBuildRoot 'release/GigaAM-Speakers-windows-x64.zip'
& $taskPython -c "import zipfile,sys; z=zipfile.ZipFile(sys.argv[1]); bad=z.testzip(); z.close(); assert bad is None" $taskZip
if ($LASTEXITCODE -ne 0) { throw 'ZIP CRC failed' }
Get-FileHash -LiteralPath $taskZip -Algorithm SHA256
```

Then extract into a new folder, verify its manifest, and test the extracted EXE. A developer's installed DLLs must not mask a missing bundle component. PATH-sanitized tests do not certify a clean Python-free VM. Endpoint sampling does not certify every native/system network path. See [TESTING.md](TESTING.md), [PRIVACY.md](PRIVACY.md), and the [runbook](DEVOPS_RUNBOOK.md).

GitHub Actions uses Windows 2022/Python 3.12.10. Its manual workflow defaults to build-only; a new pre-release requires explicit publication and a previously unused tag. Existing versions/source repository are not modified.