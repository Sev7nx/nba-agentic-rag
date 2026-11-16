from app.agent.nodes import analyze_query, plan_tools


class FakeLLM:
    def __init__(self, payload):
        self.payload = payload

    def chat_json(self, system, user, schema):
        return schema(**self.payload)

    def chat_text(self, system, user):
        return "answer"


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
    assert out["analysis"]["ambiguous"] is True