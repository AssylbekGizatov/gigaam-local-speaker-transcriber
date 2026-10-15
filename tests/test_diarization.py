"""Deterministic identity/timing safeguards, distinct from model quality tests."""
from dataclasses import replace

import numpy as np
import pytest

from gigaam_meeting.contracts import Segment, SpeakerTurn, Word
from gigaam_meeting.diarization import DiarizationEngine, HISTORY_SECONDS, MAX_TURNS
from gigaam_meeting.engine import EngineError


def vector(index=0):
    result = np.zeros(256, np.float32)
    result[index] = 1
    return result


def fake_engine(turns=((0., 3., 0),), vectors=None, **kwargs):
    engine = DiarizationEngine(**kwargs)
    engine._diarizer = engine._extractor = object()
    engine._local_turns = lambda _: list(turns)
    engine._embedding = lambda _: vector() if vectors is None else vectors.pop(0)
    return engine


def test_ids_shared_across_sources_pause_and_late_windows():
    engine = fake_engine()
    audio = np.ones(3 * 16000, np.float32)
    assert engine.analyze(audio, 16000, "microphone", 0)[0].speaker_ids == (1,)
    assert engine.analyze(audio, 16000, "system", 500)[0].speaker_ids == (1,)
    assert engine.analyze(audio, 16000, "microphone", 10000)[0].speaker_ids == (1,)
    assert engine.speaker_count == 1


def test_distinct_voices_one_microphone_not_one_source_one_speaker():
    engine = fake_engine(((0., 2.1, 0), (2.2, 4.5, 1)), [vector(0), vector(1)])
    turns = engine.analyze(np.ones(5 * 16000, np.float32), 16000, "microphone", 10)
    assert {t.speaker_ids for t in turns} == {(1,), (2,)}
    assert engine.speaker_count == 2
    assert turns[0].start == 10


def test_short_voice_never_creates_speaker():
    engine = fake_engine(((0., .5, 0),))
    turns = engine.analyze(np.ones(16000, np.float32), 16000, "system", 0)
    assert turns[0].speaker_ids == ()
    assert turns[0].status == "unknown"
    assert engine.speaker_count == 0


def test_gray_zone_does_not_split_identity_or_move_centroid():
    engine = DiarizationEngine()
    assert engine._identify(vector(), 3)[0] == 1
    original = engine._voices[0].centroid.copy()
    uncertain = .55 * vector() + np.sqrt(1 - .55 ** 2) * vector(1)
    assert engine._identify(uncertain, 3)[0] is None
    assert engine.speaker_count == 1
    np.testing.assert_array_equal(engine._voices[0].centroid, original)


def test_two_similar_profiles_are_ambiguous_not_forced_assignment():
    engine = DiarizationEngine(match_threshold=.65, new_threshold=.45)
    engine._identify(vector(0), 3)
    engine._identify(vector(1), 3)
    assert engine._identify((vector(0) + vector(1)) / np.sqrt(2), 3)[0] is None


def test_registry_limit_visible_and_bounded():
    engine = DiarizationEngine(max_speakers=2)
    assert engine._identify(vector(0), 3)[0] == 1
    assert engine._identify(vector(1), 3)[0] == 2
    assert engine._identify(vector(2), 3)[0] is None
    assert engine.speaker_count == 2
    assert engine.warning and engine.stats["speaker_limit"] == 2


def test_invalid_nan_embedding_never_adds_profile():
    engine = DiarizationEngine()
    assert engine._identify(np.full(256, np.nan), 3) == (None, None)
    assert engine.speaker_count == 0


def test_overlap_uses_only_clean_evidence_and_preserves_multiple_ids():
    engine = fake_engine(((0., 4., 0), (2., 6., 1)), [vector(0), vector(1)])
    turns = engine.analyze(np.ones(6 * 16000, np.float32), 16000, "system", 0)
    assert [(t.start, t.end, t.speaker_ids, t.status) for t in turns] == [
        (0., 2., (1,), "provisional"), (2., 4., (1, 2), "overlap"),
        (4., 6., (2,), "provisional")]


