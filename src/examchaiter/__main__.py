"""Command-line entry point for the Phase 0 skeleton."""

import argparse
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

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
    debug_parser = subparsers.add_parser(
        "debug-capture", help="dump capture, OCR, split, and LLM diagnostics"
    )
    debug_parser.add_argument("--title", required=True, help="window title substring")
    debug_parser.add_argument("--real", action="store_true", help="use the configured LLM")
    debug_parser.add_argument("--out", type=Path, default=Path("debug"), help="output root")
    debug_parser.add_argument(
        "--no-image", action="store_true", help="do not save the original screenshot"
    )
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

    if args.command == "debug-capture":
        return _run_debug_capture(
            title=args.title,
            real=args.real,
            out=args.out,
            no_image=args.no_image,
        )

    if args.command == "show-config":
        from examchaiter.storage import ConfigStore

        storage_store = ConfigStore()
        values = _display_settings(Settings())
        values["storage_dir"] = storage_store.base_dir
        for key, value in sorted(values.items()):
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
        from examchaiter.storage.history_store import NullHistoryStore

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
            history_store=NullHistoryStore(),
            session_id="",
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
        loop.start(args.text, max_repeats=args.loops)
        loop.wait_done(timeout=args.interval * args.loops + 5.0)
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


def _run_debug_capture(
    *,
    title: str,
    real: bool,
    out: Path,
    no_image: bool,
    _find_window: Callable[[str], Any] | None = None,
    _grab_window: Callable[[int], Any] | None = None,
    _ocr: Any | None = None,
    _llm: Any | None = None,
) -> int:
    import json
    import re
    from datetime import datetime

    import numpy as np
    from PIL import Image, ImageDraw

    from examchaiter.capture.screenshot import grab_window as real_grab_window
    from examchaiter.capture.window import find_window as real_find_window
    from examchaiter.llm.client import FakeLLMClient, OpenAICompatClient
    from examchaiter.llm.prompts import SPLIT_SYSTEM_PROMPT, build_messages, parse_answer
    from examchaiter.llm.splitter import QuestionSplitter
    from examchaiter.ocr.engine import RapidOcrEngine
    from examchaiter.ocr.layout import blocks_to_text

    class FixedDebugLLM(FakeLLMClient):
        """Return a split payload or a fixed answer for every debug request."""

        def __init__(self) -> None:
            super().__init__(responses=[])

        def complete(self, messages: list[dict[str, object]], *, json_mode: bool = False) -> str:
            self.calls.append(messages)
            if any(message.get("content") == SPLIT_SYSTEM_PROMPT for message in messages):
                source = str(messages[-1].get("content", ""))
                return json.dumps([{"no": "", "text": source}], ensure_ascii=False)
            return '{"type":"choice","answer":"B"}'

    def _to_rgb(image: Any) -> Any:
        array = np.asarray(image, dtype=np.uint8)
        if array.ndim == 2:
            return np.repeat(array[:, :, np.newaxis], 3, axis=2)
        if array.shape[2] >= 3:
            return np.ascontiguousarray(array[:, :, :3][:, :, ::-1])
        raise ValueError("captured image must have at least one channel")

    def _write_json(path: Path, payload: object) -> None:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is not None:
        reconfigure(encoding="utf-8")

    settings = Settings()
    find_fn = _find_window or real_find_window
    window = find_fn(re.escape(title))
    if window is None:
        print(f"ERROR: window not found: {title}", file=sys.stderr)
        return 1

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = (Path(out) / timestamp).resolve()
    run_dir.mkdir(parents=True, exist_ok=True)

    capture_fn = _grab_window or real_grab_window
    image = np.asarray(capture_fn(window.hwnd), dtype=np.uint8)
    rgb = _to_rgb(image)
    pil_image = Image.fromarray(rgb)
    if not no_image:
        pil_image.save(run_dir / "01_screenshot.png")

    height, width = image.shape[:2]
    channels = 1 if image.ndim == 2 else int(image.shape[2])
    gray = np.asarray(pil_image.convert("L"), dtype=np.float64)
    brightness = float(gray.mean())
    variance = float(gray.var())
    print(f"图像信息: {width}x{height}x{channels} 亮度均值={brightness:.2f} 方差={variance:.2f}")
    if variance < 5.0:
        print("WARNING: 图像方差低于 5，可能接近全黑或内容缺失")

    ocr = _ocr if _ocr is not None else RapidOcrEngine()
    blocks = list(ocr.recognize(image))
    _write_json(
        run_dir / "02_ocr_blocks.json",
        [
            {"text": block.text, "bbox": list(block.bbox), "confidence": block.confidence}
            for block in blocks
        ],
    )

    annotated = pil_image.copy()
    draw = ImageDraw.Draw(annotated)
    for block in blocks:
        x0, y0, x1, y1 = (round(value) for value in block.bbox)
        draw.rectangle((x0, y0, x1, y1), outline=(255, 0, 0), width=2)
        print(f"[{block.confidence:.2f}] {block.text!r} @ {block.bbox}")
    annotated.save(run_dir / "03_ocr_raw.png")

    layout_text = blocks_to_text(blocks)
    (run_dir / "04_layout_text.txt").write_text(layout_text, encoding="utf-8")

    if _llm is not None:
        llm = _llm
    elif real:
        api_key = settings.llm_api_key.get_secret_value() if settings.llm_api_key else ""
        if not api_key:
            print(
                "ERROR: --real requires EXAMCHAITER_LLM_API_KEY; continuing with FakeLLMClient",
                file=sys.stderr,
            )
            llm = FixedDebugLLM()
        else:
            llm = OpenAICompatClient(
                base_url=settings.llm_base_url,
                api_key=api_key,
                model=settings.llm_model,
                timeout=settings.llm_timeout_s,
                max_retry=settings.llm_max_retry,
            )
    else:
        llm = FixedDebugLLM()

    splitter = QuestionSplitter(llm, settings)
    questions = splitter.split(layout_text)
    _write_json(
        run_dir / "05_split_result.json",
        {
            "mode": splitter.last_mode,
            "questions": [
                {"no": question.question_no, "text": question.text} for question in questions
            ],
        },
    )

    labels: list[str] = []
    used_labels: set[str] = set()
    for index, question in enumerate(questions, start=1):
        base = question.question_no.strip() or str(index)
        label = base
        suffix = 2
        while label in used_labels:
            label = f"{base}-{suffix}"
            suffix += 1
        used_labels.add(label)
        labels.append(label)

        messages = build_messages(question.text)
        _write_json(run_dir / f"06_messages_{label}.json", messages)
        try:
            raw = llm.complete(messages, json_mode=True)
        except Exception as exc:
            raw = f"ERROR: {type(exc).__name__}: {exc}"
        (run_dir / f"07_llm_raw_{label}.txt").write_text(raw, encoding="utf-8")
        answer = parse_answer(raw)
        _write_json(
            run_dir / f"08_parsed_answer_{label}.json",
            {"qtype": answer.qtype.value, "content": answer.content},
        )

    print("===== debug-capture 汇总 =====")
    print(f"窗口: hwnd={window.hwnd} title={window.title}")
    print(f"图: {width}x{height} 亮度={brightness:.2f}")
    print(f"OCR 块数: {len(blocks)}")
    print(f"layout 文本长度: {len(layout_text)}")
    print(f"拆题: mode={splitter.last_mode} 题数={len(questions)} 题号={labels}")
    for label in labels:
        parsed_path = run_dir / f"08_parsed_answer_{label}.json"
        payload = json.loads(parsed_path.read_text(encoding="utf-8"))
        print(f"每题 LLM: no={label} qtype={payload['qtype']} answer={payload['content']}")
    print("================================")
    print(f"输出目录: {run_dir}")
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
    from examchaiter.config import Settings
    from examchaiter.llm import FakeLLMClient
    from examchaiter.llm.prompts import SPLIT_SYSTEM_PROMPT
    from examchaiter.llm.splitter import QuestionSplitter
    from examchaiter.models import OcrBlock
    from examchaiter.ocr import FakeOcrEngine
    from examchaiter.storage.history_store import HistoryStore
    from examchaiter.tts import FakeSpeaker, LoopSpeaker

    frame_limit = max(1, frames)

    settings_overrides: dict[str, Any] = {"_env_file": None}
    dry_run_settings = Settings(**settings_overrides)

    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is not None:
        reconfigure(encoding="utf-8")

    class DryRunCapture:
        """Serves hash A in phase 0, hash B afterwards (advanced by the driver)."""

        def __init__(self) -> None:
            self.phase = 0

        def advance(self) -> None:
            self.phase += 1

        def grab_window(self, _hwnd: int) -> Any:
            return object()

        def dhash(self, _image: Any) -> int:
            return 1 if self.phase == 0 else 2

    capture = DryRunCapture()
    ocr = FakeOcrEngine(
        blocks=[
            OcrBlock(
                text=(
                    "示例题一：1+1=? 请选择正确答案\n"
                    "示例题二：2+2=? 请选择正确答案\n"
                    "示例题三：3+3=? 请选择正确答案"
                ),
                bbox=(0.0, 0.0, 200.0, 20.0),
                confidence=0.99,
            )
        ]
    )

    class DryRunLLM(FakeLLMClient):
        """Serve the split payload for split prompts and queued answers otherwise."""

        def __init__(self, split_payload: str, answers: list[str]) -> None:
            super().__init__(responses=list(answers))
            self._split_payload = split_payload
            self._answers = list(answers)

        def complete(self, messages: list[dict[str, object]], *, json_mode: bool = False) -> str:
            self.calls.append(messages)
            if any(message.get("content") == SPLIT_SYSTEM_PROMPT for message in messages):
                return self._split_payload
            if not self.responses:
                self.responses = list(self._answers)
            return self.responses.pop(0)

    llm = DryRunLLM(
        '[{"no": "1", "text": "示例题一：1+1=? 请选择正确答案"},'
        ' {"no": "2", "text": "示例题二：2+2=? 请选择正确答案"},'
        ' {"no": "3", "text": "示例题三：3+3=? 请选择正确答案"}]',
        [
            '{"type":"choice","answer":"B"}',
            '{"type":"multi_choice","answer":"ABD"}',
            '{"type":"fill","answer":"9"}',
        ],
    )
    speaker = FakeSpeaker()
    loop_speaker = LoopSpeaker(speaker, interval_s=0.01)
    store = HistoryStore(base_dir=Path(tempfile.mkdtemp()))
    meta = store.create_session(session)

    states: list[str] = []
    answers: list[bool] = []
    statuses: list[str] = []
    errors: list[str] = []
    rounds: list[list[Any]] = []
    completed_rounds: list[int] = []
    config = AutoPilotConfig(poll_interval=0.02)

    def _on_status(message: str) -> None:
        statuses.append(message)
        if message.startswith("本轮朗读完成"):
            completed_rounds.append(len(completed_rounds) + 1)

    callbacks = AutoPilotCallbacks(
        on_state=lambda state: states.append(state.value),
        on_answer=lambda _result, from_cache: answers.append(from_cache),
        on_status=_on_status,
        on_error=lambda exc: errors.append(repr(exc)),
        on_round_done=rounds.append,
    )
    autopilot = AutoPilot(
        capture=capture,
        ocr=ocr,
        llm=llm,
        splitter=QuestionSplitter(llm, dry_run_settings),
        loop_speaker=loop_speaker,
        history_store=store,
        session_id=meta.session_id,
        config=config,
        callbacks=callbacks,
    )

    target_rounds = max(1, frame_limit // 2)
    autopilot.start(0)
    started_at = time.monotonic()
    waiter = threading.Event()
    deadline = time.monotonic() + 15.0
    advanced = 0
    while len(completed_rounds) < target_rounds and time.monotonic() < deadline:
        waiter.wait(0.01)
        if advanced < len(completed_rounds) < target_rounds:
            capture.advance()
            advanced = len(completed_rounds)
    autopilot.stop()
    loop_speaker.stop()

    repeat_map = {
        "choice": config.speak_choice_repeat,
        "multi_choice": config.speak_multi_choice_repeat,
        "fill": config.speak_fill_repeat,
        "short": config.speak_short_repeat,
    }
    print(f"state transitions: {' -> '.join(states)}")
    for index, results in enumerate(rounds, start=1):
        numbers = [
            result.question_no or str(position + 1) for position, result in enumerate(results)
        ]
        repeats = [repeat_map.get(result.answer.qtype.value, 1) for result in results]
        cached_in_round = sum(1 for result in results if result.reused)
        print(
            f"frame {index}: questions={numbers} speak order={' -> '.join(numbers)} "
            f"repeats={repeats} cached={cached_in_round}/{len(results)}"
        )
    cached = sum(1 for from_cache in answers if from_cache)
    print(f"on_answer count: {len(answers)}")
    print(f"from_cache: fresh={len(answers) - cached} cached={cached}")
    print(f"spoken items: {len(speaker.spoken)}")
    print(
        f"total: rounds={len(rounds)} answers={len(answers)} "
        f"elapsed={time.monotonic() - started_at:.2f}s"
    )
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
    from examchaiter.storage.history_store import NullHistoryStore
    from examchaiter.tts import FakeSpeaker, LoopSpeaker, Pyttsx3Speaker

    config_store = ConfigStore()
    settings = config_store.to_settings()
    history_store = HistoryStore(base_dir=config_store.base_dir)
    app_config = config_store.load()
    auto_config = AutoPilotConfig(
        poll_interval=app_config.auto_poll_interval,
        stable_frames=app_config.auto_stable_frames,
        speak_choice_repeat=app_config.auto_speak_choice_repeat,
        speak_multi_choice_repeat=app_config.auto_speak_multi_choice_repeat,
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
            def run_once(self, _hwnd: int) -> list[PipelineResult]:
                return []

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
                history_store=NullHistoryStore(),
                session_id="",
            )

        pipeline_factory = build_exam_pipeline
        list_windows_fn = None

    def autopilot_factory(session_id: str, callbacks: Any) -> AutoPilot:
        return AutoPilot(
            capture=capture,
            ocr=ocr,
            llm=llm,
            splitter=QuestionSplitter(llm, settings),
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
