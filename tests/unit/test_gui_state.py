"""Unit tests for GUI controller state without importing PySide6."""

from dataclasses import dataclass, field

from examchaiter.config import Settings
from examchaiter.gui.state import GuiController
from examchaiter.models import Answer, PipelineResult, Question, QuestionType, WindowInfo


@dataclass
class FakePipeline:
    result: PipelineResult | None
    error: Exception | None = None
    calls: list[int] = field(default_factory=list)

    def run_once(self, hwnd: int) -> PipelineResult | None:
        self.calls.append(hwnd)
        if self.error is not None:
            raise self.error
        return self.result


@dataclass
class FakeLoopSpeaker:
    running: bool = False
    started: list[str] = field(default_factory=list)
    stop_count: int = 0

    def start(self, text: str) -> None:
        self.started.append(text)
        self.running = True

    def stop(self) -> None:
        self.stop_count += 1
        self.running = False

    def is_running(self) -> bool:
        return self.running


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


def _controller(
    *, pipeline: FakePipeline | None = None, windows: list[WindowInfo] | None = None
) -> tuple[GuiController, FakePipeline, FakeLoopSpeaker, FakePresenter]:
    selected_pipeline = pipeline or FakePipeline(result=_result())
    loop = FakeLoopSpeaker()
    presenter = FakePresenter()
    selected_windows = windows or [WindowInfo(hwnd=1, title="Exam", rect=(0, 0, 10, 10))]
    controller = GuiController(
        pipeline_factory=lambda: selected_pipeline,  # type: ignore[arg-type]
        loop_speaker=loop,  # type: ignore[arg-type]
        presenter=presenter,  # type: ignore[arg-type]
        settings=Settings(_env_file=None),
        _list_windows_fn=lambda _title: selected_windows,
    )
    return controller, selected_pipeline, loop, presenter


def test_answer_once_without_selected_window_returns_none() -> None:
    controller, pipeline, _loop, _presenter = _controller()

    result = controller.answer_once()

    assert result is None and pipeline.calls == []


def test_answer_once_with_selected_window_calls_pipeline_and_presenter() -> None:
    controller, pipeline, _loop, presenter = _controller()
    controller.pick_window(1)

    result = controller.answer_once()

    assert result is not None and pipeline.calls == [1] and presenter.results[0].answer == result


def test_answer_once_with_pipeline_exception_recovers_busy_state() -> None:
    controller, _pipeline, _loop, _presenter = _controller(
        pipeline=FakePipeline(result=None, error=RuntimeError("boom"))
    )
    controller.pick_window(1)

    result = controller.answer_once()

    assert result is None and controller.state.busy is False


def test_toggle_tts_without_answer_returns_false_and_does_not_start() -> None:
    controller, _pipeline, loop, _presenter = _controller()

    result = controller.toggle_tts()

    assert result is False and loop.started == []


def test_toggle_tts_with_answer_starts_then_stops() -> None:
    controller, _pipeline, loop, _presenter = _controller()
    controller.pick_window(1)
    controller.answer_once()

    started = controller.toggle_tts()
    stopped = controller.toggle_tts()

    assert started is True and stopped is False and loop.stop_count == 1


def test_answer_once_while_busy_returns_none_without_second_call() -> None:
    controller, pipeline, _loop, _presenter = _controller()
    controller.pick_window(1)
    controller.state.busy = True

    result = controller.answer_once()

    assert result is None and pipeline.calls == []


def test_list_windows_with_exception_returns_empty_list() -> None:
    controller = GuiController(
        pipeline_factory=lambda: FakePipeline(result=_result()),  # type: ignore[arg-type]
        loop_speaker=FakeLoopSpeaker(),  # type: ignore[arg-type]
        presenter=FakePresenter(),  # type: ignore[arg-type]
        settings=Settings(_env_file=None),
        _list_windows_fn=lambda _title: (_ for _ in ()).throw(RuntimeError("failed")),
    )

    assert controller.list_windows() == []
