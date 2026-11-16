import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import httpx
import streamlit as st

from app.models import ChatEvent, Source, TraceStep
from app.ui.components import format_api_error, parse_sse, render_sources, render_trace

st.set_page_config(page_title="NBA Scout", page_icon="🏀", layout="wide")

api_url = os.getenv("API_URL", "http://localhost:8000")

if "messages" not in st.session_state:
    st.session_state.messages = []
if "profile" not in st.session_state:
    st.session_state.profile = {"favorite_team": None, "favorite_players": []}

with st.sidebar:
    st.header("我的偏好")
    api_url = st.text_input("FastAPI 地址", value=api_url)
    teams = ["", "勇士", "湖人", "凯尔特人", "掘金", "雄鹿", "太阳", "独行侠"]
    team = st.selectbox("主队", teams, index=0)
    players = st.multiselect(
        "喜欢的球员",
        ["库里", "詹姆斯", "约基奇", "字母哥", "东契奇", "塔图姆", "杜兰特"],
    )
    st.session_state.profile = {
        "favorite_team": team or None,
        "favorite_players": players,
    }
    st.caption("偏好会影响检索排序，不会推送。")

st.title("NBA Scout")
st.caption("问一句，帮你去虎扑、腾讯体育、B站和本地知识库里找答案，并附上可点的链接。")

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message.get("sources"):
            st.markdown(render_sources(message["sources"]), unsafe_allow_html=True)

if question := st.chat_input("问一个 NBA 问题，比如：库里哪场比赛最经典？"):
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    payload = {
        "question": question,
        "history": st.session_state.messages[:-1][-10:],
        "profile": st.session_state.profile,
    }
    answer = ""
    sources: list[Source] = []
    trace: list[TraceStep] = []

    with st.chat_message("assistant"):
        placeholder = st.empty()
        try:
            with httpx.stream(
                "POST",
                f"{api_url.rstrip('/')}/api/chat/stream",
                json=payload,
                timeout=60.0,
            ) as response:
                response.raise_for_status()
                for event in parse_sse(response.iter_lines()):
                    if event.type == "token":
                        answer += event.data.get("text", "")
                        placeholder.markdown(answer)
                    elif event.type == "sources":
                        sources = [
                            Source(**item) for item in event.data.get("sources", [])
                        ]
                    elif event.type == "trace":
                        trace = [
                            TraceStep(**item) for item in event.data.get("trace", [])
                        ]
                    elif event.type == "error":
                        st.error(
                            format_api_error(
                                RuntimeError(event.data.get("message", ""))
                            )
                        )
        except Exception as exc:
            st.error(format_api_error(exc))

        if not answer and not sources:
            st.info("没找到可靠来源，试试换个问法。")
        if sources:
            st.markdown(render_sources(sources), unsafe_allow_html=True)
        with st.expander("调试轨迹"):
            st.markdown(render_trace(trace))

    st.session_state.messages.append(
        {"role": "assistant", "content": answer, "sources": sources}
    )