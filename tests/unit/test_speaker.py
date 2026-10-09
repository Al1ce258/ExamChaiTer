"""Unit tests for speaker adapters and loop control."""

import time

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
