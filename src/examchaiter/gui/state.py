"""GUI state and controller logic independent of Qt widgets."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from loguru import logger

from examchaiter.autopilot import AutoPilot, AutoPilotCallbacks
from examchaiter.capture.window import list_windows as default_list_windows
from examchaiter.config import Settings
from examchaiter.models import Answer, PipelineResult, WindowInfo
from examchaiter.output.formatter import to_speech_text
from examchaiter.output.presenter import Presenter
from examchaiter.pipeline import ExamPipeline
from examchaiter.storage.config_store import AppConfig, ConfigStore
from examchaiter.storage.history_store import HistoryEntry, HistoryStore, SessionMeta
from examchaiter.tts.speaker import LoopSpeaker

AutoPilotFactory = Callable[[str, AutoPilotCallbacks], AutoPilot]


def _noop_callbacks() -> AutoPilotCallbacks:
    return AutoPilotCallbacks(
        on_state=lambda _state: None,
        on_answer=lambda _result, _from_cache: None,
        on_status=lambda _message: None,
        on_error=lambda _error: None,
    )


@dataclass
class GuiState:
    current_hwnd: int | None = None
    last_results: list[PipelineResult] = field(default_factory=list)
    last_question_text: str = ""
    tts_running: bool = False
    busy: bool = False
    auto_running: bool = False
    current_session_id: str | None = None

    @property
    def last_answer(self) -> Answer | None:
        """Shortcut to the most recent answer, kept for existing callers."""
        return self.last_results[-1].answer if self.last_results else None


class GuiController:
    """Coordinate GUI actions without importing Qt or concrete capture clients."""

    def __init__(
        self,
        pipeline_factory: Callable[[], ExamPipeline],
        loop_speaker: LoopSpeaker,
        presenter: Presenter,
        settings: Settings,
        config_store: ConfigStore,
        history_store: HistoryStore,
        autopilot_factory: AutoPilotFactory,
        list_windows_fn: Callable[[str], list[WindowInfo]] | None = None,
    ) -> None:
        self.pipeline = pipeline_factory()
        self.loop_speaker = loop_speaker
        self.presenter = presenter
        self.settings = settings
        self.config_store = config_store
        self.history_store = history_store
        self.autopilot_factory = autopilot_factory
        self.autopilot_callbacks: AutoPilotCallbacks | None = None
        self._list_windows_fn = list_windows_fn or default_list_windows
        self._autopilot: AutoPilot | None = None
        self.state = GuiState()

    def list_windows(self, title_filter: str = "") -> list[WindowInfo]:
        try:
            return list(self._list_windows_fn(title_filter))
        except Exception:
            logger.exception("GUI window listing failed")
            return []

    def pick_window(self, hwnd: int) -> WindowInfo | None:
        try:
            for window in self.list_windows(""):
                if window.hwnd == hwnd:
                    self.state.current_hwnd = hwnd
                    return window
            return None
        except Exception:
            logger.exception("GUI window selection failed")
            return None

    def answer_once(self) -> list[PipelineResult]:
        if self.state.busy or self.state.current_hwnd is None:
            return []

        self.state.busy = True
        try:
            results = list(self.pipeline.run_once(self.state.current_hwnd))
            if not results:
                return []
            for result in results:
                self.presenter.show(result)
            self.state.last_results = list(results)
            self.state.last_question_text = results[0].question.text
            return list(results)
        except Exception:
            logger.exception("GUI answer action failed")
            return []
        finally:
            self.state.busy = False

    def toggle_tts(self) -> bool:
        try:
            if self.state.tts_running:
                self.loop_speaker.stop()
                self.state.tts_running = False
                return False
            last = self.state.last_results[-1] if self.state.last_results else None
            if last is None:
                logger.warning("No answer available for TTS")
                return False
            self.loop_speaker.start(to_speech_text(last.answer, question_no=last.question_no))
            self.state.tts_running = True
            return True
        except Exception:
            logger.exception("GUI TTS toggle failed")
            return False

    def stop_tts(self) -> None:
        try:
            self.loop_speaker.stop()
        finally:
            self.state.tts_running = False

    def is_tts_running(self) -> bool:
        return self.state.tts_running

    def get_config(self) -> AppConfig:
        try:
            return self.config_store.load()
        except Exception:
            logger.exception("GUI config load failed")
            return AppConfig()

    def save_config(self, cfg: AppConfig) -> None:
        self.config_store.save(cfg)

    def list_sessions(self) -> list[SessionMeta]:
        try:
            return list(self.history_store.list_sessions())
        except Exception:
            logger.exception("GUI session listing failed")
            return []

    def load_history(self, session_id: str) -> list[HistoryEntry]:
        try:
            return list(self.history_store.load_session(session_id))
        except Exception:
            logger.exception("GUI history load failed")
            return []

    def search_history(self, keyword: str) -> list[tuple[str, HistoryEntry]]:
        try:
            return list(self.history_store.search(keyword))
        except Exception:
            logger.exception("GUI history search failed")
            return []

    def delete_session(self, session_id: str) -> bool:
        try:
            return bool(self.history_store.delete_session(session_id))
        except Exception:
            logger.exception("GUI session delete failed")
            return False

    def start_auto(self, hwnd: int, session_name: str) -> None:
        try:
            if self.is_auto_running():
                self.stop_auto()
            session_id = self.history_store.create_session(session_name).session_id
            callbacks = self.autopilot_callbacks or _noop_callbacks()
            autopilot = self.autopilot_factory(session_id, callbacks)
            autopilot.start(hwnd)
            self._autopilot = autopilot
            self.state.current_session_id = session_id
            self.state.auto_running = True
        except Exception:
            logger.exception("GUI AutoPilot start failed")
            self._autopilot = None
            self.state.auto_running = False

    def stop_auto(self) -> None:
        try:
            autopilot = self._autopilot
            if autopilot is not None:
                autopilot.stop()
            self._autopilot = None
            self.state.auto_running = False
        except Exception:
            logger.exception("GUI AutoPilot stop failed")
            self._autopilot = None
            self.state.auto_running = False

    def is_auto_running(self) -> bool:
        return self.state.auto_running
