"""Smoke tests for every CLI subcommand help screen."""

import pytest

from examchaiter.__main__ import main

SUBCOMMANDS = [
    "show-config",
    "list-windows",
    "ocr-self-test",
    "ask",
    "answer",
    "speak",
    "gui",
    "run",
]


@pytest.mark.parametrize("command", SUBCOMMANDS)
def test_cli_subcommand_help_exits_zero(command: str) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main([command, "--help"])

    assert exc_info.value.code == 0
