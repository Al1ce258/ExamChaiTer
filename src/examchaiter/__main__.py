"""Command-line entry point for the Phase 0 skeleton."""

import argparse
import sys
from collections.abc import Callable, Sequence

from examchaiter import __version__
from examchaiter.config import Settings


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="examchaiter")
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="show the installed version and exit",
    )
    subparsers = parser.add_subparsers(dest="command")
    list_parser = subparsers.add_parser("list-windows", help="list visible top-level windows")
    list_parser.add_argument("--filter", default=None, help="regular expression for window titles")
    subparsers.add_parser("ocr-self-test", help="run the synthetic OCR smoke test")
    ask_parser = subparsers.add_parser("ask", help="answer one question")
    ask_parser.add_argument("question")
    ask_parser.add_argument("--real", action="store_true", help="use the configured OpenAI client")
    answer_parser = subparsers.add_parser("answer", help="run one answer pipeline")
    answer_parser.add_argument("--title", required=True, help="target window title pattern")
    answer_parser.add_argument("--real", action="store_true", help="use real capture, OCR, and LLM")
    speak_parser = subparsers.add_parser("speak", help="demonstrate looped speech")
    speak_parser.add_argument("text")
    speak_parser.add_argument("--loops", type=int, default=1)
    speak_parser.add_argument("--interval", type=float, default=0.1)
    speak_parser.add_argument("--real", action="store_true", help="use pyttsx3")
    run_parser = subparsers.add_parser("run", help="start the global-hotkey app")
    run_parser.add_argument("--dry-run", action="store_true", help="print bindings without running")
    autopilot_parser = subparsers.add_parser(
        "autopilot-dry-run", help="run the AutoPilot state machine with fake dependencies"
    )
    autopilot_parser.add_argument("--frames", type=int, default=5)
    autopilot_parser.add_argument("--session", default="dry-run")
    gui_parser = subparsers.add_parser("gui", help="start the PySide6 GUI")
    gui_parser.add_argument("--fake", action="store_true", help="construct GUI without event loop")
    subparsers.add_parser("show-config", help="print effective settings with secrets masked")
    return parser


def _display_settings(settings: Settings) -> dict[str, object]:
    values: dict[str, object] = settings.model_dump(mode="json")
    values["llm_api_key"] = "sk-***" if settings.llm_api_key is not None else "<unset>"
    return values


