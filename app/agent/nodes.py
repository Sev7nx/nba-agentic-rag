from typing import Literal

from pydantic import BaseModel, Field

from app.agent.prompts import ANALYSIS_SYSTEM, PLAN_SYSTEM
from app.agent.state import AgentState
from app.llm import LLMClient

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