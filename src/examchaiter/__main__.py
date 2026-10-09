"""Command-line entry point for the Phase 0 skeleton."""

import argparse
from collections.abc import Sequence

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
    subparsers.add_parser("show-config", help="print effective settings with secrets masked")
    return parser


def _display_settings(settings: Settings) -> dict[str, object]:
    values: dict[str, object] = settings.model_dump(mode="json")
    values["llm_api_key"] = "sk-***" if settings.llm_api_key is not None else "<unset>"
    return values


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    if args.command == "show-config":
        for key, value in sorted(_display_settings(Settings()).items()):
            print(f"{key}={value}")

    if args.command == "ocr-self-test":
        import sys
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


if __name__ == "__main__":
    raise SystemExit(main())
