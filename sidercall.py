import os, json, re, time, requests
from sider_ai_api import Session

try:
    from mykey import sider_cookie, capikey
except ImportError:
    sider_cookie = ""
    capikey = ""

class SiderLLMSession:
    def __init__(self, multiturns=6):
        self._core = Session(cookie=sider_cookie, proxies={'https':'127.0.0.1:2082'})   
    def ask(self, prompt, model="gemini-3.0-flash"):
        if len(prompt) > 30000: prompt = prompt[-29500:]
        return ''.join(self._core.chat(prompt, model))
  
class LLMSession:
    def __init__(self, api_key=capikey, api_base="http://113.45.39.247:3001/v1", multiturns=6):
        self.api_key = api_key
        self.api_base = api_base
        self.messages = []
        self.multiturns = multiturns
        
    def ask(self, prompt, model="openai/gpt-5.1"):
        self.messages.append({"role": "user", "content": prompt})
        if len(self.messages) > self.multiturns:
            self.messages = self.messages[-self.multiturns:]
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        try:
            response = requests.post(
                f"{self.api_base}/chat/completions",
                headers=headers,
                json={
                    "model": model, 
                    "messages": self.messages, 
                    "temperature": 0.5
                },
                timeout=60
            )
            res_json = response.json()
            content = res_json["choices"][0]["message"]["content"]
            self.messages.append({"role": "assistant", "content": content})
            return content
        except Exception as e:
            return f"Error: {str(e)}"

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
        self.raw_api = raw_api_func
        self.auto_save_tokens = auto_save_tokens
        self.last_tools = ''
        self.total_cd_tokens = 0

    def chat(self, messages, tools=None):
        full_prompt = self._build_protocol_prompt(messages, tools)      
        print("Full prompt length:", len(full_prompt))
        raw_text = self.raw_api(full_prompt)
        with open('model_responses.txt', 'a', encoding='utf-8', errors="replace") as f:
            f.write(f"=== Prompt ===\n{full_prompt}\n=== Response ===\n{raw_text}\n\n")
        return self._parse_mixed_response(raw_text)

    def _build_protocol_prompt(self, messages, tools):
        system_content = next((m['content'] for m in messages if m['role'].lower() == 'system'), "你是一个智能助手。")
        history_msgs = [m for m in messages if m['role'].lower() != 'system']
        
        # 构造工具描述
        tool_instruction = ""
        if tools:
            tools_json = json.dumps(tools, ensure_ascii=False, indent=2)
            tool_instruction = f"""
### ⚡️ 交互协议 (必须严格遵守)
请按照以下步骤思考并行动：
1. **思考**: 在 `<thinking>` 标签中先进行思考，分析现状和策略。
2. **总结**: 在 `<summary>` 中输出*极为简短*的高度概括的单行（<30字）物理快照，包括上次工具调用结果获取的新信息+本次工具调用意图和预期。此内容将进入长期工作记忆，记录关键信息，严禁输出无实际信息增量的描述。
3. **行动**: 如果需要调用工具，请紧接着输出一个 **<tool_use>块**，然后结束，我会稍后给你返回<tool_result>块。
   格式: ```<tool_use>\n{{"function": "工具名", "arguments": {{参数}}}}\n</tool_use>\n```

### 🛠️ 可用工具库
{tools_json}
"""
            if self.auto_save_tokens and self.last_tools == tools_json:
                tool_instruction = "\n### 交互协议保持不变，沿用之前的协议和工具库。\n"
            else:
                self.total_cd_tokens = 0
            self.last_tools = tools_json
            
        prompt = f"=== SYSTEM ===\n{system_content}\n{tool_instruction}\n\n"
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
        tool_match = re.search(tool_pattern, text, re.DOTALL)
        
        json_str = ""
        if tool_match:
            json_str = tool_match.group(1).strip()
            remaining_text = re.sub(tool_pattern, "", remaining_text, flags=re.DOTALL)
        elif '<tool_use>' in remaining_text:
            weaktoolstr = remaining_text.split('<tool_use>')[-1].strip()
            json_str = weaktoolstr if weaktoolstr.endswith('}') else ''
            remaining_text = remaining_text.replace('<tool_use>'+weaktoolstr, "")

        if json_str:
            try:
                data = tryparse(json_str)
                func_name = data.get('function') or data.get('tool')
                args = data.get('arguments') or data.get('args')
                if args is None: args = {}
                if func_name: tool_calls = [MockToolCall(func_name, args)]
            except json.JSONDecodeError:
                print("[Warn] Failed to parse tool_use JSON:", json_str)
                thinking += f"[Warn] JSON 解析失败，模型输出了无效的 JSON."
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
    llmclient = ToolClient(LLMSession().ask)
    response = llmclient.chat(
        messages=[{"role": "user", "content": "我的IP是多少"}], 
        tools=[{"name": "get_ip", "parameters": {}}]
    )
    # 4. 获取结果
    print(f"思考: {response.thinking}") 
    # -> 我需要查一下 IP。

    if response.tool_calls:
        cmd = response.tool_calls[0]
        print(f"调用: {cmd.function.name} 参数: {cmd.function.arguments}")

    response = llmclient.chat(
        messages=[{"role": "user", "content": "<tool_result>10.176.45.12</tool_result>"}] 
    )
    print(response.content)