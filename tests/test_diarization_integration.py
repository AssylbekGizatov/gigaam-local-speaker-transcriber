"""Session/stream contracts with fake inference and devices, never hardware.

These are routing/conservation checks, not a diarization quality benchmark.
The encoded PCM values stand for known voices without interpreting languages.
"""
from dataclasses import replace
from queue import Empty, Queue
from time import monotonic, sleep

import numpy as np
import pytest

from gigaam_meeting.contracts import AudioBlock, AudioDevice, Segment, SessionConfig, SpeakerTurn, Word
from gigaam_meeting.engine import EngineError
from gigaam_meeting.session import SessionManager
import gigaam_meeting.session as session_module


MIC = AudioDevice(1, "Synthetic microphone", "microphone", 16000, 1, fingerprint="synthetic-microphone")
SYSTEM = AudioDevice(2, "Synthetic output", "system", 48000, 2, fingerprint="synthetic-output")
TOKENS = {11: "русская", 22: "english", 33: "қазақша", 44: "mixed"}


def wait_until(condition, timeout=3):
    deadline = monotonic() + timeout
    while not condition():
        if monotonic() >= deadline:
            raise AssertionError("Fake session did not complete within its bounded test deadline")
        sleep(.005)


def drain_events(events):
    result = []
    while True:
        try:
            result.append(events.get_nowait())
        except Empty:
            return result


def runs(samples, rate):
    cuts = np.flatnonzero(np.diff(samples) != 0) + 1
    boundaries = np.r_[0, cuts, len(samples)]
    return [(int(round(float(samples[start]) * 100)), start / rate, end / rate)
            for start, end in zip(boundaries, boundaries[1:]) if samples[start] != 0]


class FakeTranscriber:
    def __init__(self):
        self.load_calls = 0

    def load(self):
        self.load_calls += 1

    def transcribe_words(self, samples, rate):
        return [Word(start, end, TOKENS[voice]) for voice, start, end in runs(samples, rate)]


class FakeDiarizer:
    def __init__(self, *, load_error=None, analysis_error=False, annotation_error=False, finalize_error=False):
        self.load_error = load_error
        self.analysis_error = analysis_error
        self.annotation_error = annotation_error
        self.finalize_error = finalize_error
        self.turns = []
        self.calls = []
        self.identities = set()
        self.finalized_input = None
        self.warning = ""

    def load(self):
        if self.load_error:
            raise self.load_error

    @property
    def speaker_count(self):
        return len(self.identities)

    @property
    def stats(self):
        return {"estimated_speakers": self.speaker_count}

    def analyze(self, samples, rate, source, start):
        self.calls.append((source, start, rate))
        if self.analysis_error:
            raise RuntimeError("private dependency diagnostic must never reach transcript or logs")
        created = []
        for code, a, b in runs(samples, rate):
            # Codes 11/33/44 represent the SAME voice speaking three languages;
            # code 22 is a second voice. Identity does not derive from source.
            identity = 2 if code == 22 else 1
            self.identities.add(identity)
            created.append(SpeakerTurn(source, start + a, start + b, (identity,)))
        self.turns.extend(created)
        return created

    def annotate(self, segment):
        if self.annotation_error:
            raise RuntimeError("private annotation dependency details")
        groups = []
        for word in segment.words:
            center = (word.start + word.end) / 2
            turn = next((turn for turn in self.turns if turn.source == segment.source
                         and turn.start <= center <= turn.end), None)
            identity = turn.speaker_ids[0] if turn else None
            status = "provisional" if identity is not None else "unknown"
            if groups and groups[-1][0] == (identity, status):
                groups[-1][1].append(word)
            else:
                groups.append(((identity, status), [word]))
        if not groups:
            return [replace(segment, speaker_status="unknown")]
        return [replace(segment, start=words[0].start, end=words[-1].end,
                        text=" ".join(word.text for word in words), words=tuple(words),
                        speaker_id=identity, speaker_status=status)
                for (identity, status), words in groups]

    def finalize(self, segments):
        self.finalized_input = tuple(segments)
        if self.finalize_error:
            raise RuntimeError("private finalization details")
        return [replace(segment, speaker_status="final" if segment.speaker_id is not None else "unknown")
                for segment in segments]

    def clear(self):
        self.turns.clear()
        self.identities.clear()

    close = clear


