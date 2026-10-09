"""Manual smoke check for the packaged executable.

This script is not part of CI. Run it only after a successful local build.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import time
from pathlib import Path
from typing import TextIO

EXE_PATH = Path(__file__).resolve().parents[1] / "dist" / "ExamChaiTer.exe"
FAILURE_KEYWORDS = ("Traceback", "ModuleNotFoundError")


def _has_failure(text: str) -> bool:
    return any(keyword in text for keyword in FAILURE_KEYWORDS)


def _terminate_tree(process: subprocess.Popen[str]) -> None:
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    else:
        process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def _read_output(output: TextIO, error: TextIO) -> str:
    output.seek(0)
    error.seek(0)
    return f"{output.read()}\n{error.read()}"


def main() -> int:
    if not EXE_PATH.exists():
        print(f"exe-crashed: missing {EXE_PATH}")
        return 1

    with (
        tempfile.TemporaryFile(mode="w+", encoding="utf-8") as stdout,
        tempfile.TemporaryFile(mode="w+", encoding="utf-8") as stderr,
    ):
        process = subprocess.Popen(
            [str(EXE_PATH)],
            stdout=stdout,
            stderr=stderr,
            text=True,
        )
        time.sleep(15)
        if process.poll() is None:
            _terminate_tree(process)
            output = _read_output(stdout, stderr)
            if _has_failure(output):
                print(f"exe-crashed: {output.strip()}")
                return 1
            print("exe-alive")
            return 0

        output = _read_output(stdout, stderr).strip()
        print(f"exe-crashed: exit={process.returncode} {output}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
