"""Pure answer formatting functions."""

from examchaiter.models import Answer, QuestionType


def to_display_text(answer: Answer, *, choice_with_text: bool = False) -> str:
    """Format an answer for console or overlay display."""

    if answer.qtype in (QuestionType.CHOICE, QuestionType.MULTI_CHOICE):
        return f"答案：{answer.content}"
    if answer.qtype is QuestionType.FILL:
        return f"填空：{answer.content}"
    if answer.qtype is QuestionType.SHORT:
        return answer.content
    return "⚠️ 无法解析"


def to_speech_text(answer: Answer, question_no: str = "", fallback_index: int | None = None) -> str:
    """Format an answer for text-to-speech, prefixed by its question number.

    ``question_no`` wins when present; otherwise ``fallback_index`` (the frame's
    1-based order) is used; with neither, no prefix is added.
    """

    if question_no:
        prefix = f"第 {question_no} 题，"
    elif fallback_index is not None:
        prefix = f"第 {fallback_index} 题，"
    else:
        prefix = ""

    if answer.qtype is QuestionType.CHOICE:
        body = f"答案是 {answer.content}"
    elif answer.qtype is QuestionType.MULTI_CHOICE:
        body = "答案是 " + "、".join(answer.content.split())
    elif answer.qtype is QuestionType.FILL:
        body = f"填空：{answer.content}"
    elif answer.qtype is QuestionType.SHORT:
        body = answer.content
    else:
        body = "无法解析答案"
    return prefix + body
