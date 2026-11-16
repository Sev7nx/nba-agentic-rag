from app.agent.graph import build_graph
from app.tools.base import SearchResult


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


def test_execute_tools_skips_invalid_output(fake_llm, fake_tools):
    fake_llm.payload["plan"] = [{"tool": "search_news", "query": "x", "reason": "r"}]
    fake_tools["search_news"] = lambda q: "not a list"
    graph = build_graph(fake_llm, fake_tools)
    out = graph.invoke({"question": "x", "history": [], "profile": {}, "rounds": 0})
    assert "没找到" in out["answer"]


def test_graph_limits_fetch_page_calls(fake_llm, fake_tools):
    fake_llm.payload["plan"] = [
        {"tool": "fetch_page", "query": "https://example.com", "reason": "r"}
    ] * 4
    calls = []

    def fake_fetch(query):
        calls.append(query)
        return [
            SearchResult(
                title="t",
                url="https://example.com",
                site="example",
                snippet="s",
                result_type="doc",
            )
        ]

    fake_tools["fetch_page"] = fake_fetch
    graph = build_graph(fake_llm, fake_tools)
    graph.invoke({"question": "x", "history": [], "profile": {}, "rounds": 0})
    assert len(calls) == 2


def test_execute_tools_runs_in_parallel(fake_llm, fake_tools):
    import threading

    barrier = threading.Barrier(2, timeout=1)

    def tool(query):
        barrier.wait()
        return [
            SearchResult(
                title=query,
                url=f"https://example.com/{query}",
                site="example",
                snippet="s",
                result_type="doc",
            )
        ]

    fake_tools["local_rag"] = tool
    fake_tools["search_news"] = tool
    fake_llm.payload["plan"] = [
        {"tool": "local_rag", "query": "a", "reason": "r"},
        {"tool": "search_news", "query": "b", "reason": "r"},
    ]
    graph = build_graph(fake_llm, fake_tools)
    out = graph.invoke({"question": "x", "history": [], "profile": {}, "rounds": 0})
    assert len(out["tool_results"]) == 2


def test_execute_tools_records_duration(fake_llm, fake_tools):
    import time

    def slow(query):
        time.sleep(0.02)
        return [
            SearchResult(
                title="t",
                url="https://example.com",
                site="example",
                snippet="s",
                result_type="doc",
            )
        ]

    fake_tools["local_rag"] = slow
    fake_llm.payload["plan"] = [{"tool": "local_rag", "query": "x", "reason": "r"}]
    graph = build_graph(fake_llm, fake_tools)
    out = graph.invoke({"question": "x", "history": [], "profile": {}, "rounds": 0})
    steps = [step for step in out["trace"] if step["name"] == "local_rag"]
    assert steps and steps[0]["duration_ms"] >= 10


def test_out_of_scope_skips_tools(fake_llm, fake_tools):
    calls = []
    fake_tools["local_rag"] = lambda q: calls.append(q) or []
    fake_tools["search_news"] = lambda q: calls.append(q) or []
    fake_llm.payload["in_scope"] = False
    graph = build_graph(fake_llm, fake_tools)
    out = graph.invoke(
        {"question": "帮我写 Python 排序", "history": [], "profile": {}, "rounds": 0}
    )
    assert not calls
    assert "NBA" in out["answer"]


def test_ambiguous_entity_asks_for_clarification(fake_llm, fake_tools):
    calls = []
    fake_tools["local_rag"] = lambda q: calls.append(q) or []
    fake_llm.payload["ambiguous"] = True
    graph = build_graph(fake_llm, fake_tools)
    out = graph.invoke(
        {"question": "库里最近怎么样", "history": [], "profile": {}, "rounds": 0}
    )
    assert not calls
    assert "哪位" in out["answer"]