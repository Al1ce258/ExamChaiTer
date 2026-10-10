# AGENT.md — ExamChaiTer AI 编码助手工作手册

> 本文件是**面向 AI 编码助手的最高约束**。每次让 AI 修改代码，必须把本文件作为上下文注入。
> 与 `docs/DEV_SPEC.md` 冲突时，以本文件为准；本文件未覆盖处，以 `DEV_SPEC.md` 为准。

---

## 0. 项目一句话

**ExamChaiTer**：聚焦指定程序窗口 → 截图 → OCR → 调 LLM → **只输出答案**（选择/填空/简答）→ 可选循环语音朗读。Python 3.11 / Windows / 本地 MVP。

---

## 1. 绝对禁止（违反即回滚重做）

| #    | 禁止事项                                                     |
| ---- | ------------------------------------------------------------ |
| N1   | 新增任何未在 `AGENT.md` §4.1 列出的第三方依赖               |
| N2   | 修改 `tests/` 下**已有的断言**（除非任务显式要求，且单独一个 commit） |
| N3   | 修改公开接口签名（`models.py` / 各模块 Protocol）而不先更新 `DEV_SPEC.md` |
| N4   | 修改目录结构                                                 |
| N5   | 在类内部直接 `new` 具体实现（必须依赖注入，见 §4）           |
| N6   | 测试里做真实网络请求、真实 TTS 播放、`sleep` ≥ 0.1s          |
| N7   | 提交 `.env` / `debug/` / `logs/` / 真实考试截图 / 模型权重   |
| N8   | 打印或日志输出 API Key 原文（必须 `sk-***` 脱敏）            |
| N9   | 输出答案时附带解释、步骤、复述题干（`Answer.content` 只能是纯答案） |
| N10  | `git commit -am` / `--no-verify` / 跳过 pre-commit           |
| N11  | 用 `...省略...`、`# 其余不变` 之类偷懒占位替代完整代码       |
| N12  | 一次任务跨越多个 Phase                                       |

**N1 例外**：Phase 8 起允许使用 PySide6，Phase 9 起允许使用 PyInstaller；其余依赖仍禁止新增。

---

## 2. 每次任务的标准输入模板

用户会这样下发任务，AI 必须按此解析：

```
【Phase】<0-7>
【任务】<一句话>
【允许改动的文件】<白名单，AI 不得越界>
【验收】<要新增/修改的测试用例名 + 期望结果>
```

若用户未提供 `【允许改动的文件】`，AI **必须先反问**，不得擅自开工。

---

## 3. 每次任务的标准输出格式（缺一不可）

AI 回复必须且只包含以下 5 段，顺序固定：

````
### 1. 改动清单
- M src/examchaiter/capture/window.py
- A tests/unit/test_window.py

### 2. 完整代码
（每个文件一个代码块，标注路径。禁止省略、禁止占位符）

### 3. 新增/修改的测试
（完整测试文件或 diff，标注路径）

### 4. 本地验证命令
```powershell
uv run ruff format src tests
uv run ruff check src tests
uv run mypy src
uv run pytest tests/unit/test_window.py -q
```

### 5. Commit Message
```
feat(capture): 实现窗口枚举与聚焦

- list_windows 支持 title_filter
- focus_window 重试 3 次

Tests: pytest tests/unit/test_window.py -q  (12 passed)
```
````

**AI 不允许**输出「以上就是全部内容」以外的收尾话术、不允许输出未请求的重构建议。

---

## 4. 依赖注入铁律（最重要的架构约束）

所有需要 mock 的东西**必须从构造函数传入**。反面教材 vs 正确写法：

```python
# ❌ 禁止：内部 new，无法测试
class ExamPipeline:
    def __init__(self):
        self.ocr = RapidOcrEngine()
        self.llm = OpenAICompatClient()

# ✅ 正确：全部注入
class ExamPipeline:
    def __init__(self, capture, ocr, llm, settings):
        self.capture = capture
        self.ocr = ocr
        self.llm = llm
        self.settings = settings
```

