$ErrorActionPreference = "Stop"

uv run ruff format --check src tests
uv run ruff check src tests
uv run mypy src
uv run pytest -q --cov=src/examchaiter --cov-report=term-missing --cov-fail-under=90

# 单独运行 integration 测试时不要附加 --cov-fail-under：
# uv run pytest -q -m integration
