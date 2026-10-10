"""Per-session question/answer history persisted as JSON files (schema v2)."""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import asdict, dataclass, fields
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

from loguru import logger

from examchaiter.errors import StorageError
from examchaiter.storage.config_store import resolve_storage_dir

SESSIONS_DIRNAME = "sessions"
INDEX_FILENAME = "index.json"
SCHEMA_VERSION = 2

_INVALID_FILENAME_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


@dataclass
class HistoryEntry:
    """One stored question and the answer produced for it."""

    question_no: str = ""
    question_hash: str = ""
    question_text: str = ""
    answer_qtype: str = ""
    answer_content: str = ""
    model: str = ""
    latency_ms: int = 0
    created_at: float = 0.0


@dataclass
class SessionMeta:
    """Summary of one exam session, mirrored in ``index.json``."""

    session_id: str
    name: str
    created_at: float
    question_count: int


class HistoryStoreLike(Protocol):
    """Minimal history surface required by the answer engines."""

    def find_by_hash(self, session_id: str, qhash: str) -> HistoryEntry | None: ...

    def add_or_update_entry(
        self, session_id: str, entry: HistoryEntry, *, flush_now: bool = False
    ) -> None: ...


@dataclass
class _Session:
    session_id: str
    name: str
    created_at: float
    entries: list[HistoryEntry]
    index: dict[str, int]


def _entry_payload(entry: HistoryEntry) -> dict[str, Any]:
    return {field.name: getattr(entry, field.name) for field in fields(HistoryEntry)}


def _entry_from_payload(payload: Any) -> HistoryEntry:
    known = {field.name for field in fields(HistoryEntry)}
    data = {key: value for key, value in dict(payload).items() if key in known}
    return HistoryEntry(**data)


def _sanitize_name(name: str) -> str:
    cleaned = _INVALID_FILENAME_RE.sub("_", name.strip())
    return cleaned.strip(" .")


