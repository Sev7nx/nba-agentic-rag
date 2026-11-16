from app.agent.graph import build_graph
from app.agent.nodes import check_links, grade_evidence, verify
from app.models import Source


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


def test_grade_evidence_boosts_profile_favorites():
    state = {
        "analysis": {"entities": []},
        "profile": {"favorite_team": "勇士", "favorite_players": []},
        "tool_results": [
            {
                "title": "湖人新闻",
                "url": "https://a",
                "site": "x",
                "snippet": "湖人",
            },
            {
                "title": "勇士交易",
                "url": "https://b",
                "site": "x",
                "snippet": "勇士",
            },
        ],
    }
    out = grade_evidence(state)
    assert out["evidence"][0]["title"] == "勇士交易"


def test_graph_retries_once_then_stops(fake_llm, fake_tools):
    empty_tools = {name: (lambda q: []) for name in fake_tools}
    graph = build_graph(fake_llm, empty_tools)
    out = graph.invoke({"question": "没人知道", "history": [], "profile": {}, "rounds": 0})
    assert out["rounds"] == 1
    assert out["verified"] is False
    assert "谨慎参考" in out["answer"]


def test_check_links_marks_only_dead():
    sources = [
        Source(id=1, title="a", url="https://a.example", site="a", type="news"),
        Source(id=2, title="b", url="https://b.example", site="b", type="news"),
    ]
    checked = check_links(sources, checker=lambda url: not url.startswith("https://b"))
    assert [source.link_status for source in checked] == ["ok", "dead"]


def test_verify_fails_when_all_links_dead():
    source = Source(
        id=1,
        title="t",
        url="https://example.com",
        site="x",
        type="news",
        link_status="dead",
    )
    state = {"answer": "answer [1]", "sources": [source]}
    assert verify(state)["verified"] is False


def test_dead_link_is_marked(monkeypatch, fake_llm, fake_tools):
    monkeypatch.setattr("app.agent.nodes.is_link_alive", lambda url: False)
    graph = build_graph(fake_llm, fake_tools)
    out = graph.invoke(
        {"question": "库里", "history": [], "profile": {}, "rounds": 0}
    )
    assert out["sources"]
    assert all(source.link_status == "dead" for source in out["sources"])


def test_synthesize_prompt_mentions_conflict(fake_tools):
    class CapturingLLM:
        def __init__(self):
            self.system_prompts = []

        def chat_json(self, system, user, schema):
            return schema(
                **{
                    "plan": [
                        {"tool": "local_rag", "query": "x", "reason": "r"}
                    ],
                    "entities": [],
                    "intent": "news",
                    "time_sensitivity": "latest",
                    "language": "zh",
                }
            )

        def chat_text(self, system, user):
            self.system_prompts.append(system)
            return "answer [1]"

    llm = CapturingLLM()
    graph = build_graph(llm, fake_tools)
    graph.invoke({"question": "x", "history": [], "profile": {}, "rounds": 0})
    assert "冲突" in llm.system_prompts[0]