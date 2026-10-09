"""Unit tests for application orchestration."""

import pytest

from examchaiter import app as app_module
from examchaiter.app import ExamChaiTerApp, FakeHotkeyListener, PynputHotkeyListener
from examchaiter.config import Settings
from examchaiter.errors import HotkeyError
from examchaiter.models import Answer, PipelineResult, Question, QuestionType
from examchaiter.tts import FakeSpeaker, LoopSpeaker


class FakePipeline:
    def __init__(
        self, result: PipelineResult | None = None, error: Exception | None = None
    ) -> None:
        self.result = result
        self.error = error
        self.calls: list[int] = []

    def run_once(self, hwnd: int) -> PipelineResult | None:
        self.calls.append(hwnd)
        if self.error is not None:
            raise self.error
        return self.result


class FakePresenter:
    def __init__(self) -> None:
        self.results: list[PipelineResult] = []

    def show(self, result: PipelineResult) -> None:
        self.results.append(result)


def _result() -> PipelineResult:
    return PipelineResult(
        question=Question(text="Question"),
        answer=Answer(qtype=QuestionType.CHOICE, content="B"),
    )


def _app(
    *,
    pipeline: FakePipeline | None = None,
    loop_speaker: LoopSpeaker | None = None,
    presenter: FakePresenter | None = None,
    listener: FakeHotkeyListener | None = None,
) -> ExamChaiTerApp:
    selected_listener = listener or FakeHotkeyListener({})
    return ExamChaiTerApp(
        settings=Settings(_env_file=None),
        pipeline=pipeline or FakePipeline(result=_result()),
        loop_speaker=loop_speaker or LoopSpeaker(FakeSpeaker(), interval_s=0.01),
        presenter=presenter or FakePresenter(),
        hotkey_factory=lambda _bindings: selected_listener,
    )


def test_on_answer_with_no_foreground_window_logs_warning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pipeline = FakePipeline(result=_result())
    app = _app(pipeline=pipeline)
    monkeypatch.setattr(app_module, "get_foreground_window", lambda: None)

    app._on_answer()

    assert pipeline.calls == []


def test_on_answer_calls_pipeline_and_presenter(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _result()
    pipeline = FakePipeline(result=result)
    presenter = FakePresenter()
    app = _app(pipeline=pipeline, presenter=presenter)
    monkeypatch.setattr(app_module, "get_foreground_window", lambda: 42)

    app._on_answer()

    assert pipeline.calls == [42] and presenter.results == [result]


def test_on_answer_swallows_pipeline_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _app(pipeline=FakePipeline(error=RuntimeError("boom")))
    monkeypatch.setattr(app_module, "get_foreground_window", lambda: 42)

    app._on_answer()

    assert app._last_result is None


def test_on_toggle_tts_starts_then_stops() -> None:
    speaker = FakeSpeaker()
    app = _app(loop_speaker=LoopSpeaker(speaker, interval_s=0.01))
    app._last_result = _result()

    app._on_toggle_tts()
    running_after_start = app.loop_speaker.is_running()
    app._on_toggle_tts()

    assert running_after_start is True and app.loop_speaker.is_running() is False


def test_on_toggle_tts_without_answer_logs_warning() -> None:
    speaker = FakeSpeaker()
    app = _app(loop_speaker=LoopSpeaker(speaker, interval_s=0.01))

    app._on_toggle_tts()

    assert speaker.spoken == [] and app.loop_speaker.is_running() is False


def test_on_quit_stops_listener_and_speaker() -> None:
    loop = LoopSpeaker(FakeSpeaker(), interval_s=0.01)
    listener = FakeHotkeyListener({})
    app = _app(loop_speaker=loop, listener=listener)
    app._listener = listener
    loop.start("answer")

    app._on_quit()

    assert listener.stop_count == 1 and loop.is_running() is False


def test_run_exits_when_stop_event_set() -> None:
    listener = FakeHotkeyListener({})
    app = _app(listener=listener)
    app._stop_event.set()

    result = app.run()

    assert result == 0 and listener.start_count == 1


def test_hotkey_import_failure_raises_hotkey_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_import(_name: str) -> object:
        raise ImportError("pynput unavailable")

    monkeypatch.setattr(app_module.importlib, "import_module", fail_import)

    with pytest.raises(HotkeyError):
        PynputHotkeyListener({})


def test_stop_is_idempotent() -> None:
    app = _app()
    app.stop()
    app.stop()

    assert app.stop() is None
