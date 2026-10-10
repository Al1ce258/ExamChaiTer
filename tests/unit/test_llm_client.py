"""Unit tests for LLM clients."""

from types import SimpleNamespace

import pytest
from loguru import logger
from pytest_mock import MockerFixture

from examchaiter.llm import client as client_module
from examchaiter.llm.client import (
    FakeLLMClient,
    LazyLLMClient,
    LLMFailed,
    LLMTimeout,
    OpenAICompatClient,
)


def test_fake_llm_client_with_responses_returns_in_order() -> None:
    client = FakeLLMClient(responses=["first", "second"])

    assert [client.complete([]), client.complete([])] == ["first", "second"]


def test_fake_llm_client_without_responses_raises_llm_failed() -> None:
    client = FakeLLMClient(responses=[])

    with pytest.raises(LLMFailed):
        client.complete([])


def test_openai_compat_client_with_injected_response_returns_content(
    mocker: MockerFixture,
) -> None:
    backend = mocker.Mock()
    backend.chat.completions.create.return_value = _response("answer")
    client = _client(backend)

    assert client.complete([{"role": "user", "content": "question"}]) == "answer"


def test_openai_compat_client_with_timeout_raises_llm_timeout(mocker: MockerFixture) -> None:
    backend = mocker.Mock()
    backend.chat.completions.create.side_effect = TimeoutError("timed out")
    client = _client(backend)

    with pytest.raises(LLMTimeout):
        client.complete([])


def test_openai_compat_client_with_429_retries_with_exponential_sleep(
    mocker: MockerFixture,
) -> None:
    backend = mocker.Mock()
    backend.chat.completions.create.side_effect = [
        _http_error(429),
        _http_error(429),
        _response("ok"),
    ]
    sleep = mocker.Mock()
    client = _client(backend, max_retry=2, sleep=sleep)

    client.complete([])

    assert sleep.call_args_list == [mocker.call(0.5), mocker.call(1.0)]


def test_openai_compat_client_with_retry_exhaustion_raises_llm_failed(
    mocker: MockerFixture,
) -> None:
    backend = mocker.Mock()
    backend.chat.completions.create.side_effect = [_http_error(500), _http_error(500)]
    client = _client(backend, max_retry=1, sleep=mocker.Mock())

    with pytest.raises(LLMFailed):
        client.complete([])


def test_openai_compat_client_with_nested_response_status_retries(
    mocker: MockerFixture,
) -> None:
    error = Exception("response failure")
    error.response = SimpleNamespace(status_code=429)  # type: ignore[attr-defined]
    backend = mocker.Mock()
    backend.chat.completions.create.side_effect = [error, _response("ok")]
    client = _client(backend, max_retry=1, sleep=mocker.Mock())

    client.complete([])

    assert backend.chat.completions.create.call_count == 2


def test_openai_compat_client_with_import_failure_raises_llm_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_import(_name: str) -> object:
        raise ImportError("openai unavailable")

    monkeypatch.setattr(client_module.importlib, "import_module", fail_import)

    with pytest.raises(LLMFailed):
        OpenAICompatClient(
            base_url="https://example.invalid",
            api_key="sk-secret",
            model="model",
            timeout=1.0,
            max_retry=0,
        )


def test_openai_compat_client_with_json_mode_sends_response_format(
    mocker: MockerFixture,
) -> None:
    backend = mocker.Mock()
    backend.chat.completions.create.return_value = _response("ok")
    client = _client(backend)

    client.complete([], json_mode=True)

    assert backend.chat.completions.create.call_args.kwargs["response_format"] == {
        "type": "json_object"
    }


def test_openai_compat_client_failure_log_omits_raw_api_key(mocker: MockerFixture) -> None:
    backend = mocker.Mock()
    backend.chat.completions.create.side_effect = _http_error(400)
    client = _client(backend, api_key="sk-raw-secret")
    messages: list[str] = []
    sink_id = logger.add(messages.append, format="{message}")

    try:
        with pytest.raises(LLMFailed):
            client.complete([])
    finally:
        logger.remove(sink_id)

    assert "sk-raw-secret" not in "\n".join(messages)


def test_openai_compat_client_failure_log_contains_masked_api_key(mocker: MockerFixture) -> None:
    backend = mocker.Mock()
    backend.chat.completions.create.side_effect = _http_error(400)
    client = _client(backend, api_key="sk-raw-secret")
    messages: list[str] = []
    sink_id = logger.add(messages.append, format="{message}")

    try:
        with pytest.raises(LLMFailed):
            client.complete([])
    finally:
        logger.remove(sink_id)

    assert "sk-***" in "\n".join(messages)


def _client(
    backend: object,
    *,
    api_key: str = "sk-test",
    max_retry: int = 0,
    sleep: object | None = None,
) -> OpenAICompatClient:
    return OpenAICompatClient(
        base_url="https://example.invalid",
        api_key=api_key,
        model="model",
        timeout=1.0,
        max_retry=max_retry,
        _client=backend,
        _sleep=sleep,  # type: ignore[arg-type]
    )


def _response(content: str) -> object:
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


def _http_error(status_code: int) -> Exception:
    error = Exception("HTTP failure")
    error.status_code = status_code  # type: ignore[attr-defined]
    return error


def test_lazy_client_constructs_on_first_call(mocker: MockerFixture) -> None:
    inner = mocker.Mock()
    inner.complete.return_value = "answer"
    factory = mocker.Mock(return_value=inner)
    client = LazyLLMClient(factory)

    result = client.complete([{"role": "user", "content": "q"}])

    assert result == "answer"
    factory.assert_called_once()
    inner.complete.assert_called_once()


def test_lazy_client_caches_after_first_call(mocker: MockerFixture) -> None:
    inner = mocker.Mock()
    inner.complete.side_effect = ["a", "b"]
    factory = mocker.Mock(return_value=inner)
    client = LazyLLMClient(factory)

    assert client.complete([]) == "a"
    assert client.complete([]) == "b"
    factory.assert_called_once()
    assert inner.complete.call_count == 2


def test_lazy_client_propagates_factory_error() -> None:
    def _boom() -> object:
        raise RuntimeError("missing api key")

    client = LazyLLMClient(_boom)  # type: ignore[arg-type]

    with pytest.raises(LLMFailed):
        client.complete([])