class FakeCapture:
    def __init__(self, devices, on_block, on_error, on_level, clock_origin):
        self.devices = devices
        self.on_block = on_block
        self.clock_origin = clock_origin
        self.started = False
        self.paused = False
        self.tail_on_stop = None

    def start(self):
        self.started = True

    def pause(self):
        self.paused = True

    def resume(self):
        self.paused = False

    def stop(self):
        self.started = False
        if self.tail_on_stop is not None:
            self.on_block(self.tail_on_stop)


@pytest.fixture
def session_factory(tmp_path):
    sessions = []

    def create(*, backend=None, enabled=True, echo=False):
        captures, factories = [], []
        backend = backend or FakeDiarizer()

        def make_capture(*args):
            capture = FakeCapture(*args)
            captures.append(capture)
            return capture

        def make_diarizer():
            factories.append(True)
            return backend

        events = Queue()
        manager = SessionManager(events, transcriber_factory=FakeTranscriber,
                                 capture_factory=make_capture, diarizer_factory=make_diarizer)
        config = SessionConfig(MIC, SYSTEM, True, tmp_path / "no-recordings", reduce_echo=echo,
                               diarization=enabled)
        sessions.append(manager)
        return manager, captures, events, config, backend, factories

    yield create
    for manager in sessions:
        if manager.state not in {"idle", "error"}:
            manager.stop()
            wait_until(lambda: manager.state in {"idle", "error"})
        manager.close()


def block(source="microphone", *, start=0, voices=(11,), seconds_per_voice=.5):
    rate = 16000 if source == "microphone" else 48000
    mono = np.concatenate([np.full(round(rate * seconds_per_voice), voice / 100, np.float32) for voice in voices])
    values = mono if source == "microphone" else np.column_stack([mono, mono])
    return AudioBlock(source, values, rate, start)


def start(manager, config):
    manager.start(config)
    wait_until(lambda: manager.state == "recording")


def stop(manager):
    manager.stop()
    wait_until(lambda: manager.state == "idle")


def test_two_people_at_one_microphone_are_separate_turns_and_final_tail_precedes_finished(session_factory):
    manager, captures, events, config, backend, _ = session_factory()
    start(manager, config)
    captures[0].tail_on_stop = block(start=7.12345, voices=(11, 22))
    stop(manager)
    assert [(segment.source, segment.speaker_id, segment.text) for segment in manager.segments] == [
        ("microphone", 1, "русская"), ("microphone", 2, "english")]
    assert [(word.start, word.end) for segment in manager.segments for word in segment.words] == [
        (7.12345, 7.62345), (7.62345, 8.12345)]
    assert all(segment.speaker_status == "final" for segment in manager.segments)
    assert backend.finalized_input and all(segment.speaker_status == "provisional" for segment in backend.finalized_input)
    delivered = drain_events(events)
    kinds = [event.kind for event in delivered]
    assert kinds.index("segment") < kinds.index("diarization_update") < kinds.index("finished")
    assert kinds.count("finished") == 1
    assert any(event.kind == "diarization_stats" and event.data["estimated_speakers"] == 2
               and event.data["mode"] == "final" for event in delivered)
    assert not config.output_folder.exists()


