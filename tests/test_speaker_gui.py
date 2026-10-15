"""Speaker UI contracts in a withdrawn, isolated Tk process; no audio capture."""
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.parametrize("case", ["toggle", "labels", "update"])
def test_speaker_ui_without_capture(case):
    completed = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "--child", case],
        cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=15,
    )
    if completed.returncode == 77:
        pytest.skip("Tk display unavailable; no hardware audio is needed")
    assert completed.returncode == 0, completed.stdout + completed.stderr


def run_case(case):
    import gc
    from queue import Queue
    import tkinter as tk

    from gigaam_meeting.contracts import Event, Segment
    from gigaam_meeting.gui import MeetingApp
    from test_gui import FakeManager, catalog_ready

    try:
        root = tk.Tk()
    except tk.TclError:
        return 77
    root.withdraw()
    manager, events = FakeManager(), Queue()
    app = None
    try:
        app = MeetingApp(root, manager, events)
        catalog_ready(app, manager, events)
        assert app.diarization.get() and not manager.starts and not manager.previews
        if case == "toggle":
            app.combos["microphone"].current(1)
            app.consent.set(True)
            app.diarization.set(False)
            app._start()
            assert not manager.starts[-1].diarization
            assert str(app.diarization_check["state"]) == "disabled"
            events.put(Event("finished"))
            app._poll()
            assert not app.consent.get()
            assert str(app.diarization_check["state"]) == "normal"
            app.diarization.set(True)
            app.consent.set(True)
            app._start()
            assert manager.starts[-1].diarization
            assert "предварительные" in app.speaker_status.get()
        elif case == "labels":
            for segment in (
                Segment("microphone", 0, 1, "локальный", speaker_id=2, speaker_status="provisional"),
                Segment("system", 1, 2, "неясный", speaker_status="unknown"),
                Segment("system", 2, 3, "одновременно", speaker_status="overlap", overlapping_speakers=(1, 2)),
            ):
                events.put(Event("segment", data={"segment": segment}))
            events.put(Event("diarization_stats", data={"estimated_speakers": 2, "mode": "fragment-based preliminary"}))
            app._poll()
            rendered = app.transcript.get("1.0", "end")
            assert "Микрофон · Спикер 2 (предварительно)" in rendered
            assert "Звук компьютера · Неопределённый говорящий" in rendered
            assert "Перекрывающаяся речь: Спикер 1 + Спикер 2" in rendered
            assert "примерно 2" in app.speaker_status.get()
            assert "не число участников" in app.speaker_status.get()
            events.put(Event("diarization_stats", data={"estimated_speakers": 2, "mode": "final"}))
            app._poll()
            assert "Обработка фрагментов завершена" in app.speaker_status.get()
            assert "предварительными" not in app.speaker_status.get()
        elif case == "update":
            preliminary = Segment("microphone", 0, 2, "первый второй", speaker_status="unknown")
            trailing = Segment("system", 3, 4, "дальше", speaker_id=1, speaker_status="provisional")
            first = Segment("microphone", 0, 1, "первый", speaker_id=1, speaker_status="provisional")
            second = Segment("microphone", 1, 2, "второй", speaker_id=2, speaker_status="provisional")
            events.put(Event("segment", data={"segment": preliminary}))
            events.put(Event("segment", data={"segment": trailing}))
            events.put(Event("diarization_update", data={"removed": [preliminary], "added": [first, second]}))
            app._poll()
            assert app.segments == [first, second, trailing]
            rendered = app.transcript.get("1.0", "end")
            assert "первый второй" not in rendered
            assert rendered.index("первый") < rendered.index("второй") < rendered.index("дальше")
            assert "Спикер 2" in rendered and len(app.segment_marks) == 3
        else:
            raise AssertionError("Unknown case")
        return 0
    finally:
        manager.release.set()
        manager.close()
        enabled = gc.isenabled()
        gc.disable()
        try:
            for identifier in root.tk.call("after", "info"):
                root.after_cancel(identifier)
            root.destroy()
            app = None
            root = None
            gc.collect()
        finally:
            if enabled:
                gc.enable()


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    sys.exit(run_case(sys.argv[2]))
