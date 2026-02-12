import os, sys, threading, queue
import time, json, re
if sys.stdout is None: sys.stdout = open(os.devnull, "w")
if sys.stderr is None: sys.stderr = open(os.devnull, "w")
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sidercall import SiderLLMSession, LLMSession, ToolClient, ClaudeSession
from agent_loop import agent_runner_loop, StepOutcome, BaseHandler
from ga import GenericAgentHandler, smart_format, get_global_memory, format_error

with open('assets/tools_schema.json', 'r', encoding='utf-8') as f:
    TS = f.read()
    TOOLS_SCHEMA = json.loads(TS if os.name == 'nt' else TS.replace('powershell', 'bash'))

def get_system_prompt():
    if not os.path.exists('memory'): os.makedirs('memory')
    if not os.path.exists('memory/global_mem.txt'):
        with open('memory/global_mem.txt', 'w', encoding='utf-8') as f: f.write('')
    if not os.path.exists('memory/global_mem_insight.txt'):
        content = "## Global Memory Index (Logic)\n\n[CONSTITUTION]\n1. 改我自身源码前必须先问用户\n\n[STORES]\n- global_mem: ../memory/global_mem.txt\n\n[ACCESS]\n- global_mem: 按 TOPIC 检索索引\n\n[TOPICS.GLOBAL_MEM]"
        if os.path.exists('assets/global_mem_insight_template.txt'):
            with open('assets/global_mem_insight_template.txt', 'r', encoding='utf-8') as f: content = f.read()
        with open('memory/global_mem_insight.txt', 'w', encoding='utf-8') as f: f.write(content)
    with open('assets/sys_prompt.txt', 'r', encoding='utf-8') as f: prompt = f.read()
    prompt += get_global_memory()
    return prompt

class GeneraticAgent:
    def __init__(self):
        if not os.path.exists('temp'): os.makedirs('temp')
        from sidercall import sider_cookie, oai_configs, claude_configs
        llm_sessions = []
        for cfg in claude_configs.values():
            llm_sessions += [ClaudeSession(api_key=cfg['apikey'], api_base=cfg['apibase'], model=cfg['model'])]
        if sider_cookie: llm_sessions += [SiderLLMSession(default_model=x) for x in \
                                    ["gemini-3.0-flash", "claude-haiku-4.5", "kimi-k2"]]
        for cfg in oai_configs.values():
            llm_sessions += [LLMSession(api_key=cfg['apikey'], api_base=cfg['apibase'], model=cfg['model'])]
        if len(llm_sessions) > 0: 
            self.llmclient = ToolClient(llm_sessions, auto_save_tokens=True)
        else:
            self.llmclient = None
        self.lock = threading.Lock()
        self.history = []               
        self.task_queue = queue.Queue() 
        self.display_queue = queue.Queue() 
        self.last_active_time = time.time()
        self.is_running = False    
        self.llm_no = 0
        self.stop_sig = False
        self.current_source = 'none'
        self.handler = None

    def next_llm(self):
        self.llm_no = (self.llm_no + 1) % len(self.llmclient.backends)
        self.llmclient.last_tools = ''

    def abort(self):
        print('Abort current task...')
        if not self.is_running: return
        self.stop_sig = True
        if self.handler is not None: 
            self.handler.code_stop_signal.append(1)

    def put_task(self, query, source="user"):
        display_queue = queue.Queue()
        self.task_queue.put({"query": query, "source": source, "output": display_queue})
        return display_queue

    def run(self):
        while True:
            task = self.task_queue.get()
            self.is_running = True
            raw_query, source, display_queue = task["query"], task["source"], task["output"]
            self.current_source = source
            self.last_active_time = time.time()
                        
            rquery = smart_format(raw_query.replace('\n', ' '), max_str_len=200)
            self.history.append(f"[USER]: {rquery}")
            
            sys_prompt = get_system_prompt()
            handler = GenericAgentHandler(None, self.history, './temp')
            self.handler = handler
            self.llmclient.backend = self.llmclient.backends[self.llm_no]
            gen = agent_runner_loop(self.llmclient, sys_prompt, 
                        raw_query, handler, TOOLS_SCHEMA, max_turns=40)
                        
            try:
                full_response = ""; last_pos = 0
                for chunk in gen:
                    if self.stop_sig: break
                    full_response += chunk
                    if len(full_response) - last_pos > 50:
                        display_queue.put({'next': f'{full_response}', 'source': source})
                        last_pos = len(full_response)
                if '</summary>' in full_response: full_response = full_response.replace('</summary>', '</summary>\n\n')
                if '</file_content>' in full_response: full_response = re.sub(r'<file_content>\s*(.*?)\s*</file_content>', r'\n````\n<file_content>\n\1\n</file_content>\n````', full_response, flags=re.DOTALL)
                display_queue.put({'done': full_response, 'source': source})
                self.history = handler.history_info
            except Exception as e:
                print(f"Backend Error: {format_error(e)}")
                display_queue.put({'done': full_response + f'\n```\n{format_error(e)}\n```', 'source': source})
            finally:
                self.is_running = False
                self.stop_sig = False
                self.current_source = 'none'
                self.task_queue.task_done()
                if self.handler is not None: self.handler.code_stop_signal.append(1)

    
