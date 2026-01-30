import os, sys
if sys.stdout is None: sys.stdout = open(os.devnull, "w")
if sys.stderr is None: sys.stderr = open(os.devnull, "w")
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


import streamlit as st
import time, json, re

with open('tools_schema.json', 'r', encoding='utf-8') as f:
    TOOLS_SCHEMA = json.load(f)

st.set_page_config(page_title="Cowork", layout="wide")

from sidercall import SiderLLMSession, LLMSession, ToolClient
from agent_loop import agent_runner_loop, StepOutcome, BaseHandler

@st.cache_resource
def init():
    if not os.path.exists('temp'): os.makedirs('temp')
    mainllm = SiderLLMSession(multiturns=6)
    llmclient = ToolClient(mainllm.ask, auto_save_tokens=True)
    return llmclient

llmclient = init()

from ga import GenericAgentHandler, smart_format, get_global_memory

def get_system_prompt():
    if not os.path.exists('memory'): os.makedirs('memory')
    if not os.path.exists('memory/global_mem.txt'):
        with open('memory/global_mem.txt', 'w', encoding='utf-8') as f: f.write('')
    if not os.path.exists('memory/global_mem_insight.txt'):
        with open('memory/global_mem_insight.txt', 'w', encoding='utf-8') as f: f.write('')
    with open('sys_prompt.txt', 'r', encoding='utf-8') as f: prompt = f.read()
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