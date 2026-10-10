# ExamChaiTer

**状态：v0.2.0 Phase 11 完成，AutoPilot 引擎就绪（exe 打包为实验性，见下方说明）**

ExamChaiTer 是一个 Windows 本地工具：聚焦指定窗口 -> 截图 -> OCR -> 调用
OpenAI 兼容接口 -> 仅输出答案 -> 可选循环语音朗读。

本仓库只用于个人学习、技术验证和自动化流程研究。使用时应遵守考试、平台和目标
应用的规则；不要用于违反授权的场景。

## 环境要求

- Windows 10/11
- Python 3.11
- [uv](https://docs.astral.sh/uv/)
- 可选：OpenAI 兼容服务的 API Key

## 快速开始

1. 克隆仓库：`git clone <仓库地址> && cd ExamChaiTer`
2. 安装锁定依赖：`uv sync`
3. 创建本地配置，并填写 `EXAMCHAITER_LLM_API_KEY`：`copy .env.example .env`
4. 启动推荐 GUI：`uv run python -m examchaiter gui`

`.env`、`debug/`、`logs/`、真实考试截图、模型权重和 API Key 都不得提交。

## 推荐启动方式

```powershell
# 方式一（推荐）：GUI
uv run python -m examchaiter gui

# 方式二（常驻热键）
uv run python -m examchaiter run

# 方式三（CLI 单次作答）
uv run python -m examchaiter answer --title "窗口标题" --real
```

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

## 测试素材

`tests/fixtures/synthetic_question.png` 是合成图，非真实截图，只包含人工生成的
测试文字。重新生成：

```powershell
uv run python tests/fixtures/gen_sample.py
```

## 已知限制

- Phase 9 已完成：`dist/ExamChaiTer.exe` 可用，但需自备 LLM API Key。
- pynput 在部分 Windows 环境中需要管理员权限。
- 真实 OCR 模型、真实 LLM、真实 TTS 和真实窗口交互由本地手动联调。
- e2e 默认跳过，仓库不会在测试中发起真实 API 请求。
- exe 打包为实验性，未作为 MVP 验收路径

## 打包为 exe（实验性，可能失败）

本阶段 PySide6 onefile 打包在部分环境报 "DLL load failed while importing QtWidgets"。
若你不需要单文件分发，直接用上面的命令启动即可。若坚持打包，建议改用 onedir 模式（spec 里去掉 onefile）。

1. 安装依赖后执行 `powershell -ExecutionPolicy Bypass -File scripts/build.ps1`。
2. 产物位于 `dist/ExamChaiTer.exe`。
3. onefile 首次启动需解压 5~10 秒，之后正常。
4. 建议右键“以管理员身份运行”，否则 `Ctrl+Alt+Q/S/X` 可能无法注册。
5. 杀软可能误报；加入白名单即可，未签名无法根治。
6. 双击启动后默认打开 GUI 主窗口。

项目使用 `ExamChaiTer.spec` 构建无控制台窗口的单文件 `ExamChaiTer.exe`。
构建完成后可用 `scripts/verify_exe.py` 做本机存活冒烟；该脚本不进入 CI。
