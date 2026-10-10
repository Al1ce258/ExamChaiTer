"""Unit tests for speaker adapters and loop control."""

import sys
import threading
import time
import types

import pytest

from examchaiter.tts import speaker as speaker_module
from examchaiter.tts.speaker import FakeSpeaker, LoopSpeaker, Pyttsx3Speaker


def test_fake_speaker_with_speak_and_stop_records_calls() -> None:
    speaker = FakeSpeaker()

    speaker.speak("hello")
    speaker.stop()

    assert speaker.spoken == ["hello"] and len(speaker.stopped) == 1


def test_loop_speaker_with_short_interval_speaks_repeatedly() -> None:
    speaker = FakeSpeaker()
    loop = LoopSpeaker(speaker, interval_s=0.01)

    loop.start("repeat")
    time.sleep(0.05)
    loop.stop()

    assert len(speaker.spoken) >= 2 and all(text == "repeat" for text in speaker.spoken)


def test_loop_speaker_after_stop_is_not_running() -> None:
    speaker = FakeSpeaker()
    loop = LoopSpeaker(speaker, interval_s=0.01)
    loop.start("repeat")

    loop.stop()

    assert loop.is_running() is False


def test_loop_speaker_after_stop_does_not_grow_spoken() -> None:
    speaker = FakeSpeaker()
    loop = LoopSpeaker(speaker, interval_s=0.01)
    loop.start("repeat")
    time.sleep(0.05)
    loop.stop()
    stopped_length = len(speaker.spoken)

    time.sleep(0.03)

    assert len(speaker.spoken) == stopped_length


def test_loop_speaker_with_second_start_switches_text() -> None:
    speaker = FakeSpeaker()
    loop = LoopSpeaker(speaker, interval_s=0.01)
    loop.start("old")
    time.sleep(0.03)

    loop.start("new")
    time.sleep(0.03)
    loop.stop()

    assert speaker.spoken[-1] == "new"


def test_loop_speaker_stop_without_start_does_not_raise() -> None:
    loop = LoopSpeaker(FakeSpeaker())

    assert loop.stop() is None


def test_loop_speaker_stop_is_idempotent() -> None:
    loop = LoopSpeaker(FakeSpeaker())
    loop.start("repeat")

    loop.stop()
    loop.stop()

    assert loop.is_running() is False


def test_pyttsx3_speaker_with_import_failure_disables_itself(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_import(_name: str) -> object:
        raise ImportError("pyttsx3 unavailable")

    monkeypatch.setattr(speaker_module.importlib, "import_module", fail_import)
    speaker = Pyttsx3Speaker()

    speaker.speak("text")

    assert speaker._disabled is True


def test_pyttsx3_speaker_with_fake_module_speaks_and_stops(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spoken: list[str] = []
    started = threading.Event()
    stopped = threading.Event()
    release = threading.Event()

    class FakeEngine:
        def setProperty(self, _name: str, _value: object) -> None:
            return None

        def say(self, text: str) -> None:
            spoken.append(text)

        def runAndWait(self) -> None:
            started.set()
            release.wait(0.5)

        def stop(self) -> None:
            stopped.set()
            release.set()

    module = types.ModuleType("pyttsx3")
    module.init = lambda: FakeEngine()
    monkeypatch.setitem(sys.modules, "pyttsx3", module)
    speaker = Pyttsx3Speaker()

    speaker.speak("hello")
    started.wait(0.5)
    speaker.stop()

    assert spoken == ["hello"] and stopped.is_set()


def test_pyttsx3_speaker_with_say_failure_disables_after_first_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    failed = threading.Event()
    init_calls = 0

    class FakeEngine:
        def setProperty(self, _name: str, _value: object) -> None:
            return None

        def say(self, _text: str) -> None:
            failed.set()
            raise RuntimeError("say failed")

        def runAndWait(self) -> None:
            return None

        def stop(self) -> None:
            return None

    def init_engine() -> FakeEngine:
        nonlocal init_calls
        init_calls += 1
        return FakeEngine()

    module = types.ModuleType("pyttsx3")
    module.init = init_engine
    monkeypatch.setitem(sys.modules, "pyttsx3", module)
    speaker = Pyttsx3Speaker()

    speaker.speak("first")
    failed.wait(0.5)
    speaker.speak("second")
    time.sleep(0.01)

    assert speaker._disabled is True and init_calls == 1


def test_loop_speaker_with_empty_text_and_tiny_interval_records_empty() -> None:
    speaker = FakeSpeaker()
    loop = LoopSpeaker(speaker, interval_s=0.001)

    loop.start("")
    time.sleep(0.01)
    loop.stop()

    assert len(speaker.spoken) >= 1 and all(text == "" for text in speaker.spoken)


def test_loop_speaker_stop_then_start_again_stops_cleanly() -> None:
    loop = LoopSpeaker(FakeSpeaker(), interval_s=0.001)
    loop.start("first")
    loop.stop()
    loop.start("second")
    loop.stop()

    assert loop.is_running() is False


def test_loop_speaker_max_repeats_stops_after_n() -> None:
    speaker = FakeSpeaker()
    loop = LoopSpeaker(speaker, interval_s=0.01)

    loop.start("repeat", max_repeats=3)
    deadline = time.monotonic() + 0.5
    while loop.is_running() and time.monotonic() < deadline:
        time.sleep(0.005)

    assert len(speaker.spoken) == 3 and loop.is_running() is False


def test_loop_speaker_max_repeats_none_is_infinite() -> None:
    speaker = FakeSpeaker()
    loop = LoopSpeaker(speaker, interval_s=0.01)

    loop.start("repeat")
    time.sleep(0.05)
    running = loop.is_running()
    loop.stop()

    assert running is True and len(speaker.spoken) >= 2