**必须存在 Fake 实现**：`FakeLLMClient`、`FakeOcrEngine`、`FakeSpeaker`、`FakeCapture`。没有 Fake 的模块不允许写单测。

### 4.1 允许的第三方依赖白名单

- 运行时：`pywin32`、`mss`、`numpy`、`pillow`、`rapidocr-onnxruntime`、`openai`、`pydantic`、`pydantic-settings`、`pyttsx3`、`pynput`、`loguru`
- Phase 8 起追加 `PySide6>=6.7`（GUI）
- Phase 9 起追加 `PyInstaller>=6.10`（打包）
- 开发：`pytest`、`pytest-mock`、`pytest-cov`、`pytest-qt>=4.4`、`ruff`、`mypy`、`types-pywin32`

除上述列表外禁止新增依赖。Phase 8 之前不得 import PySide6；Phase 9 之前不得 import PyInstaller。

Phase 10 不新增依赖：配置与历史存储用 JSON + pathlib 即可（无需 sqlite）；API Key 加密走已授权的 pywin32（win32crypt/DPAPI）。

Phase 13 不新增依赖：拆题用 re + 现有 LLMClient（无效 regex 由 splitter 忽略）；schema v2 不写迁移（无真实用户数据）。

---

## 5. 项目结构与文件职责速查

```
.examchaiter/           # 运行时数据目录（gitignore）
├─ config.json
├─ index.json
├─ sessions/
└─ logs/

src/examchaiter/
├─ __main__.py       CLI 入口（含 debug-capture 诊断子命令）
├─ config.py        Settings（pydantic-settings，前缀 EXAMCHAITER_）
├─ models.py        WindowInfo / OcrBlock / Question / Answer / QuestionType
├─ errors.py        自定义异常，全部继承 ExamChaiTerError
├─ capture/
│   ├─ window.py    list_windows / find_window / focus_window / get_window_rect / is_window_alive
│   └─ screenshot.py grab_rect / grab_window / dhash / hamming
├─ ocr/
│   ├─ engine.py    OcrEngine(Protocol) + RapidOcrEngine
│   └─ layout.py    blocks_to_text
├─ llm/
│   ├─ client.py    LLMClient(Protocol) + OpenAICompatClient + FakeLLMClient
│   ├─ splitter.py  QuestionSplitter（正则优先 → LLM 兜底 → 单题降级）
│   └─ prompts.py   build_messages / parse_answer / build_split_messages / parse_split_response
├─ output/
│   ├─ formatter.py to_display_text / to_speech_text
│   └─ presenter.py 控制台打印 + 写剪贴板
├─ tts/speaker.py   Speaker(Protocol) + Pyttsx3Speaker + FakeSpeaker + LoopSpeaker
├─ gui/
│   ├─ __init__.py
│   ├─ main_window.py
│   ├─ tray.py
│   ├─ overlay.py
│   ├─ style.py          # Windows 浅色 QSS（apply_style）
│   ├─ config_dialog.py  # 配置对话框（读写 ConfigStore）
│   ├─ history_dialog.py # 历史面板（session 列表 + 搜索 + 详情）
│   ├─ autopilot_bridge.py # AutoPilot ↔ Qt Signal 桥接（QObject）
│   ├─ answer_list.py    # 答案列表控件（QListWidget，供主窗口与历史复用）
│   └─ state.py
├─ pipeline.py      ExamPipeline.run_once() -> list[PipelineResult]
├─ app.py           ExamChaiTerApp（pynput 热键 + 主循环）
└─ storage/
    ├─ __init__.py
    ├─ config_store.py     # ConfigStore + AppConfig
    ├─ history_store.py    # HistoryStore + HistoryEntry + SessionMeta
    └─ hashing.py          # normalize_text + question_hash
ExamChaiTer.spec（仓库根）
```

**改动前先确认目标文件已存在于上述结构**；不存在说明跨 Phase，需停下反问。

---

## 6. 关键接口契约（不得擅自变更）

