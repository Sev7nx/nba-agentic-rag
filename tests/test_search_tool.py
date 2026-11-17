from app.tools.base import SearchResult
from app.tools.search import (
    BILIBILI_DOMAINS,
    NEWS_DOMAINS,
    YOUTUBE_DOMAINS,
    news_search,
    video_search,
)


class FakeProvider:
    def __init__(self):
        self.calls = []

    def search(self, query, include_domains, max_results=5, topic="general"):
        self.calls.append({"query": query, "domains": include_domains, "topic": topic})
        return []


def test_news_search_uses_news_domains():
    provider = FakeProvider()
    news_search(provider, "勇士 交易")
    assert provider.calls[0]["domains"] == NEWS_DOMAINS


def test_video_search_prefers_bilibili():
    class Provider:
        def __init__(self):
            self.calls = []

        def search(self, query, include_domains, max_results=5, topic="general"):
            self.calls.append(include_domains)
            if include_domains == BILIBILI_DOMAINS:
                return [
                    SearchResult(
                        title="b",
                        url="https://www.bilibili.com/video/BV1",
                        site="bilibili.com",
                        result_type="video",
                    )
                ]
            return []

    provider = Provider()
    results = video_search(provider, "库里 集锦")
    assert provider.calls == [BILIBILI_DOMAINS]
    assert results[0].site == "bilibili.com"


def test_video_search_falls_back_to_youtube():
    class Provider:
        def __init__(self):
            self.calls = []

        def search(self, query, include_domains, max_results=5, topic="general"):
            self.calls.append(include_domains)
            if include_domains == YOUTUBE_DOMAINS:
                return [
                    SearchResult(
                        title="y",
                        url="https://www.youtube.com/watch?v=x",
                        site="youtube.com",
                        result_type="video",
                    )
                ]
            return []

    provider = Provider()
    results = video_search(provider, "库里 集锦")
    assert provider.calls == [BILIBILI_DOMAINS, YOUTUBE_DOMAINS]
    assert results[0].site == "youtube.com"


def test_news_search_keeps_non_title_entity_matches():
    class Provider:
        def search(self, *args, **kwargs):
            return [
                SearchResult(
                    title="Kuminga trade rumor",
                    url="https://www.espn.com/nba/story/_/id/1",
                    site="espn.com",
                    snippet="The Golden State Warriors are exploring options.",
                    result_type="news",
                ),
                SearchResult(
                    title="Warriors trade update",
                    url="https://www.espn.com/nba/story/_/id/2",
                    site="espn.com",
                    snippet="Latest update.",
                    result_type="news",
                ),
            ]

    results = news_search(Provider(), "勇士交易")
    assert len(results) == 2
    assert results[0].title == "Warriors trade update"


def test_video_search_orders_entity_matches():
    class Provider:
        def search(self, *args, **kwargs):
            return [
                SearchResult(
                    title="科比经典比赛集锦",
                    url="https://www.bilibili.com/video/BV2",
                    site="bilibili.com",
                    snippet="相关内容提到库里",
                    result_type="video",
                ),
                SearchResult(
                    title="库里绝杀集锦",
                    url="https://www.bilibili.com/video/BV1",
                    site="bilibili.com",
                    result_type="video",
                ),
            ]

    results = video_search(Provider(), "库里 经典 集锦")
    assert [result.title for result in results] == ["库里绝杀集锦"]


def test_empty_results_returns_empty_list():
    assert news_search(FakeProvider(), "不存在的问题") == []


def test_news_search_filters_non_nba_espn():
    class Provider:
        def search(self, *args, **kwargs):
            return [
                SearchResult(
                    title="NFL story",
                    url="https://www.espn.com/nfl/news/story?id=1",
                    site="espn.com",
                    result_type="news",
                ),
                SearchResult(
                    title="NBA story",
                    url="https://www.espn.com/nba/story/_/id/1",
                    site="espn.com",
                    result_type="news",
                ),
            ]

    results = news_search(Provider(), "勇士")
    assert len(results) == 1
    assert "/nba/" in results[0].url


def test_provider_error_returns_empty_list(monkeypatch):
    class BrokenProvider:
        def search(self, *args, **kwargs):
            raise RuntimeError("network down")

    assert news_search(BrokenProvider(), "x") == []


def test_tavily_provider_maps_results():
    from app.tools.search import TavilySearchProvider

    class FakeClient:
        def search(self, **kwargs):
            return {
                "results": [
                    {
                        "title": "t",
                        "url": "https://bbs.hupu.com/1",
                        "content": "s",
                        "published_date": "2026-11-01",
                    }
                ]
            }

    provider = TavilySearchProvider("key", client=FakeClient())
    results = provider.search("q", include_domains=["hupu.com"], topic="news")
    assert results[0].title == "t"
    assert results[0].url == "https://bbs.hupu.com/1"
    assert results[0].site == "bbs.hupu.com"
    assert results[0].result_type == "news"


def test_tavily_provider_uses_basic_depth():
    from app.tools.search import TavilySearchProvider

    class FakeClient:
        def __init__(self):
            self.kwargs = None

        def search(self, **kwargs):
            self.kwargs = kwargs
            return {"results": []}

    client = FakeClient()
    provider = TavilySearchProvider("key", client=client)
    provider.search("q", include_domains=["bilibili.com"])
    assert client.kwargs["search_depth"] == "basic"