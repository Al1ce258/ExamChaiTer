"""Unit tests for pre-split UI noise filtering."""

from examchaiter.ocr.filters import strip_ui_noise


def test_strip_ui_noise_removes_titlebar_line() -> None:
    text = "language.ini phase16_notepad.txt\n1. 题目内容"

    assert strip_ui_noise(text) == "1. 题目内容"


def test_strip_ui_noise_removes_menubar_line() -> None:
    text = "文件 编辑 查看 H1\n1. 题目内容"

    assert strip_ui_noise(text) == "1. 题目内容"


def test_strip_ui_noise_keeps_question_line() -> None:
    text = "1. 题目内容"

    assert strip_ui_noise(text) == text


def test_strip_ui_noise_keeps_option_lines() -> None:
    text = "A. 选项一\nB. 选项二"

    assert strip_ui_noise(text) == text


def test_strip_ui_noise_returns_original_if_all_filtered() -> None:
    text = "文件\n编辑"

    assert strip_ui_noise(text) == text


def test_custom_patterns_add_to_defaults() -> None:
    text = "文件 编辑 查看 H1\nCUSTOM_NOISE\n1. 题目内容"

    assert strip_ui_noise(text, [r"^CUSTOM_NOISE$"]) == "1. 题目内容"
