"""Unit tests for the injected capture -> OCR -> split -> LLM pipeline."""

from dataclasses import dataclass, field

import numpy as np
from pytest_mock import MockerFixture

from examchaiter.config import Settings
from examchaiter.errors import CaptureError
from examchaiter.llm.client import FakeLLMClient, LLMTimeout
from examchaiter.models import OcrBlock, SplitQuestion
from examchaiter.ocr.engine import FakeOcrEngine
from examchaiter.pipeline import ExamPipeline
from examchaiter.storage.hashing import question_hash
from examchaiter.storage.history_store import HistoryEntry

_QUESTION_TEXT = "示例题目 1+1=?"


@dataclass
class FakeCapture:
    rect: tuple[int, int, int, int] = (0, 0, 100, 100)
    img: np.ndarray = field(default_factory=lambda: np.full((100, 100, 3), 255, dtype=np.uint8))
    alive: bool = True
    focus: bool = True

    def get_window_rect(self, _hwnd: int) -> tuple[int, int, int, int]:
        return self.rect

    def is_window_alive(self, _hwnd: int) -> bool:
        return self.alive

    def focus_window(self, _hwnd: int) -> bool:
        return self.focus

    def grab_window(self, _hwnd: int) -> np.ndarray:
        return self.img.copy()


class TimeoutLLM:
    def complete(self, _messages: list[dict[str, object]], *, json_mode: bool = False) -> str:
        raise LLMTimeout("timed out")


@dataclass
class FakeSplitter:
    questions: list[SplitQuestion] = field(
        default_factory=lambda: [SplitQuestion(question_no="", text=_QUESTION_TEXT)]
    )

    def split(self, _raw_text: str) -> list[SplitQuestion]:
        return list(self.questions)


@dataclass
class FakeHistory:
    entries: dict[str, HistoryEntry] = field(default_factory=dict)
    added: list[HistoryEntry] = field(default_factory=list)

    def find_by_hash(self, _session_id: str, qhash: str) -> HistoryEntry | None:
        return self.entries.get(qhash)

    def add_or_update_entry(
        self, _session_id: str, entry: HistoryEntry, *, flush_now: bool = False
    ) -> None:
        self.added.append(entry)
        self.entries[entry.question_hash] = entry


def test_run_once_happy_path_returns_choice(mocker: MockerFixture) -> None:
    results = _pipeline(mocker).run_once(1)

    assert len(results) == 1 and results[0].reused is False and results[0].answer.content == "B"


def test_run_once_returns_question_text(mocker: MockerFixture) -> None:
    results = _pipeline(mocker).run_once(1)

    assert results[0].question.text == _QUESTION_TEXT


def test_run_once_dedup_hit_skips_llm(mocker: MockerFixture) -> None:
    llm = FakeLLMClient(responses=['{"type":"choice","answer":"B"}'])
    pipeline = _pipeline(mocker, llm=llm)

    pipeline.run_once(1)
    second = pipeline.run_once(1)

    assert second[0].reused is True and len(llm.calls) == 1


def test_run_once_multi_questions_returns_list(mocker: MockerFixture) -> None:
    splitter = FakeSplitter(
        [
            SplitQuestion(question_no="1", text="第一题内容"),
            SplitQuestion(question_no="2", text="第二题内容"),
            SplitQuestion(question_no="3", text="第三题内容"),
        ]
    )
    llm = FakeLLMClient(
        responses=[
            '{"type":"choice","answer":"A"}',
            '{"type":"choice","answer":"B"}',
            '{"type":"choice","answer":"C"}',
        ]
    )

    results = _pipeline(mocker, llm=llm, splitter=splitter).run_once(1)

    assert [(result.question_no, result.answer.content) for result in results] == [
        ("1", "A"),
        ("2", "B"),
        ("3", "C"),
    ]


def test_run_once_single_question_no_still_returns_one_element(mocker: MockerFixture) -> None:
    splitter = FakeSplitter([SplitQuestion(question_no="7", text="唯一题目内容")])

    results = _pipeline(mocker, splitter=splitter).run_once(1)

    assert len(results) == 1 and results[0].question_no == "7"


def test_run_once_empty_split_returns_empty_list(mocker: MockerFixture) -> None:
    pipeline = _pipeline(mocker, splitter=FakeSplitter([]))

    assert pipeline.run_once(1) == []


def test_run_once_cache_hit_uses_history_and_skips_llm(mocker: MockerFixture) -> None:
    splitter = FakeSplitter([SplitQuestion(question_no="1", text="缓存题内容")])
    qhash = question_hash("1|缓存题内容")
    history = FakeHistory(
        entries={
            qhash: HistoryEntry(
                question_hash=qhash,
                question_text="缓存题内容",
                answer_qtype="choice",
                answer_content="D",
            )
        }
    )
    llm = FakeLLMClient(responses=[])

    results = _pipeline(
        mocker, llm=llm, splitter=splitter, history=history, session_id="s1"
    ).run_once(1)

    assert results[0].reused is True and results[0].answer.content == "D" and not llm.calls


