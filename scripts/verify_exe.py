"""Manual smoke check for the packaged executable.

This script is not part of CI. Run it only after a successful local build.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

EXE_PATH = Path(__file__).resolve().parents[1] / "dist" / "ExamChaiTer.exe"


def main() -> int:
    if not EXE_PATH.exists():
        print(f"exe-crashed: missing {EXE_PATH}")
        return 1

    process = subprocess.Popen(
        [str(EXE_PATH)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    time.sleep(15)
    if process.poll() is None:
        process.terminate()
        process.wait(timeout=10)
        print("exe-alive")
        return 0

    _stdout, stderr = process.communicate()
    print(f"exe-crashed: {stderr.strip()}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
