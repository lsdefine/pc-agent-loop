# GenericAgent — 3,300 Lines to Full OS Autonomy

[English](#english) | [中文](#chinese)

<a name="english"></a>

A minimalist autonomous agent framework that gives any LLM physical-level control over your PC — browser, terminal, file system, keyboard, mouse, screen vision, and mobile devices — in ~3,300 lines of Python.

No Electron. No Docker. No Mac Mini. No 500K-line codebase. No paid installation service.

## What Happens When You Use It

```
You: "Read my WeChat messages"
Agent: installs dependencies → reverse-engineers DB → writes reader script → saves as SOP
Next time: instant recall, zero setup.

You: "Monitor stock prices and alert me"
Agent: installs mootdx → builds screening workflow → sets up scheduled task → saves as SOP
Next time: one sentence to run.

You: "Send this file via Gmail"
Agent: configures OAuth → writes send script → saves as SOP
Next time: just works.
```

**Dogfooding**: This repository — from installing Git to `git init`, writing this README, to every commit message — was built entirely by GenericAgent without the author opening a terminal once.

Every task the agent solves becomes a permanent skill. After a few weeks, your instance has a unique skill tree — grown entirely from 3,300 lines of seed code.

## The Seed Philosophy

Most agent frameworks ship as finished products. GenericAgent ships as a **seed**.

The 5 core SOPs define how the agent thinks, remembers, and operates. From there, every new capability is discovered and recorded by the agent itself:

1. You ask it to do something new
2. It figures out how (install dependencies, write scripts, test)
3. It saves the procedure as a new SOP in its memory
4. Next time, it recalls and executes directly

The agent doesn't just execute — it **learns and remembers**.

## Quick Start

```bash
# 1. Clone
git clone https://github.com/lsdefine/pc-agent-loop.git
cd pc-agent-loop

# 2. Install minimal deps
pip install streamlit pywebview

# 3. Configure API key
cp mykey_template.py mykey.py
# Edit mykey.py with your LLM API key

# 4. Launch
python launch.pyw
```

Once running, tell the agent: *"Execute web setup SOP to unlock browser tools"* — it handles the rest. See [WELCOME_NEW_USER.md](WELCOME_NEW_USER.md) for the full bootstrap sequence.

## vs. Alternatives

| | GenericAgent | OpenClaw | Claude Code |
|---|---|---|---|
| Codebase | ~3,300 lines | ~530,000 lines | Open-source (large) |
| Deploy | `pip install` + API key | Multi-service orchestration | CLI + subscription |
| Browser | Injects into real browser (keeps login state) | Sandboxed/headless | Via MCP plugins |
| OS Control | Keyboard, mouse, vision, ADB | Multi-agent delegation | File + terminal |
| Self-evolution | Grows SOPs & tools autonomously | Plugin ecosystem | Stateless per session |
| Core shipped | 10 .py + 5 SOPs | Hundreds of modules | Rich CLI toolkit |

## How It Works

```
User instruction
      ↓
┌─────────────────────┐
│  agent_loop.py (92L) │  ← Sense-Think-Act cycle
│  "What do I know?    │
│   What should I do?" │
└────────┬────────────┘
         ↓
┌─────────────────────┐
│  7 Atomic Tools      │  ← All capabilities derive from these
│  code_run            │     Execute any Python/PowerShell
│  file_read/write     │     Direct disk access
│  file_patch          │     Surgical code edits
│  web_scan            │     Read live web pages
│  web_execute_js      │     Control browser DOM
│  ask_user            │     Human-in-the-loop
└────────┬────────────┘
         ↓
┌─────────────────────┐
│  Memory System       │  ← Persistent across sessions
│  L0: Meta-SOP        │     How to manage memory itself
│  L2: Global Facts    │     Environment, credentials, paths
│  L3: Task SOPs       │     Learned procedures (self-growing)
└─────────────────────┘
```

The agent starts with 7 primitive tools. Through `code_run`, it can install packages, write scripts, and interface with any hardware or API — effectively manufacturing new tools at runtime.

<details>
<summary>What Ships in the Box</summary>

**Core engine** (runs the agent):
- `agent_loop.py` — Sense-Think-Act loop (92 lines)
- `ga.py` — Tool definitions and execution
- `sidercall.py` — LLM communication (multi-backend)
- `agentmain.py` — Session orchestration

**Interface** (talk to the agent):
- `stapp.py` — Streamlit web UI
- `tgapp.py` — Telegram bot interface
- `launch.pyw` — One-click launcher with floating window

**Infrastructure**:
- `TMWebDriver.py` — Browser injection bridge (not Selenium — injects JS into your real browser via Tampermonkey)
- `simphtml.py` — HTML→text cleaner for web perception

**5 Core SOPs** (shipped, version-controlled):
1. `memory_management_sop` — L0 constitution: how the agent manages its own memory
2. `autonomous_operation_sop` — Self-directed task execution
3. `scheduled_task_sop` — Cron-like recurring tasks
4. `web_setup_sop` — Browser environment bootstrap
5. `ljqCtrl_sop` — Desktop physical control (keyboard, mouse, DPI-aware)

Everything else — Gmail integration, WeChat automation, vision APIs, game downloaders, stock analysis workflows — the agent builds and memorizes on its own through use.

</details>

---

<a name="chinese"></a>

# GenericAgent — 3,300 行代码，完整 OS 级自主控制

一个极简自主 Agent 框架。用约 3,300 行 Python，让任意 LLM 获得对你 PC 的物理级控制能力——浏览器、终端、文件系统、键鼠、屏幕视觉、移动设备。

不需要 Electron，不需要 Docker，不需要 Mac Mini，不需要 53 万行代码，不需要付费安装服务。

## 用起来是什么样的

```
你："帮我读取微信消息"
Agent：安装依赖 → 逆向数据库 → 写读取脚本 → 保存为 SOP
下次：一句话直接调用，零配置。

你："帮我监控股票并提醒"
Agent：安装 mootdx → 构建选股工作流 → 设置定时任务 → 保存为 SOP
下次：一句话启动。

你："用 Gmail 发这个文件"
Agent：配置 OAuth → 写发送脚本 → 保存为 SOP
下次：直接能用。
```

**自举实证**：本仓库从安装 Git、`git init`、编写 README 到每一条 commit message，全程由 GenericAgent 完成——作者没有打开过一次终端。

每个解决过的任务都会变成永久技能。用几周后，你的 Agent 实例会拥有一套独特的技能树——全部从 3,300 行种子代码中生长出来。

## 自举哲学

多数 Agent 框架以成品形态发布。GenericAgent 以**种子**形态发布。

5 个核心 SOP 定义了 Agent 如何思考、记忆和行动。之后的一切能力，由 Agent 在使用中自主发现并记录：

1. 你让它做一件新事
2. 它自己摸索方法（安装依赖、写脚本、测试）
3. 把流程保存为新 SOP
4. 下次直接调用

Agent 不只是执行——它**学习并记忆**。

## 快速开始

```bash
# 1. 克隆
git clone https://github.com/lsdefine/pc-agent-loop.git
cd pc-agent-loop

# 2. 安装最小依赖
pip install streamlit pywebview

# 3. 配置 API Key
cp mykey_template.py mykey.py
# 编辑 mykey.py 填入你的 LLM API Key

# 4. 启动
python launch.pyw
```

启动后告诉 Agent："执行 web setup SOP 解锁浏览器工具"——剩下的它自己搞定。完整引导流程见 [WELCOME_NEW_USER.md](WELCOME_NEW_USER.md)。

## 对比

| | GenericAgent | OpenClaw | Claude Code |
|---|---|---|---|
| 代码量 | ~3,300 行 | ~530,000 行 | 已开源（体量大） |
| 部署 | `pip install` + API key | 多服务编排 | CLI + 订阅 |
| 浏览器 | 注入真实浏览器（保留登录态） | 沙箱/无头浏览器 | 通过 MCP 插件 |
| OS 控制 | 键鼠、视觉、ADB | 多 Agent 委派 | 文件 + 终端 |
| 自我进化 | 自主生长 SOP 和工具 | 插件生态 | 会话间无状态 |
| 出厂配置 | 10 个 .py + 5 个 SOP | 数百模块 | 丰富 CLI 工具集 |

## 工作原理

Agent 拥有 7 个原子工具：`code_run`（执行任意代码）、`file_read/write/patch`（文件操作）、`web_scan`（网页感知）、`web_execute_js`（浏览器控制）、`ask_user`（人机协作）。

通过 `code_run`，它可以安装任何包、编写任何脚本、对接任何硬件——相当于在运行时制造新工具。学到的流程保存为 SOP，下次直接调用。

核心循环只有 92 行（`agent_loop.py`）：感知 → 思考 → 行动 → 记忆。

<details>
<summary>出厂清单</summary>

**核心引擎**：
- `agent_loop.py` — 感知-思考-行动循环（92 行）
- `ga.py` — 工具定义与执行
- `sidercall.py` — LLM 通信（多后端）
- `agentmain.py` — 会话编排

**交互界面**：
- `stapp.py` — Streamlit Web UI
- `tgapp.py` — Telegram 机器人
- `launch.pyw` — 一键启动 + 悬浮窗

**基础设施**：
- `TMWebDriver.py` — 浏览器注入桥接（非 Selenium，通过 Tampermonkey 注入真实浏览器）
- `simphtml.py` — HTML→文本清洗

**5 个核心 SOP**（出厂自带，版本控制）：
1. `memory_management_sop` — L0 宪法：Agent 如何管理自身记忆
2. `autonomous_operation_sop` — 自主任务执行
3. `scheduled_task_sop` — 定时任务
4. `web_setup_sop` — 浏览器环境引导
5. `ljqCtrl_sop` — 桌面物理控制（键鼠、DPI 感知）

其余一切——Gmail、微信自动化、视觉 API、游戏下载、股票分析——都是 Agent 在使用中自主构建并记忆的。

</details>

## 许可

MIT