```python
# ---- models ----
Answer.qtype: QuestionType           # CHOICE / MULTI_CHOICE / FILL / SHORT / UNKNOWN
Answer.content: str                  # ← 唯一对外输出，纯答案（多选规范化为 "A B D"）
@dataclass
class PipelineResult:
    question: Question
    answer: Answer
    reused: bool = False
    question_no: str = ""            # 新增，如 "1" / "2" / 空串表示无题号

@dataclass
class SplitQuestion:
    question_no: str                 # 正则捕获的题号，LLM 拆分时也用，无题号时空串
    text: str                        # 纯净题干（已去掉题号前缀、前后空白）

# ---- pipeline ----
ExamPipeline.run_once(hwnd: int) -> list[PipelineResult]
    # 返回类型从单个变列表；空列表表示本帧无效（无文字 / 窗口死）
    # __init__ 必填注入 splitter: QuestionSplitter + history_store + session_id（只答不存请显式传 NullHistoryStore）
    # storage/history_store.py 提供 NullHistoryStore（find_by_hash→None、add_or_update_entry 空操作）

# ---- llm/prompts ----
parse_answer(raw: str) -> Answer     # 任何输入都不抛异常，最差返回 UNKNOWN；多字母 → MULTI_CHOICE
build_messages(question_text: str, images: list[bytes] | None = None) -> list[dict]
build_split_messages(raw_text: str) -> list[dict]
parse_split_response(raw: str) -> list[SplitQuestion]   # 解析失败返回 []，由调用方降级

# ---- llm/splitter.py（新模块）----
class QuestionSplitter:
    def __init__(self, llm: LLMClient, settings: Settings) -> None
    def split(self, raw_text: str) -> list[SplitQuestion]
        # 正则优先 → LLM 兜底 → 单题降级（永不抛异常）

# ---- tts ----
LoopSpeaker(speaker: Speaker, interval_s: float = 3.0)
    .start(text, max_repeats: int | None = None) / .stop() / .is_running() -> bool
    .wait_done(timeout: float | None = None) -> bool
    # max_repeats=None → 无限循环；max_repeats=N → 朗读 N 遍后线程自行退出
    # wait_done：阻塞到 读完 / stop() / timeout；True=正常读完，False=超时或提前中断
    # timeout=None 无限等；未 start 时立即返回 True
    # 内部 _done_event：每次 start 清零，读完或 stop 时 set（stop 能立刻唤醒 wait_done）
    # 二次 start 先 stop 旧线程再起新线程

# ---- 热键 ----
Ctrl+Alt+Q  作答一次
Ctrl+Alt+S  停/续循环朗读
Ctrl+Alt+X  退出

# gui/main_window.py
class MainWindow(QMainWindow):
    def __init__(self,
                 pipeline_factory: Callable[[], ExamPipeline],
                 loop_speaker: LoopSpeaker,
                 settings: Settings) -> None: ...

# gui/state.py  ← GUI 测试只测这里
class GuiController:
    def pick_window(self, title_filter: str) -> WindowInfo | None: ...
    def answer_once(self) -> list[PipelineResult]   # 变更：返回本帧所有题
    def toggle_tts(self) -> bool: ...
    # GuiState：last_results: list[PipelineResult]（替换原 last_answer 字段）
    # 保留 last_answer 为只读快捷访问 = last_results[-1].answer if last_results else None
```

**GUI 铁律**：GUI 文件内禁止直接 new OpenAICompatClient / RapidOcrEngine / win32gui 等具体实现，全部从 MainWindow.__init__ 注入。

