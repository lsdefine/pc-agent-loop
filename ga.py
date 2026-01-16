import sys, os, re
import pyperclip
import json, time
from pathlib import Path
import subprocess
import tempfile
if sys.stdout is None: sys.stdout = open(os.devnull, "w")
if sys.stderr is None: sys.stderr = open(os.devnull, "w")
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sidercall import LLMSession, ToolClient
from agent_loop import BaseHandler, StepOutcome, agent_runner_loop

def code_run(code: str, code_type: str = "python", timeout: int = 60, cwd: str = None):
    """
    针对 Windows 优化的双模态执行器
    python: 运行复杂的 .py 脚本（文件模式）
    powershell: 运行单行指令（命令模式）
    优先使用python，仅在必要系统操作时使用powershell。
    """
    # 统一路径处理
    preview = (code[:60].replace('\n', ' ') + '...') if len(code) > 60 else code.strip()
    yield f"\n[Action] Running {code_type} in {os.path.basename(cwd)}: {preview}\n"
    cwd = cwd or os.getcwd()
    if code_type == "python":
        # Python 依然建议走文件，因为模型生成的逻辑通常包含多行、import 和类定义
        tmp_file = tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode='w', encoding='utf-8')
        tmp_file.write(code)
        tmp_path = tmp_file.name
        tmp_file.close()
        cmd = ["python", "-u", tmp_path]   
    elif code_type == "powershell":
        cmd = ["powershell", "-NoProfile", "-NonInteractive", "-Command", code]
        tmp_path = None
    else:
        return {"status": "error", "msg": f"不支持的类型: {code_type}"}
    print("code run output:") 
    startupinfo = None
    if os.name == 'nt':
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0 # SW_HIDE
    full_stdout = []
    full_stderr = []
    try:
        process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            bufsize=0, cwd=cwd, startupinfo=startupinfo
        )
        for line_bytes in iter(process.stdout.readline, b''):
            try:
                line = line_bytes.decode('utf-8')
            except UnicodeDecodeError:
                line = line_bytes.decode('gbk', errors='ignore')
            print(line, end="") 
            full_stdout.append(line)

        stdout_rem, stderr_raw = process.communicate(timeout=timeout)
        if stdout_rem:
            try: rem_str = stdout_rem.decode('utf-8')
            except UnicodeDecodeError:
                rem_str = stdout_rem.decode('gbk', errors='ignore')
            full_stdout.append(rem_str)
            
        if stderr_raw:
            try: stderr_str = stderr_raw.decode('utf-8')
            except UnicodeDecodeError:
                stderr_str = stderr_raw.decode('gbk', errors='ignore')
            full_stderr.append(stderr_str)
            print(f"Error: {stderr_str}")
       
        status = "success" if process.returncode == 0 else "error"
        stdout_str = "".join(full_stdout)
        stderr_str = "".join(full_stderr)
        status_icon = "✅" if process.returncode == 0 else "❌"
        output_snippet = (stdout_str[:200] + '...') if len(stdout_str) > 200 else stdout_str
        yield f"[Status] {status_icon} Exit Code: {process.returncode}\n[Stdout] {output_snippet}\n"
        return {
            "status": status,
            "stdout": stdout_str[-2000:],
            "stderr": stderr_str[-2000:],
            "exit_code": process.returncode
        }
    except subprocess.TimeoutExpired:
        return {"status": "error", "msg": "Timeout"}
    except Exception as e:
        return {"status": "error", "msg": str(e)}
    finally:
        if code_type == "python" and tmp_path and os.path.exists(tmp_path): os.remove(tmp_path)


def ask_user(question: str, candidates: list = None):
    """
    构造一个中断请求。
    question: 向用户提出的问题。
    candidates: 可选的候选项列表。
    需要保证should_exit为True
    """
    return {
        "status": "INTERRUPT",
        "intent": "HUMAN_INTERVENTION",
        "data": {
            "question": question,
            "candidates": candidates or []
        }
    }

from web_tools import execute_js_rich, get_html

driver = None

def first_init_driver():
    global driver
    from TMWebDriver import TMWebDriver
    driver = TMWebDriver()
    while True:
        time.sleep(1)
        sess = driver.get_all_sessions()
        if len(sess) > 0: break
    driver.newtab()
    time.sleep(5)

def web_scan(focus_item="", switch_tab_id=None):
    """
    利用 get_html 获取清洗后的网页内容。
    focus_item: 语义过滤指令。如果用户在找特定内容（如“小米汽车”），
                       算法会优先保留包含该关键词的列表项。
    switch_tab_id: 可选参数，如果提供，则在扫描前切换到该标签页。
    应当多用execute_js，少全量观察html。
    """
    global driver
    if driver is None: first_init_driver()
    try:
        tabs = []
        for sess in driver.get_all_sessions(): 
            sess.pop('connected_at', None)
            sess.pop('type', None)
            sess['url'] = sess.get('url', '')[:50] + ("..." if len(sess.get('url', '')) > 50 else "")
            tabs.append(sess)
        if switch_tab_id: driver.default_session_id = switch_tab_id
        content = get_html(driver, cutlist=True, instruction=focus_item, maxchars=23000)
        return {
            "status": "success",
            "metadata": {
                "tabs_count": len(tabs),
                "tabs": tabs,
                "active_tab": driver.default_session_id
            },
            "content": content
        }
    except Exception as e:
        return {"status": "error", "msg": format_error(e)}
    