def _atomic_write_text(path: Path, text: str) -> None:
    """Write ``text`` atomically via a sibling tmp file and ``os.replace``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(path.name + ".tmp")
    try:
        tmp_path.write_text(text, encoding="utf-8")
        os.replace(tmp_path, path)
    except OSError as exc:
        raise StorageError(f"无法写入 {path.name}") from exc


class HistoryStore:
    """Manage ``base_dir/sessions/*.json`` plus a ``base_dir/index.json`` summary."""

    def __init__(self, base_dir: Path | None = None) -> None:
        self._base_dir = Path(base_dir) if base_dir is not None else self.default_base_dir()
        self._base_dir.mkdir(parents=True, exist_ok=True)
        self._sessions_dir = self._base_dir / SESSIONS_DIRNAME
        self._index_path = self._base_dir / INDEX_FILENAME
        self._cache: dict[str, _Session] = {}
        self._dirty: set[str] = set()

    @staticmethod
    def default_base_dir() -> Path:
        return resolve_storage_dir()

    @property
    def base_dir(self) -> Path:
        return self._base_dir

    def list_sessions(self) -> list[SessionMeta]:
        self.flush()
        return self._read_index()

    def create_session(self, name: str) -> SessionMeta:
        self.flush()
        metas = self._read_index()
        base = _sanitize_name(name) or datetime.now().strftime("%Y-%m-%d-%H%M")
        existing = {meta.session_id for meta in metas}
        session_id = base
        suffix = 1
        while session_id in existing:
            suffix += 1
            session_id = f"{base}-{suffix}"
        created_at = time.time()
        self._cache[session_id] = _Session(session_id, session_id, created_at, [], {})
        self._dirty.add(session_id)
        self.flush()
        return SessionMeta(session_id, session_id, created_at, 0)

    def load_session(self, session_id: str) -> list[HistoryEntry]:
        self.flush()
        session = self._ensure_loaded(session_id)
        return list(session.entries)

    def get_index(self, session_id: str) -> dict[str, HistoryEntry]:
        self.flush()
        session = self._ensure_loaded(session_id)
        return {entry.question_hash: entry for entry in session.entries}

    def find_by_hash(self, session_id: str, qhash: str) -> HistoryEntry | None:
        self.flush()
        session = self._cache.get(session_id)
        if session is None:
            path = self._session_path(session_id)
            if not path.exists():
                return None
            session = self._ensure_loaded(session_id)
        position = session.index.get(qhash)
        return None if position is None else session.entries[position]

    def add_or_update_entry(
        self, session_id: str, entry: HistoryEntry, *, flush_now: bool = False
    ) -> None:
        """Overwrite a matching ``question_hash`` in place, else append at the end."""
        session = self._ensure_loaded(session_id)
        position = session.index.get(entry.question_hash)
        if position is None:
            session.entries.append(entry)
            session.index[entry.question_hash] = len(session.entries) - 1
        else:
            session.entries[position] = entry
        self._dirty.add(session_id)
        if flush_now:
            self.flush()

    def rename_session(self, session_id: str, new_name: str) -> bool:
        self.flush()
        if session_id not in self._cache and not self._session_path(session_id).exists():
            return False
        session = self._ensure_loaded(session_id)
        session.name = new_name
        self._dirty.add(session_id)
        self.flush()
        return True

    def delete_session(self, session_id: str) -> bool:
        self.flush()
        path = self._session_path(session_id)
        if not path.exists():
            return False
        try:
            path.unlink()
        except OSError as exc:
            raise StorageError(f"无法删除会话: {session_id}") from exc
        self._cache.pop(session_id, None)
        self._dirty.discard(session_id)
        metas = [meta for meta in self._read_index() if meta.session_id != session_id]
        self._write_index(metas)
        return True

    def search(self, keyword: str, limit: int = 50) -> list[tuple[str, HistoryEntry]]:
        self.flush()
        matches: list[tuple[str, HistoryEntry]] = []
        for meta in self._read_index():
            try:
                session = self._ensure_loaded(meta.session_id)
            except StorageError:
                continue
            for entry in session.entries:
                if keyword in entry.question_text:
                    matches.append((meta.session_id, entry))
        matches.sort(key=lambda item: item[1].created_at, reverse=True)
        return matches[:limit]

    def flush(self) -> None:
        """Persist every dirty session file and refresh ``index.json`` atomically."""
        if not self._dirty:
            return
        pending = sorted(self._dirty)
        metas = {meta.session_id: meta for meta in self._read_index()}
        for session_id in pending:
            session = self._cache.get(session_id)
            if session is None:
                self._dirty.discard(session_id)
                continue
            self._write_session(session)
            meta = metas.get(session_id)
            if meta is None:
                metas[session_id] = SessionMeta(
                    session_id, session.name, session.created_at, len(session.entries)
                )
            else:
                meta.name = session.name
                meta.question_count = len(session.entries)
        self._write_index(list(metas.values()))
        self._dirty.difference_update(pending)

    def _session_path(self, session_id: str) -> Path:
        return self._sessions_dir / f"{session_id}.json"

    def _ensure_loaded(self, session_id: str) -> _Session:
        cached = self._cache.get(session_id)
        if cached is not None:
            return cached
        path = self._session_path(session_id)
        if not path.exists():
            raise StorageError(f"会话不存在: {session_id}")
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise StorageError(f"会话文件损坏: {session_id}") from exc

        if not isinstance(raw, dict) or int(raw.get("schema_version", 1)) != SCHEMA_VERSION:
            version = raw.get("schema_version", 1) if isinstance(raw, dict) else 1
            logger.warning(
                "不支持的 session schema v{}，按空 session 处理: {}", version, session_id
            )
            session = _Session(session_id, session_id, 0.0, [], {})
            self._cache[session_id] = session
            return session

        entries: list[HistoryEntry] = []
        index: dict[str, int] = {}
        raw_entries = raw.get("entries", [])
        if isinstance(raw_entries, list):
            for payload in raw_entries:
                entry = _entry_from_payload(payload)
                index[entry.question_hash] = len(entries)
                entries.append(entry)
        session = _Session(
            session_id=session_id,
            name=str(raw.get("name", session_id)),
            created_at=float(raw.get("created_at", 0.0)),
            entries=entries,
            index=index,
        )
        self._cache[session_id] = session
        return session

    def _write_session(self, session: _Session) -> None:
        payload = {
            "schema_version": SCHEMA_VERSION,
            "name": session.name,
            "created_at": session.created_at,
            "entries": [_entry_payload(entry) for entry in session.entries],
        }
        text = json.dumps(payload, ensure_ascii=False, indent=2)
        _atomic_write_text(self._session_path(session.session_id), text)

    def _read_index(self) -> list[SessionMeta]:
        if not self._index_path.exists():
            return []
        try:
            raw = json.loads(self._index_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise StorageError("历史索引损坏，无法读取") from exc
        sessions = raw.get("sessions", []) if isinstance(raw, dict) else []
        metas: list[SessionMeta] = []
        for item in sessions:
            if not isinstance(item, dict):
                continue
            metas.append(
                SessionMeta(
                    session_id=str(item.get("session_id", "")),
                    name=str(item.get("name", "")),
                    created_at=float(item.get("created_at", 0.0)),
                    question_count=int(item.get("question_count", 0)),
                )
            )
        return metas

    def _write_index(self, metas: list[SessionMeta]) -> None:
        text = json.dumps(
            {"sessions": [asdict(meta) for meta in metas]}, ensure_ascii=False, indent=2
        )
        _atomic_write_text(self._index_path, text)


class NullHistoryStore:
    """No-op store for explicit "answer without persistence" runs."""

    def __init__(self, base_dir: Path | None = None) -> None:
        self._base_dir = Path(base_dir) if base_dir is not None else resolve_storage_dir()

    @property
    def base_dir(self) -> Path:
        return self._base_dir

    def list_sessions(self) -> list[SessionMeta]:
        return []

    def create_session(self, name: str) -> SessionMeta:
        session_id = _sanitize_name(name) or "null-session"
        return SessionMeta(session_id, session_id, 0.0, 0)

    def load_session(self, session_id: str) -> list[HistoryEntry]:
        return []

    def get_index(self, session_id: str) -> dict[str, HistoryEntry]:
        return {}

    def find_by_hash(self, session_id: str, qhash: str) -> HistoryEntry | None:
        return None

    def add_or_update_entry(
        self, session_id: str, entry: HistoryEntry, *, flush_now: bool = False
    ) -> None:
        return None

    def rename_session(self, session_id: str, new_name: str) -> bool:
        return False

    def delete_session(self, session_id: str) -> bool:
        return False

    def search(self, keyword: str, limit: int = 50) -> list[tuple[str, HistoryEntry]]:
        return []

    def flush(self) -> None:
        return None
