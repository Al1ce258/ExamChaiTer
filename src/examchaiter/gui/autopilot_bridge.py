"""Bridge AutoPilot worker callbacks onto Qt signals for thread-safe updates."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from examchaiter.autopilot import AutoPilotCallbacks, AutoPilotState
from examchaiter.models import PipelineResult


class AutoPilotBridge(QObject):
    """Forward AutoPilot callbacks to the GUI through Qt signals.

    AutoPilot runs on its own worker thread; emitting a Qt signal from that
    thread is safe and Qt queues the slot invocation back onto the thread that
    owns the connected widget.
    """

    state_changed = Signal(str)
    answer_ready = Signal(object, bool)
    round_done = Signal(list)
    status_message = Signal(str)
    error_occurred = Signal(object)

    def make_callbacks(self) -> AutoPilotCallbacks:
        return AutoPilotCallbacks(
            on_state=self._emit_state,
            on_answer=self._emit_answer,
            on_status=self._emit_status,
            on_error=self._emit_error,
            on_round_done=self._emit_round_done,
        )

    def _emit_round_done(self, results: list[PipelineResult]) -> None:
        self.round_done.emit(results)

    def _emit_state(self, state: AutoPilotState) -> None:
        self.state_changed.emit(state.value)

    def _emit_answer(self, result: PipelineResult, from_cache: bool) -> None:
        self.answer_ready.emit(result, from_cache)

    def _emit_status(self, message: str) -> None:
        self.status_message.emit(message)

    def _emit_error(self, error: Exception) -> None:
        self.error_occurred.emit(error)