import traceback
def format_error(e):
    exc_type, exc_value, exc_traceback = sys.exc_info()
    tb = traceback.extract_tb(exc_traceback)
    if tb:
        f = tb[-1]
        fname = os.path.basename(f.filename)
        return f"{exc_type.__name__}: {str(e)} @ {fname}:{f.lineno}, {f.name} -> `{f.line}`"
    return f"{exc_type.__name__}: {str(e)}"

def web_execute_js(script: str):
    """
    执行 JS 脚本来控制浏览器，并捕获结果和页面变化。
    script: 要执行的 JavaScript 代码字符串。
    return {
        "status": "failed" if error_msg else "success",
        "js_return": result,
        "error": error_msg,
        "transients": transients, 
        "environment": {
            "new_tab": new_tab,
            "reloaded": reloaded
        },
        "diff": diff_summary,
        "suggestion": "" if is_significant_change else "页面无明显变化"
    }
    """
    global driver
    if driver is None: first_init_driver()
    try:
        result = execute_js_rich(script, driver)
        return result
    except Exception as e:
        return {"status": "error", "msg": format_error(e)}
    
def file_patch(path: str, old_content: str, new_content: str):
    """
    在文件中寻找唯一的 old_content 块并替换为 new_content。
    """
    path = str(Path(path).resolve())
    try:
        if not os.path.exists(path):
            return {"status": "error", "msg": "文件不存在"}
        with open(path, 'r', encoding='utf-8') as f:
            full_text = f.read()
        # 检查唯一性
        count = full_text.count(old_content)
        if count == 0:
            return {"status": "error", "msg": "未找到匹配的旧文本块，请检查空格、缩进和换行是否完全一致。"}
        if count > 1:
            return {"status": "error", "msg": f"找到 {count} 处匹配，请提供更长的旧文本块以确保唯一性。"}
        updated_text = full_text.replace(old_content, new_content)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(updated_text)
        return {"status": "success", "msg": "文件局部修改成功"}
    except Exception as e:
        return {"status": "error", "msg": str(e)}

def file_read(path, start=1, count=100, show_linenos=True):
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
        chunk = lines[start-1 : start-1+count]
        if show_linenos: res = [f"{i+start}|{l[:200]}" for i, l in enumerate(chunk)]
        else: res = [l for l in chunk]
        return f"Total:{len(lines)} lines\n" + "".join(res)
    except Exception as e:
        return f"Error: {str(e)}"