def test_shared_ids_across_channels_languages_and_pause_without_resetting_clock(session_factory):
    manager, captures, events, config, backend, _ = session_factory()
    start(manager, config)
    captures[0].on_block(block("system", start=1.125, voices=(11, 22)))
    manager.pause()
    wait_until(lambda: manager.state == "paused" and len(manager.segments) == 2)
    provisional = list(manager.segments)
    assert all(segment.speaker_status == "provisional" for segment in provisional)
    assert backend.speaker_count == 2
    manager.resume()
    wait_until(lambda: manager.state == "recording")
    captures[0].on_block(block("microphone", start=900.625, voices=(33, 44)))
    stop(manager)
    words = [(segment.source, word.text, word.start, word.end, segment.speaker_id)
             for segment in manager.segments for word in segment.words]
    assert words == [("system", "русская", 1.125, 1.625, 1),
                     ("system", "english", 1.625, 2.125, 2),
                     ("microphone", "қазақша", 900.625, 901.125, 1),
                     ("microphone", "mixed", 901.125, 901.625, 1)]
    assert backend.calls == [("system", 1.125, 48000), ("microphone", 900.625, 16000)]
    assert any(event.kind == "diarization_stats" for event in drain_events(events))


def test_late_echo_removes_all_split_display_views_and_preserves_words_once(session_factory, monkeypatch):
    from gigaam_meeting.echo import EchoAudioHistory
    monkeypatch.setattr(EchoAudioHistory, "matches", lambda *args: True)
    manager, _, events, config, backend, _ = session_factory(echo=True)
    start(manager, config)
    echoed = tuple(Word(1.123 + index * .4, 1.333 + index * .4, token)
                   for index, token in enumerate(("today", "we", "тексереміз")))
    own = Word(4.123456, 4.654321, "own-response")
    backend.turns = [SpeakerTurn("microphone", 1, 1.6, (1,)), SpeakerTurn("microphone", 1.6, 3, (2,)),
                     SpeakerTurn("microphone", 4, 5, (1,)), SpeakerTurn("system", 1, 3, (2,))]
    backend.identities = {1, 2}
    mic = Segment("microphone", echoed[0].start, own.end, "today we тексереміз own-response", (*echoed, own))
    system = Segment("system", echoed[0].start, echoed[-1].end, "today we тексереміз", echoed)
    manager._segment(mic)
    assert len(manager.segments) == 3  # Multiple views map to the one raw echo record.
    manager._segment(system)
    stop(manager)
    microphone = [segment for segment in manager.segments if segment.source == "microphone"]
    assert len(microphone) == 1 and microphone[0].words == (own,) and microphone[0].words[0] is own
    system_words = tuple(word for segment in manager.segments if segment.source == "system" for word in segment.words)
    assert system_words == echoed
    assert [segment.text for segment in microphone] == ["own-response"]
    delivered = drain_events(events)
    updates = [event for event in delivered if event.kind == "echo_update"]
    assert len(updates) == 1 and len(updates[0].data["removed"]) == 3
    assert sum(len(segment.words) for segment in manager.segments) == 4


@pytest.mark.parametrize("failure", ["analysis_error", "annotation_error", "finalize_error"])
def test_diarization_failure_preserves_every_asr_word_and_safe_warning(session_factory, failure):
    backend = FakeDiarizer(**{failure: True})
    manager, captures, events, config, _, _ = session_factory(backend=backend)
    start(manager, config)
    captures[0].on_block(block(start=4.125, voices=(11, 22)))
    stop(manager)
    assert [(word.text, word.start, word.end) for segment in manager.segments for word in segment.words] == [
        ("русская", 4.125, 4.625), ("english", 4.625, 5.125)]
    delivered = drain_events(events)
    warnings = [event for event in delivered if event.kind == "warning"]
    assert warnings and not any("private" in event.message for event in delivered)
    if failure != "finalize_error":
        assert all(segment.speaker_id is None and segment.speaker_status == "unknown" for segment in manager.segments)
    else:
        assert all(segment.speaker_status == "provisional" for segment in manager.segments)


