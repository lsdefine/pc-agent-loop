import json, re
from dataclasses import dataclass
from typing import Any, Optional
@dataclass
class StepOutcome:
    data: Any
    next_prompt: Optional[str] = None
    should_exit: bool = False


def try_call_generator(func, *args, **kwargs):
    ret = func(*args, **kwargs)
    if hasattr(ret, '__iter__') and not isinstance(ret, (str, bytes, dict, list)):
        ret = yield from ret
    return ret

class BaseHandler:
    def tool_before_callback(self, tool_name, args, response): pass
    def tool_after_callback(self, tool_name, args, response, ret): pass
    def dispatch(self, tool_name, args, response):
        method_name = f"do_{tool_name}"
        if hasattr(self, method_name):
            _ = yield from try_call_generator(self.tool_before_callback, tool_name, args, response)
            ret = yield from try_call_generator(getattr(self, method_name), args, response)
            _ = yield from try_call_generator(self.tool_after_callback, tool_name, args, response, ret)
            return ret
        else:
            yield f"❌ 未知工具: {tool_name}\n"
            return StepOutcome(None, "未知工具", "ERROR")

def json_default(o):
    if isinstance(o, set): return list(o)
    return str(o) 

def get_pretty_json(data):
    if isinstance(data, dict) and "script" in data:
        data = data.copy()
        data["script"] = data["script"].replace("; ", ";\n  ")
    return json.dumps(data, indent=2, ensure_ascii=False).replace('\\n', '\n')

def agent_runner_loop(client, system_prompt, user_input, handler, tools_schema, max_turns=15):
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_input}
    ]
    for turn in range(max_turns):
        yield f"**LLM Running (Turn {turn+1}) ...**\n\n"
        response = client.chat(messages=messages, tools=tools_schema)

        if response.thinking: yield '<thinking>' + response.thinking + '</thinking>\n\n'
        if '</summary>```'  in response.content: response.content = response.content.replace('</summary>```', '</summary>\n```')
        showcontent = response.content
        if '</file_content>' in showcontent:
            showcontent = re.sub(r'<file_content>\s*(.*?)\s*</file_content>', r'\n````\n<file_content>\n\1\n</file_content>\n````', showcontent, flags=re.DOTALL)
        yield showcontent + '\n\n'

        if not response.tool_calls:
            tool_name, args = 'no_tool', {}
        else:
            tool_call = response.tool_calls[0] 
            tool_name = tool_call.function.name
            args = json.loads(tool_call.function.arguments)

        if tool_name == 'no_tool': pass
        else: 
            yield f"🛠️ **正在调用工具:** `{tool_name}`  📥**参数:**\n"
            yield f"````text\n{get_pretty_json(args)}\n````\n" 
        yield '`````\n'
        outcome = yield from handler.dispatch(tool_name, args, response)
        yield '`````\n'

        if outcome.next_prompt is None: return {'result': 'CURRENT_TASK_DONE', 'data': outcome.data}
        if outcome.should_exit: return {'result': 'EXITED', 'data': outcome.data}

        next_prompt = ""
        if outcome.data is not None: 
            datastr = json.dumps(outcome.data, ensure_ascii=False, default=json_default) if type(outcome.data) in [dict, list] else str(outcome.data) 
            next_prompt += f"<tool_result>\n{datastr}\n</tool_result>\n\n"
        next_prompt += outcome.next_prompt
        messages = [{"role": "user", "content": next_prompt}]
    return {'result': 'MAX_TURNS_EXCEEDED'}