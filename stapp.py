import os, sys
if sys.stdout is None: sys.stdout = open(os.devnull, "w")
if sys.stderr is None: sys.stderr = open(os.devnull, "w")
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import streamlit as st
import time, json, re, threading
from agentmain import GeneraticAgent

st.set_page_config(page_title="Cowork", layout="wide")

@st.cache_resource
def init():
    agent = GeneraticAgent()
    if agent.llmclient is None:
        st.error("⚠️ 未配置任何可用的 LLM 接口，请在 mykey.py 中添加 sider_cookie 或 oai_apikey+oai_apibase 等信息后重启。")
        st.stop()
    else:
        threading.Thread(target=agent.run, daemon=True).start()
    return agent

agent = init()

st.title("🖥️ Cowork")

@st.fragment
def render_llm_switcher():
    current_idx = agent.llm_no
    st.caption(f"LLM Core: {current_idx}: {agent.llmclient.backends[current_idx].default_model}", help="点击切换备用链路")
    if st.button("切换备用链路"):
        agent.next_llm()
        st.rerun(scope="fragment")
    if st.button("强行停止任务"):
        agent.abort()
        st.toast("已发送停止信号")
    if st.button("重新注入System Prompt"):
        agent.llmclient.last_tools = ''
        st.toast("下次将重新注入System Prompt")
with st.sidebar: render_llm_switcher()


def agent_backend_stream(prompt):
    display_queue = agent.put_task(prompt, source="user")
    try:
        while True:
            item = display_queue.get()
            if 'next' in item: yield item['next'] 
            if 'done' in item: 
                yield item['done']; break
    finally:
        agent.abort()

if "messages" not in st.session_state: st.session_state.messages = []
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]): st.markdown(msg["content"])

if prompt := st.chat_input("请输入指令"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"): st.markdown(prompt)

    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        response = ''
        for response in agent_backend_stream(prompt):
            message_placeholder.markdown(response + "▌")
        message_placeholder.markdown(response)
    st.session_state.messages.append({"role": "assistant", "content": response})
    st.session_state.last_reply_time = int(time.time())

st.markdown(f"""<div id="last-reply-time" style="display:none">{st.session_state.get('last_reply_time', int(time.time()))}</div>""", unsafe_allow_html=True)