def test_fully_overlapping_voices_not_used_as_independent_embeddings():
    engine = fake_engine(((0., 4., 0), (0., 4., 1)))
    engine._embedding = lambda _: pytest.fail("Overlap PCM must not enter embedding model")
    turns = engine.analyze(np.ones(4 * 16000, np.float32), 16000, "system", 0)
    assert turns[0].status == "overlap" and turns[0].speaker_ids == ()
    assert engine.speaker_count == 0


def test_annotate_splits_words_without_loss_duplication_or_time_shift():
    engine = DiarizationEngine()
    engine._turns.extend([SpeakerTurn("microphone", 0, 1, (1,)),
                          SpeakerTurn("microphone", 1, 3, (2,))])
    words = (Word(.1, .4, "Сегодня"), Word(.5, .8, "today"), Word(1.2, 1.5, "бүгін"))
    segment = Segment("microphone", .1, 1.5, "Сегодня today бүгін", words)
    result = engine.annotate(segment)
    assert [s.speaker_id for s in result] == [1, 2]
    retained = tuple(w for s in result for w in s.words)
    assert retained == words and all(a is b for a, b in zip(retained, words))
    assert " ".join(s.text for s in result) == segment.text


def test_word_crossing_equally_two_turns_unknown():
    engine = DiarizationEngine()
    engine._turns.extend([SpeakerTurn("system", 0, 1, (1,)), SpeakerTurn("system", 1, 2, (2,))])
    word = Word(.9, 1.1, "yes")
    result = engine.annotate(Segment("system", .9, 1.1, "yes", (word,)))
    assert result[0].speaker_status == "unknown" and result[0].words[0] is word


def test_overlap_keeps_asr_word_once_and_unknown_attribution():
    engine = DiarizationEngine()
    engine._turns.append(SpeakerTurn("system", 0, 2, (1, 2), "overlap"))
    word = Word(.3, .7, "hello")
    result = engine.annotate(Segment("system", .3, .7, "hello", (word,)))
    assert len(result) == 1 and result[0].words == (word,)
    assert result[0].speaker_id is None and result[0].overlapping_speakers == (1, 2)
    assert result[0].speaker_status == "overlap"


def test_timestamp_free_text_retained_without_guessing():
    segment = Segment("microphone", 0, 5, "keep entire paragraph")
    result = DiarizationEngine().annotate(segment)
    assert result[0].text == segment.text and result[0].speaker_status == "unknown"


def test_new_overlap_window_replaces_stale_turns_not_double_counts():
    engine = DiarizationEngine()
    engine._store([SpeakerTurn("system", 0, 8, (1,))], 0, 8, "system")
    engine._store([SpeakerTurn("system", 7, 15, (2,))], 7, 15, "system")
    assert [(t.start, t.end, t.speaker_ids) for t in engine._turns] == [(0, 7, (1,)), (7, 15, (2,))]


def test_failed_window_masks_old_evidence_with_unknown():
    engine = DiarizationEngine()
    engine._store([SpeakerTurn("system", 0, 8, (1,))], 0, 8, "system")
    engine.invalidate("system", 7, 15)
    word = Word(7.2, 7.5, "keep")
    assert engine.annotate(Segment("system", 7.2, 7.5, "keep", (word,)))[0].speaker_id is None


def test_turn_history_bounded_and_centroid_remains_for_long_session():
    engine = DiarizationEngine()
    engine._identify(vector(), 3)
    engine._store([SpeakerTurn("system", i / 100, (i + 1) / 100, (1,)) for i in range(MAX_TURNS + 100)],
                  0, 30, "system")
    assert len(engine._turns) == MAX_TURNS
    engine._store([], HISTORY_SECONDS * 100, HISTORY_SECONDS * 100 + 1, "system")
    assert not engine._turns and engine._identify(vector(), 3)[0] == 1


