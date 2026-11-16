from langgraph.graph import END, START, StateGraph

from app.agent.nodes import analyze_query, execute_tools, plan_tools, synthesize
from app.agent.state import AgentState
from app.llm import LLMClient


def build_graph(llm: LLMClient, tools: dict):
    graph = StateGraph(AgentState)
    graph.add_node("analyze", lambda state: analyze_query(state, llm))
    graph.add_node("plan", lambda state: plan_tools(state, llm))
    graph.add_node("execute", lambda state: execute_tools(state, tools))
    graph.add_node("synthesize", lambda state: synthesize(state, llm))
    graph.add_edge(START, "analyze")
    graph.add_edge("analyze", "plan")
    graph.add_edge("plan", "execute")
    graph.add_edge("execute", "synthesize")
    graph.add_edge("synthesize", END)
    return graph.compile()