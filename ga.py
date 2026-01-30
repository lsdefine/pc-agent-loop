import sys, os, re, json, time, pyperclip, threading
from pathlib import Path
import tempfile, traceback, subprocess, itertools, collections
if sys.stdout is None: sys.stdout = open(os.devnull, "w")
if sys.stderr is None: sys.stderr = open(os.devnull, "w")
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agent_loop import BaseHandler, StepOutcome, try_call_generator

def code_run(code: str, code_type: str = "python", timeout: int = 60, cwd: str = None):
    """
    针对 Windows 优化的双模态执行器
    python: 运行复杂的 .py 脚本（文件模式）
    powershell: 运行单行指令（命令模式）
    优先使用python，仅在必要系统操作时使用powershell。
    """
    preview = (code[:60].replace('\n', ' ') + '...') if len(code) > 60 else code.strip()
    yield f"[Action] Running {code_type} in {os.path.basename(cwd)}: {preview}\n"
    cwd = cwd or os.path.join(os.getcwd(), 'temp'); tmp_path = None
    if code_type == "python":
        tmp_file = tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode='w', encoding='utf-8')
        tmp_file.write(code)
        tmp_path = tmp_file.name
        tmp_file.close()
        cmd = ["python", "-X", "utf8", "-u", tmp_path]   
    elif code_type in ["powershell", "bash"]:
        if os.name == 'nt': cmd = ["powershell", "-NoProfile", "-NonInteractive", "-Command", code]
        else: cmd = ["bash", "-c", code]
    else:
        return {"status": "error", "msg": f"不支持的类型: {code_type}"}
    print("code run output:") 
    startupinfo = None
    if os.name == 'nt':
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0 # SW_HIDE
    full_stdout = []

    def stream_reader(proc, logs):
        for line_bytes in iter(proc.stdout.readline, b''):
            try: line = line_bytes.decode('utf-8')
            except UnicodeDecodeError: line = line_bytes.decode('gbk', errors='ignore')
            logs.append(line)
            print(line, end="") 

    try:
        process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            bufsize=0, cwd=cwd, startupinfo=startupinfo
        )
        start_t = time.time()
        t = threading.Thread(target=stream_reader, args=(process, full_stdout), daemon=True)
        t.start()

        while t.is_alive():
            if time.time() - start_t > timeout:
                process.kill()
                full_stdout.append("\n[Timeout Error] 超时强制终止")
                break
            time.sleep(0.2)

        t.join(timeout=1)
        exit_code = process.poll()

        stdout_str = "".join(full_stdout)
        status = "success" if exit_code == 0 else "error"
        status_icon = "✅" if exit_code == 0 else "❌"
        if exit_code is None: status_icon = "⏳" 
        output_snippet = (stdout_str[:100] + '...' + stdout_str[-100:]) if len(stdout_str) > 300 else stdout_str
        yield f"[Status] {status_icon} Exit Code: {exit_code}\n[Stdout]\n{output_snippet}\n"
        if process.stdout: process.stdout.close()
        return {
            "status": status,
            "stdout": stdout_str[-2000:],
            "exit_code": exit_code
        }
    except Exception as e:
        if 'process' in locals(): process.kill()
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
    focus_item: 语义过滤指令。如果用户在找特定内容（如“小米汽车”），算法会优先保留包含该关键词的列表项。
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
    """在文件中寻找唯一的 old_content 块并替换为 new_content。
    """
    path = str(Path(path).resolve())
    try:
        if not os.path.exists(path): return {"status": "error", "msg": "文件不存在"}
        with open(path, 'r', encoding='utf-8') as f: full_text = f.read()
        # 检查唯一性
        count = full_text.count(old_content)
        if count == 0: return {"status": "error", "msg": "未找到匹配的旧文本块，请检查空格、缩进和换行是否完全一致。"}
        if count > 1: return {"status": "error", "msg": f"找到 {count} 处匹配，请提供更长的旧文本块以确保唯一性。"}
        updated_text = full_text.replace(old_content, new_content)
        with open(path, 'w', encoding='utf-8') as f: f.write(updated_text)
        return {"status": "success", "msg": "文件局部修改成功"}
    except Exception as e:
        return {"status": "error", "msg": str(e)}

