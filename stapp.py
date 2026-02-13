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

if 'autonomous_enabled' not in st.session_state:
    st.session_state.autonomous_enabled = False

@st.fragment
def render_sidebar():
    current_idx = agent.llm_no
    st.caption(f"LLM Core: {current_idx}: {agent.get_llm_name()}", help="点击切换备用链路")
    last_reply_time = st.session_state.get('last_reply_time', 0)
    if last_reply_time > 0:
        st.caption(f"空闲时间：{int(time.time()) - last_reply_time}秒", help="当超过30分钟未收到回复时，系统会自动任务")
    if st.button("切换备用链路"):
        agent.next_llm()
        st.rerun(scope="fragment")
    if st.button("强行停止任务"):
        agent.abort()
        st.toast("已发送停止信号")
    if st.button("重新注入System Prompt"):
        agent.llmclient.last_tools = ''
        st.toast("下次将重新注入System Prompt")
    
    st.divider()
    if st.button("开始空闲自主行动"):
        st.session_state.last_reply_time = int(time.time()) - 1800
        st.toast("已将上次回复时间设为1800秒前")
        st.rerun()
    if st.session_state.autonomous_enabled:
        if st.button("⏸️ 禁止自主行动"):
            st.session_state.autonomous_enabled = False
            st.toast("⏸️ 已禁止自主行动")
            st.rerun(scope="fragment")
        st.caption("🟢 自主行动运行中，会在你离开它30分钟后自动进行")
    else:
        if st.button("▶️ 允许自主行动", type="primary"):
            st.session_state.autonomous_enabled = True
            st.toast("✅ 已允许自主行动")
            st.rerun(scope="fragment")
        st.caption("🔴 自主行动已停止")
with st.sidebar: render_sidebar()


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

if st.session_state.autonomous_enabled:
    st.markdown(f"""<div id="last-reply-time" style="display:none">{st.session_state.get('last_reply_time', int(time.time()))}</div>""", unsafe_allow_html=True)

