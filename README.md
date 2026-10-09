# ExamChaiTer

**状态：Phase 8 完成，GUI 可用。**

ExamChaiTer 是一个 Windows 本地工具：聚焦指定窗口 -> 截图 -> OCR -> 调用
OpenAI 兼容接口 -> 仅输出答案 -> 可选循环语音朗读。

本仓库只用于个人学习、技术验证和自动化流程研究。使用时应遵守考试、平台和目标
应用的规则；不要用于违反授权的场景。

## 环境要求

- Windows 10/11
- Python 3.11
- [uv](https://docs.astral.sh/uv/)
- 可选：OpenAI 兼容服务的 API Key

## 三步跑通

```powershell
# 1. 安装锁定依赖
uv sync

# 2. 创建本地配置，并填写 EXAMCHAITER_LLM_API_KEY
Copy-Item .env.example .env

# 3. 启动常驻热键应用
uv run python -m examchaiter run
```

`.env`、`debug/`、`logs/`、真实考试截图、模型权重和 API Key 都不得提交。

## 热键

| 热键 | 行为 |
| --- | --- |
| `Ctrl+Alt+Q` | 对当前前台窗口作答一次 |
| `Ctrl+Alt+S` | 开始或停止循环朗读最近一次答案 |
| `Ctrl+Alt+X` | 退出常驻应用 |

## CLI 命令

查看当前配置。API Key 始终以 `sk-***` 形式脱敏：

```powershell
uv run python -m examchaiter show-config
```

列出可见顶层窗口，支持正则过滤：

```powershell
uv run python -m examchaiter list-windows --filter "Exam"
```

使用合成图跑离线 OCR 布局 smoke：

```powershell
uv run python -m examchaiter ocr-self-test
```

离线调用提示词与答案解析链路：

```powershell
uv run python -m examchaiter ask "1+1=?"
```

运行一次完整流水线。默认使用 fake 截图、OCR 和 LLM，不联网：

```powershell
uv run python -m examchaiter answer --title "任意"
```

真实链路需要 API Key，并会查找标题匹配的窗口：

```powershell
uv run python -m examchaiter answer --title "Exam" --real
```

演示循环朗读。默认使用 FakeSpeaker：

```powershell
uv run python -m examchaiter speak "测试" --loops 3 --interval 0.05
```

使用 pyttsx3 真实朗读：

```powershell
uv run python -m examchaiter speak "测试" --loops 3 --interval 0.05 --real
```

启动全局热键应用。`--dry-run` 只打印热键绑定，不启动 pynput：

```powershell
uv run python -m examchaiter run --dry-run
uv run python -m examchaiter run
```

启动 PySide6 主窗口与托盘：

```powershell
uv run python -m examchaiter gui --fake
uv run python -m examchaiter gui
```

## 开发

格式化、静态检查和 90% 覆盖率门槛：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/check.ps1
```

单独运行测试：

```powershell
uv run pytest -q
uv run pytest -q -m integration
uv run pytest -q -m e2e
```

`tests/unit` 不访问网络、真实窗口、真实音频设备或真实 LLM。`integration` 与
`e2e` 默认不随普通提交运行，单独运行时不套用 90% 总覆盖率门槛。

## 打包

Phase 9 尚未完成。后续将使用 `ExamChaiTer.spec` 与 `scripts/build.ps1` 构建
无控制台窗口的 `ExamChaiTer.exe`；当前 README 的 exe 步骤只是占位。

## 测试素材

`tests/fixtures/synthetic_question.png` 是合成图，非真实截图，只包含人工生成的
测试文字。重新生成：

```powershell
uv run python tests/fixtures/gen_sample.py
```

## 已知限制

- Phase 9 打包尚未完成。
- pynput 在部分 Windows 环境中需要管理员权限。
- 真实 OCR 模型、真实 LLM、真实 TTS 和真实窗口交互由本地手动联调。
- e2e 默认跳过，仓库不会在测试中发起真实 API 请求。
