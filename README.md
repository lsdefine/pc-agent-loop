# PC-Agent-Loop: High-Performance Autonomous PC Controller

[English](#english) | [中文说明](#chinese)

<a name="english"></a>

PC-Agent-Loop is a minimalist yet powerful autonomous agent framework designed to bridge Large Language Models with direct OS-level execution. Unlike traditional chatbots, it possesses "physical" agency—the ability to perceive its environment, reason about complex goals, and execute multi-step operations across the file system, browsers, and local applications.

## 🚀 Evolutionary Intelligence & Extensibility

This agent is not limited to a fixed set of features. Its true power lies in its ability to **autonomously discover environment-specific capabilities** and **manufacture its own tools**:

- **Self-Discovery via Long-Term Memory**: 
  - The agent maintains a "Global Memory" (L2 Facts) to store system paths, credentials, and environmental status.
  - It can autonomously retrieve context-aware SOPs (Standard Operating Procedures) to handle specialized tasks like WeChat database decryption or Gmail API operations.
- **Dynamic Tool Manufacturing**:
  - Through `code_run`, the agent can write and execute arbitrary Python scripts to interface with new hardware or software.
  - Examples of self-integrated capabilities include:
    - **Deep Web Interaction**: JS injection via Tampermonkey for UI automation.
    - **Digital Forensics**: Querying SQLCipher-encrypted databases (e.g., WeChat v4.0+).
    - **Vision-Driven Logic**: Understanding UI states through local vision APIs (`ask_vision`).
    - **System Indexing**: Utilizing **Everything CLI (es.exe)** for instant file discovery across the entire OS.
    - **Android Automation**: ADB-based control for mobile device interaction.

## 📂 Project Architecture

- `agent_loop.py`: The core "Sense-Think-Act" engine (under 100 lines) driving the autonomous cycle.
- `ga.py`: The fundamental atomic toolset (File, Web, Code, User interaction).
- `agentapp.py` & `launch.pyw`: A Streamlit-based graphical interface and persistent launcher.
- `sidercall.py`: Robust LLM session management supporting multiple backends and model switching.

## 🛠️ Usage Examples

### 1. Autonomous Environment Adaptation
"Scan my local memory for recent SOPs regarding mail processing, then find and download my latest reimbursement receipts from Gmail."

### 2. Complex Multi-Step Automation
"Locate the WeChat database, decrypt it to find messages about 'Project X', and summarize the findings into a PDF report."

### 3. Real-Time System Intervention
"Monitor my cloud dashboard via the browser; if the status turns red, execute a local PowerShell script to restart the service and notify me."

## 🧩 Atomic Toolset (The Primitives)

The agent achieves high-level goals by orchestrating these 7 primitive actions:
1. `code_run`: The ultimate "Swiss Army Knife" for executing Python/PowerShell.
2. `web_scan`: Semantic perception of live web pages and tabs.
3. `web_execute_js`: Direct physical interaction with web DOM elements.
4. `file_read` & `file_write`: Direct disk access and file management.
5. `file_patch`: Safe, block-level code modification to evolve its own scripts.
6. `ask_user`: Bridging the gap for human decision-making or sensitive credentials.
7. `conclude_and_reflect`: The mechanism for distilling experiences into long-term memory.

---

<a name="chinese"></a>

# PC-Agent-Loop: 高性能 PC 级自主 AI Agent

pc-agent-loop 是一个极致简约的 PC 级自主 AI Agent 框架。它通过不到 100 行的核心引擎代码，构筑了对浏览器、终端和文件系统的物理级自动化能力。

## 🚀 进化智能与扩展性

本 Agent 不局限于预设功能。其核心优势在于能够**自主发现环境特定能力**并**制造属于自己的工具**：

- **基于长期记忆的自我发现**: 
  - Agent 维护“全局记忆”（L2 Facts）以存储系统路径、凭据和环境状态。
  - 能够自主检索上下文相关的 SOP（标准作业程序），以处理微信数据库解密、Gmail API 操作等专业任务。
- **动态工具制造**:
  - 通过 `code_run`，Agent 可以编写并执行 Python/PowerShell 脚本来对接新硬件或软件。
  - **自集成能力示例**:
    - **深度 Web 自动化**: 通过 Tampermonkey 进行 JS 注入实现 UI 自动化。
    - **数字取证**: 查询 SQLCipher 加密的数据库（如微信 v4.0+）。
    - **视觉驱动逻辑**: 通过本地视觉 API (`ask_vision`) 理解 UI 状态。
    - **系统全盘索引**: 利用 **Everything CLI (es.exe)** 实现毫秒级文件检索。
    - **安卓自动化**: 基于 ADB 控制移动设备交互。

## 📂 项目结构

- `agent_loop.py`: 核心引擎，负责“感知-思考-行动”的自主循环逻辑。
- `ga.py`: 工具箱，定义了原子工具的具体实现。
- `agentapp.py` & `launch.pyw`: 基于 Streamlit 的交互界面与持久化启动器。
- `sidercall.py`: LLM 通信层，支持多后端切换。

## 🛠️ 典型使用场景

1. **环境自适应**: “扫描我的本地记忆寻找邮件处理 SOP，然后从 Gmail 下载最新的报销收据。”
2. **跨模块协作**: “定位微信数据库并解密，查找关于‘项目 X’的消息，并汇总成 PDF 报告。”
3. **系统干预**: “监控云端控制台，若状态异常则执行本地脚本重启服务并邮件通知我。”

## 🧩 7 大核心原子工具

1. `code_run`: 终极工具，执行 Python/PowerShell 脚本。
2. `web_scan`: 网页与标签页的语义化感知。
3. `web_execute_js`: 物理级网页操控（点击、滚动、数据提取）。
4. `file_read` & `file_write`: 磁盘文件直接访问。
5. `file_patch`: 安全的源码级局部修改。
6. `ask_user`: 关键决策或凭据输入时的人机协作。
7. `conclude_and_reflect`: 将执行经验提炼进长期记忆的机制。

## ⚠️ 警告
本 Agent 具备执行本地代码和控制操作系统的**物理权限**。请务必在受信任的环境中运行。

---
*Note: This README was autonomously generated and refined by the Agent.*