def test_run_once_new_answer_writes_history(mocker: MockerFixture) -> None:
    splitter = FakeSplitter([SplitQuestion(question_no="2", text="新题内容")])
    history = FakeHistory()

    _pipeline(mocker, splitter=splitter, history=history, session_id="s1").run_once(1)

    assert history.added[0].question_hash == question_hash("2|新题内容")
    assert history.added[0].answer_content == "B"


def test_run_once_empty_ocr_with_vision_configured_uses_image(mocker: MockerFixture) -> None:
    llm = FakeLLMClient(responses=['{"type":"choice","answer":"B"}'])
    settings = Settings(_env_file=None, llm_vision_model="vision", min_text_len=1)
    pipeline = _pipeline(mocker, ocr=FakeOcrEngine(blocks=[]), llm=llm, settings=settings)

    pipeline.run_once(1)

    assert "image_url" in str(llm.calls[0])


def test_run_once_empty_ocr_without_vision_returns_unknown(mocker: MockerFixture) -> None:
    llm = FakeLLMClient(responses=[])
    pipeline = _pipeline(mocker, ocr=FakeOcrEngine(blocks=[]), llm=llm)

    results = pipeline.run_once(1)

    assert len(results) == 1 and results[0].answer.qtype.value == "unknown" and not llm.calls


def test_run_once_llm_timeout_returns_unknown_not_raise(mocker: MockerFixture) -> None:
    results = _pipeline(mocker, llm=TimeoutLLM()).run_once(1)

    assert len(results) == 1 and results[0].answer.qtype.value == "unknown"


def test_run_once_dead_window_returns_empty_list(mocker: MockerFixture) -> None:
    result = _pipeline(mocker, capture=FakeCapture(alive=False)).run_once(1)

    assert result == []


def test_run_once_focus_failed_returns_empty_list(mocker: MockerFixture) -> None:
    result = _pipeline(mocker, capture=FakeCapture(focus=False)).run_once(1)

    assert result == []


def test_run_once_different_image_reuses_llm(mocker: MockerFixture) -> None:
    llm = FakeLLMClient(
        responses=[
            '{"type":"choice","answer":"B"}',
            '{"type":"choice","answer":"C"}',
        ]
    )
    capture = FakeCapture()
    pipeline = _pipeline(mocker, capture=capture, llm=llm)

    first = pipeline.run_once(1)
    gradient = np.tile(np.arange(100, dtype=np.uint8), (100, 1))
    capture.img = np.repeat(gradient[:, :, np.newaxis], 3, axis=2)
    second = pipeline.run_once(1)

    assert first[0].reused is False and second[0].reused is False and len(llm.calls) == 2


def test_run_once_empty_ocr_vision_timeout_returns_unknown(mocker: MockerFixture) -> None:
    settings = Settings(_env_file=None, llm_vision_model="vision", min_text_len=1)
    pipeline = _pipeline(
        mocker,
        ocr=FakeOcrEngine(blocks=[]),
        llm=TimeoutLLM(),
        settings=settings,
    )

    results = pipeline.run_once(1)

    assert len(results) == 1 and results[0].answer.qtype.value == "unknown"


def test_run_once_capture_exception_returns_empty_list(mocker: MockerFixture) -> None:
    capture = FakeCapture()
    mocker.patch.object(capture, "get_window_rect", side_effect=CaptureError("rect failed"))
    pipeline = _pipeline(mocker, capture=capture)

    result = pipeline.run_once(1)

    assert result == []


def _pipeline(
    mocker: MockerFixture,
    *,
    capture: FakeCapture | None = None,
    ocr: FakeOcrEngine | None = None,
    llm: object | None = None,
    settings: Settings | None = None,
    splitter: FakeSplitter | None = None,
    history: FakeHistory | None = None,
    session_id: str = "",
) -> ExamPipeline:
    selected_llm = llm or FakeLLMClient(responses=['{"type":"choice","answer":"B"}'])
    selected_ocr = ocr or FakeOcrEngine(
        blocks=[OcrBlock(text=_QUESTION_TEXT, bbox=(0.0, 0.0, 160.0, 20.0))]
    )
    selected_settings = settings or Settings(_env_file=None)
    actual_splitter = splitter or FakeSplitter()
    return ExamPipeline(
        capture=capture or FakeCapture(),
        ocr=selected_ocr,
        llm=selected_llm,  # type: ignore[arg-type]
        settings=selected_settings,
        splitter=actual_splitter,  # type: ignore[arg-type]
        history_store=history,  # type: ignore[arg-type]
        session_id=session_id,
        _clock=mocker.Mock(return_value=1.0),
        _sleep=mocker.Mock(),
    )
