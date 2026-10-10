"""Unit tests for text normalization and question hashing."""

from examchaiter.storage.hashing import normalize_text, question_hash


def test_question_hash_with_empty_and_whitespace_only_texts_are_equal() -> None:
    assert question_hash("") == question_hash(" \t\n\u3000 ")


def test_question_hash_is_case_insensitive_for_ascii_letters() -> None:
    assert question_hash("ABC") == question_hash("abc")


def test_question_hash_unifies_cjk_and_ascii_comma() -> None:
    assert question_hash("A,B") == question_hash("A，B")


def test_question_hash_ignores_newlines_and_ideographic_space() -> None:
    assert question_hash("甲\n乙") == question_hash("甲乙\u3000")


def test_question_hash_differs_for_different_texts() -> None:
    assert question_hash("第一题") != question_hash("第二题")


def test_question_hash_is_stable_for_long_text() -> None:
    long_text = "题目内容" * 250

    assert question_hash(long_text) == question_hash(long_text)


def test_normalize_text_folds_fullwidth_ascii_letters() -> None:
    assert normalize_text("ＡＢＣ") == "abc"


def test_normalize_text_maps_cjk_punctuation_to_ascii() -> None:
    assert normalize_text("（甲）【乙】“丙”") == '(甲)[乙]"丙"'


def test_normalize_text_returns_empty_string_for_whitespace_only_input() -> None:
    assert normalize_text(" \n\u3000\t") == ""
