import pytest

from app.tools.base import SearchResult


class FakeLLM:
    def __init__(self):
        self.payload = {}

    def chat_json(self, system, user, schema):
        return schema(**self.payload)

    def chat_text(self, system, user):
        return "answer [1]"


@pytest.fixture
def fake_llm():
    llm = FakeLLM()
    llm.payload = {
        "entities": ["库里"],
        "intent": "history",
        "time_sensitivity": "classic",
        "language": "zh",
        "plan": [
            {"tool": "local_rag", "query": "库里 最经典 比赛", "reason": "history"},
            {"tool": "search_news", "query": "库里 新闻", "reason": "news"},
        ],
    }
    return llm


@pytest.fixture
def fake_tools():
    return {
        "local_rag": lambda q: [
            SearchResult(
                title="库里经典比赛",
                url="https://example.com/curry",
                site="example",
                snippet="2016 年总决赛",
                result_type="doc",
            )
        ],
        "search_news": lambda q: [
            SearchResult(
                title="勇士交易消息",
                url="https://example.com/news",
                site="example",
                snippet="交易传闻",
                result_type="news",
            )
        ],
        "search_videos": lambda q: [
            SearchResult(
                title="库里集锦",
                url="https://example.com/video",
                site="example",
                snippet="集锦",
                result_type="video",
            )
        ],
        "fetch_page": lambda q: [],
    }