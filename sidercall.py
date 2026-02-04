import os, json, re, time, requests, sys

try: from mykey import sider_cookie
except ImportError: sider_cookie = ""
try: from mykey import oai_apikey, oai_apibase, oai_model
except ImportError: oai_apikey = oai_apibase = oai_model = ""

class SiderLLMSession:
    def __init__(self, default_model="gemini-3.0-flash"):
        from sider_ai_api import Session
        self._core = Session(cookie=sider_cookie, proxies={'https':'127.0.0.1:2082'})   
        self.default_model = default_model
    def ask(self, prompt, model=None, stream=False):
        if model is None: model = self.default_model
        if len(prompt) > 29000: 
            print(f"[Warn] Prompt too long ({len(prompt)} chars), truncating.")
            prompt = prompt[-29000:]
        gen = self._core.chat(prompt, model)
        if stream: return gen
        return ''.join(list(gen))
  
class LLMSession:
    def __init__(self, api_key=oai_apikey, api_base=oai_apibase, model=oai_model, context_win=12000):
        self.api_key = api_key
        self.api_base = api_base
        self.raw_msgs = []
        self.messages = []
        self.context_win = context_win
        self.model = model

    def raw_ask(self, messages, model=None, temperature=0.5):
        if model is None: model = self.model
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
                    obj = json.loads(data)
                    ch = (obj.get("choices") or [{}])[0]
                    if ch.get("finish_reason") is not None: break
                    delta = (ch.get("delta") or {}).get("content")
                    if not delta: continue
                    yield delta
                    buffer += delta
                    if '</tool_use>' in buffer[-30:]: break
        except Exception as e:
            yield f"Error: {str(e)}"

    def make_messages(self, raw_list, omit_images=True):
        messages = []
        for msg in raw_list:
            if omit_images and msg['image']:
                messages.append({"role": msg['role'], "content": "[Image omitted, if you needed it, ask me]\n" + msg['prompt']})
            elif not omit_images and msg['image']:
                messages.append({"role": msg['role'], "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{msg['image']}"}},
                    {"type": "text", "text": msg['prompt']} ]})
            else:
                messages.append({"role": msg['role'], "content": msg['prompt']})
        return messages
       
    def summary_history(self, model=None):
        if model is None: model = self.model
        keep = max(2, len(self.raw_msgs)//2)
        old, self.raw_msgs = self.raw_msgs[:-keep], self.raw_msgs[-keep:]
        if len(old) == 0: old = self.raw_msgs; self.raw_msgs = []
        p = "Summarize prev summary and prev conversations into compact memory (facts/decisions/constraints/open questions). Do NOT restate long schemas. The new summary should less than 1000 tokens.\n"
        messages = self.make_messages(old, omit_images=True)
        messages += [{"role":"user", "content":p}]
        summary = ''.join(list(self.raw_ask(messages, model, temperature=0.1)))
        if not summary.startswith("Error:"): 
            self.raw_msgs.insert(0, {"role":"system", "prompt":"Prev summary:\n"+summary, "image":None})
        else: self.raw_msgs = old + self.raw_msgs   # 不做了，下次再做

    def ask(self, prompt, model=None, image_base64=None, stream=False):
        if model is None: model = self.model
        self.raw_msgs.append({"role": "user", "prompt": prompt, "image": image_base64})
        messages = self.make_messages(self.raw_msgs[:-1], omit_images=True)
        messages += self.make_messages([self.raw_msgs[-1]], omit_images=False)
        msg_lens = [1000 if isinstance(m["content"], list) else len(str(m["content"]))//4 for m in messages]
        total_len = sum(msg_lens)   # estimate token count
        gen = self.raw_ask(messages, model)
        def _ask_gen():
            content = ''
            for chunk in gen:
                content += chunk; yield chunk
            if not content.startswith("Error:"):
                self.raw_msgs.append({"role": "assistant", "prompt": content, "image": None})
            if total_len > 5000: print(f"[Debug] Whole context length {total_len} {str(msg_lens)}.")
            if total_len > self.context_win: self.summary_history()
        if stream: return _ask_gen()
        return ''.join(list(_ask_gen())) 
        

class MockFunction:
    def __init__(self, name, arguments):
        self.name = name
        self.arguments = arguments  

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
    def __init__(self, raw_api_func, auto_save_tokens=False):
        if isinstance(raw_api_func, list): self.raw_apis = raw_api_func
        else: self.raw_apis = [raw_api_func]
        self.raw_api = self.raw_apis[0]
        self.auto_save_tokens = auto_save_tokens
        self.last_tools = ''
        self.total_cd_tokens = 0

    def chat(self, messages, tools=None):
        full_prompt = self._build_protocol_prompt(messages, tools)      
        print("Full prompt length:", len(full_prompt))
        gen = self.raw_api(full_prompt, stream=True)
        raw_text = ''
        for chunk in gen:
            raw_text += chunk; yield chunk
        with open('model_responses.txt', 'a', encoding='utf-8', errors="replace") as f:
            f.write(f"=== Prompt ===\n{full_prompt}\n=== Response ===\n{raw_text}\n\n")
        return self._parse_mixed_response(raw_text)

    def _build_protocol_prompt(self, messages, tools):
        system_content = next((m['content'] for m in messages if m['role'].lower() == 'system'), "")
        history_msgs = [m for m in messages if m['role'].lower() != 'system']
        
        # 构造工具描述
        tool_instruction = ""
        if tools:
            tools_json = json.dumps(tools, ensure_ascii=False, separators=(',', ':'))
            tool_instruction = f"""
### 交互协议 (必须严格遵守)
请按照以下步骤思考并行动，标签之间需要回车换行：
1. **思考**: 在 `<thinking>` 标签中先进行思考，分析现状和策略。
2. **总结**: 在 `<summary>` 中输出*极为简短*的高度概括的单行（<30字）物理快照，包括上次工具调用结果获取的新信息+本次工具调用意图和预期。此内容将进入长期工作记忆，记录关键信息，严禁输出无实际信息增量的描述。
3. **行动**: 如果需要调用工具，请在回复正文之后输出一个 **<tool_use>块**，然后结束，我会稍后给你返回<tool_result>块。
   格式: ```<tool_use>\n{{"function": "工具名", "arguments": {{参数}}}}\n</tool_use>\n```

### 可用工具库
{tools_json}
"""
            if self.auto_save_tokens and self.last_tools == tools_json:
                tool_instruction = "\n### 交互协议保持不变，沿用之前的协议和工具库。\n"
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
            
        if self.total_cd_tokens > 9000: self.last_tools = ''

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
        tool_match = re.search(tool_pattern, remaining_text, re.DOTALL)
        
        json_str = ""
        if tool_match:
            json_str = tool_match.group(1).strip()
            remaining_text = re.sub(tool_pattern, "", remaining_text, flags=re.DOTALL)
        elif '<tool_use>' in remaining_text:
            weaktoolstr = remaining_text.split('<tool_use>')[-1].strip()
            json_str = weaktoolstr if weaktoolstr.endswith('}') else ''
            if json_str == '' and '```' in weaktoolstr and weaktoolstr.split('```')[0].strip().endswith('}'):
                json_str = weaktoolstr.split('```')[0].strip()
            remaining_text = remaining_text.replace('<tool_use>'+weaktoolstr, "")

        if json_str:
            try:
                data = tryparse(json_str)
                func_name = data.get('function') or data.get('tool')
                args = data.get('arguments') or data.get('args')
                if args is None: args = data
                if func_name: tool_calls = [MockToolCall(func_name, args)]
            except json.JSONDecodeError:
                print("[Warn] Failed to parse tool_use JSON:", json_str)
                remaining_text += f"[Warning] JSON 解析失败，模型输出了无效的 JSON."
            except Exception as e:
                print("[Error] Exception during tool_use parsing:", str(e), data)

        content = remaining_text.strip()
        if not content: content = ""
        return MockResponse(thinking, content, tool_calls, text)

def tryparse(json_str):
    try: return json.loads(json_str)
    except:
        return json.loads(json_str[:-1])

if __name__ == "__main__":
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    try: from mykey import sider_cookie
    except ImportError: sider_cookie = ""
    try: from mykey import oai_apikey, oai_apibase, oai_model
    except ImportError: oai_apikey = oai_apibase = oai_model = ""

    llmclient = ToolClient(LLMSession(api_key=oai_apikey, api_base=oai_apibase, model=oai_model).ask)
    print(llmclient.raw_api("Hello, world!", stream=False))
    #llmclient = ToolClient(SiderLLMSession().ask)
    def get_final(gen):
        try:
            while True: 
                print('mid:', next(gen))
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