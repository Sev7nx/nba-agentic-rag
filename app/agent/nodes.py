import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Literal

from pydantic import BaseModel, Field

from app.agent.prompts import ANALYSIS_SYSTEM, PLAN_SYSTEM
from app.agent.state import AgentState
from app.llm import LLMClient
from app.models import Source
from app.tools.base import SearchResult
from app.tools.fetch import is_link_alive

TOOL_NAMES = {"local_rag", "search_news", "search_videos", "fetch_page", "live_query"}


class Analysis(BaseModel):
    entities: list[str] = Field(default_factory=list)
    intent: str = "other"
    time_sensitivity: Literal["latest", "classic", "none"] = "none"
    language: Literal["zh", "en"] = "zh"
    ambiguous: bool = False
    in_scope: bool = True


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


def _history_text(state: AgentState) -> str:
    history = state.get("history") or []
    return "\n".join(
        f"{turn.get('role', 'user')}: {turn.get('content', '')}"
        for turn in history[-4:]
    )


def _append_trace(
    state: AgentState,
    name: str,
    detail: str,
    duration_ms: int,
    tokens: int = 0,
    cost_cny: float = 0.0,
) -> list[dict]:
    trace = list(state.get("trace") or [])
    trace.append(
        {
            "name": name,
            "detail": detail,
            "duration_ms": duration_ms,
            "tokens": tokens,
            "cost_cny": cost_cny,
        }
    )
    return trace


def analyze_query(state: AgentState, llm: LLMClient) -> dict:
    user = (
        f"历史对话:\n{_history_text(state)}\n"
        f"问题: {state['question']}\n用户偏好: {_profile_text(state)}"
    )
    start = time.perf_counter()
    try:
        analysis = llm.chat_json(ANALYSIS_SYSTEM, user, Analysis)
    except Exception:
        analysis = Analysis(intent="other")
    duration_ms = int((time.perf_counter() - start) * 1000)
    usage = getattr(llm, "last_usage", {}) or {}
    return {
        "analysis": analysis.model_dump(),
        "trace": _append_trace(
            state,
            "analyze",
            analysis.intent,
            duration_ms,
            usage.get("tokens", 0),
            usage.get("cost_cny", 0.0),
        ),
    }


def plan_tools(state: AgentState, llm: LLMClient) -> dict:
    analysis = state.get("analysis") or {}
    user = (
        f"历史对话:\n{_history_text(state)}\n"
        f"问题: {state['question']}\n"
        f"分析: {analysis}\n"
        f"用户偏好: {_profile_text(state)}\n"
        f"可用工具: {sorted(TOOL_NAMES)}"
    )
    start = time.perf_counter()
    try:
        plan = llm.chat_json(PLAN_SYSTEM, user, Plan)
        calls = [
        call.model_dump()
        for call in plan.plan
        if call.tool in TOOL_NAMES
        and (
            call.tool != "fetch_page"
            or call.query.strip().startswith(("http://", "https://"))
        )
    ][:4]
    except Exception:
        calls = [
            {
                "tool": "local_rag",
                "query": state["question"],
                "reason": "llm_fallback",
            },
            {
                "tool": "search_news",
                "query": state["question"],
                "reason": "llm_fallback",
            },
        ]
    duration_ms = int((time.perf_counter() - start) * 1000)
    usage = getattr(llm, "last_usage", {}) or {}
    detail = " | ".join(
        f"{call['tool']}：{call['query'][:40]}" for call in calls
    ) or "0 tools"
    return {
        "plan": calls,
        "trace": _append_trace(
            state,
            "plan",
            detail,
            duration_ms,
            usage.get("tokens", 0),
            usage.get("cost_cny", 0.0),
        ),
    }


def refuse(state: AgentState) -> dict:
    return {
        "answer": "我只能回答 NBA 相关问题。你可以问球员、球队、比赛、新闻或集锦。",
        "sources": [],
        "verified": True,
        "trace": _append_trace(state, "refuse", "out_of_scope", 0),
    }


def clarify(state: AgentState) -> dict:
    entities = (state.get("analysis") or {}).get("entities", [])
    name = entities[0] if entities else "这个球员"
    return {
        "answer": f"你指的是哪位{name}？请补充完整姓名或球队，我再帮你查。",
        "sources": [],
        "verified": True,
        "trace": _append_trace(state, "clarify", "ambiguous_entity", 0),
    }


