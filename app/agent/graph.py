from langgraph.graph import END, START, StateGraph

from app.agent.nodes import (
    analyze_query,
    clarify,
    execute_tools,
    grade_evidence,
    plan_tools,
    refuse,
    refine_query,
    synthesize,
    verify,
)
from app.agent.state import AgentState
from app.llm import LLMClient


def route_after_verify(state: AgentState) -> str:
    if state.get("verified"):
        return END
    if (state.get("rounds") or 0) >= 1:
        return END
    return "refine"


def route_after_analyze(state: AgentState) -> str:
    analysis = state.get("analysis") or {}
    if not analysis.get("in_scope", True):
        return "refuse"
    if analysis.get("ambiguous", False):
        return "clarify"
    return "plan"


def build_graph(llm: LLMClient, tools: dict):
    graph = StateGraph(AgentState)
    graph.add_node("analyze", lambda state: analyze_query(state, llm))
    graph.add_node("refuse", refuse)
    graph.add_node("clarify", clarify)
    graph.add_node("plan", lambda state: plan_tools(state, llm))
    graph.add_node("execute", lambda state: execute_tools(state, tools))
    graph.add_node("grade", grade_evidence)
    graph.add_node("synthesize", lambda state: synthesize(state, llm))
    graph.add_node("verify", verify)
    graph.add_node("refine", refine_query)
    graph.add_edge(START, "analyze")
    graph.add_conditional_edges(
        "analyze",
        route_after_analyze,
        {"refuse": "refuse", "clarify": "clarify", "plan": "plan"},
    )
    graph.add_edge("refuse", END)
    graph.add_edge("clarify", END)
    graph.add_edge("plan", "execute")
    graph.add_edge("execute", "grade")
    graph.add_edge("grade", "synthesize")
    graph.add_edge("synthesize", "verify")
    graph.add_conditional_edges(
        "verify",
        route_after_verify,
        {"refine": "refine", END: END},
    )
    graph.add_edge("refine", "execute")
    return graph.compile()