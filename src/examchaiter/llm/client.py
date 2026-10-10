"""LLM client protocol, OpenAI-compatible adapter, and fake implementation."""

from __future__ import annotations

import importlib
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

from loguru import logger

from examchaiter.errors import LlmError

Message = dict[str, object]
SleepFunction = Callable[[float], None]

LLMFailed = LlmError


class LLMTimeout(LLMFailed):
    """Raised when an OpenAI-compatible request times out."""


class LLMClient(Protocol):
    """Protocol implemented by real and fake LLM clients."""

    def complete(self, messages: list[Message], *, json_mode: bool = False) -> str: ...


@dataclass
class FakeLLMClient:
    """Return queued responses in order without using a network client."""

    responses: list[str]
    model: str = "fake"
    calls: list[list[Message]] = field(default_factory=list)

    def complete(self, messages: list[Message], *, json_mode: bool = False) -> str:
        self.calls.append(messages)
        if not self.responses:
            raise LLMFailed("FakeLLMClient has no queued responses")
        return self.responses.pop(0)


class OpenAICompatClient:
    """Minimal OpenAI-compatible chat client with retry and timeout handling."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout: float,
        max_retry: int,
        _client: Any = None,
        _sleep: SleepFunction = time.sleep,
    ) -> None:
        self.base_url = base_url
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.max_retry = max(0, max_retry)
        self._sleep = _sleep
        self._client = _client if _client is not None else self._load_client()

    def _load_client(self) -> Any:
        try:
            module = importlib.import_module("openai")
            return module.OpenAI(  # pragma: no cover - real network client
                base_url=self.base_url,
                api_key=self.api_key,
                timeout=self.timeout,
            )
        except Exception as exc:
            raise LLMFailed("OpenAI SDK is unavailable or could not be initialized") from exc

    def complete(self, messages: list[Message], *, json_mode: bool = False) -> str:
        for attempt in range(self.max_retry + 1):
            try:
                request: dict[str, object] = {"model": self.model, "messages": messages}
                if json_mode:
                    request["response_format"] = {"type": "json_object"}
                response = self._client.chat.completions.create(**request)
                content = response.choices[0].message.content
                return "" if content is None else str(content)
            except Exception as exc:
                if _is_timeout(exc):
                    self._log_failure("timeout", None)
                    raise LLMTimeout("OpenAI-compatible request timed out") from exc

                status_code = _status_code(exc)
                if _is_retryable(status_code) and attempt < self.max_retry:
                    self._sleep(0.5 * (2**attempt))
                    continue

                self._log_failure("request failed", status_code)
                raise LLMFailed("OpenAI-compatible request failed") from exc

        raise LLMFailed("OpenAI-compatible request failed")

    def _log_failure(self, reason: str, status_code: int | None) -> None:
        logger.error(
            "OpenAI-compatible {}: api_key=sk-*** model={} status={}",
            reason,
            self.model,
            status_code,
        )


def _status_code(exc: BaseException) -> int | None:
    status_code = getattr(exc, "status_code", None)
    if isinstance(status_code, int):
        return status_code
    response = getattr(exc, "response", None)
    response_status = getattr(response, "status_code", None)
    return response_status if isinstance(response_status, int) else None


def _is_retryable(status_code: int | None) -> bool:
    return status_code == 429 or (status_code is not None and 500 <= status_code < 600)


def _is_timeout(exc: BaseException) -> bool:
    return isinstance(exc, TimeoutError) or exc.__class__.__name__ in {
        "APITimeoutError",
        "ConnectTimeout",
        "ReadTimeout",
        "TimeoutException",
    }


class LazyLLMClient:
    """Delay building the real client until the first ``complete`` call.

    Used at GUI startup so a missing/expired API key does not block the window
    from opening; the failure surfaces only when an answer is requested.
    """

    def __init__(self, factory: Callable[[], LLMClient]) -> None:
        self._factory = factory
        self._client: LLMClient | None = None

    def complete(self, messages: list[Message], *, json_mode: bool = False) -> str:
        if self._client is None:
            try:
                self._client = self._factory()
            except Exception as exc:
                raise LLMFailed(f"LLM 未就绪：{exc}") from exc
        return self._client.complete(messages, json_mode=json_mode)
