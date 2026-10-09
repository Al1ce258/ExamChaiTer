"""GUI state and controller logic independent of Qt widgets."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from loguru import logger

from examchaiter.capture.window import list_windows as default_list_windows
from examchaiter.config import Settings
from examchaiter.models import Answer, WindowInfo
from examchaiter.output.formatter import to_speech_text
from examchaiter.output.presenter import Presenter
from examchaiter.pipeline import ExamPipeline
from examchaiter.tts.speaker import LoopSpeaker


@dataclass
class GuiState:
    current_hwnd: int | None = None
    last_answer: Answer | None = None
    last_question_text: str = ""
    tts_running: bool = False
    busy: bool = False


class GuiController:
    """Coordinate GUI actions without importing Qt or concrete capture clients."""

    def __init__(
        self,
        pipeline_factory: Callable[[], ExamPipeline],
        loop_speaker: LoopSpeaker,
        presenter: Presenter,
        settings: Settings,
        _list_windows_fn: Callable[[str], list[WindowInfo]] | None = None,
    ) -> None:
        self.pipeline = pipeline_factory()
        self.loop_speaker = loop_speaker
        self.presenter = presenter
        self.settings = settings
        self._list_windows_fn = _list_windows_fn or default_list_windows
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

    def answer_once(self) -> Answer | None:
        if self.state.busy or self.state.current_hwnd is None:
            return None

        self.state.busy = True
        try:
            result = self.pipeline.run_once(self.state.current_hwnd)
            if result is None:
                return None
            self.presenter.show(result)
            self.state.last_answer = result.answer
            self.state.last_question_text = result.question.text
            return result.answer
        except Exception:
            logger.exception("GUI answer action failed")
            return None
        finally:
            self.state.busy = False

    def toggle_tts(self) -> bool:
        try:
            if self.state.tts_running:
                self.loop_speaker.stop()
                self.state.tts_running = False
                return False
            if self.state.last_answer is None:
                logger.warning("No answer available for TTS")
                return False
            self.loop_speaker.start(to_speech_text(self.state.last_answer))
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