def test_finalize_keeps_expired_labels_word_identity_and_order():
    engine = DiarizationEngine()
    word = Word(0, .5, "text")
    original = Segment("system", 0, .5, "text", (word,), 3, "provisional")
    result = engine.finalize([original])[0]
    assert result == replace(original, speaker_status="final")
    assert result.words[0] is word and result.speaker_id == 3


def test_clear_new_session_starts_at_one_only_explicitly():
    engine = DiarizationEngine()
    engine._identify(vector(), 3)
    engine.clear()
    assert engine.speaker_count == 0 and not engine._turns
    assert engine._identify(vector(1), 3)[0] == 1


@pytest.mark.parametrize("audio,rate,start", [(np.ones(160001), 16000, 0),
                                              (np.array([np.nan]), 16000, 0),
                                              (np.ones(20), 0, 0), (np.ones(20), 16000, -1)])
def test_window_bounds_invalid_audio_actionable(audio, rate, start):
    with pytest.raises(EngineError):
        fake_engine().analyze(audio, rate, "microphone", start)


def test_missing_model_fails_offline_with_clear_error(tmp_path):
    with pytest.raises(EngineError, match="Модели диаризации не найдены"):
        DiarizationEngine(tmp_path).load()


def test_corrupt_model_fails_before_import_or_download(tmp_path):
    (tmp_path / "segmentation.onnx").write_bytes(b"wrong")
    with pytest.raises(EngineError, match="повреждена"):
        DiarizationEngine(tmp_path).load()


def test_license_cache_and_weight_pins_match_runtime(tmp_path):
    from build.acquire_diarization import LICENSE_FILES, MODEL_FILES, acquire, digest
    from gigaam_meeting.diarization import MODEL_FILES as runtime
    from pathlib import Path
    assert MODEL_FILES == runtime
    notices = Path(__file__).resolve().parent.parent / "assets/licenses/diarization"
    assert all(digest(notices / name) == expected for name, expected in LICENSE_FILES.items())
    with pytest.raises(RuntimeError, match="missing or failed pinned"):
        acquire(tmp_path / "models", tmp_path / "missing-license-cache")


def test_powerset_geometry_output_produces_overlap_intervals():
    engine = DiarizationEngine()
    output = np.full((1, 589, 7), -20, np.float32)
    output[:, :, 0] = 0
    output[:, 0:60, 1] = 5
    output[:, 60:120, 4] = 5
    class Session:
        def run(self, names, inputs):
            assert inputs["x"].shape == (1, 1, 160000)
            return [output]
    engine._diarizer = Session()
    result = engine._local_turns(np.ones(3 * 16000, np.float32))
    assert {t[2] for t in result} == {0, 1}
    assert result[0][0] == pytest.approx((991 / 2 - 270 / 2) / 16000)
    assert all(0 <= a < b <= 3 for a, b, _ in result)


def test_adjacent_segmentation_boundaries_share_exact_lattice_not_zero_turns():
    engine = DiarizationEngine()
    output = np.full((1, 589, 7), -20, np.float32)
    output[:, :, 0] = 0
    output[:, :200, 1] = 5
    output[:, 200:400, 2] = 5
    class Session:
        def run(self, *_):
            return [output]
    engine._diarizer = Session()
    local = engine._local_turns(np.ones(8 * 16000, np.float32))
    assert local[0][1] == local[1][0]


def test_first_observed_local_voice_numbered_one_not_arbitrary_model_slot():
    engine = fake_engine(((0., 2.1, 2), (2.2, 4.5, 0)), [vector(0), vector(1)])
    turns = engine.analyze(np.ones(5 * 16000, np.float32), 16000, "microphone", 10)
    assert turns[0].speaker_ids == (1,) and turns[1].speaker_ids == (2,)
