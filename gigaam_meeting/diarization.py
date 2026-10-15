"""Local CPU window diarization with one bounded, source-independent registry.

Segmentation slot IDs are local to a window. We match non-overlap speaker
embeddings against session centroids; audio never survives ``analyze``. This is
windowed provisional diarization, not an end-to-end streaming model or source
separation. Stop finalizes labels without claiming a full-recording reanalysis.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, replace
import hashlib
import math
from pathlib import Path
import threading

import numpy as np

from .contracts import Segment, SpeakerTurn
from .engine import EngineError, bundle_root

RATE = 16000
MAX_WINDOW_SECONDS = 9
MAX_SPEAKERS = 64
MAX_TURNS = 2048
HISTORY_SECONDS = 120
MODEL_FILES = {
    "segmentation.onnx": "220ad67ca923bef2fa91f2390c786097bf305bceb5e261d4af67b38e938e1079",
    "embedding.onnx": "e9848563da86f263117134dfd7ad63c92355b37de492b55e325400c9d9c39012",
}


@dataclass
class _Voice:
    speaker_id: int
    centroid: np.ndarray
    observations: int = 1


class DiarizationEngine:
    def __init__(self, model_dir=None, *, max_speakers=MAX_SPEAKERS,
                 match_threshold=.65, new_threshold=.45, ambiguity_margin=.08):
        self.model_dir = Path(model_dir) if model_dir else bundle_root() / "models" / "diarization"
        self.max_speakers = max(1, min(MAX_SPEAKERS, int(max_speakers)))
        self.match_threshold = float(match_threshold)
        self.new_threshold = float(new_threshold)
        self.ambiguity_margin = float(ambiguity_margin)
        self._diarizer = None
        self._extractor = None
        self._voices: list[_Voice] = []
        self._turns: deque[SpeakerTurn] = deque(maxlen=MAX_TURNS)
        self._lock = threading.RLock()
        self._latest = 0.
        self._warning = ""
        self._windows = 0

    def load(self):
        with self._lock:
            if self._diarizer is not None:
                return
            for name, expected in MODEL_FILES.items():
                path = self.model_dir / name
                if not path.is_file():
                    raise EngineError("Модели диаризации не найдены. Распакуйте весь ZIP с папкой models/diarization или выключите диаризацию.")
                with path.open("rb") as stream:
                    if hashlib.file_digest(stream, "sha256").hexdigest() != expected:
                        raise EngineError("Модель диаризации повреждена. Заново распакуйте проверенный ZIP; автоматического скачивания нет.")
            try:
                import onnxruntime as ort
                ort.disable_telemetry_events()
                options = ort.SessionOptions()
                options.intra_op_num_threads = options.inter_op_num_threads = 1
                options.log_severity_level = 3
                self._extractor = ort.InferenceSession(str(self.model_dir / "embedding.onnx"),
                                                       options, providers=["CPUExecutionProvider"])
                self._diarizer = ort.InferenceSession(str(self.model_dir / "segmentation.onnx"),
                                                      options, providers=["CPUExecutionProvider"])
                metadata = self._diarizer.get_modelmeta().custom_metadata_map
                if (metadata.get("sample_rate") != "16000"
                        or metadata.get("receptive_field_size") != "991"
                        or metadata.get("receptive_field_shift") != "270"):
                    raise ValueError("Unexpected segmentation geometry")
            except Exception as error:
                self._extractor = self._diarizer = None
                raise EngineError("Не удалось загрузить локальный движок диаризации. Проверьте полный ZIP и совместимость Windows x64.") from error

    @property
    def speaker_count(self):
        with self._lock:
            return len(self._voices)

    @property
    def warning(self):
        return self._warning

    @property
    def stats(self):
        with self._lock:
            return {"speaker_count_estimate": len(self._voices), "speaker_limit": self.max_speakers,
                    "retained_turns": len(self._turns), "turn_limit": MAX_TURNS,
                    "history_seconds": HISTORY_SECONDS, "analyzed_windows": self._windows,
                    "warning": self._warning, "full_session_audio_retained": False}

    def clear(self):
        with self._lock:
            self._voices.clear()
            self._turns.clear()
            self._latest = 0.
            self._warning = ""
            self._windows = 0

    close = clear

    def invalidate(self, source, start, end):
        """Newest failed analysis masks previous overlapping window evidence."""
        with self._lock:
            self._store([SpeakerTurn(source, start, end, (), "unknown")], start, end, source)

    def _store(self, turns, start, end, source):
        kept = []
        for turn in self._turns:
            if turn.source != source or turn.end <= start or turn.start >= end:
                kept.append(turn)
            else:
                if turn.start < start:
                    kept.append(replace(turn, end=start))
                if turn.end > end:
                    kept.append(replace(turn, start=end))
        self._latest = max(self._latest, end)
        kept.extend(turns)
        self._turns = deque((t for t in sorted(kept, key=lambda t: (t.start, t.end, t.source))
                             if t.end >= self._latest - HISTORY_SECONDS), maxlen=MAX_TURNS)

    def _identify(self, vector, duration):
        """Uncertain similarity never creates a new speaker or updates centroids."""
        vector = np.asarray(vector, np.float32).reshape(-1)
        norm = float(np.linalg.norm(vector))
        if len(vector) != 256 or not np.isfinite(vector).all() or norm < 1e-8 or duration < 1.2:
            return None, None
        vector = vector / norm
        scores = sorted(((float(np.dot(v.centroid, vector)), v) for v in self._voices),
                        key=lambda item: item[0], reverse=True)
        best = scores[0][0] if scores else -1.
        if scores and best >= self.match_threshold:
            if len(scores) > 1 and best - scores[1][0] < self.ambiguity_margin:
                return None, best
            voice = scores[0][1]
            # Bounded adaptation: an entire long meeting does not freeze the
            # centroid, and one uncertain sample cannot move it.
            weight = min(voice.observations, 20)
            mixed = voice.centroid * weight + vector
            voice.centroid = mixed / max(float(np.linalg.norm(mixed)), 1e-8)
            voice.observations += 1
            return voice.speaker_id, best
        if best >= self.new_threshold or duration < 1.8:
            return None, best if scores else None
        if len(self._voices) >= self.max_speakers:
            self._warning = "Достигнут предел голосовых профилей; новые неопределённые голоса не нумеруются. Число голосов — оценка."
            return None, best if scores else None
        voice = _Voice(len(self._voices) + 1, vector.copy())
        self._voices.append(voice)
        return voice.speaker_id, None

    def _embedding(self, samples):
        import torch
        from torchaudio.compliance.kaldi import fbank
        # WeSpeaker's official ONNX inference path: 16-bit PCM amplitude,
        # 80-bin Kaldi filterbanks, Hamming25ms/10ms, zero dither, then CMN.
        # Implementation follows the algorithm, not a bundled toolkit loader.
        waveform = torch.from_numpy(np.ascontiguousarray(samples)).unsqueeze(0) * 32768
        with torch.inference_mode():
            features = fbank(waveform, num_mel_bins=80, frame_length=25.,
                             frame_shift=10., dither=0., sample_frequency=RATE,
                             window_type="hamming", use_energy=False)
            features = features - features.mean(dim=0, keepdim=True)
        return self._extractor.run(["embs"], {"feats": features.unsqueeze(0).numpy()})[0][0]

    def _local_turns(self, samples):
        padded = np.zeros((1, 1, 10 * RATE), np.float32)
        padded[0, 0, :len(samples)] = samples
        output = self._diarizer.run(["y"], {"x": padded})[0]
        if output.shape != (1, 589, 7) or not np.isfinite(output).all():
            raise ValueError("Invalid segmentation output")
        # Official pyannote powerset order: silence, three singleton slots,
        # then (0,1), (0,2), (1,2). These slots are NOT session speaker IDs.
        mapping = np.array(((0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1),
                            (1, 1, 0), (1, 0, 1), (0, 1, 1)), dtype=bool)
        activity = mapping[np.argmax(output[0], axis=1)]
        duration = len(samples) / RATE
        centers = (991 / 2 + np.arange(589) * 270) / RATE
        activity[centers >= duration] = False
        local = []
        for slot in range(3):
            begins = np.flatnonzero(np.diff(np.r_[False, activity[:, slot], False].astype(np.int8)) == 1)
            ends = np.flatnonzero(np.diff(np.r_[False, activity[:, slot], False].astype(np.int8)) == -1)
            for first, last in zip(begins, ends):
                # Construct shared boundaries from exact half-sample numerators.
                # Subtracting two rounded seconds values can create spurious
                # 1e-16s turns that collapse on the absolute session clock.
                a = max(0., ((991 - 270) / 2 + 270 * first) / RATE)
                b = min(duration, ((991 + 270) / 2 + 270 * (last - 1)) / RATE)
                if b > a:
                    local.append((a, b, slot))
        return sorted(local)

    def analyze(self, pcm, rate, source, start) -> list[SpeakerTurn]:
        values = np.asarray(pcm, np.float32)
        if (source not in ("microphone", "system") or not isinstance(rate, int)
                or not 8000 <= rate <= 192000 or values.ndim != 1
                or len(values) > rate * MAX_WINDOW_SECONDS
                or not np.isfinite(values).all() or not math.isfinite(start) or start < 0):
            raise EngineError("Некорректное окно звука для диаризации: допускается не более 9 секунд.")
        if not len(values):
            return []
        end = start + len(values) / rate
        if rate != RATE:
            # The existing application already bundles torchaudio's band-limited
            # resampler. Avoid a second, lower-quality preprocessing path.
            import torch
            from torchaudio.functional import resample
            values = resample(torch.from_numpy(values.copy()), rate, RATE).numpy()
        with self._lock:
            self.load()
            self._windows += 1
            if not np.any(values):
                self._store([], start, end, source)
                return []
            try:
                local = self._local_turns(values)
                identities = {}
                ordered_slots = sorted({t[2] for t in local},
                                       key=lambda slot: min(a for a, _, s in local if s == slot))
                for slot in ordered_slots:
                    mask = np.zeros(len(values), dtype=bool)
                    other = np.zeros(len(values), dtype=bool)
                    for a, b, speaker in local:
                        target = mask if speaker == slot else other
                        target[max(0, round(a * RATE)):min(len(values), round(b * RATE))] = True
                    clean = values[mask & ~other][:6 * RATE]
                    duration = len(clean) / RATE
                    if duration < 1.2:
                        identities[slot] = (None, None)
                        continue
                    embedding = self._embedding(clean)
                    identities[slot] = (self._identify(embedding, duration) if embedding is not None else (None, None))
                edges = sorted({0., len(values) / RATE, *(x for a, b, _ in local for x in (a, b))})
                turns = []
                for a, b in zip(edges, edges[1:]):
                    active = {slot for x, y, slot in local if x < b and y > a}
                    if not active or b <= a or start + b <= start + a:
                        continue
                    ids = tuple(sorted({identities[s][0] for s in active if identities[s][0] is not None}))
                    scores = [identities[s][1] for s in active if identities[s][1] is not None]
                    status = "overlap" if len(active) > 1 else ("provisional" if ids else "unknown")
                    turn = SpeakerTurn(source, start + a, start + b, ids, status,
                                       min(scores) if scores else None)
                    if turns and (turn.speaker_ids, turn.status, turn.confidence) == (turns[-1].speaker_ids, turns[-1].status, turns[-1].confidence):
                        turns[-1] = replace(turns[-1], end=turn.end)
                    else:
                        turns.append(turn)
                self._store(turns, start, end, source)
                return turns
            except EngineError:
                raise
            except Exception as error:
                self.invalidate(source, start, end)
                raise EngineError("Окно диаризации не обработано; текст сохранён с неопределённым говорящим.") from error

    def _word_label(self, source, word):
        a, b = word.start, word.end
        if b == a:
            a, b = a - .005, b + .005
        active = [(t, max(0., min(b, t.end) - max(a, t.start)))
                  for t in self._turns if t.source == source and t.end > a and t.start < b]
        overlaps = [(t, span) for t, span in active if t.status == "overlap" and span > 0]
        if sum(span for _, span in overlaps) >= (b - a) * .2:
            ids = tuple(sorted({i for t, _ in overlaps for i in t.speaker_ids}))
            return None, "overlap", ids, None
        totals, confidence = {}, {}
        for turn, span in active:
            if len(turn.speaker_ids) == 1 and turn.status != "unknown":
                ident = turn.speaker_ids[0]
                totals[ident] = totals.get(ident, 0.) + span
                if turn.confidence is not None:
                    confidence[ident] = turn.confidence
        ranked = sorted(totals.items(), key=lambda item: item[1], reverse=True)
        if (not ranked or ranked[0][1] < (b - a) * .5
                or len(ranked) > 1 and ranked[0][1] - ranked[1][1] < (b - a) * .15):
            return None, "unknown", (), None
        ident = ranked[0][0]
        return ident, "provisional", (), confidence.get(ident)

    def annotate(self, segment: Segment) -> list[Segment]:
        with self._lock:
            if not segment.words:
                # Guessing one label for a timestamp-free paragraph would lose
                # a turn inside that paragraph. Keep all original text intact.
                return [replace(segment, speaker_id=None, speaker_status="unknown",
                                overlapping_speakers=(), speaker_confidence=None)]
            groups = []
            for word in segment.words:
                label = self._word_label(segment.source, word)
                if groups and groups[-1][0] == label:
                    groups[-1][1].append(word)
                else:
                    groups.append((label, [word]))
            return [Segment(segment.source, words[0].start, words[-1].end,
                            " ".join(w.text for w in words), tuple(words),
                            label[0], label[1], label[2], label[3]) for label, words in groups]

    def finalize(self, segments: list[Segment]) -> list[Segment]:
        # Evidence for old words has intentionally expired. Preserve their
        # assigned IDs; never replace them with unknown or renumber on stop.
        return [replace(s, speaker_status="final" if s.speaker_status == "provisional" else s.speaker_status)
                for s in segments]
