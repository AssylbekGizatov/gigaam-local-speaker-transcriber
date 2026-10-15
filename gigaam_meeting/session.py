"""Explicit session lifecycle; UI never waits for model, drivers, or inference."""
from concurrent.futures import ThreadPoolExecutor
import threading
from time import perf_counter

from .audio import AudioCaptureError, CaptureGroup, list_devices
from .contracts import Event
from .engine import EngineError, Transcriber
from .echo import EchoDuplicateFilter
from .recording import AudioRecorder
from .streaming import StreamProcessor
from .storage import validate_local_path


def _make_diarizer():
    from .diarization import DiarizationEngine
    return DiarizationEngine()


class SessionManager:
    def __init__(self, event_queue, *, transcriber_factory=Transcriber, capture_factory=CaptureGroup,
                 device_provider=list_devices, diarizer_factory=_make_diarizer):
        self.events = event_queue
        self.state = "idle"
        self.segments = []
        self._transcriber_factory = transcriber_factory
        self._capture_factory = capture_factory
        self._device_provider = device_provider
        self._diarizer_factory = diarizer_factory
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="session-control")
        self._lock = threading.RLock()
        self._cancel = threading.Event()
        self._capture = self._processor = self._recorder = self._transcriber = None
        self._last_level = {}
        self._last_lag = 0
        self._stop_pending = False
        self._closed = False
        self._error = None
        self._echo = None
        self._diarizer = None
        # Raw echo-filter objects are mapped to their split display objects.
        # Late reference-channel echo edits must remove every corresponding
        # speaker turn, rather than compare raw and labelled Segment equality.
        self._speaker_views = {}
        self._speaker_warning = ""

    def _event(self, kind, message="", **data):
        self.events.put(Event(kind, message, data))

    def _state(self, value):
        self.state = value
        self._event("state", state=value)

    def devices(self):
        # Enumeration opens no capture streams and accesses no audio content.
        return self._device_provider()

    def _reserve(self, config, state):
        with self._lock:
            if self._closed or self.state not in {"idle", "error"}:
                raise AudioCaptureError("Сначала завершите текущий сеанс.")
            if not config.consent or not (config.microphone or config.system):
                raise AudioCaptureError("Выберите источники и явно разрешите захват.")
            if config.microphone and config.microphone.source != "microphone" or config.system and config.system.source != "system":
                raise AudioCaptureError("Неверный тип источника. Обновите список устройств.")
            validate_local_path(config.output_folder)
            self._cancel.clear()
            self._stop_pending = False
            self._error = None
            self._state(state)

    def start(self, config):
        with self._lock:
            self._reserve(config, "loading")
            self.segments = []
            self._speaker_views = {}
            self._speaker_warning = ""
            self._diarizer = None
            self._echo = EchoDuplicateFilter() if config.reduce_echo and config.microphone and config.system else None
            self._executor.submit(self._start, config)

    def _start(self, config):
        try:
            if self._transcriber is None:
                self._transcriber = self._transcriber_factory()
            self._transcriber.load()
            if self._cancel.is_set():
                return
            if config.diarization:
                self._diarizer = self._diarizer_factory()
                self._diarizer.load()
                self._speaker_stats()
            if self._cancel.is_set():
                return
            options = {"diarizer": self._diarizer} if self._diarizer else {}
            self._processor = StreamProcessor(self._transcriber, self._segment, self._status, **options)
            self._processor.start()
            if config.save_audio:
                self._recorder = AudioRecorder(config.output_folder, self._fault)
            self._capture = self._capture_factory([d for d in (config.microphone, config.system) if d],
                self._block, self._fault, self._level, perf_counter())
            self._capture.cancel_event = self._cancel
            # Stop during slow model initialization never opens an audio stream.
            if self._cancel.is_set():
                return
            self._state("starting")
            self._capture.start()
            with self._lock:
                if self._cancel.is_set():
                    return
                self._state("recording")
        except (EngineError, AudioCaptureError) as exc:
            if not self._cancel.is_set():
                self._fault(str(exc))
        except Exception:
            self._fault("Не удалось запустить локальное распознавание. Проверьте целостность ZIP и доступную память.")

    def preview(self, config, seconds=3):
        with self._lock:
            self._reserve(config, "preview")
            self._executor.submit(self._preview, config, min(3, max(0.1, seconds)))

    def _preview(self, config, seconds):
        deadline = None
        try:
            self._capture = self._capture_factory([d for d in (config.microphone, config.system) if d],
                lambda block: None, self._fault, self._level, perf_counter())
            self._capture.cancel_event = self._cancel
            if self._cancel.is_set():
                return
            # A driver can stall while starting the second source. The deadline
            # cancels native callbacks independently of the control worker.
            deadline = threading.Timer(seconds, self.stop)
            deadline.daemon = True
            deadline.start()
            self._capture.start()
            self._cancel.wait(seconds)
        except AudioCaptureError as exc:
            if not self._cancel.is_set():
                self._fault(str(exc))
        except Exception:
            self._fault("Проверка устройств завершилась ошибкой. Обновите список и проверьте подключение.")
        finally:
            if deadline:
                deadline.cancel()
            self.stop()

    def _block(self, block):
        # Already captured owned blocks are accepted during pause/stop draining.
        echo = self._echo
        if echo:
            echo.feed(block)
        if self._processor:
            self._processor.feed(block)
        if self._recorder:
            self._recorder.feed(block)
        now = perf_counter()
        if self._processor and now - self._last_lag > 1:
            self._last_lag = now
            self._event("lag", pending_seconds=self._processor.pending_seconds)

    def _level(self, source, value):
        now = perf_counter()
        if now - self._last_level.get(source, 0) >= 0.1 and self.events.qsize() < 128:
            self._last_level[source] = now
            self._event("level", source=source, level=value)

    def _segment(self, segment):
        removed, added = self._echo.accept(segment) if self._echo else ([], [segment])
        displayed_removed, displayed_added = [], []
        with self._lock:
            for old in removed:
                views = self._speaker_views.pop(id(old), [old])
                for view in views:
                    if view in self.segments:
                        self.segments.remove(view)
                        displayed_removed.append(view)
            for raw in added:
                if self._diarizer:
                    try:
                        views = self._diarizer.annotate(raw)
                        # A malformed annotation must never silently drop or
                        # duplicate ASR words, even when it does not raise.
                        if (not views or any(view.source != raw.source for view in views)
                                or tuple(word for view in views for word in view.words) != raw.words
                                or " ".join(" ".join(view.text.split()) for view in views) != " ".join(raw.text.split())):
                            raise ValueError("speaker_annotation_changed_words")
                    except Exception:
                        from dataclasses import replace
                        views = [replace(raw, speaker_id=None, speaker_status="unknown", overlapping_speakers=())]
                        self._event("warning", "Метка говорящего недоступна; распознанный текст сохранён.")
                else:
                    views = [raw]
                self._speaker_views[id(raw)] = views
                displayed_added.extend(views)
            self.segments.extend(displayed_added)
            self.segments.sort(key=lambda s: (s.start, s.end, s.source))
        if displayed_removed:
            self._event("echo_update", removed=displayed_removed, added=displayed_added)
        else:
            for item in displayed_added:
                self._event("segment", segment=item)
        if self._echo:
            self._event("echo_stats", hidden_words=self._echo.hidden_words)
            # Only EchoDuplicateFilter's retained raw objects can receive a
            # late edit. Do not build a second full-session object archive.
            retained = {id(item) for record in self._echo._microphone for item in record.visible}
            retained.update(id(item) for item in self._echo._system)
            self._speaker_views = {key: value for key, value in self._speaker_views.items() if key in retained}
        else:
            self._speaker_views.clear()
        self._speaker_stats()

    def _speaker_stats(self):
        if self._diarizer is not None:
            warning = getattr(self._diarizer, "warning", "")
            if warning and warning != self._speaker_warning:
                self._speaker_warning = warning
                self._event("warning", warning)
            self._event("diarization_stats", estimated_speakers=self._diarizer.speaker_count,
                        mode="fragment_preliminary", message="Число голосов — оценка. Метки фрагментов предварительные до остановки.")

    def _status(self, kind, data):
        if kind == "progress":
            self._event("lag", pending_seconds=data.get("pending_seconds", 0))
        elif kind in {"inference_failed", "invalid_audio", "capture_timestamp"}:
            self._fault(data.get("message", "Ошибка обработки звука."))
        else:
            self._event("warning", data.get("message", "Пропуск аудио."))

    def _fault(self, message):
        with self._lock:
            if self._error is None:
                self._error = message
        self.stop()

    def pause(self):
        self._executor.submit(self._pause)

    def _pause(self):
        if self.state != "recording" or self._cancel.is_set():
            return
        try:
            self._capture.pause()
            self._processor.pause_flush()
            self._state("paused")
        except Exception:
            self._fault("Не удалось безопасно поставить захват на паузу. Сеанс остановлен.")

    def resume(self):
        self._executor.submit(self._resume)

    def _resume(self):
        if self.state != "paused" or self._cancel.is_set():
            return
        try:
            self._state("starting")
            self._capture.resume()
            with self._lock:
                if not self._cancel.is_set():
                    self._state("recording")
        except AudioCaptureError as exc:
            if not self._cancel.is_set():
                self._fault(str(exc))
        except Exception:
            self._fault("Устройство изменилось. Сеанс остановлен; выберите источники заново.")

    def stop(self):
        self._cancel.set()
        with self._lock:
            if self._stop_pending or self.state in {"idle", "error"}:
                return
            self._stop_pending = True
            self._executor.submit(self._finish)

    def _finish(self):
        self._state("stopping")
        try:
            # Each resource must be stopped even if an earlier driver fails.
            for index, resource in enumerate((self._capture, self._processor, self._recorder)):
                if index == 1:
                    self._state("draining")
                if resource:
                    try:
                        resource.stop()
                    except Exception:
                        self._error = self._error or "Ошибка завершения сеанса. Полученный текст доступен для экспорта."
        finally:
            with self._lock:
                if self._diarizer:
                    try:
                        previous = list(self.segments)
                        self.segments = self._diarizer.finalize(previous)
                        self._event("diarization_update", removed=previous, added=list(self.segments))
                        self._event("diarization_stats", estimated_speakers=self._diarizer.speaker_count,
                                    mode="final", message="Обработка завершена; неопределённые и перекрывающиеся голоса остаются отмеченными.")
                    except Exception:
                        self._event("warning", "Не удалось уточнить метки говорящих. Предварительный текст сохранён.")
                    self._diarizer = None
                self._speaker_views.clear()
                if self._echo:
                    self._echo.clear()
                    self._echo = None
                self._capture = self._processor = self._recorder = None
                self._event("lag", pending_seconds=0)
                self._state("error" if self._error else "idle")
                if self._error:
                    self._event("error", self._error)
                self._event("finished")

    def close(self):
        with self._lock:
            self._closed = True
            self.stop()
            self._executor.shutdown(wait=False)
