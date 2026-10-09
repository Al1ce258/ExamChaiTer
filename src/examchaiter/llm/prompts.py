"""Prompt construction and defensive answer parsing."""

from __future__ import annotations

import base64
import json
import re

from examchaiter.models import Answer, QuestionType

SYSTEM_PROMPT = (
    '只输出 JSON，格式必须为 {"type":"choice|fill|short","answer":"<纯答案>"}。'
    '不得包含解释、步骤或题干复述。选择题 answer 只给字母（如 "B"），不给选项原文。'
)
_VALID_TYPES = {
    "choice": QuestionType.CHOICE,
    "fill": QuestionType.FILL,
    "short": QuestionType.SHORT,
}


def build_messages(
    question_text: str, images: list[bytes] | None = None
) -> list[dict[str, object]]:
    """Build system and user messages for text-only or vision input."""

    messages: list[dict[str, object]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    if images:
        content: list[dict[str, object]] = [{"type": "text", "text": question_text}]
        for image in images:
            encoded = base64.b64encode(image).decode("ascii")
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{encoded}"},
                }
            )
        messages.append({"role": "user", "content": content})
    else:
        messages.append({"role": "user", "content": question_text})
    return messages


def parse_answer(raw: str) -> Answer:
    """Parse any input into an Answer without raising."""

    if not isinstance(raw, str) or not raw.strip():
        return Answer(qtype=QuestionType.UNKNOWN, content="")

    candidate = _answer_from_json(raw)
    if candidate is not None:
        return candidate

    object_match = re.search(r"\{.*?\}", raw, flags=re.DOTALL)
    if object_match is not None:
        candidate = _answer_from_json(object_match.group(0))
        if candidate is not None:
            return candidate

    return _heuristic_answer(raw.strip())


def _answer_from_json(raw: str) -> Answer | None:
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError):
        return None

    if not isinstance(payload, dict):
        return None

    qtype = _VALID_TYPES.get(str(payload.get("type", "")).lower())
    if qtype is None:
        return None

    answer = payload.get("answer")
    if answer is None:
        return None
    content = str(answer).strip()
    if not content:
        return None
    return Answer(qtype=qtype, content=content)


def _heuristic_answer(raw: str) -> Answer:
    if re.fullmatch(r"[A-Da-d]", raw):
        return Answer(qtype=QuestionType.CHOICE, content=raw.upper())

    choice_match = re.search(r"答案\s*[:：]\s*([A-Da-d])", raw, flags=re.IGNORECASE)
    if choice_match is not None:
        return Answer(qtype=QuestionType.CHOICE, content=choice_match.group(1).upper())

    if "____" in raw:
        content = re.sub(r"_+", " ", raw)
        content = re.sub(r"^\s*(?:答案|填空)\s*[:：]\s*", "", content).strip()
        return Answer(qtype=QuestionType.FILL, content=content)

    return Answer(qtype=QuestionType.SHORT, content=raw)
