# Web 工具链初始化执行 SOP (精简版)

若web_scan和web_execute_js已测试可用，无需进行此sop。
此sop仅供初始安装时，code_run可用但web工具第一次配置使用。

## 目标
在仅具备系统级权限时，引导用户建立 Web 交互能力。

## 阶段一：引导安装 (Action: code_run)
1.  **启动导航**：使用 PowerShell 启动 Chrome 并直达测试版页面：
    `start chrome "https://chromewebstore.google.com/detail/%E7%AF%A1%E6%94%B9%E7%8C%B4%E6%B5%8B%E8%AF%95%E7%89%88/gcalenpjmijncebpfijmoaglllgpjagf"`

## 阶段二：脚本分发 (Action: file_read + code_run)
1.  **资源提取与写入**：使用 Python 读取 `../assets/ljq_web_driver.user.js` 并通过 `pyperclip` 写入系统剪贴板。
2.  **用户交互指令**：通知用户“脚本已入剪贴板”，请求用户在插件中完成【新建-全选-粘贴-保存】操作。

## 阶段三：环境确认 (Action: code_run)
1.  **切换驱动**：尝试调用 `web_scan` 或注入 JS 进行心跳检测，确认 `ljq_web_driver.user.js` 是否已在目标域生效。