```python
# ---- storage/hashing.py（纯函数）----
def normalize_text(text: str) -> str
    # 去除所有空白字符；全角转半角；英文小写化；中文标点统一为英文标点
def question_hash(text: str) -> str
    # sha256(normalize_text(text)) 的十六进制字符串

# ---- storage/config_store.py ----
@dataclass
class AppConfig:
    llm_base_url: str = "https://api.deepseek.com/v1"
    llm_api_key: str = ""
    llm_model: str = "deepseek-chat"
    llm_vision_model: str = ""
    llm_timeout: float = 30.0
    tts_enabled: bool = False
    tts_rate: int = 180
    tts_loop_interval: float = 3.0
    settle_ms: int = 150
    dedup_threshold: int = 5
    min_text_len: int = 20
    choice_with_text: bool = False
    clipboard: bool = True
    hotkey_answer: str = "<ctrl>+<alt>+q"
    hotkey_tts: str = "<ctrl>+<alt>+s"
    hotkey_quit: str = "<ctrl>+<alt>+x"
    log_level: str = "INFO"
    # Phase 11 AutoPilot（预留字段，本 Phase 只存不读）
    auto_enabled: bool = False
    auto_poll_interval: float = 1.5
    auto_stable_frames: int = 2
    auto_speak_choice_repeat: int = 5
    auto_speak_multi_choice_repeat: int = 5
    auto_speak_fill_repeat: int = 3
    auto_speak_short_repeat: int = 1
    auto_speak_interval: float = 3.0

class ConfigStore:
    def __init__(self, base_dir: Path | None = None) -> None
        # base_dir=None → default_base_dir()
        # 构造时 mkdir(parents=True, exist_ok=True)
    @staticmethod
    def default_base_dir() -> Path
        # 1. 若环境变量 EXAMCHAITER_STORAGE_DIR 非空 → 用它
        # 2. 否则 → Path.cwd() / ".examchaiter"
        # 3. 返回 .resolve()
        # 4. 不再使用 %APPDATA%
    def load(self) -> AppConfig
        # 优先级：base_dir/config.json > 项目根 .env > AppConfig 默认值
        # config.json 不存在时返回基于 .env 的 AppConfig
    def save(self, cfg: AppConfig) -> None
        # 原子写：先写 config.json.tmp 再 os.replace
        # api_key 用 win32crypt.CryptProtectData 加密后 base64 存入字段 "api_key_enc"
        # 若 win32crypt 不可用 → 明文存入 "api_key" 并在日志里 warning（仅一次）
    def to_settings(self) -> Settings
        # 返回 examchaiter.config.Settings 实例，用 AppConfig 字段覆盖默认值

# ---- storage/history_store.py（schema v2）----
@dataclass
class HistoryEntry:
    question_no: str = ""                # 新增
    question_hash: str = ""              # sha256(no + normalized_text)
    question_text: str = ""
    answer_qtype: str = ""
    answer_content: str = ""
    model: str = ""
    latency_ms: int = 0
    created_at: float = 0.0

@dataclass
class SessionMeta:
    session_id: str      # 文件名（不含 .json）
    name: str            # 显示名（用户可改）
    created_at: float
    question_count: int

class HistoryStore:
    def __init__(self, base_dir: Path | None = None) -> None
        # base_dir=None → ConfigStore.default_base_dir()
        # 构造时 mkdir(parents=True, exist_ok=True)
    def list_sessions(self) -> list[SessionMeta]
    def create_session(self, name: str) -> SessionMeta
        # name 为空时用当前时间 "YYYY-MM-DD-HHMM"
        # 冲突时追加 "-2" "-3"
    def load_session(self, session_id: str) -> list[HistoryEntry]   # 从 dict 改 list
    def get_index(self, session_id: str) -> dict[str, HistoryEntry] # 新增，返回 {qhash: entry} 快速查
    def find_by_hash(self, session_id: str, qhash: str) -> HistoryEntry | None
    def add_or_update_entry(self, session_id: str, entry: HistoryEntry, *, flush_now: bool = False) -> None
        # 同 qhash 已存在 → 覆盖并保持原位置；不存在 → 追加到 entries 末尾
    def rename_session(self, session_id: str, new_name: str) -> bool
    def delete_session(self, session_id: str) -> bool
    def search(self, keyword: str, limit: int = 50) -> list[tuple[str, HistoryEntry]]
        # 跨 session 搜索 question_text 包含 keyword 的条目
        # 返回 [(session_id, entry), ...]
    # session json 结构 v2：{schema_version: 2, name, created_at, entries: [HistoryEntry, ...]}
    # 读到 schema_version != 2 → log.warning 并当作空 session（不迁移）
    # 禁止存截图；HistoryEntry 不含任何图像字段
```

