# pc-agent-loop

> **全能，且危险；要么解决问题，要么解决掉系统。**

pc-agent-loop 是一个极致简约的 PC 级自主 AI Agent 框架。它通过不到 100 行的核心引擎代码，构筑了对浏览器、终端和文件系统的物理级自动化能力。

## 🚀 核心特性

- **极简设计**: 仅由 7 个原子工具和一个高效的 Agentic Loop 构成。
- **自主代码执行**: 能够根据任务需求自主编写并运行 Python 或 PowerShell 脚本，直接操控系统资源。
- **深度 Web 自动化**: 提供语义化网页扫描与 JS 注入执行，实现精准的浏览器控制。
- **精准文件编辑**: 支持基于源码块匹配的 `file_patch` 功能。
- **人机协作**: 在关键决策点主动请求人类干预。

## 📂 项目结构

- `agent_loop.py`: 核心引擎，负责“感知-思考-行动”的自主循环逻辑。
- `ga.py`: 工具箱，定义了 7 大原子工具的具体实现。
- `agentapp.py`: 基于 Streamlit 构建的交互式 Web 界面。
- `sidercall.py`: LLM 通信层，支持流式输出与 API 调用。

## 🛠️ 如何启动

为了使 Agent 正常工作，你需要进行以下手动配置：

1.  **API Key 设置**: 在 `sidercall.py` 中设置你的 LLM API 访问 Key。
2.  **Session 修改**: 在 `agentapp.py` 的 `init` 方法中，根据需要修改使用的 `LLMSession` 实例。

配置完成后，在项目根目录下执行：
```bash
python launch.pyw
```

## 🧩 7 大核心工具

Agent 仅依靠以下原子工具的组合来完成任务：
`code_run`, `web_scan`, `web_execute_js`, `file_read`, `file_write`, `file_patch`, `ask_user`。

---

### 📝 自动生成说明
**特别说明**：本 `README.md` 文件、项目中的核心 Prompt 以及工具描述（Tools SCHEMA）完全由 Agent 自主生成并迭代优化。

**⚠️ 警告**: 本 Agent 具备执行本地代码和控制操作系统的物理权限。请务必在受信任的环境中运行。