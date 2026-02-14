import os, json, re, time, requests, sys, threading, urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

try: import mykey
except: raise Exception('[ERROR] mykey.py not found, please copy mykey_template.py to mykey.py and fill your LLM backend.')

mykeys = vars(mykey)
sider_cookie = mykeys.get("sider_cookie")
oai_configs = {k: v for k, v in vars(mykey).items() if k.startswith("oai_config") and v}
claude_configs = {k: v for k, v in vars(mykey).items() if k.startswith("claude_config") and v}
google_api_key = mykeys.get("google_api_key")

proxy = mykeys.get("proxy", 'http://127.0.0.1:2082')
proxies = {"http": proxy, "https": proxy} if proxy else None

class SiderLLMSession:
    def __init__(self, default_model="gemini-3.0-flash"):
        from sider_ai_api import Session
        self._core = Session(cookie=sider_cookie, proxies=proxies)   
        self.default_model = default_model
    def ask(self, prompt, model=None, stream=False):
        if model is None: model = self.default_model
        if len(prompt) > 28000: 
            print(f"[Warn] Prompt too long ({len(prompt)} chars), truncating.")
            prompt = prompt[-28000:]
        full_text = self._core.chat(prompt, model, stream=False)
        if stream: return iter([full_text])   # gen有奇怪的空回复或死循环行为，sider足够快
        return full_text   

class ClaudeSession:
    def __init__(self, api_key, api_base, model="claude-opus", context_win=10000):
        self.api_key, self.api_base, self.default_model, self.context_win = api_key, api_base.rstrip('/'), model, context_win
        self.raw_msgs, self.lock = [], threading.Lock()
    def _trim_messages(self, messages):
        # 压缩4轮前的assistant消息：truncate <thinking>/<tool_use> 块
        for i, msg in enumerate(messages):
            if i < len(messages) - 4 and 'orig' not in msg:
                msg['orig'] = msg['prompt']
                for tag in ('thinking', 'tool_use', 'tool_result'):
                    msg['prompt'] = re.sub(
                        rf'(<{tag}>)([\s\S]*?)(</{tag}>)',
                        lambda m: m.group(1) + (m.group(2)[:200] + '...') + m.group(3) if len(m.group(2)) > 200 else m.group(0),
                        msg['prompt']
                    )
        total = sum(len(m['prompt']) for m in messages)
        if total <= self.context_win * 4: return messages
        target, current, result = self.context_win * 4 * 0.9, 0, []
        for msg in reversed(messages):
            if (msg_len := len(msg['prompt'])) + current <= target:
                result.append(msg); current += msg_len
            else: break
        if current > 10000 * 4: print(f'[DEBUG] Whole context length {current//4}.')
        return result[::-1] or messages[-2:]
    def raw_ask(self, messages, model=None, temperature=0.5, max_tokens=4096):
        model = model or self.default_model
        headers = {"x-api-key": self.api_key, "Content-Type": "application/json", "anthropic-version": "2023-06-01"}
        payload = {"model": model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens, "stream": True}
        try:
            with requests.post(f"{self.api_base}/v1/messages", headers=headers, json=payload, stream=True, timeout=(5,60)) as r:
                r.raise_for_status()
                for line in r.iter_lines():
                    if not line: continue
                    line = line.decode("utf-8") if isinstance(line, bytes) else line
                    if not line.startswith("data:"): continue
                    data = line[5:].lstrip()
                    if data == "[DONE]": break
                    try:
                        obj = json.loads(data)
                        if obj.get("type") == "content_block_delta" and obj.get("delta", {}).get("type") == "text_delta":
                            text = obj["delta"].get("text", "")
                            if text: yield text
                    except: pass
        except Exception as e: yield f"Error: {str(e)}"
    def make_messages(self, raw_list):
        trimmed = self._trim_messages(raw_list)
        return [{"role": m['role'], "content": m['prompt']} for m in trimmed]
    def ask(self, prompt, model=None, stream=False):
        def _ask_gen():
            content = ''
            with self.lock:
                self.raw_msgs.append({"role": "user", "prompt": prompt})
                messages = self.make_messages(self.raw_msgs)
            for chunk in self.raw_ask(messages, model):
                content += chunk; yield chunk
            if not content.startswith("Error:"): self.raw_msgs.append({"role": "assistant", "prompt": content})
        return _ask_gen() if stream else ''.join(list(_ask_gen()))

