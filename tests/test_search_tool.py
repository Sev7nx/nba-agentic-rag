from app.tools.search import NEWS_DOMAINS, VIDEO_DOMAINS, news_search, video_search


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


def test_video_search_uses_video_domains():
    provider = FakeProvider()
    video_search(provider, "库里 集锦")
    assert provider.calls[0]["domains"] == VIDEO_DOMAINS


def test_empty_results_returns_empty_list():
    assert news_search(FakeProvider(), "不存在的问题") == []


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