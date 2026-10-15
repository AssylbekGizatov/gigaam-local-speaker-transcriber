from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

Source = Literal["microphone", "system"]
SOURCE_LABELS = {"microphone": "Микрофон", "system": "Звук компьютера"}


@dataclass(frozen=True)
class AudioDevice:
    id: int
    name: str
    source: Source
    sample_rate: int
    channels: int
    host_api: str = "WASAPI"
    is_default: bool = False
    fingerprint: str = ""


@dataclass(frozen=True)
class AudioBlock:
    source: Source
    samples: Any  # NumPy float32 [frames, channels], owned copy, normalized [-1,1]
    sample_rate: int
    start: float  # seconds on one session monotonic clock; includes pause gaps
    discontinuity: bool = False


@dataclass(frozen=True)
class Word:
    start: float
    end: float
    text: str


@dataclass(frozen=True)
class Segment:
    source: Source
    start: float
    end: float
    text: str
    words: tuple[Word, ...] = field(default=(), compare=False, repr=False)
    # A source is an audio device, never a person. Speaker IDs belong to one
    # shared session registry and may occur in either source.
    speaker_id: int | None = None
    speaker_status: str = "off"
    overlapping_speakers: tuple[int, ...] = ()
    speaker_confidence: float | None = None


@dataclass(frozen=True)
class SpeakerTurn:
    """Speaker evidence on the same absolute session clock as Word/AudioBlock.

    An empty tuple means unknown. Multiple IDs denote overlap; they do not
    imply that one ASR transcript has separated the simultaneous voices.
    Confidence is an uncalibrated model score, not participant certainty.
    """

    source: Source
    start: float
    end: float
    speaker_ids: tuple[int, ...]
    status: str = "provisional"
    confidence: float | None = None


@dataclass(frozen=True)
class SessionConfig:
    microphone: AudioDevice | None
    system: AudioDevice | None
    consent: bool
    output_folder: Path
    save_audio: bool = False
    reduce_echo: bool = True
    diarization: bool = False


@dataclass(frozen=True)
class Event:
    kind: str
    message: str = ""
    data: dict[str, Any] = field(default_factory=dict)
