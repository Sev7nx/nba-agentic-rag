from typing import TypedDict


class AgentState(TypedDict, total=False):
    question: str
    history: list[dict]
    profile: dict
    analysis: dict
    plan: list[dict]
    tool_results: list[dict]
    evidence: list[dict]
    answer: str
    sources: list[dict]
    trace: list[dict]
    rounds: int
    verified: bool