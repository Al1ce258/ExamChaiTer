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


def to_speech_text(answer: Answer) -> str:
    """Format an answer for text-to-speech."""

    if answer.qtype is QuestionType.CHOICE:
        return f"答案是 {answer.content}"
    if answer.qtype is QuestionType.MULTI_CHOICE:
        return "答案是 " + "、".join(answer.content.split())
    if answer.qtype is QuestionType.FILL:
        return f"填空：{answer.content}"
    if answer.qtype is QuestionType.SHORT:
        return answer.content
    return "无法解析答案"
