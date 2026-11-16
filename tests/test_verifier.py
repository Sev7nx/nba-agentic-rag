from app.agent.graph import build_graph
from app.agent.nodes import grade_evidence, verify


def test_grade_evidence_dedupes_urls():
    state = {
        "tool_results": [
            {"title": "a", "url": "https://x", "site": "hupu", "snippet": "s"},
            {"title": "a2", "url": "https://x", "site": "hupu", "snippet": "s2"},
        ]
    }
    out = grade_evidence(state)
    assert len(out["evidence"]) == 1


def test_verify_fails_without_citations():
    state = {"answer": "库里很强。", "sources": []}
    assert verify(state)["verified"] is False


def test_no_sources_produces_caveat(fake_llm, fake_tools):
    empty_tools = {name: (lambda q: []) for name in fake_tools}
    graph = build_graph(fake_llm, empty_tools)
    out = graph.invoke(
        {"question": "一个没人知道的问题", "history": [], "profile": {}, "rounds": 0}
    )
    assert "没找到" in out["answer"]


def test_conflicting_sources_are_both_kept():
    state = {
        "tool_results": [
            {
                "title": "A 说交易",
                "url": "https://a",
                "site": "hupu",
                "snippet": "会交易",
                "claim": "trade",
            },
            {
                "title": "B 说不会",
                "url": "https://b",
                "site": "qq",
                "snippet": "不会交易",
                "claim": "no-trade",
            },
        ]
    }
    out = grade_evidence(state)
    assert len(out["evidence"]) == 2


def test_graph_retries_once_then_stops(fake_llm, fake_tools):
    empty_tools = {name: (lambda q: []) for name in fake_tools}
    graph = build_graph(fake_llm, empty_tools)
    out = graph.invoke({"question": "没人知道", "history": [], "profile": {}, "rounds": 0})
    assert out["rounds"] == 2
    assert out["verified"] is False