```python
# ---- autopilot.py（纯逻辑，不依赖 Qt；用回调通知外部）----
from enum import Enum
class AutoPilotState(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"

@dataclass
class AutoPilotConfig:
    poll_interval: float = 1.5
    stable_frames: int = 2
    speak_choice_repeat: int = 5
    speak_multi_choice_repeat: int = 5
    speak_fill_repeat: int = 3
    speak_short_repeat: int = 1
    speak_interval: float = 3.0
    min_text_len: int = 20

@dataclass
class AutoPilotCallbacks:
    on_state: Callable[[AutoPilotState], None]
    on_answer: Callable[[PipelineResult, bool], None]   # (result, from_cache)
    on_round_done: Callable[[list[PipelineResult]], None]  # 一帧所有题作答完成（可选，默认 no-op）
    on_status: Callable[[str], None]
    on_error: Callable[[Exception], None]

class AutoPilot:
    def __init__(
        self,
        capture,            # 需提供 grab_window(hwnd) 与 dhash(img)
        ocr,                # OcrEngine
        llm,                # LLMClient
        splitter,           # QuestionSplitter（必须注入）
        loop_speaker,       # LoopSpeaker
        history_store,      # HistoryStore
        session_id: str,
        config: AutoPilotConfig,
        callbacks: AutoPilotCallbacks,
        *,
        _sleep: Callable[[float], None] | None = None,  # 测试注入
        _wait_done_timeout: float = 30.0,  # 朗读兜底超时（防 TTS 卡死）
    ) -> None
    def start(self, hwnd: int) -> None          # 非阻塞，起工作线程
    def stop(self, timeout: float = 2.0) -> None  # 幂等
    def is_running(self) -> bool
    @property
    def state(self) -> AutoPilotState

# 状态机（一轮循环）：
#   1. img = capture.grab_window(hwnd)；失败 → on_error + 继续
#   2. h = dhash(img)；与 last_hash 对比：
#        相似 → stable_count += 1
#        不同 → stable_count = 0；last_hash = h；has_answered_this_frame = False
#   3. if stable_count >= stable_frames and not has_answered_this_frame：
#         text = blocks_to_text(ocr.recognize(img))
#         if len(text) < min_text_len → 跳过本轮
#         qhash = question_hash(text)
#         entry = history.find_by_hash(session_id, qhash)
#         if entry：
#             answer = Answer(qtype=QuestionType(entry.answer_qtype), content=entry.answer_content)
#             from_cache = True；on_status("缓存命中")
#         else：
#             answer = parse_answer(llm.complete(build_messages(text), json_mode=True))
#             history.add_entry(session_id, HistoryEntry(...), flush_now=True)
#             from_cache = False
#         result = PipelineResult(question=Question(text), answer=answer, reused=from_cache)
#         on_answer(result, from_cache)
#         repeat = {CHOICE: cfg.speak_choice_repeat, FILL: cfg.speak_fill_repeat,
#                   SHORT: cfg.speak_short_repeat, UNKNOWN: 1}[answer.qtype]
#         loop_speaker.stop()                        # 若上一次还在跑
#         loop_speaker.start(to_speech_text(answer), max_repeats=repeat)
#         has_answered_this_frame = True
#   4. _sleep(cfg.poll_interval)  ← 用 _stop_event.wait(cfg.poll_interval) 实现，让 stop 立刻返回
#   5. 循环直到 stop() 被调用
#
# stop()：设 _stop_event；join 工作线程（timeout）；loop_speaker.stop()；state=STOPPED
# 全部异常捕获后调 on_error，不让工作线程崩溃
```

