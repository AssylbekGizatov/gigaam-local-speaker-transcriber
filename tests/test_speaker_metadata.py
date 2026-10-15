"""Public synthetic metadata only: no capture of microphone/system devices."""
from dataclasses import asdict, replace
import json
from pathlib import Path

import pytest

from gigaam_meeting.contracts import Segment, SpeakerTurn, Word
from gigaam_meeting.echo import EchoDuplicateFilter, MAX_WORDS
from gigaam_meeting.exports import export_transcript, speaker_label


def timed_segment(source, words, **speaker):
    return Segment(source, words[0].start, words[-1].end,
                   " ".join(word.text for word in words), tuple(words), **speaker)


@pytest.mark.parametrize("system_first", [True, False])
def test_echo_edit_keeps_exact_surviving_words_and_all_speaker_metadata(monkeypatch, system_first):
    # The acoustic detector is independently exercised with real licensed PCM
    # in test_echo.py. Here a deterministic detector isolates the destructive
    # transcript edit that previously erased word timestamps.
    reducer = EchoDuplicateFilter()
    monkeypatch.setattr(reducer.audio, "matches", lambda start, end: True)
    reference = tuple(Word(2 + index * .5, 2.321 + index * .5, token)
                      for index, token in enumerate(("сегодня", "we", "тексереміз")))
    before, after = Word(1.00123, 1.37891, "local-before"), Word(5.00017, 5.44581, "local-after")
    echo_words = tuple(Word(word.start + .12345, word.end + .12345, word.text) for word in reference)
    original = timed_segment("microphone", (before, *echo_words, after),
                             speaker_id=7, speaker_status="provisional",
                             overlapping_speakers=(7, 9), speaker_confidence=.8123)
    system = timed_segment("system", reference, speaker_id=3, speaker_status="final")
    visible = []
    for record in ((system, original) if system_first else (original, system)):
        removed, added = reducer.accept(record)
        for old in removed:
            visible.remove(old)
        visible.extend(added)
    microphone = sorted((segment for segment in visible if segment.source == "microphone"), key=lambda item: item.start)
    assert tuple(word for segment in microphone for word in segment.words) == (before, after)
    assert " ".join(segment.text for segment in microphone) == "local-before local-after"
    assert [(segment.start, segment.end) for segment in microphone] == [(before.start, before.end), (after.start, after.end)]
    assert all(segment.words[0] is word for segment, word in zip(microphone, (before, after)))
    for segment in microphone:
        assert (segment.speaker_id, segment.speaker_status, segment.overlapping_speakers,
                segment.speaker_confidence) == (7, "provisional", (7, 9), .8123)
    retained_system = next(segment for segment in visible if segment.source == "system")
    assert retained_system is system
    assert retained_system.words == reference
    assert original.words == (before, *echo_words, after)  # An edit never mutates the input.
    assert reducer.hidden_words == 3


@pytest.mark.parametrize("source", ["microphone", "system"])
@pytest.mark.parametrize("word_count", [0, 4, MAX_WORDS + 1])
def test_echo_no_match_and_fallback_keep_word_timing_and_identity(source, word_count):
    words = tuple(Word(3.14159 + index * .25, 3.34159 + index * .25, f"token{index}")
                  for index in range(word_count))
    original = (timed_segment(source, words, speaker_id=2, speaker_status="final") if words
                else Segment(source, 3.14159, 3.34159, "untimed legacy text", speaker_id=2,
                             speaker_status="final"))
    removed, added = EchoDuplicateFilter().accept(original)
    assert removed == []
    assert len(added) == 1 and added[0] is original
    assert added[0].words is original.words
    assert asdict(added[0]) == asdict(original)


def test_contracts_keep_old_positional_construction_and_source_separate_from_person():
    word = Word(20.125, 20.875, "speech")
    old_style = Segment("system", word.start, word.end, word.text, (word,))
    assert old_style.speaker_id is None and old_style.speaker_status == "off"
    assert old_style.overlapping_speakers == () and old_style.speaker_confidence is None
    turn = SpeakerTurn("microphone", 20.125, 20.875, (2, 3))
    assert turn.status == "provisional" and turn.confidence is None
    same_person_system = replace(old_style, speaker_id=2, speaker_status="final")
    same_person_microphone = replace(same_person_system, source="microphone")
    assert same_person_system.speaker_id == same_person_microphone.speaker_id
    assert same_person_system.source != same_person_microphone.source


