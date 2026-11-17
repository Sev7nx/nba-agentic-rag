from app.agent.nodes import analyze_query, plan_tools, synthesize
from app.tools.base import SearchResult


class FakeLLM:
    def __init__(self, payload):
        self.payload = payload

    def chat_json(self, system, user, schema):
        return schema(**self.payload)

    def chat_text(self, system, user):
        return "answer"


class CapturingLLM(FakeLLM):
    def __init__(self, payload):
        super().__init__(payload)
        self.user_prompts = []

    def chat_json(self, system, user, schema):
        self.user_prompts.append(user)
        return super().chat_json(system, user, schema)


class FailingLLM:
    def chat_json(self, system, user, schema):
        raise RuntimeError("llm timeout")

    def chat_text(self, system, user):
        raise RuntimeError("llm timeout")


def test_analyze_query_extracts_entity_and_intent():
    state = {"question": "库里哪场比赛最经典", "history": [], "profile": {}}
    out = analyze_query(
        state,
        FakeLLM(
            {
                "entities": ["库里"],
                "intent": "history",
                "time_sensitivity": "classic",
                "language": "zh",
            }
        ),
    )
    assert out["analysis"]["entities"] == ["库里"]


def test_plan_tools_caps_at_four():
    state = {
        "question": "x",
        "analysis": {
            "entities": [],
            "intent": "news",
            "time_sensitivity": "latest",
            "language": "zh",
        },
    }
    plan = [{"tool": "search_news", "query": "x", "reason": "r"}] * 6
    out = plan_tools(state, FakeLLM({"plan": plan}))
    assert len(out["plan"]) == 4


def test_plan_tools_rejects_unknown_tool():
    state = {
        "question": "x",
        "analysis": {
            "entities": [],
            "intent": "news",
            "time_sensitivity": "latest",
            "language": "zh",
        },
    }
    out = plan_tools(
        state,
        FakeLLM({"plan": [{"tool": "rm_rf", "query": "x", "reason": "r"}]}),
    )
    assert out["plan"] == []


def test_analysis_marks_ambiguous_entity():
    state = {"question": "格林最近怎么样", "history": [], "profile": {}}
    out = analyze_query(
        state,
        FakeLLM(
            {
                "entities": ["格林"],
                "intent": "news",
                "time_sensitivity": "latest",
                "language": "zh",
                "ambiguous": True,
            }
        ),
    )
    assert out["analysis"]["ambiguous"] is True


def test_alias_clears_ambiguous_flag():
    state = {"question": "库里最近怎么样", "history": [], "profile": {}}
    out = analyze_query(
        state,
        FakeLLM(
            {
                "entities": ["库里"],
                "intent": "news",
                "time_sensitivity": "latest",
                "language": "zh",
                "ambiguous": True,
            }
        ),
    )
    assert out["analysis"]["ambiguous"] is False


def test_analyze_query_includes_history():
    state = {
        "question": "他上一场得了多少分？",
        "history": [
            {"role": "user", "content": "库里最近怎么样？"},
            {"role": "assistant", "content": "库里状态不错 [1]"},
        ],
        "profile": {},
    }
    llm = CapturingLLM(
        {
            "entities": ["库里"],
            "intent": "stats",
            "time_sensitivity": "latest",
            "language": "zh",
        }
    )
    analyze_query(state, llm)
    assert "库里最近怎么样" in llm.user_prompts[0]


def test_analyze_query_falls_back_on_llm_error():
    state = {"question": "库里", "history": [], "profile": {}}
    out = analyze_query(state, FailingLLM())
    assert out["analysis"]["intent"] == "other"
    assert out["analysis"]["entities"] == []


def test_analyze_query_appends_trace():
    state = {"question": "库里", "history": [], "profile": {}}
    out = analyze_query(
        state,
        FakeLLM(
            {
                "entities": ["库里"],
                "intent": "history",
                "time_sensitivity": "classic",
                "language": "zh",
            }
        ),
    )
    assert out["trace"][-1]["name"] == "analyze"


def test_plan_tools_falls_back_on_llm_error():
    state = {
        "question": "库里",
        "analysis": {
            "entities": ["库里"],
            "intent": "news",
            "time_sensitivity": "latest",
            "language": "zh",
        },
        "history": [],
        "profile": {},
    }
    out = plan_tools(state, FailingLLM())
    assert {call["tool"] for call in out["plan"]} == {"local_rag", "search_news"}


def test_plan_tools_trace_contains_query():
    state = {
        "question": "勇士交易",
        "analysis": {
            "entities": ["勇士"],
            "intent": "news",
            "time_sensitivity": "latest",
            "language": "zh",
        },
        "history": [],
        "profile": {},
    }
    out = plan_tools(
        state,
        FakeLLM(
            {
                "plan": [
                    {
                        "tool": "search_news",
                        "query": "勇士交易",
                        "reason": "news",
                    }
                ]
            }
        ),
    )
    assert "勇士交易" in out["trace"][-1]["detail"]


def test_plan_tools_drops_fetch_page_without_url():
    state = {
        "question": "勇士交易",
        "analysis": {
            "entities": ["勇士"],
            "intent": "news",
            "time_sensitivity": "latest",
            "language": "zh",
        },
        "history": [],
        "profile": {},
    }
    out = plan_tools(
        state,
        FakeLLM(
            {
                "plan": [
                    {
                        "tool": "fetch_page",
                        "query": "勇士交易",
                        "reason": "news",
                    }
                ]
            }
        ),
    )
    assert out["plan"] == []


def test_tool_names_include_live_query():
    from app.agent.nodes import TOOL_NAMES

    assert "live_query" in TOOL_NAMES


def test_tool_names_include_stats_query():
    from app.agent.nodes import TOOL_NAMES

    assert "stats_query" in TOOL_NAMES


def test_plan_tools_accepts_stats_query():
    state = {
        "question": "库里本赛季场均多少分",
        "analysis": {
            "entities": ["库里"],
            "intent": "stats",
            "time_sensitivity": "latest",
            "language": "zh",
        },
        "history": [],
        "profile": {},
    }
    out = plan_tools(
        state,
        FakeLLM(
            {
                "plan": [
                    {
                        "tool": "stats_query",
                        "query": "库里 2026-27 场均",
                        "reason": "structured stats",
                    }
                ]
            }
        ),
    )
    assert out["plan"][0]["tool"] == "stats_query"


def test_plan_tools_accepts_live_query():
    state = {
        "question": "今天有什么比赛",
        "analysis": {
            "entities": [],
            "intent": "news",
            "time_sensitivity": "latest",
            "language": "zh",
        },
        "history": [],
        "profile": {},
    }
    out = plan_tools(
        state,
        FakeLLM(
            {
                "plan": [
                    {
                        "tool": "live_query",
                        "query": "今天比赛",
                        "reason": "live",
                    }
                ]
            }
        ),
    )
    assert out["plan"][0]["tool"] == "live_query"


def test_synthesize_falls_back_on_llm_error():
    state = {
        "question": "库里",
        "history": [],
        "profile": {},
        "tool_results": [
            SearchResult(
                title="t",
                url="https://example.com",
                site="x",
                snippet="s",
                result_type="doc",
            )
        ],
    }
    out = synthesize(state, FailingLLM())
    assert "[1]" in out["answer"]
    assert out["sources"]