def execute_tools(state: AgentState, tools: dict) -> dict:
    results: list[SearchResult] = list(state.get("tool_results") or [])
    trace = list(state.get("trace") or [])
    filtered: list[dict] = []
    fetch_count = 0
    for call in (state.get("plan") or [])[:4]:
        if call.get("tool") == "fetch_page":
            if fetch_count >= 2:
                continue
            fetch_count += 1
        filtered.append(call)

    def run(call: dict):
        name = call.get("tool", "")
        func = tools.get(name)
        if func is None:
            return name, None, None, 0
        start = time.perf_counter()
        try:
            output = func(call.get("query", "")) or []
        except Exception as exc:
            return name, None, str(exc), int((time.perf_counter() - start) * 1000)
        duration_ms = int((time.perf_counter() - start) * 1000)
        if not isinstance(output, list):
            return name, None, "invalid output type", duration_ms
        return name, output, None, duration_ms

    if not filtered:
        return {"tool_results": results, "trace": trace}

    with ThreadPoolExecutor(max_workers=min(4, len(filtered))) as pool:
        futures = [pool.submit(run, call) for call in filtered]
        for future in as_completed(futures):
            name, output, error, duration_ms = future.result()
            if error:
                trace.append(
                    {
                        "name": name,
                        "detail": f"error: {error}",
                        "duration_ms": duration_ms,
                        "tokens": 0,
                        "cost_cny": 0.0,
                    }
                )
                continue
            if output is None:
                continue
            results.extend(output)
            trace.append(
                {
                    "name": name,
                    "detail": f"{len(output)} results",
                    "duration_ms": duration_ms,
                    "tokens": 0,
                    "cost_cny": 0.0,
                }
            )
    return {"tool_results": results, "trace": trace}


def check_links(sources: list[Source], checker=None) -> list[Source]:
    if not sources:
        return []
    check = checker or is_link_alive
    with ThreadPoolExecutor(max_workers=min(4, len(sources))) as pool:
        statuses = list(pool.map(lambda source: check(source.url), sources))
    for source, alive in zip(sources, statuses):
        source.link_status = "ok" if alive else "dead"
    return sources


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
    sources = check_links(sources)

    context = "\n".join(
        f"[{source.id}] {source.title}: {source.snippet or ''}" for source in sources[:6]
    )
    start = time.perf_counter()
    try:
        answer = llm.chat_text(
            "你是 NBA 问答助手。只根据给定来源回答，关键事实后标注 [n]。如果来源之间冲突，必须同时呈现双方，不要只给一个结论。没有来源就说没找到。",
            f"历史对话:\n{_history_text(state)}\n"
            f"问题: {state['question']}\n来源:\n{context}",
        )
    except Exception:
        answer = (
            "模型暂时不可用，先列出检索到的来源："
            + "；".join(f"[{source.id}] {source.title}" for source in sources[:3])
            + "。"
        )
    duration_ms = int((time.perf_counter() - start) * 1000)
    usage = getattr(llm, "last_usage", {}) or {}
    return {
        "answer": answer,
        "sources": sources,
        "trace": _append_trace(
            state,
            "synthesize",
            f"{len(sources)} sources",
            duration_ms,
            usage.get("tokens", 0),
            usage.get("cost_cny", 0.0),
        ),
    }


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
    profile = state.get("profile") or {}
    favorites = [
        value
        for value in [
            profile.get("favorite_team"),
            *(profile.get("favorite_players") or []),
        ]
        if value
    ]
    for item in state.get("tool_results") or []:
        data = _as_dict(item)
        url = data.get("url", "")
        if not url or url in seen:
            continue
        seen.add(url)
        text = f"{data.get('title', '')} {data.get('snippet', '')}"
        entity_bonus = 0.1 if any(entity in text for entity in entities) else 0.0
        recency_bonus = 0.05 if data.get("published_date") else 0.0
        profile_bonus = 0.1 if any(favorite in text for favorite in favorites) else 0.0
        ranked.append(
            (_quality(url) + entity_bonus + recency_bonus + profile_bonus, data)
        )
    ranked.sort(key=lambda item: item[0], reverse=True)
    return {"evidence": [data for _, data in ranked[:8]]}


def verify(state: AgentState) -> dict:
    answer = (state.get("answer") or "").strip()
    sources = state.get("sources") or []
    caveat = "（提示：部分来源或自检未通过，请谨慎参考。）"

    def fail(note: str) -> dict:
        if caveat not in answer:
            answer_with_caveat = f"{answer}{caveat}".strip()
        else:
            answer_with_caveat = answer
        return {
            "verified": False,
            "verification_notes": note,
            "answer": answer_with_caveat,
            "trace": _append_trace(state, "verify", note, 0),
        }

    if not answer:
        return fail("empty answer")
    if not sources:
        return fail("no sources")
    if not re.search(r"\[\d+\]", answer):
        return fail("no inline citations")
    alive = [
        source
        for source in sources
        if (
            source.get("link_status", "ok")
            if isinstance(source, dict)
            else getattr(source, "link_status", "ok")
        )
        != "dead"
    ]
    if not alive:
        return fail("all links dead")
    return {
        "verified": True,
        "verification_notes": "ok",
        "trace": _append_trace(state, "verify", "ok", 0),
    }


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
    return {
        "rounds": rounds,
        "plan": refined,
        "trace": _append_trace(state, "refine", f"round {rounds}", 0),
    }