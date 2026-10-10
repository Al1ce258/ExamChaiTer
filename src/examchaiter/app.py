"""Application orchestration and global hotkey handling."""

from __future__ import annotations

import importlib
import threading
from collections.abc import Callable
from contextlib import suppress
from types import SimpleNamespace
from typing import Any, Protocol

from loguru import logger

from examchaiter.capture.screenshot import grab_window
from examchaiter.capture.window import (
    focus_window,
    get_foreground_window,
    get_window_rect,
    is_window_alive,
)
from examchaiter.config import Settings
from examchaiter.errors import HotkeyError
from examchaiter.llm.client import OpenAICompatClient
from examchaiter.llm.splitter import QuestionSplitter
from examchaiter.models import PipelineResult
from examchaiter.ocr.engine import RapidOcrEngine
from examchaiter.output.formatter import to_speech_text
from examchaiter.output.presenter import Presenter
from examchaiter.pipeline import ExamPipeline
from examchaiter.tts.speaker import LoopSpeaker, Pyttsx3Speaker

HotkeyCallback = Callable[[], None]


class HotkeyListener(Protocol):
    """Hotkey listener lifecycle used by the app."""

    def start(self) -> None: ...

    def stop(self) -> None: ...


class PipelineLike(Protocol):
    def run_once(self, hwnd: int) -> list[PipelineResult]: ...


class PresenterLike(Protocol):
    def show(self, result: PipelineResult) -> None: ...


class FakeHotkeyListener:
    """Record listener lifecycle calls and expose callbacks for tests."""

    def __init__(self, bindings: dict[str, HotkeyCallback]) -> None:
        self.bindings = bindings
        self.start_count = 0
        self.stop_count = 0

    def start(self) -> None:
        self.start_count += 1

    def stop(self) -> None:
        self.stop_count += 1

    def trigger(self, key: str) -> None:
        self.bindings[key]()


class PynputHotkeyListener:
    """Lazy pynput GlobalHotKeys adapter with guarded callbacks."""

    def __init__(self, bindings: dict[str, HotkeyCallback]) -> None:
        self.bindings = bindings
        guarded = {key: self._guard(callback) for key, callback in bindings.items()}
        try:
            module = importlib.import_module("pynput.keyboard")
            self._listener: Any = module.GlobalHotKeys(guarded)
        except Exception as exc:
            raise HotkeyError("pynput hotkey listener could not be initialized") from exc

    def start(self) -> None:
        try:
            self._listener.start()
        except Exception as exc:
            raise HotkeyError("pynput hotkey listener could not start") from exc

    def stop(self) -> None:
        with suppress(Exception):
            self._listener.stop()

    @staticmethod
    def _guard(callback: HotkeyCallback) -> HotkeyCallback:
        def guarded() -> None:
            try:
                callback()
            except Exception:
                logger.exception("Hotkey callback failed")

        return guarded


class ExamChaiTerApp:
    """Coordinate hotkeys, answer pipeline, presentation, and looped speech."""

    def __init__(
        self,
        settings: Settings,
        pipeline: PipelineLike | None = None,
        loop_speaker: LoopSpeaker | None = None,
        presenter: PresenterLike | None = None,
        hotkey_factory: Callable[[dict[str, HotkeyCallback]], HotkeyListener] | None = None,
        _stdin: Any = None,
    ) -> None:
        self.settings = settings
        self.pipeline = pipeline or _build_pipeline(settings)
        self.loop_speaker = loop_speaker or LoopSpeaker(Pyttsx3Speaker(rate=settings.tts_rate))
        self.presenter = presenter or Presenter(settings)
        self.hotkey_factory = hotkey_factory or (lambda bindings: PynputHotkeyListener(bindings))
        self._stdin = _stdin
        self._stop_event = threading.Event()
        self._listener: HotkeyListener | None = None
        self._last_result: PipelineResult | None = None
        self._lock = threading.RLock()

    def _create_bindings(self) -> dict[str, HotkeyCallback]:
        return {
            "<ctrl>+<alt>+q": self._on_answer,
            "<ctrl>+<alt>+s": self._on_toggle_tts,
            "<ctrl>+<alt>+x": self._on_quit,
        }

    def _on_answer(self) -> None:
        try:
            hwnd = get_foreground_window()
            if hwnd is None:
                logger.warning("No foreground window available")
                return
            results = self.pipeline.run_once(hwnd)
            if not results:
                logger.warning("Pipeline returned no result")
                return
            self._last_result = results[-1]
            for result in results:
                self.presenter.show(result)
        except Exception:
            logger.exception("Answer hotkey failed")

    def _on_toggle_tts(self) -> None:
        try:
            if not self.settings.tts_enabled:
                logger.warning("TTS is disabled by settings")
                return
            if self.loop_speaker.is_running():
                self.loop_speaker.stop()
                return
            if self._last_result is None:
                logger.warning("No answer available for speech")
                return
            self.loop_speaker.start(to_speech_text(self._last_result.answer))
        except Exception:
            logger.exception("TTS toggle hotkey failed")

    def _on_quit(self) -> None:
        self.stop()

    def run(self) -> int:
        try:
            listener = self.hotkey_factory(self._create_bindings())
            with self._lock:
                self._listener = listener
            listener.start()
            self._stop_event.wait()
            return 0
        except Exception:
            logger.exception("Application run failed")
            return 1
        finally:
            self.stop()

    def stop(self) -> None:
        self._stop_event.set()
        with self._lock:
            listener = self._listener
            self._listener = None
        with suppress(Exception):
            self.loop_speaker.stop()
        if listener is not None:
            with suppress(Exception):
                listener.stop()


def _build_pipeline(settings: Settings) -> ExamPipeline:
    capture = SimpleNamespace(
        get_window_rect=get_window_rect,
        is_window_alive=is_window_alive,
        focus_window=focus_window,
        grab_window=grab_window,
    )
    api_key = settings.llm_api_key.get_secret_value() if settings.llm_api_key else ""
    llm = OpenAICompatClient(
        base_url=settings.llm_base_url,
        api_key=api_key,
        model=settings.llm_model,
        timeout=settings.llm_timeout_s,
        max_retry=settings.llm_max_retry,
    )
    return ExamPipeline(
        capture=capture,
        ocr=RapidOcrEngine(),
        llm=llm,
        settings=settings,
        splitter=QuestionSplitter(llm, settings),
    )
