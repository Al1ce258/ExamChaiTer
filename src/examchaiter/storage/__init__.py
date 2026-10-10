"""Configuration and history persistence for ExamChaiTer."""

from examchaiter.storage.config_store import AppConfig, ConfigStore
from examchaiter.storage.hashing import normalize_text, question_hash
from examchaiter.storage.history_store import (
    HistoryEntry,
    HistoryStore,
    HistoryStoreLike,
    NullHistoryStore,
    SessionMeta,
)

__all__ = [
    "AppConfig",
    "ConfigStore",
    "HistoryEntry",
    "HistoryStore",
    "HistoryStoreLike",
    "NullHistoryStore",
    "SessionMeta",
    "normalize_text",
    "question_hash",
]
