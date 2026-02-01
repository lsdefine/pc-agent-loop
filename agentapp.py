import os, sys
if sys.stdout is None: sys.stdout = open(os.devnull, "w")
if sys.stderr is None: sys.stderr = open(os.devnull, "w")
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


import streamlit as st
import time, json, re

with open('assets/tools_schema.json', 'r', encoding='utf-8') as f:
    TOOLS_SCHEMA = json.load(f)

st.set_page_config(page_title="Cowork", layout="wide")

from sidercall import SiderLLMSession, LLMSession, ToolClient
from agent_loop import agent_runner_loop, StepOutcome, BaseHandler

@st.cache_resource
def init():
    if not os.path.exists('temp'): os.makedirs('temp')
    llm_sessions = [SiderLLMSession(default_model="gemini-3.0-flash"), 
                    SiderLLMSession(default_model="gpt-5-mini"), 
                    SiderLLMSession(default_model="claude-4.5-haiku"), 
                    LLMSession()]
    llmclient = ToolClient([x.ask for x in llm_sessions], auto_save_tokens=True)
    return llmclient

llmclient = init()

from ga import GenericAgentHandler, smart_format, get_global_memory

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

if "last_goal" not in st.session_state:
    st.session_state.last_goal = ""

def agent_backend_stream(raw_query):
    history = st.session_state.get("last_history", [])
    rquery = smart_format(raw_query.replace('\n', ' '), max_str_len=200)
    history.append(f"[USER]: {rquery}")

    sys_prompt = get_system_prompt()
    handler = GenericAgentHandler(None, history, './temp')
    llmclient.last_tools = ''   
    llmclient.raw_api = llmclient.raw_apis[st.session_state.get("llm_no", 0)]
    ret = yield from agent_runner_loop(llmclient,
        sys_prompt, raw_query, handler,
        TOOLS_SCHEMA, max_turns=25)
    st.session_state.last_history = handler.history_info
    return ret

st.title("🖥️ Cowork")

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

with st.sidebar:
    current_idx = st.session_state.get("llm_no", 0)
    st.caption(f"LLM Core: {current_idx}")
    if st.button("切换备用链路"):
        st.session_state.llm_no = (st.session_state.get("llm_no", 0) + 1) % len(llmclient.raw_apis)
        st.rerun()

if prompt := st.chat_input("请输入指令"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = ""
        for chunk in agent_backend_stream(prompt):
            full_response += chunk
            message_placeholder.markdown(full_response + "▌")
        message_placeholder.markdown(full_response)
    st.session_state.messages.append({"role": "assistant", "content": full_response})