@pytest.mark.parametrize("metadata,expected", [
    ({}, "Диаризация выключена"),
    ({"speaker_status": "unknown"}, "Неопределённый говорящий"),
    ({"speaker_status": "provisional"}, "Неопределённый говорящий (предварительно)"),
    ({"speaker_id": 5, "speaker_status": "provisional"}, "Спикер 5 (предварительно)"),
    ({"speaker_id": 5, "speaker_status": "final"}, "Спикер 5"),
    ({"speaker_status": "provisional", "overlapping_speakers": (2, 5)},
     "Перекрывающаяся речь: Спикер 2 + Спикер 5 (предварительно)"),
    ({"speaker_status": "overlap"}, "Перекрывающаяся речь: говорящие не определены"),
])
def test_uncertainty_and_overlap_labels_do_not_invent_names(metadata, expected):
    assert speaker_label(Segment("system", 0, 1, "test", **metadata)) == expected


def extracted(path: Path, kind: str) -> str:
    if kind in {"TXT", "MD"}:
        return path.read_text(encoding="utf-8")
    if kind == "DOCX":
        docx = pytest.importorskip("docx")
        return "\n".join(paragraph.text for paragraph in docx.Document(path).paragraphs)
    pypdf = pytest.importorskip("pypdf")
    return "\n".join(page.extract_text() for page in pypdf.PdfReader(path).pages)


@pytest.mark.parametrize("kind", ["TXT", "MD", "DOCX", "PDF"])
def test_exports_preserve_sources_speakers_uncertainty_and_tokens_once(tmp_path, kind):
    if kind == "PDF":
        pytest.importorskip("reportlab")
        from gigaam_meeting.exports import _pdf_font
        try:
            _pdf_font()
        except FileNotFoundError:
            pytest.skip("No bundled Unicode font in this test environment")
    records = [
        timed_segment("system", (Word(20.111, 20.333, "second-voice"),),
                      speaker_id=2, speaker_status="final"),
        timed_segment("microphone", (Word(1.123, 1.789, "бірінші-voice"),),
                      speaker_id=1, speaker_status="provisional"),
        timed_segment("system", (Word(25.432, 25.976, "short-uncertain"),),
                      speaker_status="unknown"),
        timed_segment("microphone", (Word(35.125, 35.750, "overlap-estimate"),),
                      speaker_status="final", overlapping_speakers=(1, 2)),
        timed_segment("system", (Word(40.321, 40.876, "diarization-off"),)),
    ]
    before = [asdict(record) for record in records]
    file = export_transcript(records, tmp_path / f"speakers.{kind.lower()}", kind)
    output = extracted(file, kind)
    # PDF page width may wrap long source/speaker headers. Compare their
    # reading order after whitespace normalization without ignoring content.
    readable = " ".join(output.split())
    for phrase in ("бірінші-voice", "second-voice", "short-uncertain", "overlap-estimate", "diarization-off"):
        assert output.count(phrase) == 1
    for expected in ("Источник: Микрофон", "Источник: Звук компьютера", "Говорящий: Спикер 1 (предварительно)",
                     "Говорящий: Спикер 2", "Говорящий: Неопределённый говорящий",
                     "Говорящий: Перекрывающаяся речь: Спикер 1 + Спикер 2", "Говорящий: Диаризация выключена"):
        assert expected in readable
    assert output.index("00:00:01.123") < output.index("00:00:20.111")
    assert "00:00:35.125" in output and "00:00:35.750" in output
    assert [asdict(record) for record in records] == before


def test_json_export_preserves_exact_word_timing_speaker_metadata_and_unknown_legacy_text(tmp_path):
    words = (Word(4500.123456789, 4500.321987654, "қазақша"),
             Word(4500.456789123, 4501.987654321, "mixed"))
    precise = timed_segment("system", words, speaker_id=8, speaker_status="provisional",
                            overlapping_speakers=(8, 11), speaker_confidence=.76123456789)
    legacy = Segment("microphone", 4502.25, 4503.75, "Untimed speech preserved", speaker_status="unknown")
    file = export_transcript([legacy, precise], tmp_path / "structured.json", "JSON")
    raw = file.read_text(encoding="utf-8")
    payload = json.loads(raw)
    assert payload["schemaVersion"] == 1
    assert payload["timeUnit"] == "seconds_from_session_start_including_pauses"
    assert payload["speakerConfidenceInterpretation"] == "uncalibrated_score_not_probability"
    assert "қазақша" in raw  # UTF-8 text, not escaped replacement glyphs.
    assert payload["segments"][0] == {
        "source": "system", "start": words[0].start, "end": words[-1].end,
        "text": "қазақша mixed", "words": [asdict(word) for word in words],
        "speaker_id": 8, "speaker_status": "provisional", "overlapping_speakers": [8, 11],
        "speaker_confidence": .76123456789,
    }
    assert payload["segments"][1]["words"] == []  # No guessed timestamps for legacy text.
    assert payload["segments"][1]["text"] == legacy.text
    original = file.read_bytes()
    with pytest.raises(FileExistsError):
        export_transcript([], file, "JSON")
    assert file.read_bytes() == original