class GenericAgentHandler(BaseHandler):
    '''
    Generic Agent 工具库，包含多种工具的实现。工具函数自动加上了 do_ 前缀。实际工具名没有前缀。
    '''
    def __init__(self, parent, user_input, cwd):
        self.parent = parent
        self.user_input = user_input
        self.plan = ""
        self.focus = ""
        self.cwd = cwd

    def _get_abs_path(self, path):
        if not path: return ""
        return os.path.abspath(os.path.join(self.cwd, path))

    def do_code_run(self, args, response):
        '''执行代码片段，有长度限制，不允许代码中放大量数据，如有需要应当通过文件读取进行。
        '''
        code_type = args.get("type", "python")
        # 从 response.content 中提取代码块
        # 匹配 ```python ... ``` 或 ```powershell ... ```
        pattern = rf"```{code_type}\n(.*?)\n```"
        # 也可以更通用一点，不分类型提取最后一个代码块：rf"```(?:{code_type})?\n(.*?)\n```"
        matches = re.findall(pattern, response.content, re.DOTALL)
        if not matches:
            return StepOutcome(None, next_prompt=f"【系统错误】：你调用了 code_run，但未在回复中提供 ```{code_type} 代码块。请重新输出代码并附带工具调用。")       
        # 提取最后一个代码块（通常是模型修正后的最终逻辑）
        code = matches[-1].strip()
        timeout = args.get("timeout", 60)
        cwd = args.get("cwd", self.cwd)
        result = yield from code_run(code, code_type, timeout, cwd)
        return StepOutcome(result, next_prompt=self._get_anchor_prompt())
    
    def do_ask_user(self, args, response):
        question = args.get("question", "请提供输入：")
        candidates = args.get("candidates", [])
        result = ask_user(question, candidates)
        return StepOutcome(result, next_prompt="", should_exit=True)
    
    def do_web_scan(self, args, response):
        '''focus_item仅用于在长列表中模糊搜寻相关item
        此工具也提供标签页查看和标签页切换功能。
        '''
        focus_item = args.get("focus_item", "")
        switch_tab_id = args.get("switch_tab_id", None)
        result = web_scan(focus_item, switch_tab_id=switch_tab_id)
        content = result.pop("content", None) 
        yield f'\n{str(result)}\n'
        next_prompt = f"```html\n{content}\n```"
        return StepOutcome(result, next_prompt=next_prompt)
    
    def do_web_execute_js(self, args, response):
        '''web情况下的优先使用工具，执行任何js达成对浏览器的*完全*控制。
        支持将结果保存到文件供后续读取分析，但保存功能仅限即时读取，与await等异步操作不兼容。
        '''
        script = args.get("script", "")
        save_to_file = args.get("save_to_file", "")
        result = web_execute_js(script)
        if save_to_file and "js_return" in result:
            content = str(result["js_return"] or '')
            abs_path = self._get_abs_path(save_to_file)
            with open(abs_path, 'w', encoding='utf-8') as f: f.write(str(content))
            result["js_return"] = content[:200] + ("..." if len(content) > 200 else "")
            result["js_return"] += f"\n\n[已保存以上内容到 {abs_path}]"
        print("Web Execute JS Result:", result)
        return StepOutcome(result, next_prompt=self._get_anchor_prompt())
    
    def do_file_patch(self, args, response):
        path = self._get_abs_path(args.get("path", ""))
        yield f"\n[Action] Patching file: {path}\n"
        old_content = args.get("old_content", "")
        new_content = args.get("new_content", "")
        result = file_patch(path, old_content, new_content)
        yield str(result) + "\n"
        return StepOutcome(result, next_prompt=self._get_anchor_prompt())
    
    def do_file_write(self, args, response):
        '''用于对整个文件的大量处理，精细修改要用file_patch。
        '''
        path = self._get_abs_path(args.get("path", ""))
        mode = args.get("mode", "overwrite") 
        action_str = "Appending to" if mode == "append" else "Writing"
        yield f"\n[Action] {action_str} file: {os.path.basename(path)}\n"

        def extract_intended_block(content):
            start_marker = "```"
            first_idx = content.find(start_marker)
            last_idx = content.rfind(start_marker)
            if first_idx == -1 or last_idx == -1 or first_idx == last_idx:
                return None
            header_end = content.find("\n", first_idx)
            if header_end == -1 or header_end > last_idx:
                return None
            actual_content = content[header_end + 1 : last_idx].strip()
            return actual_content
        
        blocks = extract_intended_block(response.content)
        if not blocks:
            yield f"[Status] ❌ 失败: 未在回复中找到代码块内容\n"
            return StepOutcome({"status": "error", "msg": "No code block found in response"}, next_prompt="\n")
        new_content = blocks
        try:
            write_mode = 'a' if mode == "append" else 'w'
            final_content = ("\n" + new_content) if mode == "append" else new_content
            with open(path, write_mode, encoding="utf-8") as f:
                f.write(final_content)
            yield f"[Status] ✅ {mode.capitalize()} 成功 ({len(new_content)} bytes)\n"
            return StepOutcome({"status": "success"}, 
                               next_prompt=f"\n提醒: <user_input>{self.user_input}</user_input>请继续执行下一步。\n")
        except Exception as e:
            yield f"[Status] ❌ 写入异常: {str(e)}\n"
            return StepOutcome({"status": "error", "msg": str(e)}, next_prompt="\n")
        
    def do_file_read(self, args, response):
        path = self._get_abs_path(args.get("path", ""))
        yield f"\n[Action] Reading file: {path}\n"
        start = args.get("start", 1)
        count = args.get("count", 100)
        show_linenos = args.get("show_linenos", True)
        result = file_read(path, start, count, show_linenos)
        return StepOutcome(result, next_prompt=self._get_anchor_prompt())
    
    def do_update_plan(self, args, response):
        '''
        同步宏观任务进度与战略重心。       
        【设计意图】：
        1. 仅在任务涉及多步逻辑（如：先搜索、再重构、后测试）时进行初始拆解。
        2. 仅在发生重大的方针变更时调用（例如：原定方案 A 物理不可行，需彻底转向方案 B）。
        3. 严禁用于记录细微的调试步骤或代码纠错。
        简单任务无需使用。
        '''
        new_plan = args.get("plan", "")
        new_focus = args.get("focus", "")
        if new_plan: self.plan = new_plan
        if new_focus: self.focus = new_focus
        yield f"\n[Info] Updated plan and focus.\n"
        yield f"New Plan:\n{self.plan}\n\n"
        yield f"New Focus:\n{self.focus}\n"
        return StepOutcome({"status": "success"}, 
                           next_prompt=self._get_anchor_prompt())

    def do_no_tool(self, args, response):
        '''这是一个特殊工具，由引擎自主调用，不要包含在TOOLS_SCHEMA里。
        '''
        yield "\n\n[Info] No tool called. Final response to user.\n"
        return StepOutcome(response, next_prompt=None, should_exit=True)
    
    def _get_anchor_prompt(self):
        prompt = f"\n提醒: \n<user_input>{self.user_input}</user_input>\n"
        if self.plan: prompt += f"<plan>\n{self.plan}\n</plan>\n"
        if self.focus: prompt += f"<current>\n{self.focus}\n</current>\n"
        prompt += "\n请继续执行下一步。"
        return prompt


if __name__ == "__main__":
    pass