def file_read(path, start=1, keyword=None, count=100, show_linenos=True):
    L_MAX = max(100, 1024000//count); TAG = " ... [TRUNCATED]"
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            stream = (
                (i, (l[:L_MAX].rstrip() + TAG if len(l) > L_MAX else l.rstrip()))
                for i, l in enumerate(f, 1)
            )
            stream = itertools.dropwhile(lambda x: x[0] < start, stream)
            if keyword:
                before = collections.deque(maxlen=count//3)
                for i, l in stream:
                    if keyword.lower() in l.lower():
                        res = list(before) + [(i, l)] + list(itertools.islice(stream, count - len(before) - 1))
                        break
                    before.append((i, l))
                else: return f"Keyword '{keyword}' not found after line {start}."
            else: res = itertools.islice(stream, count)
            return "\n".join(f"{i}| {l}" if show_linenos else l for i, l in res)
    except Exception as e:
        return f"Error: {str(e)}"

def smart_format(data, max_depth=2, max_str_len=100):
    def truncate(obj, depth):
        if isinstance(obj, str):
            if len(obj) > max_str_len: return f"{obj[:max_str_len//2]} ... {obj[-max_str_len//2:]}"
            return obj
        if depth >= max_depth: return truncate(str(obj), depth + 1)
        if isinstance(obj, dict): return {k: truncate(v, depth + 1) for k, v in obj.items()}
        if isinstance(obj, list): return [truncate(i, depth + 1) for i in obj]
        return obj
    if isinstance(data, (str, bytes)): return truncate(data, 0)
    return json.dumps(truncate(data, 0), indent=2, ensure_ascii=False, default=str)

class GenericAgentHandler(BaseHandler):
    '''
    Generic Agent 工具库，包含多种工具的实现。工具函数自动加上了 do_ 前缀。实际工具名没有前缀。
    '''
    def __init__(self, parent, last_history=None, cwd='./'):
        self.parent = parent
        self.plan = ""
        self.focus = ""
        self.cwd = cwd
        self.history_info = last_history if last_history else []

    def _get_abs_path(self, path):
        if not path: return ""
        return os.path.abspath(os.path.join(self.cwd, path))
    
    def tool_after_callback(self, tool_name, args, response, ret):
        rsumm = re.search(r"<summary>(.*?)</summary>", response.content, re.DOTALL)
        if rsumm: summary = rsumm.group(1).strip()[:200]
        else:
            summary = f"调用工具{tool_name}, args: {args}"
            if tool_name == 'no_tool': summary = "直接回答了用户问题"
            if type(ret.next_prompt) is str:
                ret.next_prompt += "\nPROTOCOL_VIOLATION: 上一轮遗漏了<summary>。 我已根据物理动作自动补全。请务必在下次回复中记得<summary>协议。" 
        self.history_info.append('[Agent] ' + smart_format(summary, max_str_len=100))

    def do_code_run(self, args, response):
        '''执行代码片段，有长度限制，不允许代码中放大量数据，如有需要应当通过文件读取进行。
        '''
        code_type = args.get("type", "python")
        # 从 response.content 中提取代码块, 匹配 ```python ... ``` 或 ```powershell ... ```
        pattern = rf"```{code_type}\n(.*?)\n```"
        matches = re.findall(pattern, response.content, re.DOTALL)
        if not matches:
            return StepOutcome(None, next_prompt=f"【系统错误】：你调用了 code_run，但未在回复中提供 ```{code_type} 代码块。请重新输出代码并附带工具调用。")       
        # 提取最后一个代码块（通常是模型修正后的最终逻辑）
        code = matches[-1].strip()
        timeout = args.get("timeout", 60)
        raw_path = os.path.join(self.cwd, args.get("cwd", './'))
        cwd = os.path.normpath(os.path.abspath(raw_path))
        result = yield from code_run(code, code_type, timeout, cwd)
        next_prompt = self._get_anchor_prompt()
        return StepOutcome(result, next_prompt=next_prompt)
    
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
        yield f'[Info] {str(result)}\n'
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
        print("Web Execute JS Result:", smart_format(result))
        yield f"JS 执行结果:\n{smart_format(result)}\n"
        next_prompt = self._get_anchor_prompt()
        return StepOutcome(result, next_prompt=next_prompt)
    
    def do_file_patch(self, args, response):
        path = self._get_abs_path(args.get("path", ""))
        yield f"[Action] Patching file: {path}\n"
        old_content = args.get("old_content", "")
        new_content = args.get("new_content", "")
        result = file_patch(path, old_content, new_content)
        yield f"\n{smart_format(result)}\n"
        next_prompt = self._get_anchor_prompt()
        return StepOutcome(result, next_prompt=next_prompt)
    
    def do_file_write(self, args, response):
        '''用于对整个文件的大量处理，精细修改要用file_patch。
        需要将要写入的内容放在<file_content>标签内，或者放在代码块中。
        '''
        path = self._get_abs_path(args.get("path", ""))
        mode = args.get("mode", "overwrite") 
        action_str = "Appending to" if mode == "append" else "Writing"
        yield f"[Action] {action_str} file: {os.path.basename(path)}\n"

        def extract_robust_content(text):
            tag = re.search(r"<file_content>(.*?)</file_content>", text, re.DOTALL)
            if tag: return tag.group(1).strip()
            s, e = text.find("```"), text.rfind("```")
            if -1 < s < e: return text[text.find("\n", s)+1 : e].strip()
            return None
        
        blocks = extract_robust_content(response.content)
        if not blocks:
            yield f"[Status] ❌ 失败: 未在回复中找到代码块内容\n"
            return StepOutcome({"status": "error", "msg": "No content found, if you want a blank, you should use code_run"}, next_prompt="\n")
        new_content = blocks
        try:
            write_mode = 'a' if mode == "append" else 'w'
            final_content = ("\n" + new_content) if mode == "append" else new_content
            with open(path, write_mode, encoding="utf-8") as f:
                f.write(final_content)
            yield f"[Status] ✅ {mode.capitalize()} 成功 ({len(new_content)} bytes)\n"
            next_prompt = self._get_anchor_prompt()
            return StepOutcome({"status": "success", 'writed_bytes': len(new_content)}, 
                               next_prompt=next_prompt)
        except Exception as e:
            yield f"[Status] ❌ 写入异常: {str(e)}\n"
            return StepOutcome({"status": "error", "msg": str(e)}, next_prompt="\n")
        
    def do_file_read(self, args, response):
        '''读取文件内容。从第start行开始读取。如有keyword则返回第一个keyword(忽略大小写)周边内容'''
        path = self._get_abs_path(args.get("path", ""))
        yield f"\n[Action] Reading file: {path}\n"
        start = args.get("start", 1)
        count = args.get("count", 100)
        keyword = args.get("keyword")
        show_linenos = args.get("show_linenos", True)
        result = file_read(path, start=start, keyword=keyword,
                           count=count, show_linenos=show_linenos)
        next_prompt = self._get_anchor_prompt()
        return StepOutcome(result, next_prompt=next_prompt)
    
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
        yield f"[Info] Updated plan and focus.\n"
        yield f"New Plan:\n{self.plan}\n\n"
        yield f"New Focus:\n{self.focus}\n"
        next_prompt = self._get_anchor_prompt()
        return StepOutcome({"status": "success"}, next_prompt=next_prompt)

    def do_no_tool(self, args, response):
        '''这是一个特殊工具，由引擎自主调用，不要包含在TOOLS_SCHEMA里。
        '''
        if not response or not getattr(response, 'content', '').strip():
            yield "[Warn] LLM returned an empty response. Retrying...\n"
            next_prompt = "[System] 检测到空回复，请重新生成内容或调用工具。"
            return StepOutcome({}, next_prompt=next_prompt, should_exit=False)
        yield "[Info] No tool called. Final response to user.\n"
        return StepOutcome(response, next_prompt=None, should_exit=True)
    
    def do_distill_good_memory(self, args, response):
        '''Agent觉得当前任务完成后有重要信息需要记忆时调用此工具。
        目前只支持全局记忆，暂不处理过程记忆或特定任务经验。
        '''
        prompt = '''### [总结提炼经验] 既然你觉得当前任务有重要信息需要记忆，请提取最近一次任务中【事实验证成功且长期有效】的环境事实与用户偏好，更新至全局记忆。
1. 严禁记录任何任务特定中间执行过程或临时变量经验，那是过程记忆不是全局记忆。
2. 若无高价值新事实，那就不更新任何内容。
3. 尽量先查看现有全局记忆形式，仅作少量修改不要影响其余部分。insight也要同步更新全局记忆的短印象来提醒存在性。
4. 优先使用file_read和file_patch来保证少量修改。''' + get_global_memory()
        yield "[Info] Start distilling good memory for long-term storage.\n"
        return StepOutcome({"status": "success"}, next_prompt=prompt)

    def _get_anchor_prompt(self):
        h_str = "\n".join(self.history_info[-20:])
        prompt = f"\n### [WORKING MEMORY]\n<history>\n{h_str}\n</history>"
        print(prompt)
        if self.plan: prompt += f"\n<plan>{self.plan}</plan>"
        if self.focus: prompt += f"\n<focus>{self.focus}</focus>"
        return prompt + "\n请继续执行下一步。"

def get_global_memory():
    prompt = "\n"
    try:
        with open('memory/global_mem_insight.txt', 'r', encoding='utf-8') as f: insight = f.read()
        prompt += f"\n\n[Global Memory Insight]\n"
        prompt += 'IMPORTANT PATHS: ../memory/global_mem.txt (Facts), ../memory/global_mem_insight.txt (Logic), ../ (Your Code Root).\n'
        prompt += 'MEM_RULE: Insight is the index of Facts. Sync Insight whenever Facts change. For details, read Facts.\n'
        prompt += "EXT: ../memory/ may contain other task-specific memories.\n"
        prompt += insight + "\n"
    except FileNotFoundError: pass
    return prompt