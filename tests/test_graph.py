from app.agent.graph import build_graph


def test_graph_runs_with_fake_tools(fake_llm, fake_tools):
    graph = build_graph(fake_llm, fake_tools)
    out = graph.invoke({"question": "库里最经典的比赛", "history": [], "profile": {}, "rounds": 0})
    assert "answer" in out["answer"]
    assert len(out["sources"]) == 2


def test_execute_tools_skips_failed_tool(fake_llm, fake_tools):
    fake_llm.payload["plan"] = [{"tool": "search_news", "query": "勇士交易", "reason": "news"}]
    fake_tools["search_news"] = lambda q: (_ for _ in ()).throw(RuntimeError("down"))
    graph = build_graph(fake_llm, fake_tools)
    out = graph.invoke({"question": "勇士交易", "history": [], "profile": {}, "rounds": 0})
    assert "没找到" in out["answer"]


def test_graph_respects_max_tool_calls(fake_llm, fake_tools):
    fake_llm.payload["plan"] = [
        {"tool": "local_rag", "query": "x", "reason": "r"}
    ] * 6
    graph = build_graph(fake_llm, fake_tools)
    out = graph.invoke({"question": "x", "history": [], "profile": {}, "rounds": 0})
    assert len(out.get("tool_results", [])) == 4