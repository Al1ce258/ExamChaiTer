# ExamChaiTer

ExamChaiTer is a Windows-local MVP that will connect window capture, OCR, an
OpenAI-compatible LLM, and optional text-to-speech output. Phase 0 contains only
the repository skeleton, configuration, models, CLI entry point, and offline
test harness. Real integrations are not executed in unit tests.

## Requirements

- Windows
- Python 3.11
- [uv](https://docs.astral.sh/uv/)

## Setup

```powershell
uv sync
Copy-Item .env.example .env
```

Do not commit `.env`, debug images, logs, or API keys.

## Checks

```powershell
uv run ruff format src tests
uv run ruff check src tests
uv run mypy src
uv run pytest -q
```

## Phase 0 Commands

```powershell
uv run python -m examchaiter --version
uv run python -m examchaiter show-config
```

`show-config` masks the configured API key and never starts a network request.
