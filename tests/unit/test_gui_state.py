"""Unit tests for GUI controller state without importing PySide6."""

from dataclasses import dataclass, field

from examchaiter.config import Settings
from examchaiter.gui.state import GuiController
from examchaiter.models import Answer, PipelineResult, Question, QuestionType, WindowInfo
from examchaiter.storage.config_store import AppConfig
from examchaiter.storage.history_store import HistoryEntry, SessionMeta


@dataclass
class FakePipeline:
    result: PipelineResult | None
    error: Exception | None = None
    calls: list[int] = field(default_factory=list)

    def run_once(self, hwnd: int) -> list[PipelineResult]:
        self.calls.append(hwnd)
        if self.error is not None:
            raise self.error
        return [self.result] if self.result is not None else []


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


@dataclass
class FakeConfigStore:
    config: AppConfig = field(default_factory=AppConfig)
    saved: list[AppConfig] = field(default_factory=list)

    def load(self) -> AppConfig:
        return self.config

    def save(self, cfg: AppConfig) -> None:
        self.saved.append(cfg)


@dataclass
class FakeHistoryStore:
    sessions: list[SessionMeta] = field(default_factory=list)
    created: list[str] = field(default_factory=list)
    entries: dict[str, dict[str, HistoryEntry]] = field(default_factory=dict)
    search_results: list[tuple[str, HistoryEntry]] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)

    def list_sessions(self) -> list[SessionMeta]:
        return list(self.sessions)

    def create_session(self, name: str) -> SessionMeta:
        self.created.append(name)
        session_id = name or "session-1"
        meta = SessionMeta(session_id, session_id, 0.0, 0)
        self.sessions.append(meta)
        return meta

    def load_session(self, session_id: str) -> dict[str, HistoryEntry]:
        return dict(self.entries.get(session_id, {}))

    def search(self, keyword: str) -> list[tuple[str, HistoryEntry]]:
        return list(self.search_results)

    def delete_session(self, session_id: str) -> bool:
        self.deleted.append(session_id)
        return True


@dataclass
class FakeAutopilot:
    session_id: str
    callbacks: object
    started: list[int] = field(default_factory=list)
    stop_count: int = 0

    def start(self, hwnd: int) -> None:
        self.started.append(hwnd)

    def stop(self, timeout: float = 2.0) -> None:
        self.stop_count += 1


@dataclass
class BrokenStore:
    """Store double whose every operation fails."""

    def load(self) -> AppConfig:
        raise RuntimeError("boom")

    def save(self, cfg: AppConfig) -> None:
        raise RuntimeError("boom")

    def list_sessions(self) -> list[SessionMeta]:
        raise RuntimeError("boom")

    def create_session(self, name: str) -> SessionMeta:
        raise RuntimeError("boom")

    def load_session(self, session_id: str) -> dict[str, HistoryEntry]:
        raise RuntimeError("boom")

    def search(self, keyword: str) -> list[tuple[str, HistoryEntry]]:
        raise RuntimeError("boom")

    def delete_session(self, session_id: str) -> bool:
        raise RuntimeError("boom")


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
        config_store=FakeConfigStore(),  # type: ignore[arg-type]
        history_store=FakeHistoryStore(),  # type: ignore[arg-type]
        autopilot_factory=lambda _sid, _cb: FakeAutopilot(_sid, _cb),  # type: ignore[arg-type]
        list_windows_fn=lambda _title: selected_windows,
    )
    return controller, selected_pipeline, loop, presenter


def _auto_controller() -> tuple[
    GuiController, FakeConfigStore, FakeHistoryStore, list[FakeAutopilot]
]:
    created: list[FakeAutopilot] = []

    def factory(session_id: str, callbacks: object) -> FakeAutopilot:
        autopilot = FakeAutopilot(session_id, callbacks)
        created.append(autopilot)
        return autopilot

    config_store = FakeConfigStore()
    history_store = FakeHistoryStore()
    controller = GuiController(
        pipeline_factory=lambda: FakePipeline(result=_result()),  # type: ignore[arg-type]
        loop_speaker=FakeLoopSpeaker(),  # type: ignore[arg-type]
        presenter=FakePresenter(),  # type: ignore[arg-type]
        settings=Settings(_env_file=None),
        config_store=config_store,  # type: ignore[arg-type]
        history_store=history_store,  # type: ignore[arg-type]
        autopilot_factory=factory,  # type: ignore[arg-type]
        list_windows_fn=lambda _title: [],
    )
    return controller, config_store, history_store, created


def _broken_controller() -> GuiController:
    return GuiController(
        pipeline_factory=lambda: FakePipeline(result=_result()),  # type: ignore[arg-type]
        loop_speaker=FakeLoopSpeaker(),  # type: ignore[arg-type]
        presenter=FakePresenter(),  # type: ignore[arg-type]
        settings=Settings(_env_file=None),
        config_store=BrokenStore(),  # type: ignore[arg-type]
        history_store=BrokenStore(),  # type: ignore[arg-type]
        autopilot_factory=lambda _sid, _cb: FakeAutopilot(_sid, _cb),  # type: ignore[arg-type]
        list_windows_fn=lambda _title: [],
    )


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
        config_store=FakeConfigStore(),  # type: ignore[arg-type]
        history_store=FakeHistoryStore(),  # type: ignore[arg-type]
        autopilot_factory=lambda _sid, _cb: FakeAutopilot(_sid, _cb),  # type: ignore[arg-type]
        list_windows_fn=lambda _title: (_ for _ in ()).throw(RuntimeError("failed")),
    )

    assert controller.list_windows() == []


