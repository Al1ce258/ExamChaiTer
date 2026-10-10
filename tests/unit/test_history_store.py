"""Unit tests for the JSON-backed :class:`HistoryStore`."""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import fields
from pathlib import Path

import pytest

from examchaiter.errors import StorageError
from examchaiter.storage.history_store import HistoryEntry, HistoryStore


def _entry(
    qhash: str, text: str = "题目", created_at: float = 0.0, content: str = "A"
) -> HistoryEntry:
    return HistoryEntry(
        question_hash=qhash,
        question_text=text,
        answer_qtype="choice",
        answer_content=content,
        model="deepseek-chat",
        latency_ms=10,
        created_at=created_at,
    )


def test_history_entry_has_no_image_fields() -> None:
    assert {field.name for field in fields(HistoryEntry)} == {
        "question_hash",
        "question_text",
        "answer_qtype",
        "answer_content",
        "model",
        "latency_ms",
        "created_at",
    }


def test_create_session_with_empty_name_uses_date_format(tmp_path: Path) -> None:
    meta = HistoryStore(tmp_path).create_session("")

    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}-\d{4}", meta.session_id)


def test_create_session_with_duplicate_name_appends_suffix(tmp_path: Path) -> None:
    store = HistoryStore(tmp_path)
    first = store.create_session("午间")

    second = store.create_session("午间")

    assert second.session_id == f"{first.session_id}-2"


def test_create_session_sanitizes_illegal_filename_characters(tmp_path: Path) -> None:
    meta = HistoryStore(tmp_path).create_session("a/b:c")

    assert "/" not in meta.session_id


def test_list_sessions_after_add_reports_question_count(tmp_path: Path) -> None:
    store = HistoryStore(tmp_path)
    meta = store.create_session("exam")
    store.add_entry(meta.session_id, _entry("h1"))
    store.add_entry(meta.session_id, _entry("h2"))

    assert store.list_sessions()[0].question_count == 2


def test_add_entry_same_hash_twice_keeps_latest(tmp_path: Path) -> None:
    store = HistoryStore(tmp_path)
    meta = store.create_session("exam")
    store.add_entry(meta.session_id, _entry("h1", content="A"))
    store.add_entry(meta.session_id, _entry("h1", content="B"))

    entries = store.load_session(meta.session_id)

    assert (len(entries), entries["h1"].answer_content) == (1, "B")


def test_find_by_hash_returns_stored_entry(tmp_path: Path) -> None:
    store = HistoryStore(tmp_path)
    meta = store.create_session("exam")
    store.add_entry(meta.session_id, _entry("h1", content="C"))

    assert store.find_by_hash(meta.session_id, "h1") is not None


def test_find_by_hash_with_unknown_hash_returns_none(tmp_path: Path) -> None:
    store = HistoryStore(tmp_path)
    meta = store.create_session("exam")

    assert store.find_by_hash(meta.session_id, "missing") is None


def test_find_by_hash_on_missing_session_returns_none(tmp_path: Path) -> None:
    assert HistoryStore(tmp_path).find_by_hash("nope", "h1") is None


def test_add_entry_to_missing_session_raises_storage_error(tmp_path: Path) -> None:
    with pytest.raises(StorageError):
        HistoryStore(tmp_path).add_entry("nope", _entry("h1"))


def test_rename_session_updates_display_name(tmp_path: Path) -> None:
    store = HistoryStore(tmp_path)
    meta = store.create_session("old")

    store.rename_session(meta.session_id, "new")

    assert store.list_sessions()[0].name == "new"


def test_rename_missing_session_returns_false(tmp_path: Path) -> None:
    assert HistoryStore(tmp_path).rename_session("nope", "new") is False


def test_delete_session_removes_it_from_index(tmp_path: Path) -> None:
    store = HistoryStore(tmp_path)
    meta = store.create_session("exam")
    store.delete_session(meta.session_id)

    assert store.list_sessions() == []


def test_delete_missing_session_returns_false(tmp_path: Path) -> None:
    assert HistoryStore(tmp_path).delete_session("nope") is False


def test_load_session_after_delete_raises_storage_error(tmp_path: Path) -> None:
    store = HistoryStore(tmp_path)
    meta = store.create_session("exam")
    store.delete_session(meta.session_id)

    with pytest.raises(StorageError):
        store.load_session(meta.session_id)


