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
- 开发：`pytest`、`pytest-mock`、`pytest-cov`、`ruff`、`mypy`、`types-pywin32`

除上述列表外禁止新增依赖。Phase 8 之前不得 import PySide6；Phase 9 之前不得 import PyInstaller。

---

## 5. 项目结构与文件职责速查

```
src/examchaiter/
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
│   └─ prompts.py   build_messages / parse_answer
├─ output/
│   ├─ formatter.py to_display_text / to_speech_text
│   └─ presenter.py 控制台打印 + 写剪贴板
├─ tts/speaker.py   Speaker(Protocol) + Pyttsx3Speaker + FakeSpeaker + LoopSpeaker
├─ gui/
│   ├─ __init__.py
│   ├─ main_window.py
│   ├─ tray.py
│   ├─ overlay.py
│   └─ state.py
├─ pipeline.py      ExamPipeline.run_once() -> PipelineResult | None
└─ app.py           ExamChaiTerApp（pynput 热键 + 主循环）
ExamChaiTer.spec（仓库根）
```

**改动前先确认目标文件已存在于上述结构**；不存在说明跨 Phase，需停下反问。

---

## 6. 关键接口契约（不得擅自变更）

```python
# ---- models ----
Answer.qtype: QuestionType           # CHOICE / FILL / SHORT / UNKNOWN
Answer.content: str                  # ← 唯一对外输出，纯答案
PipelineResult.reused: bool          # True = 命中去重，未调 LLM

# ---- pipeline ----
ExamPipeline.run_once(hwnd: int) -> PipelineResult | None

# ---- llm/prompts ----
parse_answer(raw: str) -> Answer     # 任何输入都不抛异常，最差返回 UNKNOWN
build_messages(question_text: str, images: list[bytes] | None = None) -> list[dict]

# ---- tts ----
LoopSpeaker(speaker: Speaker, interval_s: float = 3.0)
    .start(text) / .stop() / .is_running() -> bool

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
    def answer_once(self) -> Answer | None: ...
    def toggle_tts(self) -> bool: ...
```

**GUI 铁律**：GUI 文件内禁止直接 new OpenAICompatClient / RapidOcrEngine / win32gui 等具体实现，全部从 MainWindow.__init__ 注入。

---

## 7. 测试规范

### 7.1 分层
| 目录                | 允许 IO                   | 何时跑                         |
| ------------------- | ------------------------- | ------------------------------ |
| `tests/unit`        | ❌ 无 IO 无网络            | 每次 commit（pre-commit 强制） |
| `tests/integration` | 本地文件/OCR 模型，无网络 | 手动 / CI                      |
| `tests/e2e`         | 真实 API + 真窗口         | 手动，默认跳过                 |

### 7.2 必用 Fixture（定义在 `tests/conftest.py`）
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
| 9     | 打包 exe | ExamChaiTer.spec + scripts/build.ps1 | 产物 ExamChaiTer.exe 双击打开主窗口；无控制台黑框；图标正常 |

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

### Phase 9 打包坑清单

- PySide6 体积：--exclude-module PySide6.QtWebEngine* 等
- rapidocr 模型：--add-data 显式带 rapidocr_onnxruntime/models/*
- pyttsx3：懒加载，失败降级静默
- 热键：Phase 8 起用 Qt QShortcut 取代 pynput
- 控制台黑框：--noconsole / console=False
- 杀软误报：不签名无法根治，告知用户加白名单

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