```python
# ---- gui/autopilot_bridge.py ----
class AutoPilotBridge(QObject):
    state_changed = Signal(str)              # AutoPilotState.value
    answer_ready = Signal(object, bool)      # (PipelineResult, from_cache)
    status_message = Signal(str)
    error_occurred = Signal(object)
    round_done = Signal(list)                # list[PipelineResult]，一轮答案批量刷新
    def make_callbacks(self) -> AutoPilotCallbacks
    # make_callbacks 返回的 callbacks 内部全部走 .emit()，保证跨线程安全

# ---- gui/state.py 扩展 GuiController ----
class GuiController:
    # 新增：构造参数追加 config_store, history_store, autopilot_factory
    def __init__(self, pipeline_factory, loop_speaker, presenter, settings,
                 config_store, history_store, autopilot_factory,
                 list_windows_fn=None) -> None
    # 新增方法：
    def get_config(self) -> AppConfig
    def save_config(self, cfg: AppConfig) -> None       # 调 config_store.save
    def list_sessions(self) -> list[SessionMeta]
    def load_history(self, session_id: str) -> list[HistoryEntry]   # 从 dict 改 list（与 storage 一致）
    def search_history(self, keyword: str) -> list[tuple[str, HistoryEntry]]
    def delete_session(self, session_id: str) -> bool
    def start_auto(self, hwnd: int, session_name: str) -> None
        # 若已 running → 先 stop；构造 AutoPilot 并 start(hwnd)
    def stop_auto(self) -> None
    def is_auto_running(self) -> bool
    # GuiState 追加字段：
    auto_running: bool = False
    current_session_id: str | None = None
```

---

## 7. 测试规范

### 7.1 分层
| 目录                | 允许 IO                   | 何时跑                         |
| ------------------- | ------------------------- | ------------------------------ |
| `tests/unit`        | ❌ 无 IO 无网络            | 每次 commit（pre-commit 强制） |
| `tests/integration` | 本地文件/OCR 模型，无网络 | 手动 / CI                      |
| `tests/e2e`         | 真实 API + 真窗口         | 手动，默认跳过                 |

### 7.2 必用 Fixture（定义在 `tests/conftest.py`）
GUI 测试分两层：GuiController 用 `tests/unit` 普通测试；Qt 控件用 `tests/integration` + pytest-qt 的 `qtbot`，标 `@pytest.mark.integration` 默认 skip；pytest 运行环境设 `QT_QPA_PLATFORM=offscreen`。

```python
fake_capture      # 从 tests/fixtures/*.png 读 ndarray
fake_ocr          # FakeOcrEngine(blocks=[...])
fake_llm          # FakeLLMClient(responses=["{\"type\":\"choice\",\"answer\":\"B\"}"])
fake_speaker      # FakeSpeaker.spoken: list[str]
settings          # 隔离的 Settings，全部默认值 + 可覆盖
```

### 7.3 命名与断言
- 文件：`test_<被测模块>.py`
- 函数：`test_<行为>_<条件>_<期望>`，如 `test_parse_answer_with_fenced_json_returns_choice`
- 每个测试**只断言一件事**；参数化用 `@pytest.mark.parametrize`
- 涉及线程的测试用 `interval_s=0.01` + `threading.Event`，**禁止 `time.sleep`**

### 7.4 覆盖率
`fail_under = 80`。`capture/` 中纯调用 Windows API 的行可用 `# pragma: no cover`，逻辑行必须覆盖。

---

## 8. Phase 划分与验收（AI 不得跨 Phase）

