"""Prompt construction and defensive answer/parse helpers."""

from __future__ import annotations

import base64
import json
import re

from examchaiter.models import Answer, QuestionType, SplitQuestion

SYSTEM_PROMPT = (
    '只输出 JSON，格式必须为 {"type":"choice|multi_choice|fill|short","answer":"<纯答案>"}。'
    '不得包含解释、步骤或题干复述。单选题 answer 只给一个大写字母（如 "B"）；'
    '多选题把选项字母连写（如 "ABD"）；填空题/简答题给纯文本。'
)
SPLIT_SYSTEM_PROMPT = (
    "你是题目切分助手。把用户给的整段 OCR 文本拆成一道道独立题目。"
    '只输出 JSON 数组，元素形如 {"no": "1", "text": "题干全文"}；'
    "no 为题号（没有就空串），text 保留完整题干（含选项与空位），不要作答、不要解释、不要省略。"
)
_VALID_TYPES = {
    "choice": QuestionType.CHOICE,
    "multi_choice": QuestionType.MULTI_CHOICE,
    "fill": QuestionType.FILL,
    "short": QuestionType.SHORT,
}
_MULTI_LETTERS_RE = re.compile(r"[A-Da-d,，、\s]+")
_LETTER_RE = re.compile(r"[A-D]")
_ARRAY_RE = re.compile(r"\[.*\]", re.DOTALL)
_ANSWER_PREFIX_RE = re.compile(r"^\s*(?:答案|填空)\s*[:：]\s*")


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
                    "image_url": {"url": f"[image omitted]{encoded}"},
                }
            )
        messages.append({"role": "user", "content": content})
    else:
        messages.append({"role": "user", "content": question_text})
    return messages


def build_split_messages(raw_text: str) -> list[dict[str, object]]:
    """Build messages asking the LLM to split one OCR block into questions."""

    return [
        {"role": "system", "content": SPLIT_SYSTEM_PROMPT},
        {"role": "user", "content": raw_text},
    ]


def parse_split_response(raw: str) -> list[SplitQuestion]:
    """Parse an LLM split response; return ``[]`` for anything unusable."""

    if not isinstance(raw, str) or not raw.strip():
        return []
    payload = _load_json_array(raw)
    if payload is None:
        return []
    questions: list[SplitQuestion] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text", "")).strip()
        if not text:
            continue
        no_value = item.get("no", "")
        question_no = "" if no_value is None else str(no_value).strip()
        questions.append(SplitQuestion(question_no=question_no, text=text))
    return questions


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
    if qtype is QuestionType.MULTI_CHOICE:
        return _multi_answer(content)
    return Answer(qtype=qtype, content=content)


def _heuristic_answer(raw: str) -> Answer:
    if re.fullmatch(r"[A-Da-d]", raw):
        return Answer(qtype=QuestionType.CHOICE, content=raw.upper())

    if _MULTI_LETTERS_RE.fullmatch(raw) is not None and len(_letters(raw)) >= 2:
        multi = _multi_answer(raw)
        if multi is not None:
            return multi

    choice_match = re.search(r"答案\s*[:：]\s*([A-Da-d][A-Da-d,，、\s]*)", raw, flags=re.IGNORECASE)
    if choice_match is not None:
        letters = _letters(choice_match.group(1))
        if len(letters) >= 2:
            return Answer(qtype=QuestionType.MULTI_CHOICE, content=" ".join(letters))
        if letters:
            return Answer(qtype=QuestionType.CHOICE, content=letters[0])

    if "____" in raw:
        content = re.sub(r"_+", " ", raw)
        content = _ANSWER_PREFIX_RE.sub("", content).strip()
        return Answer(qtype=QuestionType.FILL, content=content)

    return Answer(qtype=QuestionType.SHORT, content=raw)


def _letters(raw: str) -> list[str]:
    return _LETTER_RE.findall(raw.upper())


def _multi_answer(content: str) -> Answer | None:
    letters = _letters(content)
    if len(letters) >= 2:
        return Answer(qtype=QuestionType.MULTI_CHOICE, content=" ".join(letters))
    if len(letters) == 1:
        return Answer(qtype=QuestionType.CHOICE, content=letters[0])
    return None


def _load_json_array(raw: str) -> list[object] | None:
    for candidate in (raw, _extract_array(raw)):
        if candidate is None:
            continue
        try:
            payload = json.loads(candidate)
        except (TypeError, ValueError):
            continue
        if isinstance(payload, list):
            return payload
    return None


def _extract_array(raw: str) -> str | None:
    match = _ARRAY_RE.search(raw)
    return match.group(0) if match is not None else None
