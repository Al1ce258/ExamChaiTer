# Smoke only. 真联调请手动跑 `python -m examchaiter answer --title xx --real`。

"""Exercise App callbacks without real windows, OCR, LLM, or audio."""

from __future__ import annotations

import sys

from examchaiter import app as app_module
from examchaiter.app import ExamChaiTerApp, FakeHotkeyListener
from examchaiter.config import Settings
from examchaiter.models import Answer, PipelineResult, Question, QuestionType
from examchaiter.output import Presenter
from examchaiter.tts import FakeSpeaker, LoopSpeaker


class SmokePipeline:
    def run_once(self, _hwnd: int) -> PipelineResult:
        return PipelineResult(
            question=Question(text="Smoke question"),
            answer=Answer(qtype=QuestionType.CHOICE, content="B"),
        )


def main() -> int:
    try:
        reconfigure = getattr(sys.stdout, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8")
        settings = Settings(_env_file=None, clipboard=False, tts_enabled=True)
        listener = FakeHotkeyListener({})
        app = ExamChaiTerApp(
            settings=settings,
            pipeline=SmokePipeline(),
            loop_speaker=LoopSpeaker(FakeSpeaker(), interval_s=0.01),
            presenter=Presenter(settings, _printer=lambda text: print(f"presenter: {text}")),
            hotkey_factory=lambda _bindings: listener,
        )
        listener.bindings = app._create_bindings()
        app._listener = listener

        original_foreground = app_module.get_foreground_window
        app_module.get_foreground_window = lambda: 1
        try:
            listener.trigger("<ctrl>+<alt>+q")
            print("answer: ok")

            listener.trigger("<ctrl>+<alt>+s")
            print(f"tts: running={app.loop_speaker.is_running()}")
            listener.trigger("<ctrl>+<alt>+s")
            print("tts: stopped")

            listener.trigger("<ctrl>+<alt>+x")
            print("quit: ok")
        finally:
            app_module.get_foreground_window = original_foreground
        return 0
    except Exception as exc:
        print(f"smoke failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
