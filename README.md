# ExamChaiTer

**状态：v0.3.5 完成，支持多题识别、按题号顺序朗读、题号级缓存与项目本地存储（exe 打包为实验性，见下方说明）**

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
3. 启动 GUI：`uv run python -m examchaiter gui`（**不需要 Key 即可启动**）
4. 点“配置” → 填 LLM Base URL（含 `/v1`）/ API Key / 模型 → 保存
5. 关闭 GUI，重新启动（配置生效）
6. 下拉框选目标窗口 → 点“作答一次”

请在仓库根目录执行上述命令；默认运行时数据目录基于启动时的工作目录生成。

`.env`、`debug/`、`logs/`、真实考试截图、模型权重和 API Key 都不得提交。

> 仍兼容 `.env`：`config.json` 不存在时会回退到项目根 `.env`。命令行不改也行。

## 界面功能

- 主窗口：窗口选择 / 刷新 / 题目预览 / 答案展示 / 状态栏
- 视觉：主窗口采用 Windows 11 风格浅色主题，支持空态提示、卡片式布局与状态栏中文化
- 配置按钮：可视化编辑 LLM Key、模型、TTS 语速、自动模式节奏
- 历史按钮：查看每场考试记录，支持搜索与删除 session
- 自动模式：勾选后循环识别→作答→朗读，题目变化自动切换，再点停止

## 多题识别

- 一帧内多道题自动拆分（正则可配，默认 4 条规则，见 `split_patterns`）
- 每题独立作答、独立缓存（缓存键 = sha256(题号 + 归一化题干)）
- 自动模式按题号顺序朗读：题 1 N 遍 → 题 2 N 遍 → …
- 多选题答案显示为 `A B D`，朗读为“答案是 A、B、D”

## 配置文件位置

- 默认位置：`.examchaiter/config.json`（与启动时的工作目录同级）
- 可通过环境变量 `EXAMCHAITER_STORAGE_DIR` 覆盖存储目录
- API Key 用 DPAPI 加密（`api_key_enc` 字段）
- `.examchaiter/` 已加入 `.gitignore`，不会误提交

主要配置项：`split_patterns`（拆题正则数组，高级用户可自定义）、`auto_speak_multi_choice_repeat`（多选朗读次数，默认 5）。

## 跨机器部署

- `config.json` 里的 `api_key_enc` 用 Windows DPAPI 加密，**跨机器无法解密**（换机器/重装系统后失效）
- 换机器后启动 GUI，状态栏会提示“未配置 API Key”，GUI 仍可正常打开
- 点“配置”重新填一次 API Key 即可，旧配置的其他字段保留
- 若同时存在项目根 `.env`，解密失败后会自动回落到 `.env` 里的 Key

## 配置优先级

`ConfigStore` 读 API Key 的优先级：

1. `config.json` 里的 `api_key_enc`（DPAPI 解密成功）
2. `config.json` 里的 `llm_api_key`（明文，向后兼容）
3. 环境变量（`EXAMCHAITER_LLM_API_KEY`）
4. `.env` 文件
5. 默认值（无 Key）

`config.json` 里没有的字段（或值为 `null`）不会覆盖低优先级的值，因此 `.env` 里的 Key 不会再被空配置吃掉。

## 历史文件位置

`.examchaiter/sessions/*.json`（汇总在 `.examchaiter/index.json`）。

每条记录含 `question_no`，按题目出现顺序排列（session JSON 为 schema v2 的 `entries` 列表）。

## 从旧版本升级

v0.3.1 及更早版本的数据位于 `%APPDATA%\ExamChaiTer\`。

- 想保留旧数据：手动把 `%APPDATA%\ExamChaiTer\` 下的 `config.json`、`index.json` 和 `sessions/` 复制到项目根的 `.examchaiter/` 下
- 不想保留：直接忽略旧目录，首次启动会在项目根重新生成空的 `.examchaiter/`
- 本版本不读取、不写入、也不删除旧 `%APPDATA%\ExamChaiTer\` 数据

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