def test_requested_missing_local_model_blocks_capture_but_disabled_mode_does_not_load_it(session_factory):
    missing = FakeDiarizer(load_error=EngineError("Локальная модель диаризации не найдена; распакуйте models."))
    manager, captures, events, config, _, factories = session_factory(backend=missing)
    manager.start(config)
    wait_until(lambda: manager.state == "error")
    assert not captures and factories == [True] and not config.output_folder.exists()
    assert any("диаризации не найдена" in event.message for event in drain_events(events) if event.kind == "error")
    plain, captures, _, config, _, factories = session_factory(backend=missing, enabled=False)
    start(plain, config)
    captures[0].on_block(block(start=1.125, voices=(11, 22)))
    stop(plain)
    assert not factories
    assert " ".join(segment.text for segment in plain.segments) == "русская english"
    assert all(segment.speaker_status == "off" and segment.speaker_id is None for segment in plain.segments)


def test_disabled_diarization_keeps_legacy_processor_constructor_without_keyword(session_factory, monkeypatch):
    made = []

    class LegacyProcessor:
        def __init__(self, model, segment, status):
            made.append(True)
            self.pending_seconds = 0

        def start(self):
            pass

        def stop(self):
            pass

    monkeypatch.setattr(session_module, "StreamProcessor", LegacyProcessor)
    manager, captures, _, config, _, factories = session_factory(enabled=False)
    start(manager, config)
    stop(manager)
    assert made == [True] and not factories and len(captures) == 1


def test_actual_turn_assignment_keeps_each_word_once_with_switches_unknown_and_overlap():
    # Use actual assignment rules with independently specified speaker evidence.
    # Loading native inference/models is deliberately unnecessary for this test.
    from gigaam_meeting.diarization import DiarizationEngine
    engine = DiarizationEngine()
    turns = [SpeakerTurn("microphone", 0, 1, (1,)),
             SpeakerTurn("microphone", 1, 2, (2,)),
             SpeakerTurn("microphone", 2, 2.7, (1, 2), "overlap")]
    engine._store(turns, 0, 4, "microphone")
    engine._store([SpeakerTurn("system", 0, 1, (9,))], 0, 4, "system")
    words = (Word(.123456, .456789, "қазақша"), Word(.712345, 1.312345, "boundary"),
             Word(1.523456, 1.912345, "русский"), Word(2.123456, 2.523456, "English"),
             Word(2.823456, 3.212345, "short-uncertain"))
    original = Segment("microphone", words[0].start, words[-1].end,
                       " ".join(word.text for word in words), words)
    assigned = engine.annotate(original)
    flattened = tuple(word for segment in assigned for word in segment.words)
    assert flattened == words and all(actual is expected for actual, expected in zip(flattened, words))
    assert " ".join(segment.text for segment in assigned) == original.text
    assert [(segment.speaker_id, segment.speaker_status, segment.overlapping_speakers) for segment in assigned] == [
        (1, "provisional", ()), (None, "unknown", ()), (2, "provisional", ()),
        (None, "overlap", (1, 2)), (None, "unknown", ())]
    assert all(segment.source == "microphone" for segment in assigned)


def test_actual_finalization_preserves_old_word_times_and_ids_after_history_expiry():
    from gigaam_meeting.diarization import DiarizationEngine
    engine = DiarizationEngine()
    engine._store([SpeakerTurn("system", 1, 3, (4,))], 1, 3, "system")
    word = Word(1.123456, 1.654321, "historical-text")
    labeled = engine.annotate(Segment("system", word.start, word.end, word.text, (word,)))
    engine._store([SpeakerTurn("microphone", 900, 903, (4,))], 900, 903, "microphone")
    assert not any(turn.start < 100 for turn in engine._turns)
    final = engine.finalize(labeled)
    assert len(final) == 1 and final[0].speaker_id == 4 and final[0].speaker_status == "final"
    assert final[0].words == (word,) and final[0].words[0] is word
    assert (final[0].start, final[0].end, final[0].text) == (word.start, word.end, word.text)