class LLMSession:
    def __init__(self, api_key, api_base, model, context_win=16000):
        self.api_key = api_key
        self.api_base = api_base
        self.raw_msgs = []
        self.messages = []
        self.context_win = context_win
        self.default_model = model
        self.lock = threading.Lock()

    def raw_ask(self, messages, model=None, temperature=0.5):
        if model is None: model = self.default_model
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json", "Accept": "text/event-stream"}
        payload = {"model": model, "messages": messages, "temperature": temperature, "stream": True}
        try:
            with requests.post(f"{self.api_base}/chat/completions",
                            headers=headers, json=payload, stream=True, timeout=(5, 60)) as r:
                r.raise_for_status()
                buffer = ''
                for line in r.iter_lines():
                    line = line.decode("utf-8")
                    if not line or not line.startswith("data:"): continue
                    data = line[5:].lstrip()
                    if data == "[DONE]": break
                    obj = json.loads(data); ch = (obj.get("choices") or [{}])[0]
                    finish_reason = ch.get("finish_reason")
                    delta = (ch.get("delta") or {}).get("content")
                    if delta:
                        yield delta; buffer += delta
                        if '</tool_use>' in buffer[-30:]: break
                    if finish_reason: break
        except Exception as e:
            yield f"Error: {str(e)}"

    def make_messages(self, raw_list, omit_images=True):
        messages = []
        for i, msg in enumerate(raw_list):
            if i < len(raw_list) - 4 and 'orig' not in msg:
                msg['orig'] = msg['prompt']
                for tag in ('thinking', 'tool_use', 'tool_result'):
                    msg['prompt'] = re.sub(
                        rf'(<{tag}>)([\s\S]*?)(</{tag}>)',
                        lambda m: m.group(1) + (m.group(2)[:200] + '...') + m.group(3) if len(m.group(2)) > 200 else m.group(0),
                        msg['prompt']
                    )
            prompt = msg['prompt']
            if omit_images and msg['image']: messages.append({"role": msg['role'], "content": "[Image omitted, if you needed it, ask me]\n" + prompt})
            elif not omit_images and msg['image']:
                messages.append({"role": msg['role'], "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{msg['image']}"}},
                    {"type": "text", "text": prompt} ]})
            else:
                messages.append({"role": msg['role'], "content": prompt})
        return messages
       
    def summary_history(self, model=None):
        if model is None: model = self.default_model
        with self.lock:
            keep = 0; tok = 0
            for m in reversed(self.raw_msgs):
                l = len(str(m))//4
                if tok + l > self.context_win*0.2: break
                tok += l; keep += 1
            keep = max(2, keep)
            old, self.raw_msgs = self.raw_msgs[:-keep], self.raw_msgs[-keep:]
            if len(old) == 0: old = self.raw_msgs; self.raw_msgs = []
            p = "Summarize prev summary and prev conversations into compact memory (facts/decisions/constraints/open questions). Do NOT restate long schemas. The new summary should less than 1000 tokens. Permit dropping non-important things.\n"
            messages = self.make_messages(old, omit_images=True)
            messages += [{"role":"user", "content":p}]
            msg_lens = [1000 if isinstance(m["content"], list) else len(str(m["content"]))//4 for m in messages]
            summary = ''.join(list(self.raw_ask(messages, model, temperature=0.1)))
            print('[Debug] Summary length:', len(summary)//4, '; Orig context lengths:', str(msg_lens))
            if not summary.startswith("Error:"): 
                self.raw_msgs.insert(0, {"role":"assistant", "prompt":"Prev summary:\n"+summary, "image":None})
            else: self.raw_msgs = old + self.raw_msgs   # 不做了，下次再做

    def ask(self, prompt, model=None, image_base64=None, stream=False):
        if model is None: model = self.default_model
        def _ask_gen():
            content = ''
            with self.lock:
                self.raw_msgs.append({"role": "user", "prompt": prompt, "image": image_base64})
                messages = self.make_messages(self.raw_msgs[:-1], omit_images=True)
                messages += self.make_messages([self.raw_msgs[-1]], omit_images=False)
                msg_lens = [1000 if isinstance(m["content"], list) else len(str(m["content"]))//4 for m in messages]
                total_len = sum(msg_lens)   # estimate token count
            gen = self.raw_ask(messages, model)
            for chunk in gen:
                content += chunk; yield chunk
            if not content.startswith("Error:"):
                self.raw_msgs.append({"role": "assistant", "prompt": content, "image": None})
            if total_len > 5000: print(f"[Debug] Whole context length {total_len} {str(msg_lens)}.")
            if total_len > self.context_win: 
                yield '[NextWillSummary]'
                threading.Thread(target=self.summary_history, daemon=True).start()
        if stream: return _ask_gen()
        return ''.join(list(_ask_gen())) 
        
  
class GeminiSession:
    def __init__(self, api_key=None, default_model="gemini-2.0-flash-001", proxy=proxy):
        self.api_key = api_key or google_api_key
        if not self.api_key: raise ValueError("google_api_key 未配置或为空，请在 mykey.py 中设置")
        self.default_model = default_model
        self.proxies = {"http":proxy, "https":proxy} if proxy else None
    def ask(self, prompt, model=None, stream=False):
        if model is None: model = self.default_model
        url = f"https://generativelanguage.googleapis.com/v1/models/{model}:generateContent?key={self.api_key}"
        headers = {"Content-Type":"application/json"}
        data = {"contents":[{"role":"user","parts":[{"text":prompt}]}]}
        try:
            kw = {"headers":headers, "json":data, "timeout":60, 'proxies': self.proxies}
            r = requests.post(url, **kw)
        except Exception as e:
            return f"[GeminiError] request failed: {e}"
        if r.status_code != 200:
            body = r.text[:500].replace("\n"," ")
            return f"[GeminiError] HTTP {r.status_code}: {body}"
        try:
            obj = r.json(); cands = obj.get("candidates") or []
            if not cands: return "[GeminiError] empty candidates"
            parts = (cands[0].get("content") or {}).get("parts") or []
            full_text = "".join(p.get("text","") for p in parts)
        except Exception as e:
            return f"[GeminiError] invalid response format: {e}"
        return iter([full_text]) if stream else full_text

class MockFunction:
    def __init__(self, name, arguments): self.name, self.arguments = name, arguments  
         
class MockToolCall:
    def __init__(self, name, args):
        arg_str = json.dumps(args, ensure_ascii=False) if isinstance(args, dict) else args
        self.function = MockFunction(name, arg_str)

class MockResponse:
    def __init__(self, thinking, content, tool_calls, raw):
        self.thinking = thinking        # 存放 <thinking> 内部的思维过程
        self.content = content          # 存放去除标签后的纯文本回复
        self.tool_calls = tool_calls    # 存放 MockToolCall 列表 或 None
        self.raw = raw
    def __repr__(self):    
        return f"<MockResponse thinking={bool(self.thinking)}, content='{self.content}', tools={bool(self.tool_calls)}>"

class ToolClient:
    def __init__(self, backends, auto_save_tokens=False):
        if isinstance(backends, list): self.backends = backends
        else: self.backends = [backends]
        self.backend = self.backends[0]
        self.auto_save_tokens = auto_save_tokens
        self.last_tools = ''
        self.total_cd_tokens = 0

    def chat(self, messages, tools=None):
        full_prompt = self._build_protocol_prompt(messages, tools)      
        print("Full prompt length:", len(full_prompt), 'chars')
        with open('model_responses.txt', 'a', encoding='utf-8', errors="replace") as f:
            f.write(f"=== Prompt ===\n{full_prompt}\n")
        gen = self.backend.ask(full_prompt, stream=True)
        raw_text = ''; summarytag = '[NextWillSummary]'
        for chunk in gen:
            raw_text += chunk; 
            if chunk != summarytag: yield chunk
        print('Complete response received.')
        if raw_text.endswith(summarytag):
            self.last_tools = ''; raw_text = raw_text[:-len(summarytag)]
        with open('model_responses.txt', 'a', encoding='utf-8', errors="replace") as f:
            f.write(f"=== Response ===\n{raw_text}\n\n")
        return self._parse_mixed_response(raw_text)

    def _build_protocol_prompt(self, messages, tools):
        system_content = next((m['content'] for m in messages if m['role'].lower() == 'system'), "")
        history_msgs = [m for m in messages if m['role'].lower() != 'system']
        # 构造工具描述
        tool_instruction = ""
        if tools:
            tools_json = json.dumps(tools, ensure_ascii=False, separators=(',', ':'))
            tool_instruction = f"""
### 交互协议 (必须严格遵守，持续有效)
请按照以下步骤思考并行动，标签之间需要回车换行：
1. **思考**: 在 `<thinking>` 标签中先进行思考，分析现状和策略。
2. **总结**: 在 `<summary>` 中输出*极为简短*的高度概括的单行（<30字）物理快照，包括上次工具调用结果获取的新信息+本次工具调用意图和预期。此内容将进入长期工作记忆，记录关键信息，严禁输出无实际信息增量的描述。
3. **行动**: 如需调用工具，请在回复正文之后输出一个 **<tool_use>块**，然后结束，我会稍后给你返回<tool_result>块。
   格式: ```<tool_use>\n{{"name": "工具名", "arguments": {{参数}}}}\n</tool_use>\n```

### 可用工具库（已挂载，持续有效）
{tools_json}
"""
            if self.auto_save_tokens and self.last_tools == tools_json:
                tool_instruction = "\n### 工具库状态：持续有效（code_run/file_read等），**可正常调用**。调用协议沿用。\n"
            else:
                self.total_cd_tokens = 0
            self.last_tools = tools_json
            
        prompt = ""
        if system_content: prompt += f"=== SYSTEM ===\n{system_content}\n"
        prompt += f"{tool_instruction}\n\n"
        for m in history_msgs:
            role = "USER" if m['role'] == 'user' else "ASSISTANT"
            prompt += f"=== {role} ===\n{m['content']}\n\n"
            self.total_cd_tokens += len(m['content'])
            
        if self.total_cd_tokens > 6000: self.last_tools = ''

        prompt += "=== ASSISTANT ===\n" 
        return prompt

    def _parse_mixed_response(self, text):
        remaining_text = text
        thinking = ''
        think_pattern = r"<thinking>(.*?)</thinking>"
        think_match = re.search(think_pattern, text, re.DOTALL)
        
        if think_match:
            thinking = think_match.group(1).strip()
            remaining_text = re.sub(think_pattern, "", remaining_text, flags=re.DOTALL)
        
        tool_calls = None
        tool_pattern = r"<tool_use>(.*?)</tool_use>"
        tool_all = re.findall(tool_pattern, remaining_text, re.DOTALL)
        
        json_str = ""
        if tool_all:
            json_str = tool_all[-1].strip()
            remaining_text = re.sub(tool_pattern, "", remaining_text, flags=re.DOTALL)
        elif '<tool_use>' in remaining_text:
            weaktoolstr = remaining_text.split('<tool_use>')[-1].strip()
            json_str = weaktoolstr if weaktoolstr.endswith('}') else ''
            if json_str == '' and '```' in weaktoolstr and weaktoolstr.split('```')[0].strip().endswith('}'):
                json_str = weaktoolstr.split('```')[0].strip()
            remaining_text = remaining_text.replace('<tool_use>'+weaktoolstr, "")
        elif '"name":' in remaining_text and '"arguments":' in remaining_text:
            json_match = re.search(r"(\{.*\"name\":.*?\})", remaining_text, re.DOTALL | re.MULTILINE)
            if json_match:
                json_str = json_match.group(1).strip()
                remaining_text = remaining_text.replace(json_str, "").strip()
        if json_str:
            try:
                data = tryparse(json_str)
                func_name = data.get('name') or data.get('function') or data.get('tool')
                args = data.get('arguments') or data.get('args') or data.get('params') or data.get('parameters')
                if args is None: args = data
                if func_name: tool_calls = [MockToolCall(func_name, args)]
            except json.JSONDecodeError as e:
                print("[Warn] Failed to parse tool_use JSON:", json_str)
                tool_calls = [MockToolCall('bad_json', {'msg': f'Failed to parse tool_use JSON: {json_str[:200]}'})]
            except Exception as e:
                print("[Error] Exception during tool_use parsing:", str(e), data)

        content = remaining_text.strip()
        if not content: content = ""
        return MockResponse(thinking, content, tool_calls, text)

def tryparse(json_str):
    try: return json.loads(json_str)
    except: pass
    json_str = json_str.strip().strip('`').replace('json\n', '', 1).strip()
    try: return json.loads(json_str)
    except: pass
    try: return json.loads(json_str[:-1])
    except: pass
    if '}' in json_str: json_str = json_str[:json_str.rfind('}') + 1]
    return json.loads(json_str)

if __name__ == "__main__":
    import sys, os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    try:
        import mykey
    except ImportError:
        class MockMyKey: pass
        mykey = MockMyKey()
    
    mykeys = vars(mykey)
    sider_cookie = mykeys.get("sider_cookie")
    oai_configs = {
        k: v for k, v in vars(mykey).items() if k.startswith("oai_config") and v
    }
    google_api_key = mykeys.get("google_api_key")
    cfg = oai_configs.get("oai_config")

    llmclient = ToolClient(GeminiSession(api_key=google_api_key, proxy='127.0.0.1:2082').ask)
    #llmclient = ToolClient(LLMSession(api_key=cfg['apikey'], api_base=cfg['apibase'], model=cfg['model']).ask)
    #llmclient = ToolClient(SiderLLMSession().ask)
    def get_final(gen):
        try:
            while True: print('mid:', next(gen))
        except StopIteration as e:
            return e.value
        
    response = get_final(llmclient.chat(
        messages=[{"role": "user", "content": "我的IP是多少"}], 
        tools=[{"name": "get_ip", "parameters": {}}]
    ))
    print(f"思考: {response.thinking}") 
    if response.tool_calls:
        cmd = response.tool_calls[0]
        print(f"调用: {cmd.function.name} 参数: {cmd.function.arguments}")

    response = get_final(llmclient.chat(
        messages=[{"role": "user", "content": "<tool_result>10.176.45.12</tool_result>"}] 
    ))
    print(response.content)