def test_pick_window_with_unknown_hwnd_returns_none() -> None:
    controller, _pipeline, _loop, _presenter = _controller()

    assert controller.pick_window(99) is None


def test_answer_once_with_none_result_recovers_busy_state() -> None:
    controller, _pipeline, _loop, _presenter = _controller(pipeline=FakePipeline(result=None))
    controller.pick_window(1)

    result = controller.answer_once()

    assert result is None and controller.state.busy is False


def test_toggle_tts_with_start_exception_returns_false() -> None:
    class BrokenLoop(FakeLoopSpeaker):
        def start(self, text: str) -> None:
            raise RuntimeError(text)

    controller, _pipeline, _loop, _presenter = _controller()
    controller.loop_speaker = BrokenLoop()  # type: ignore[assignment]
    controller.state.last_answer = Answer(qtype=QuestionType.CHOICE, content="B")

    result = controller.toggle_tts()

    assert result is False and controller.state.tts_running is False


def test_stop_tts_is_idempotent_and_clears_state() -> None:
    controller, _pipeline, loop, _presenter = _controller()
    controller.state.tts_running = True

    controller.stop_tts()
    controller.stop_tts()

    assert loop.stop_count == 2 and controller.is_tts_running() is False


def test_get_config_returns_appconfig_from_store() -> None:
    controller, config_store, _history, _created = _auto_controller()
    config_store.config = AppConfig(llm_model="deepseek-reasoner")

    assert controller.get_config().llm_model == "deepseek-reasoner"


def test_save_config_calls_store_save() -> None:
    controller, config_store, _history, _created = _auto_controller()
    config = AppConfig(llm_model="custom")

    controller.save_config(config)

    assert config_store.saved == [config]


def test_list_sessions_delegates_to_store() -> None:
    controller, _config, history_store, _created = _auto_controller()
    history_store.sessions = [SessionMeta("s1", "Session 1", 0.0, 0)]

    assert controller.list_sessions() == history_store.sessions


def test_load_history_delegates_to_store() -> None:
    controller, _config, history_store, _created = _auto_controller()
    entry = HistoryEntry("h1", "question", "choice", "A")
    history_store.entries["s1"] = {"h1": entry}

    assert controller.load_history("s1") == {"h1": entry}


def test_search_history_delegates_to_store() -> None:
    controller, _config, history_store, _created = _auto_controller()
    entry = HistoryEntry("h1", "question", "choice", "A")
    history_store.search_results = [("s1", entry)]

    assert controller.search_history("question") == [("s1", entry)]


def test_delete_session_delegates_to_store() -> None:
    controller, _config, history_store, _created = _auto_controller()

    result = controller.delete_session("s1")

    assert result is True and history_store.deleted == ["s1"]


def test_start_auto_creates_session_and_starts_autopilot() -> None:
    controller, _config, history_store, created = _auto_controller()

    controller.start_auto(7, "")

    assert (history_store.created, created[0].started, controller.is_auto_running()) == (
        [""],
        [7],
        True,
    )


def test_start_auto_twice_stops_previous_first() -> None:
    controller, _config, _history, created = _auto_controller()

    controller.start_auto(1, "first")
    controller.start_auto(2, "second")

    assert (created[0].stop_count, created[1].started) == (1, [2])


def test_stop_auto_idempotent() -> None:
    controller, _config, _history, created = _auto_controller()
    controller.start_auto(1, "session")

    controller.stop_auto()
    controller.stop_auto()

    assert (created[0].stop_count, controller.is_auto_running()) == (1, False)


def test_is_auto_running_reflects_state() -> None:
    controller, _config, _history, _created = _auto_controller()
    controller.start_auto(1, "session")

    running = controller.is_auto_running()
    controller.stop_auto()

    assert (running, controller.is_auto_running()) == (True, False)


def test_get_config_with_store_error_returns_default() -> None:
    assert _broken_controller().get_config() == AppConfig()


def test_list_sessions_with_store_error_returns_empty() -> None:
    assert _broken_controller().list_sessions() == []


def test_load_history_with_store_error_returns_empty() -> None:
    assert _broken_controller().load_history("s1") == {}


def test_search_history_with_store_error_returns_empty() -> None:
    assert _broken_controller().search_history("keyword") == []


def test_delete_session_with_store_error_returns_false() -> None:
    assert _broken_controller().delete_session("s1") is False


def test_start_auto_with_store_error_keeps_state_stopped() -> None:
    controller = _broken_controller()

    controller.start_auto(1, "session")

    assert controller.is_auto_running() is False