| Phase | 目标       | 交付文件                                                     | 验收                                                         |
| ----- | ---------- | ------------------------------------------------------------ | ------------------------------------------------------------ |
| 0     | 骨架       | config / models / errors / pyproject / .gitignore / pre-commit | `pytest -q` ≥3 用例通过                                      |
| 1     | 窗口捕获   | capture/window.py, screenshot.py                             | `python -m examchaiter list-windows` 列出真实窗口；截图存 `debug/` |
| 2     | OCR        | ocr/engine.py, layout.py                                     | 合成图识别出全部文字，阅读顺序正确                           |
| 3     | LLM 与解析 | llm/client.py, prompts.py                                    | `parse_answer` 参数化 ≥10 组全过                             |
| 4     | 流水线     | pipeline.py, output/*                                        | 真实窗口→OCR→LLM→控制台只输出答案                            |
| 5     | 循环朗读   | tts/speaker.py                                               | `LoopSpeaker` 循环且可停；切题自动换内容                     |
| 6     | 热键常驻   | app.py                                                       | 三个热键生效；异常不退出                                     |
| 7     | 打磨       | README, e2e_smoke.py                                         | 三步跑通文档                                                 |
| 8     | GUI | gui/*.py | 双击 main_window 能开窗；三按钮绑定 ExamPipeline / LoopSpeaker；托盘菜单可用；GUI 层零业务逻辑 |
| 9     | 打包 exe | ExamChaiTer.spec + scripts/build.ps1 | 产物 dist/ExamChaiTer.exe 存在；双击打开主窗口；无控制台黑框；托盘图标与菜单可用；Ctrl+Alt+Q/S/X 生效（管理员权限下）；缺 API Key 时弹窗提示 |
| 10    | 配置持久化 + 历史存储 | storage/*.py | ConfigStore + HistoryStore 可读写、可单测；API Key 加密存盘 |
| 11    | AutoPilot 引擎 | autopilot.py + tts/speaker.py 扩展 | AutoPilot 纯逻辑可单测；Fake 依赖下能跑完整状态机；缓存命中不调 LLM；按题型朗读 N 遍；stop 后 200ms 内 is_running 为 False |
| 12    | GUI 大改版 | gui/*.py | Windows 浅色风格（Segoe UI + #0078D4 主色 + 圆角按钮 + 卡片留白）；配置面板读写 %APPDATA%\ExamChaiTer\config.json；历史面板列出/切换/搜索 session；自动模式开关一次进入循环、再点停止；AutoPilot 回调全部经 Qt Signal 回主线程 |
| 13    | 拆题引擎 + 多题返回 + schema v2 | llm/splitter.py, pipeline.py, storage/* | run_once 返回 list；题号落地；schema v2 |
| 14    | AutoPilot 适配多题 + 顺序朗读 | autopilot.py, tts/speaker.py | AutoPilot 一帧多题时按题号顺序朗读；朗读期间题目变化 200ms 内中断；LoopSpeaker.wait_done 在读完/stop/超时三种情况下都正确返回 |
| 15    | GUI 适配多题 | gui/* | 主窗口答案区一次显示 N 条（N=本帧题数），每条带题号；缓存命中行尾灰字；历史对话框表格含题号列且按题号排序；自动模式一帧多题时列表一次性刷新（不是逐条追加） |

每个 Phase 结束打 tag：`v0.1.0-phase<N>`。

---

## 9. 每次改动后的标准验证命令

```powershell
# 一键全检查
uv run ruff format src tests
uv run ruff check src tests
uv run mypy src
uv run pytest -q -m "not e2e and not integration and not slow"

# 单独跑目标测试
uv run pytest tests/unit/test_<模块>.py -q -v

# 覆盖率
uv run pytest --cov=src/examchaiter --cov-report=term-missing
```

**全部命令退出码为 0 才允许 commit。**

---

## 10. Commit 规范

格式：Conventional Commits，正文中文。

```
<type>(<scope>): <简述>

<可选的要点列表>

Tests: pytest tests/unit/test_xxx.py -q  (N passed)
```

- `type`：`feat` / `fix` / `test` / `refactor` / `chore` / `docs` / `perf`
- `scope`：`capture` / `ocr` / `llm` / `output` / `tts` / `pipeline` / `app` / `config`
- **一个 commit 只做一件事**；测试与实现放同一个 commit（保持原子性）
- 每个 Phase 的最后一个 commit 后打 tag

---

## 11. AI 常见踩坑清单（每次自检）

- [ ] 我是否在类内部直接 new 了具体实现？→ 改注入
- [ ] 我是否新增了依赖？→ 检查 DEV_SPEC §2
- [ ] 我的测试是否真的没有 IO / 网络 / 秒级 sleep？
- [ ] 我的 `parse_answer` 是否对**任何**输入都不抛异常？
- [ ] 我是否真的只输出了答案，没夹带解释？
- [ ] 我是否修改了既有测试断言？→ 单独 commit 并说明
- [ ] 我是否跨 Phase 了？
- [ ] 我的代码块是否完整，没有 `...省略...`？
- [ ] 我是否给出了可执行的验证命令和 commit message？

- 存储目录基于 `Path.cwd()`，启动前先 cd 到仓库根
- `%APPDATA%` 已弃用；不自动迁移，用户手动复制旧数据到 `.examchaiter/`
- 老版本的 `%APPDATA%\ExamChaiTer\` 内容原样保留，本版本不读、不写、不删
- `debug-capture` 用于诊断 OCR/拆题问题，每次跑生成 `debug/<timestamp>/` 目录；`debug/` 已 gitignore

### Phase 9 打包坑清单

- PySide6 体积：--exclude-module PySide6.QtWebEngine* 等
- rapidocr 模型：--add-data 显式带 rapidocr_onnxruntime/models/*
- pyttsx3：懒加载，失败降级静默
- 热键：Phase 8 起用 Qt QShortcut 取代 pynput
- 控制台黑框：--noconsole / console=False
- 杀软误报：不签名无法根治，告知用户加白名单
- onefile 首次启动 5~10 秒解压，属正常，README 需注明
- rapidocr 模型文件用 PyInstaller.utils.hooks.collect_data_files("rapidocr_onnxruntime") 收集，不要手写路径
- 所有延迟 import 的第三方包（openai / pyttsx3 等）必须在 spec 的 hiddenimports 用 collect_submodules 显式收集，否则 exe 启动时 ModuleNotFoundError
- 已知问题：PySide6 在 onefile 模式下可能报 "DLL load failed while importing QtWidgets: 找不到指定的程序"，与 VC++ 运行库版本、onefile 解压冲突有关；MVP 阶段不修，用户改用命令启动 `uv run python -m examchaiter gui`

### Phase 10 存储坑清单

- 历史记录禁止存截图：单张 200KB × 500 题 = 100MB，会毁掉 JSON 文件
- 配置写盘必须原子写（tmp + os.replace），否则崩溃时损坏文件
- win32crypt 延迟 import；不可用时降级明文并只在首次 log.warning
- Qt 主线程不能跑 pipeline，Phase 11 必须用 QThread + signal

### Phase 11 AutoPilot 坑清单

- AutoPilot 主循环用 _stop_event.wait(interval) 而非 time.sleep，保证 stop 及时返回
- AutoPilot 每次新答案必须 add_entry(..., flush_now=True)，否则崩溃会丢历史

### Phase 12 GUI 坑清单

- AutoPilot 在工作线程，GUI 更新必须走 QObject.Signal + QueuedConnection，禁止跨线程直接操作 widget
- Qt 主线程不能调用 pipeline.run_once（会卡 UI），手动作答走 QTimer.singleShot(0) + 状态回填，或用 QThread
- 配置对话框保存 API Key 时必须调用 ConfigStore.save（走 DPAPI），不得明文落盘

### Phase 13 拆题/多题坑清单

- run_once 现在是 list[PipelineResult]，所有旧调用方必须 for-each 处理
- schema v2 不写迁移：v0.2.1 无真实用户数据，直接覆盖
- 拆题 LLM 调用独立于答题 LLM 调用，走同一个 LLMClient（FakeLLMClient 需按顺序排队响应）

### Phase 14 顺序朗读坑清单

- LoopSpeaker.wait_done 必须能被 stop() 立刻唤醒，不能只靠 max_repeats 结束
- AutoPilot 顺序朗读时用 wait_done(timeout=_wait_done_timeout) 兜底，防止 TTS 引擎卡死导致主循环永不前进

### Phase 15 GUI 多答案坑清单

- 答案列表控件必须支持空态与多条目，禁止把答案区做成多行文本（丢题号元数据）

---

## 12. 遇到歧义时

AI **必须停下并反问**，不得猜测。典型需要反问的情况：

1. 用户未给 `【允许改动的文件】` 白名单
2. 任务要求修改公开接口或 `models.py`
3. 任务要求新增依赖
4. 任务横跨两个 Phase
5. 现有测试失败且原因不明
6. 需要真实 API Key / 真实截图才能验收

反问格式：
```
❓ 需要确认：
1. <问题>
2. <问题>
原因：<为什么必须问>
```

---

## 13. 一句话总结给 AI

> **依赖注入 → Fake 优先 → 测试全绿 → 原子提交 → 只输出答案。**
> 任何一步做不到，就停下来问，不要硬写。