def _prefixed_printer(prefix: str) -> Callable[[str], object]:
    """Return a printer that prefixes each rendered answer (multi-question CLI)."""

    def _printer(text: str) -> object:
        return print(prefix + text)

    return _printer


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    raw_argv = list(argv) if argv is not None else sys.argv[1:]
    if not raw_argv:
        raw_argv = ["gui"]
    args = parser.parse_args(raw_argv)

    if args.command is None:
        parser.print_help()
        return 0

    if args.command == "show-config":
        for key, value in sorted(_display_settings(Settings()).items()):
            print(f"{key}={value}")

    if args.command == "ocr-self-test":
        from pathlib import Path
        from typing import Any, cast

        import numpy as np
        from PIL import Image

        from examchaiter.models import OcrBlock
        from examchaiter.ocr import FakeOcrEngine, blocks_to_text

        fixture_path = (
            Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "synthetic_question.png"
        )
        with Image.open(fixture_path) as source:
            image = np.asarray(source.convert("RGB"), dtype=np.uint8)

        blocks = [
            OcrBlock(text="第一行 题目示例", bbox=(40.0, 30.0, 400.0, 80.0), confidence=0.99),
            OcrBlock(text="Second line sample", bbox=(40.0, 105.0, 450.0, 155.0), confidence=0.99),
            OcrBlock(text="12345", bbox=(40.0, 180.0, 180.0, 230.0), confidence=0.99),
        ]
        cast(Any, sys.stdout).reconfigure(encoding="utf-8")
        print(blocks_to_text(FakeOcrEngine(blocks=blocks).recognize(image)))

    if args.command == "ask":
        from examchaiter.llm import (
            FakeLLMClient,
            LLMClient,
            OpenAICompatClient,
            build_messages,
            parse_answer,
        )

        client: LLMClient

        if args.real:
            settings = Settings()
            if settings.llm_api_key is None:
                parser.error("--real requires EXAMCHAITER_LLM_API_KEY")
            client = OpenAICompatClient(
                base_url=settings.llm_base_url,
                api_key=settings.llm_api_key.get_secret_value(),
                model=settings.llm_model,
                timeout=settings.llm_timeout_s,
                max_retry=settings.llm_max_retry,
            )
        else:
            client = FakeLLMClient(responses=['{"type":"choice","answer":"B"}'])

        answer = parse_answer(client.complete(build_messages(args.question), json_mode=True))
        print(f"qtype={answer.qtype.value}")
        print(f"content={answer.content}")

    if args.command == "answer":
        import time
        from types import SimpleNamespace

        import numpy as np

        from examchaiter.capture.screenshot import grab_window
        from examchaiter.capture.window import (
            find_window,
            focus_window,
            get_window_rect,
            is_window_alive,
        )
        from examchaiter.llm.client import FakeLLMClient, LLMClient, OpenAICompatClient
        from examchaiter.llm.splitter import QuestionSplitter
        from examchaiter.models import OcrBlock
        from examchaiter.ocr.engine import FakeOcrEngine, OcrEngine, RapidOcrEngine
        from examchaiter.output import Presenter
        from examchaiter.pipeline import Capture, ExamPipeline

        settings = Settings()
        hwnd = 1
        capture: Capture
        ocr: OcrEngine
        llm: LLMClient

        if args.real:
            if settings.llm_api_key is None:
                print("ERROR: --real requires EXAMCHAITER_LLM_API_KEY", file=sys.stderr)
                return 1
            target = find_window(args.title)
            if target is None:
                print(f"ERROR: window not found: {args.title}", file=sys.stderr)
                return 1
            hwnd = target.hwnd
            capture = SimpleNamespace(
                get_window_rect=get_window_rect,
                is_window_alive=is_window_alive,
                focus_window=focus_window,
                grab_window=grab_window,
            )
            ocr = RapidOcrEngine()
            llm = OpenAICompatClient(
                base_url=settings.llm_base_url,
                api_key=settings.llm_api_key.get_secret_value(),
                model=settings.llm_model,
                timeout=settings.llm_timeout_s,
                max_retry=settings.llm_max_retry,
            )
        else:
            white_image = np.full((100, 100, 3), 255, dtype=np.uint8)
            capture = SimpleNamespace(
                get_window_rect=lambda _hwnd: (0, 0, 100, 100),
                is_window_alive=lambda _hwnd: True,
                focus_window=lambda _hwnd: True,
                grab_window=lambda _hwnd: white_image.copy(),
            )
            ocr = FakeOcrEngine(
                blocks=[
                    OcrBlock(
                        text="1. 示例题目 1+1=?\n2. 示例题目 2+2=?\n3. 示例题目 3+3=?",
                        bbox=(0.0, 0.0, 300.0, 60.0),
                        confidence=0.99,
                    )
                ]
            )
            llm = FakeLLMClient(
                responses=[
                    '{"type":"choice","answer":"B"}',
                    '{"type":"choice","answer":"C"}',
                    '{"type":"choice","answer":"D"}',
                ]
            )

        pipeline = ExamPipeline(
            capture=capture,
            ocr=ocr,
            llm=llm,
            settings=settings,
            splitter=QuestionSplitter(llm, settings),
            _sleep=time.sleep if args.real else lambda _delay: None,
        )
        results = pipeline.run_once(hwnd)
        if not results:
            print(f"ERROR: could not process window: {args.title}", file=sys.stderr)
            return 1
        reconfigure = getattr(sys.stdout, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8")
        for result in results:
            prefix = f"{result.question_no}. " if result.question_no else ""
            Presenter(settings, _printer=_prefixed_printer(prefix)).show(result)

    if args.command == "speak":
        import time

        from examchaiter.tts import FakeSpeaker, LoopSpeaker, Pyttsx3Speaker, Speaker

        speaker: Speaker

        if args.loops < 1 or args.interval < 0:
            print("ERROR: --loops must be >= 1 and --interval must be >= 0", file=sys.stderr)
            return 1

        if args.real:
            speaker = Pyttsx3Speaker(rate=Settings().tts_rate)
            if speaker._disabled:
                print("ERROR: pyttsx3 is unavailable or failed to initialize", file=sys.stderr)
                return 1
        else:
            speaker = FakeSpeaker()

        loop = LoopSpeaker(speaker, interval_s=args.interval)
        loop.start(args.text)
        if isinstance(speaker, FakeSpeaker):
            deadline = time.monotonic() + args.interval * args.loops + 0.2
            poll_interval = max(0.001, min(0.01, args.interval / 2 or 0.01))
            while len(speaker.spoken) < args.loops and time.monotonic() < deadline:
                time.sleep(poll_interval)
        else:
            time.sleep(args.interval * max(0, args.loops - 1))
        loop.stop()

        reconfigure = getattr(sys.stdout, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8")
        spoken = speaker.spoken if isinstance(speaker, FakeSpeaker) else [args.text] * args.loops
        print(f"spoken={spoken}")

    if args.command == "run":
        from examchaiter.app import ExamChaiTerApp, FakeHotkeyListener
        from examchaiter.models import PipelineResult
        from examchaiter.output import Presenter
        from examchaiter.tts import FakeSpeaker, LoopSpeaker

        settings = Settings()
        if args.dry_run:

            class DryRunPipeline:
                def run_once(self, _hwnd: int) -> list[PipelineResult]:
                    return []

            app = ExamChaiTerApp(
                settings=settings,
                pipeline=DryRunPipeline(),
                loop_speaker=LoopSpeaker(FakeSpeaker()),
                presenter=Presenter(settings, _printer=lambda _text: None),
            )
            listener = FakeHotkeyListener(app._create_bindings())
            print(f"bindings={sorted(listener.bindings)}")
            return 0

        try:
            app = ExamChaiTerApp(settings)
        except Exception as exc:
            print(f"ERROR: could not start application: {exc}", file=sys.stderr)
            return 1
        exit_code = app.run()
        if exit_code != 0:
            print("ERROR: application failed to start", file=sys.stderr)
        return exit_code

    if args.command == "gui":
        return _run_gui(fake=args.fake)

    if args.command == "autopilot-dry-run":
        return _run_autopilot_dry_run(frames=args.frames, session=args.session)

    if args.command == "list-windows":
        from examchaiter.capture.window import list_windows
        from examchaiter.errors import WindowError

        try:
            windows = list_windows(args.filter)
        except WindowError as exc:
            parser.error(str(exc))

        for window in windows:
            left, top, right, bottom = window.rect
            print(f"0x{window.hwnd:08X}\t{window.title}\t{left},{top},{right},{bottom}")

    return 0


def _run_autopilot_dry_run(*, frames: int, session: str) -> int:
    import tempfile
    import threading
    import time
    from pathlib import Path
    from typing import Any

    from examchaiter.autopilot import (
        AutoPilot,
        AutoPilotCallbacks,
        AutoPilotConfig,
    )
    from examchaiter.llm import FakeLLMClient
    from examchaiter.models import OcrBlock
    from examchaiter.ocr import FakeOcrEngine
    from examchaiter.storage.history_store import HistoryStore
    from examchaiter.tts import FakeSpeaker, LoopSpeaker

    frame_limit = max(1, frames)

    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is not None:
        reconfigure(encoding="utf-8")

    class DryRunCapture:
        """Serves hash A on the first two frames, then hash B."""

        def __init__(self) -> None:
            self.frames_served = 0

        def grab_window(self, _hwnd: int) -> int:
            self.frames_served += 1
            return self.frames_served

        def dhash(self, image: Any) -> int:
            return 1 if int(image) <= 2 else 2

    capture = DryRunCapture()
    ocr = FakeOcrEngine(
        blocks=[
            OcrBlock(
                text="示例题目：1+1=? 请从下列选项中选择正确答案。",
                bbox=(0.0, 0.0, 200.0, 20.0),
                confidence=0.99,
            )
        ]
    )
    llm = FakeLLMClient(responses=['{"type":"choice","answer":"B"}'])
    speaker = FakeSpeaker()
    loop_speaker = LoopSpeaker(speaker, interval_s=0.01)
    store = HistoryStore(base_dir=Path(tempfile.mkdtemp()))
    meta = store.create_session(session)

    states: list[str] = []
    answers: list[bool] = []
    statuses: list[str] = []
    errors: list[str] = []
    callbacks = AutoPilotCallbacks(
        on_state=lambda state: states.append(state.value),
        on_answer=lambda _result, from_cache: answers.append(from_cache),
        on_status=statuses.append,
        on_error=lambda exc: errors.append(repr(exc)),
    )
    autopilot = AutoPilot(
        capture=capture,
        ocr=ocr,
        llm=llm,
        loop_speaker=loop_speaker,
        history_store=store,
        session_id=meta.session_id,
        config=AutoPilotConfig(poll_interval=0.02),
        callbacks=callbacks,
    )

    autopilot.start(0)
    waiter = threading.Event()
    deadline = time.monotonic() + 5.0
    while capture.frames_served < frame_limit and time.monotonic() < deadline:
        waiter.wait(0.005)
    autopilot.stop()
    loop_speaker.stop()

    cached = sum(1 for from_cache in answers if from_cache)
    print(f"state transitions: {' -> '.join(states)}")
    print(f"on_answer count: {len(answers)}")
    print(f"from_cache: fresh={len(answers) - cached} cached={cached}")
    if statuses:
        print(f"status: {'; '.join(statuses)}")
    if errors:
        print(f"errors: {'; '.join(errors)}")
    return 0


def _run_gui(*, fake: bool) -> int:
    from typing import Any, cast

    try:
        from PySide6.QtWidgets import QApplication
    except Exception as exc:
        print(f"ERROR: PySide6 is unavailable: {exc}", file=sys.stderr)
        return 1

    from examchaiter.autopilot import AutoPilot, AutoPilotConfig
    from examchaiter.gui.main_window import MainWindow
    from examchaiter.gui.state import GuiController
    from examchaiter.gui.tray import TrayController
    from examchaiter.llm import FakeLLMClient, OpenAICompatClient
    from examchaiter.llm.splitter import QuestionSplitter
    from examchaiter.models import OcrBlock, PipelineResult
    from examchaiter.ocr import FakeOcrEngine, RapidOcrEngine
    from examchaiter.output import Presenter
    from examchaiter.pipeline import ExamPipeline
    from examchaiter.storage import ConfigStore, HistoryStore
    from examchaiter.tts import FakeSpeaker, LoopSpeaker, Pyttsx3Speaker

    config_store = ConfigStore()
    settings = config_store.to_settings()
    history_store = HistoryStore(base_dir=config_store.base_dir)
    app_config = config_store.load()
    auto_config = AutoPilotConfig(
        poll_interval=app_config.auto_poll_interval,
        stable_frames=app_config.auto_stable_frames,
        speak_choice_repeat=app_config.auto_speak_choice_repeat,
        speak_fill_repeat=app_config.auto_speak_fill_repeat,
        speak_short_repeat=app_config.auto_speak_short_repeat,
        speak_interval=app_config.auto_speak_interval,
        min_text_len=app_config.min_text_len,
    )
    argv = ["-platform", "offscreen"] if fake else sys.argv
    instance = QApplication.instance()
    qapp = cast(QApplication, instance) if instance is not None else QApplication(argv)

    if fake:

        class GuiSmokePipeline:
            def run_once(self, _hwnd: int) -> PipelineResult | None:
                return None

        class FakeAutoCapture:
            def grab_window(self, _hwnd: int) -> Any:
                return object()

            def dhash(self, _image: Any) -> int:
                return 1

        capture: Any = FakeAutoCapture()
        ocr: Any = FakeOcrEngine(
            blocks=[
                OcrBlock(
                    text="示例题目 1+1=? 请选择正确答案",
                    bbox=(0.0, 0.0, 200.0, 20.0),
                    confidence=0.99,
                )
            ]
        )
        llm: Any = FakeLLMClient(
            responses=[
                '[{"no": "", "text": "示例题目 1+1=? 请选择正确答案"}]',
                '{"type":"choice","answer":"B"}',
            ]
        )
        loop_speaker = LoopSpeaker(FakeSpeaker())

        def make_smoke_pipeline() -> Any:
            return GuiSmokePipeline()

        def list_no_windows(_title: str) -> list[Any]:
            return []

        pipeline_factory: Any = make_smoke_pipeline
        presenter: Any = Presenter(settings, _printer=lambda _text: None)
        list_windows_fn: Any = list_no_windows
    else:
        from examchaiter.capture.screenshot import dhash as _dhash
        from examchaiter.capture.screenshot import grab_window as _grab_window
        from examchaiter.capture.window import focus_window, get_window_rect, is_window_alive

        class ScreenshotCapture:
            def get_window_rect(self, hwnd: int) -> tuple[int, int, int, int]:
                return get_window_rect(hwnd)

            def is_window_alive(self, hwnd: int) -> bool:
                return is_window_alive(hwnd)

            def focus_window(self, hwnd: int) -> bool:
                return focus_window(hwnd)

            def grab_window(self, hwnd: int) -> Any:
                return _grab_window(hwnd)

            def dhash(self, image: Any) -> int:
                return _dhash(image)

        api_key = settings.llm_api_key.get_secret_value() if settings.llm_api_key else ""
        capture = ScreenshotCapture()
        ocr = RapidOcrEngine()
        llm = OpenAICompatClient(
            base_url=settings.llm_base_url,
            api_key=api_key,
            model=settings.llm_model,
            timeout=settings.llm_timeout_s,
            max_retry=settings.llm_max_retry,
        )
        loop_speaker = LoopSpeaker(Pyttsx3Speaker(rate=settings.tts_rate))
        presenter = Presenter(settings)

        def build_exam_pipeline() -> ExamPipeline:
            return ExamPipeline(
                capture=capture,
                ocr=ocr,
                llm=llm,
                settings=settings,
                splitter=QuestionSplitter(llm, settings),
            )

        pipeline_factory = build_exam_pipeline
        list_windows_fn = None

    def autopilot_factory(session_id: str, callbacks: Any) -> AutoPilot:
        return AutoPilot(
            capture=capture,
            ocr=ocr,
            llm=llm,
            loop_speaker=loop_speaker,
            history_store=history_store,
            session_id=session_id,
            config=auto_config,
            callbacks=callbacks,
        )

    controller = GuiController(
        pipeline_factory=pipeline_factory,
        loop_speaker=loop_speaker,
        presenter=presenter,
        settings=settings,
        config_store=config_store,
        history_store=history_store,
        autopilot_factory=autopilot_factory,
        list_windows_fn=list_windows_fn,
    )

    main_window = MainWindow(controller, settings)
    _tray = TrayController(qapp, main_window, controller)
    if fake:
        print("gui-ok")
        return 0

    main_window.show()
    return int(qapp.exec())


if __name__ == "__main__":
    raise SystemExit(main())
