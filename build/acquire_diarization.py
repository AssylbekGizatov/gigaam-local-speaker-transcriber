"""Acquire public pinned diarization assets at BUILD TIME, never at runtime."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tarfile
import tempfile
import urllib.request

SEGMENTATION_URL = "https://github.com/k2-fsa/sherpa-onnx/releases/download/speaker-segmentation-models/sherpa-onnx-pyannote-segmentation-3-0.tar.bz2"
EMBEDDING_URL = "https://github.com/k2-fsa/sherpa-onnx/releases/download/speaker-recongition-models/wespeaker_en_voxceleb_resnet34_LM.onnx"
ARCHIVE_SHA256 = "24615ee884c897d9d2ba09bb4d30da6bb1b15e685065962db5b02e76e4996488"
MODEL_FILES = {
    "segmentation.onnx": "220ad67ca923bef2fa91f2390c786097bf305bceb5e261d4af67b38e938e1079",
    "embedding.onnx": "e9848563da86f263117134dfd7ad63c92355b37de492b55e325400c9d9c39012",
}
LICENSE_FILES = {
    "LICENSE-pyannote-MIT.txt": "14d7016ad68e7394d6e6b78d96cc2ae431c905287b89674cfdf021e79e62b8ba",
    "LICENSE-WeSpeaker-CC-BY-4.0.txt": "9ba9550ad48438d0836ddab3da480b3b69ffa0aac7b7878b5a0039e7ab429411",
    "LICENSE-sherpa-onnx-APACHE-2.0.txt": "cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30",
}


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _verify(path, expected):
    if not path.is_file() or digest(path) != expected:
        raise RuntimeError(f"{path.name} is missing or failed pinned SHA256; existing files are never overwritten")


def _download(url, destination):
    with urllib.request.urlopen(url, timeout=120) as response, destination.open("xb") as output:
        shutil.copyfileobj(response, output, length=1024 * 1024)


def acquire(directory, notice_directory=None):
    directory = Path(directory)
    notices = (Path(notice_directory) if notice_directory else
               Path(__file__).resolve().parent.parent / "assets" / "licenses" / "diarization")
    # The exact full public license text is checked before ANY acquisition.
    for name, expected in LICENSE_FILES.items():
        _verify(notices / name, expected)
    directory.mkdir(parents=True, exist_ok=True)
    for name, expected in MODEL_FILES.items():
        target = directory / name
        if not target.exists():
            with tempfile.TemporaryDirectory(prefix=".acquire-", dir=directory) as scratch:
                partial = Path(scratch) / name
                if name == "segmentation.onnx":
                    archive = Path(scratch) / "segmentation.tar.bz2"
                    _download(SEGMENTATION_URL, archive)
                    _verify(archive, ARCHIVE_SHA256)
                    # Read one known member; never extract arbitrary archive paths.
                    with tarfile.open(archive, "r:bz2") as tar:
                        member = tar.getmember("sherpa-onnx-pyannote-segmentation-3-0/model.onnx")
                        if not member.isfile() or member.size != 5992913:
                            raise RuntimeError("Unexpected segmentation archive member")
                        with tar.extractfile(member) as source, partial.open("xb") as output:
                            shutil.copyfileobj(source, output)
                else:
                    _download(EMBEDDING_URL, partial)
                _verify(partial, expected)
                partial.rename(target)  # Windows refuses an existing destination.
        _verify(target, expected)
    for name, expected in LICENSE_FILES.items():
        target = directory / name
        if not target.exists():
            with target.open("xb") as output:
                output.write((notices / name).read_bytes())
        _verify(target, expected)
    notice = notices / "NOTICE.md"
    if not notice.is_file():
        raise RuntimeError("Diarization attribution NOTICE.md is missing")
    target_notice = directory / "NOTICE.md"
    if not target_notice.exists():
        with target_notice.open("xb") as output:
            output.write(notice.read_bytes())
    elif target_notice.read_bytes() != notice.read_bytes():
        raise RuntimeError("Existing diarization NOTICE differs; never overwrite it silently")
    record = {
        "schema": 1, "runtime": "onnxruntime==1.23.2; CPU; local files only; no sherpa runtime",
        "models": {
            "segmentation.onnx": {"model": "pyannote/segmentation-3.0", "license": "MIT",
                                   "sha256": MODEL_FILES["segmentation.onnx"], "size": 5992913,
                                   "artifact_source": SEGMENTATION_URL,
                                   "archive_sha256": ARCHIVE_SHA256,
                                   "conversion": "Official sherpa-onnx fp32 conversion; unmodified",
                                   "source_revision": "Upstream model revision not recorded in artifact; binary pinned by SHA256"},
            "embedding.onnx": {"model": "Wespeaker/wespeaker-voxceleb-resnet34-LM", "license": "CC-BY-4.0",
                                "sha256": MODEL_FILES["embedding.onnx"], "size": 26530550,
                                "artifact_source": EMBEDDING_URL,
                                "source_model_revision": "f0c48c298fd835726c27956a5d617bad7115627e",
                                "source_model_sha256": "7bb2f06e9df17cdf1ef14ee8a15ab08ed28e8d0ef5054ee135741560df2ec068",
                                "source_and_converted_graph_equal": True,
                                "onnx_graph_sha256": "3247a23b25effa9659dde48ed38693dc45e1d89a6f2a922632909f69589ccda3",
                                "source_model_card": "https://huggingface.co/Wespeaker/wespeaker-voxceleb-resnet34-LM/blob/f0c48c298fd835726c27956a5d617bad7115627e/README.md",
                                "conversion": "Official sherpa-onnx ONNX with metadata; unmodified; source HF ONNX has different metadata/hash"},
        },
        "licenses_sha256": LICENSE_FILES,
        "network_during_runtime": False, "acquisition_requires_authentication": False,
    }
    provenance = directory / "provenance.json"
    if provenance.exists():
        if json.loads(provenance.read_text(encoding="utf-8")) != record:
            raise RuntimeError("Existing diarization provenance differs; never overwrite it silently")
    else:
        with provenance.open("x", encoding="utf-8") as output:
            json.dump(record, output, indent=2)
            output.write("\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", type=Path, default=Path("models/diarization"))
    args = parser.parse_args()
    acquire(args.directory)


if __name__ == "__main__":
    main()