def test_actual_registry_short_uncertain_samples_do_not_inflate_count_and_capacity_is_explicit():
    from gigaam_meeting.diarization import DiarizationEngine
    engine = DiarizationEngine(max_speakers=2)
    vectors = np.eye(256, dtype=np.float32)[:3]
    assert engine._identify(vectors[0], .5)[0] is None and engine.speaker_count == 0
    assert engine._identify(vectors[0], 3)[0] == 1
    assert engine._identify(vectors[1], 3)[0] == 2
    assert engine._identify(vectors[0], 2)[0] == 1  # Identity survives a later observation.
    assert engine._identify(vectors[2], 3)[0] is None
    assert engine.speaker_count == 2 and engine.warning


@pytest.mark.parametrize("malformed", ["empty", "duplicate", "drop", "word_time", "source", "text", "word_order"])
def test_malformed_annotation_falls_back_to_unknown_without_losing_asr(session_factory, malformed):
    manager, _, events, config, backend, _ = session_factory()
    words = (Word(5.123456, 5.321234, "қазақша"), Word(5.432123, 5.876543, "русский"),
             Word(6.123456, 6.654321, "English"))
    original = Segment("microphone", words[0].start, words[-1].end,
                       " ".join(word.text for word in words), words)
    valid = replace(original, speaker_id=1, speaker_status="provisional")
    alterations = {
        "empty": [],
        "duplicate": [valid, valid],
        "drop": [replace(valid, words=words[:-1], text="қазақша русский")],
        "word_time": [replace(valid, words=(replace(words[0], start=words[0].start + .001), *words[1:]))],
        "source": [replace(valid, source="system")],
        "text": [replace(valid, text="changed transcript")],
        "word_order": [replace(valid, words=tuple(reversed(words)))],
    }
    backend.annotate = lambda segment: alterations[malformed]
    start(manager, config)
    manager._segment(original)
    stop(manager)
    assert len(manager.segments) == 1
    preserved = manager.segments[0]
    assert (preserved.source, preserved.start, preserved.end, preserved.text) == (
        original.source, original.start, original.end, original.text)
    assert preserved.words == words and all(a is b for a, b in zip(preserved.words, words))
    assert preserved.speaker_id is None and preserved.speaker_status == "unknown"
    assert any(event.kind == "warning" and "текст сохранён" in event.message for event in drain_events(events))


def test_echo_display_mapping_is_bounded_by_live_history_and_whole_transcript_is_retained(session_factory):
    manager, _, events, config, _, _ = session_factory(echo=True)
    start(manager, config)
    peak = 0
    originals = []
    for index in range(160):
        for source in ("microphone", "system"):
            offset = index * 2 + (.05 if source == "system" else 0)
            words = tuple(Word(offset + .1 + n * .2, offset + .2 + n * .2, token)
                          for n, token in enumerate(("unique", str(index), source)))
            raw = Segment(source, words[0].start, words[-1].end,
                          " ".join(word.text for word in words), words)
            originals.append(raw)
            manager._segment(raw)
            retained = {id(item) for record in manager._echo._microphone for item in record.visible}
            retained.update(id(item) for item in manager._echo._system)
            assert set(manager._speaker_views).issubset(retained)
            peak = max(peak, len(manager._speaker_views))
    # One paragraph per source every two seconds: even hundreds of historical
    # paragraphs must leave only the recent echo-edit candidates in the map.
    assert 0 < peak < 100 and len(manager.segments) == len(originals) == 320
    stop(manager)
    assert not manager._speaker_views
    assert [(segment.source, segment.words) for segment in manager.segments] == [
        (segment.source, segment.words) for segment in sorted(originals, key=lambda item: (item.start, item.end, item.source))]
    assert any(event.kind == "finished" for event in drain_events(events))

