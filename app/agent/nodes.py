import re
from typing import Literal

from pydantic import BaseModel, Field

from app.agent.prompts import ANALYSIS_SYSTEM, PLAN_SYSTEM
from app.agent.state import AgentState
from app.llm import LLMClient
from app.models import Source
from app.tools.base import SearchResult

TOOL_NAMES = {"local_rag", "search_news", "search_videos", "fetch_page"}


class Analysis(BaseModel):
    entities: list[str] = Field(default_factory=list)
    intent: str = "other"
    time_sensitivity: Literal["latest", "classic", "none"] = "none"
    language: Literal["zh", "en"] = "zh"
    ambiguous: bool = False


class ToolCall(BaseModel):
    tool: str
    query: str
    reason: str


class Plan(BaseModel):
    plan: list[ToolCall] = Field(default_factory=list)


def _profile_text(state: AgentState) -> str:
    profile = state.get("profile") or {}
    team = profile.get("favorite_team") or ""
    players = ", ".join(profile.get("favorite_players") or [])
    return f"主队: {team}; 喜欢的球员: {players}"


def analyze_query(state: AgentState, llm: LLMClient) -> dict:
    user = f"问题: {state['question']}\n用户偏好: {_profile_text(state)}"
    analysis = llm.chat_json(ANALYSIS_SYSTEM, user, Analysis)
    return {"analysis": analysis.model_dump()}


def plan_tools(state: AgentState, llm: LLMClient) -> dict:
    analysis = state.get("analysis") or {}
    user = (
        f"问题: {state['question']}\n"
        f"分析: {analysis}\n"
        f"用户偏好: {_profile_text(state)}\n"
        f"可用工具: {sorted(TOOL_NAMES)}"
    )
    plan = llm.chat_json(PLAN_SYSTEM, user, Plan)
    calls = [call.model_dump() for call in plan.plan if call.tool in TOOL_NAMES][:4]
    return {"plan": calls}


def execute_tools(state: AgentState, tools: dict) -> dict:
    results: list[SearchResult] = []
    trace = list(state.get("trace") or [])
    for call in (state.get("plan") or [])[:4]:
        name = call.get("tool", "")
        func = tools.get(name)
        if func is None:
            continue
        try:
            output = func(call.get("query", "")) or []
        except Exception as exc:
            trace.append({"name": name, "detail": f"error: {exc}", "duration_ms": 0})
            continue
        results.extend(output)
        trace.append({"name": name, "detail": f"{len(output)} results", "duration_ms": 0})
    return {"tool_results": results, "trace": trace}


def synthesize(state: AgentState, llm: LLMClient) -> dict:
    evidence = state.get("evidence") or state.get("tool_results") or []
    if not evidence:
        return {"answer": "没找到可靠来源，试试换个问法。", "sources": []}

    sources: list[Source] = []
    for index, item in enumerate(evidence, start=1):
        data = item.model_dump() if hasattr(item, "model_dump") else item
        sources.append(
            Source(
                id=index,
                title=data.get("title", ""),
                url=data.get("url", ""),
                site=data.get("site", ""),
                date=data.get("published_date"),
                type=data.get("result_type", "doc"),
                snippet=data.get("snippet"),
            )
        )

    context = "\n".join(
        f"[{source.id}] {source.title}: {source.snippet or ''}" for source in sources[:6]
    )
    answer = llm.chat_text(
        "你是 NBA 问答助手。只根据给定来源回答，关键事实后标注 [n]。没有来源就说没找到。",
        f"问题: {state['question']}\n来源:\n{context}",
    )
    return {"answer": answer, "sources": sources}


SOURCE_QUALITY = {
    "nba.com": 1.0,
    "espn.com": 0.9,
    "sports.qq.com": 0.8,
    "hupu.com": 0.7,
    "bilibili.com": 0.6,
    "youtube.com": 0.6,
}


def _as_dict(item) -> dict:
    return item.model_dump() if hasattr(item, "model_dump") else item


def _quality(url: str) -> float:
    for domain, score in SOURCE_QUALITY.items():
        if domain in url:
            return score
    return 0.5


def grade_evidence(state: AgentState) -> dict:
    seen: set[str] = set()
    ranked: list[tuple[float, dict]] = []
    entities = (state.get("analysis") or {}).get("entities", [])
    for item in state.get("tool_results") or []:
        data = _as_dict(item)
        url = data.get("url", "")
        if not url or url in seen:
            continue
        seen.add(url)
        text = f"{data.get('title', '')} {data.get('snippet', '')}"
        entity_bonus = 0.1 if any(entity in text for entity in entities) else 0.0
        recency_bonus = 0.05 if data.get("published_date") else 0.0
        ranked.append((_quality(url) + entity_bonus + recency_bonus, data))
    ranked.sort(key=lambda item: item[0], reverse=True)
    return {"evidence": [data for _, data in ranked[:8]]}


def verify(state: AgentState) -> dict:
    answer = (state.get("answer") or "").strip()
    sources = state.get("sources") or []
    if not answer:
        return {"verified": False, "verification_notes": "empty answer"}
    if not sources:
        return {"verified": False, "verification_notes": "no sources"}
    if not re.search(r"\[\d+\]", answer):
        return {"verified": False, "verification_notes": "no inline citations"}
    return {"verified": True, "verification_notes": "ok"}


def refine_query(state: AgentState) -> dict:
    rounds = (state.get("rounds") or 0) + 1
    refined = [
        {
            "tool": call.get("tool", ""),
            "query": f"{call.get('query', '')} 最新 详细",
            "reason": "retry with broader query",
        }
        for call in (state.get("plan") or [])[:4]
    ]
    return {"rounds": rounds, "plan": refined}