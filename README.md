# pc-agent-loop

pc-agent-loop 是一个**极致简约**的 PC 级自主 AI Agent 框架。它通过不到 100 行的核心代码和约 200 行的工具实现，构筑了把整个pc给它（浏览器、终端、文件系统）的物理级自动化能力。

## 🚀 核心特性

- **极简设计**: 仅由 **7 个基本工具** 和一个高效的 **Agentic Loop** 构成，拒绝过度设计。
- **自主代码执行 (Code Execution)**: 能够根据任务需求自主编写并运行 Python 或 PowerShell 脚本，直接操控系统资源。
- **深度 Web 自动化 (Advanced Web Automation)**: 
    - **语义化扫描**: 自动清洗 HTML 内容，将复杂的 DOM 转化为 AI 易读的结构。
    - **JS 注入执行**: 在浏览器上下文中执行自定义 JavaScript，实现精准点击、滚动或数据抓取。
    - **TMWebDriver**: 支持通过 Tampermonkey 实现的持久化会话驱动。
- **精准文件编辑 (Smart File Patching)**: 并非盲目覆盖，而是支持通过 `file_patch` 以代码块匹配方式进行精确修改。
- **人机协作模式 (Human-in-the-loop)**: 在遇到验证码、关键权限或模糊决策时，主动请求用户介入。

## 📂 项目结构

- `agent_loop.py`: **核心引擎**，负责“感知-思考-行动”的自主循环逻辑。
- `ga.py`: **工具箱**，定义了 7 大核心原子工具的具体实现。
- `agentapp.py`: 基于 Streamlit 构建的轻量化交互式 Web 界面。
- `sidercall.py`: LLM 通信层，支持流式输出与 API 调用。
- `TMWebDriver.py`: 浏览器驱动模块（需配合 Tampermonkey 脚本使用）。

## 🛠️ 快速开始

### 1. 环境准备
- 安装 Python 3.8+。
- （可选）若需网页自动化，请在浏览器中安装 **Tampermonkey** 插件并导入本项目提供的对应脚本。

### 2. 安装依赖
缺啥装啥

### 3. 启动应用
在项目根目录下执行：
```bash
python launch.pyw
```

## 🧩 7 大核心工具

Agent 仅依靠以下 7 个原子工具的组合来完成复杂任务：

1.  **`code_run`**: 针对 Windows 优化的双模态代码执行器（Python/PowerShell）。
2.  **`web_scan`**: 获取网页清洗后的语义化 HTML 结构，支持多标签管理。
3.  **`web_execute_js`**: 网页 JS 脚本注入，支持将结果存盘分析。
4.  **`file_read`**: 分页式文件读取，支持行号定位。
5.  **`file_write`**: 文件全量写入或追加。
6.  **`file_patch`**: 基于源码块匹配的精准局部修改，确保缩进一致性。
7.  **`ask_user`**: 关键节点请求人类干预。

---
**⚠️ 警告**: 本 Agent 具备执行本地代码和控制操作系统的物理权限。请务必在受信任的环境中运行，并在运行前仔细检查 Agent 的执行意图。