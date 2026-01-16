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
    mainllm = SiderLLMSession(multiturns=6)
    llmclient = ToolClient(mainllm.ask, auto_save_tokens=True)
    return llmclient

llmclient = init()

from ga import GenericAgentHandler

def get_system_prompt():
    with open('sys_prompt.txt', 'r', encoding='utf-8') as f:
        return f.read()

if "last_goal" not in st.session_state:
    st.session_state.last_goal = ""

def refine_user_goal(raw_query, last_goal):
    """通过 LLM 提炼用户真实意图"""
    if not last_goal:
        return raw_query

    decide_prompt = f"""
用户之前的目标是: "{last_goal}"
用户现在输入了: "{raw_query}"

请判断：
1. 如果用户提供补充信息、或者是接续之前的任务，请输出合并后的【最终目标】。
2. 如果用户只是指出之前做法有错而非变更目标，那么请输出原目标不做修改。
3. 如果用户开启了一个完全不相关的新话题，请直接输出用户现在的输入内容。

请直接输出目标描述，不要包含任何多余的文字、解释或标点。
"""
    try:
        refined = llmclient.llm_func(decide_prompt).strip()
        return refined if refined else raw_query
    except:
        return raw_query

def agent_backend_stream(raw_query):
    final_goal = refine_user_goal(raw_query, st.session_state.last_goal)
    
    if final_goal != raw_query:
        yield f"[Goal Refined] {final_goal}\n"

    sys_prompt = get_system_prompt()
    handler = GenericAgentHandler(None, final_goal, './temp')
    llmclient.last_tools = ''   
    ret = yield from agent_runner_loop(llmclient,
        sys_prompt, raw_query, handler,
        TOOLS_SCHEMA, max_turns=25)
    st.session_state.last_goal = final_goal
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