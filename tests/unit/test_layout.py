"""Unit tests for OCR block layout."""

import pytest

from examchaiter.models import OcrBlock
from examchaiter.ocr.layout import blocks_to_text


def _block(text: str, bbox: tuple[float, float, float, float], confidence: float = 1.0) -> OcrBlock:
    return OcrBlock(text=text, bbox=bbox, confidence=confidence)


def test_blocks_to_text_with_empty_blocks_returns_empty_string() -> None:
    assert blocks_to_text([]) == ""


def test_blocks_to_text_with_single_block_returns_text() -> None:
    assert blocks_to_text([_block("Only", (10.0, 10.0, 50.0, 20.0))]) == "Only"


def test_blocks_to_text_with_same_row_sorts_by_x() -> None:
    blocks = [
        _block("Right", (100.0, 0.0, 160.0, 20.0)),
        _block("Left", (0.0, 1.0, 50.0, 21.0)),
    ]

    assert blocks_to_text(blocks) == "Left Right"


def test_blocks_to_text_with_two_rows_sorts_by_y() -> None:
    blocks = [
        _block("Second", (0.0, 100.0, 60.0, 120.0)),
        _block("First", (0.0, 0.0, 50.0, 20.0)),
    ]

    assert blocks_to_text(blocks) == "First\nSecond"


def test_blocks_to_text_with_close_y_and_reversed_x_sorts_by_x() -> None:
    blocks = [
        _block("Right", (100.0, 0.0, 160.0, 20.0)),
        _block("Left", (0.0, 2.0, 50.0, 22.0)),
    ]

    assert blocks_to_text(blocks) == "Left Right"


def test_blocks_to_text_with_low_confidence_block_keeps_text() -> None:
    blocks = [_block("Noise", (0.0, 0.0, 50.0, 20.0), confidence=0.01)]

    assert blocks_to_text(blocks) == "Noise"


def test_blocks_to_text_fills_missing_option_letters() -> None:
    lines = [
        "在 OAuth2.0 中为什么需要授权码？",
        "A）减少授权服务器负载",
        "B 避免令牌在浏览器传输中被截获",
        "支持多因素认证流程",
        "简化客户端实现复杂度",
        "单选题",
    ]
    blocks = [
        _block(text, (0.0, index * 20.0, 200.0, index * 20.0 + 16.0))
        for index, text in enumerate(lines)
    ]

    assert blocks_to_text(blocks).splitlines()[3:5] == [
        "C. 支持多因素认证流程",
        "D. 简化客户端实现复杂度",
    ]


def test_blocks_to_text_corrects_misread_first_option_letter() -> None:
    lines = [
        "以下哪个算法不是对称加密算法？",
        "P DES",
        "B RC5",
        "AES",
        "D RSA",
        "单选题",
    ]
    blocks = [
        _block(text, (0.0, index * 20.0, 200.0, index * 20.0 + 16.0))
        for index, text in enumerate(lines)
    ]

    assert blocks_to_text(blocks).splitlines()[1:5] == [
        "A. DES",
        "B. RC5",
        "C. AES",
        "D. RSA",
    ]


def test_blocks_to_text_infers_unmarked_choice_options() -> None:
    lines = [
        "这些信息从服务器的哪个位置获得（)",
        "sam数据库",
        "本地配置文件",
        "windows隐藏密码本",
        "内存",
        "交卷",
        "答题卡",
    ]
    blocks = [
        _block(text, (0.0, index * 20.0, 200.0, index * 20.0 + 16.0))
        for index, text in enumerate(lines)
    ]

    assert blocks_to_text(blocks).splitlines()[1:5] == [
        "A. sam数据库",
        "B. 本地配置文件",
        "C. windows隐藏密码本",
        "D. 内存",
    ]


def test_blocks_to_text_does_not_label_only_the_tail_as_options() -> None:
    lines = [
        "假设系统中共需要管理多少密钥，每个用户需要保存多少个密钥？",
        "口",
        "n-1 单题",
        "2n",
        "Cn2",
        "n!",
        "单选题",
    ]
    blocks = [
        _block(text, (0.0, index * 20.0, 200.0, index * 20.0 + 16.0))
        for index, text in enumerate(lines)
    ]

    assert blocks_to_text(blocks).splitlines()[2:6] == [
        "A. n-1 单题",
        "B. 2n",
        "C. n2",
        "D. n!",
    ]


@pytest.mark.parametrize(
    ("line_gap_ratio", "expected"),
    [(0.1, "Left\nRight"), (2.0, "Left Right")],
)
def test_blocks_to_text_with_line_gap_ratio_changes_rows(
    line_gap_ratio: float, expected: str
) -> None:
    blocks = [
        _block("Left", (0.0, 0.0, 50.0, 20.0)),
        _block("Right", (100.0, 10.0, 160.0, 30.0)),
    ]

    assert blocks_to_text(blocks, line_gap_ratio=line_gap_ratio) == expected