def test_load_missing_session_raises_storage_error(tmp_path: Path) -> None:
    with pytest.raises(StorageError):
        HistoryStore(tmp_path).load_session("nope")


def test_search_matches_across_sessions_sorted_by_time_desc(tmp_path: Path) -> None:
    store = HistoryStore(tmp_path)
    older = store.create_session("older")
    newer = store.create_session("newer")
    store.add_entry(older.session_id, _entry("h1", text="共有题干", created_at=1.0))
    store.add_entry(newer.session_id, _entry("h2", text="共有题干", created_at=2.0))

    results = store.search("共有")

    assert [session_id for session_id, _ in results] == [newer.session_id, older.session_id]


def test_search_respects_limit(tmp_path: Path) -> None:
    store = HistoryStore(tmp_path)
    meta = store.create_session("exam")
    for index in range(3):
        store.add_entry(meta.session_id, _entry(f"h{index}", text="关键字"))

    assert len(store.search("关键字", limit=2)) == 2


def test_search_skips_corrupt_session_file(tmp_path: Path) -> None:
    creator = HistoryStore(tmp_path)
    meta = creator.create_session("exam")
    creator.add_entry(meta.session_id, _entry("h1", text="关键字"))
    creator.flush()
    (tmp_path / "sessions" / f"{meta.session_id}.json").write_text("{broken", encoding="utf-8")

    results = HistoryStore(tmp_path).search("关键字")

    assert results == []


def test_load_corrupt_session_file_raises_storage_error(tmp_path: Path) -> None:
    creator = HistoryStore(tmp_path)
    meta = creator.create_session("exam")
    (tmp_path / "sessions" / f"{meta.session_id}.json").write_text("{broken", encoding="utf-8")

    with pytest.raises(StorageError):
        HistoryStore(tmp_path).load_session(meta.session_id)


def test_list_sessions_with_corrupt_index_raises_storage_error(tmp_path: Path) -> None:
    (tmp_path / "index.json").write_text("{broken", encoding="utf-8")

    with pytest.raises(StorageError):
        HistoryStore(tmp_path).list_sessions()


def test_list_sessions_ignores_non_dict_index_items(tmp_path: Path) -> None:
    payload = {
        "sessions": [
            "not-a-dict",
            {"session_id": "s1", "name": "n", "created_at": 1.0, "question_count": 2},
        ]
    }
    (tmp_path / "index.json").write_text(json.dumps(payload), encoding="utf-8")

    assert len(HistoryStore(tmp_path).list_sessions()) == 1


def test_flush_without_dirty_sessions_writes_nothing(tmp_path: Path) -> None:
    HistoryStore(tmp_path).flush()

    assert not (tmp_path / "index.json").exists()


def test_add_entry_performance_under_500ms(tmp_path: Path) -> None:
    store = HistoryStore(tmp_path)
    meta = store.create_session("perf")
    start = time.perf_counter()
    for index in range(1000):
        store.add_entry(
            meta.session_id,
            HistoryEntry(
                question_hash=f"h{index}",
                question_text="performance",
                answer_qtype="choice",
                answer_content="A",
                created_at=float(index),
            ),
        )
    entries = store.load_session(meta.session_id)

    assert (len(entries), time.perf_counter() - start < 0.5) == (1000, True)


def test_save_replace_failure_preserves_old_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = HistoryStore(tmp_path)
    meta = store.create_session("exam")
    store.add_entry(meta.session_id, _entry("h1", content="A"))
    store.flush()

    def _boom(source: str | os.PathLike[str], target: str | os.PathLike[str]) -> None:
        raise OSError("replace failed")

    monkeypatch.setattr(os, "replace", _boom)
    store.add_entry(meta.session_id, _entry("h2", content="B"))
    with pytest.raises(StorageError):
        store.flush()

    raw = json.loads(
        (tmp_path / "sessions" / f"{meta.session_id}.json").read_text(encoding="utf-8")
    )
    assert list(raw["entries"]) == ["h1"]


def test_add_entry_flush_now_writes_immediately(tmp_path: Path) -> None:
    store = HistoryStore(tmp_path)
    meta = store.create_session("exam")

    store.add_entry(meta.session_id, _entry("h1", content="A"), flush_now=True)

    raw = json.loads(
        (tmp_path / "sessions" / f"{meta.session_id}.json").read_text(encoding="utf-8")
    )
    assert list(raw["entries"]) == ["h1"]
