from app.tools.base import SearchResult
from scripts.fetch_docs import fetch_documents


def test_fetch_documents_dedupes_and_filters():
    def search(query, domains, max_results, topic):
        return [
            SearchResult(
                title="Hupu Game Recap",
                url="https://bbs.hupu.com/1.html",
                site="hupu.com",
                snippet="",
                result_type="news",
            ),
            SearchResult(
                title="ESPN NFL",
                url="https://www.espn.com/nfl/story/1",
                site="espn.com",
                snippet="",
                result_type="news",
            ),
            SearchResult(
                title="ESPN NBA Game Recap",
                url="https://www.espn.com/nba/story/1",
                site="espn.com",
                snippet="",
                result_type="news",
            ),
            SearchResult(
                title="Hupu duplicate",
                url="https://bbs.hupu.com/1.html",
                site="hupu.com",
                snippet="",
                result_type="news",
            ),
        ]

    def extract(urls):
        return {url: f"content for {url}" for url in urls}

    queries = [
        {
            "doc_type": "game_report",
            "query": "q",
            "domains": ["hupu.com", "espn.com"],
            "topic": "news",
        }
    ]
    docs = fetch_documents(search, extract, queries, max_docs=10, pause=0)

    assert len(docs) == 2
    urls = {doc["url"] for doc in docs}
    assert "https://bbs.hupu.com/1.html" in urls
    assert "https://www.espn.com/nba/story/1" in urls
    assert "https://www.espn.com/nfl/story/1" not in urls
    assert all(doc["doc_type"] == "game_report" for doc in docs)
    assert all(doc["text"].startswith("content for") for doc in docs)


def test_fetch_documents_stops_at_max_docs():
    def search(query, domains, max_results, topic):
        return [
            SearchResult(
                title=f"Game Recap {i}",
                url=f"https://bbs.hupu.com/{i}.html",
                site="hupu.com",
                snippet="",
                result_type="news",
            )
            for i in range(5)
        ]

    def extract(urls):
        return {url: f"content for {url}" for url in urls}

    queries = [
        {
            "doc_type": "game_report",
            "query": "q",
            "domains": ["hupu.com"],
            "topic": "news",
        }
    ]
    docs = fetch_documents(search, extract, queries, max_docs=2, pause=0)
    assert len(docs) == 2


def test_fetch_documents_skips_empty_extract():
    def search(query, domains, max_results, topic):
        return [
            SearchResult(
                title="Game Recap",
                url="https://bbs.hupu.com/1.html",
                site="hupu.com",
                snippet="",
                result_type="news",
            )
        ]

    def extract(urls):
        return {}

    queries = [
        {
            "doc_type": "game_report",
            "query": "q",
            "domains": ["hupu.com"],
            "topic": "news",
        }
    ]
    assert fetch_documents(search, extract, queries, pause=0) == []


def test_fetch_documents_filters_low_quality_game_pages():
    def search(query, domains, max_results, topic):
        return [
            SearchResult(
                title="How to watch NBA",
                url="https://www.espn.com/nba/story/1",
                site="espn.com",
                snippet="",
                result_type="news",
            ),
            SearchResult(
                title="Collection",
                url="https://www.espn.com/nba/story/2",
                site="espn.com",
                snippet="",
                result_type="news",
            ),
        ]

    def extract(urls):
        return {url: "content" for url in urls}

    queries = [
        {
            "doc_type": "game_report",
            "query": "q",
            "domains": ["espn.com"],
            "topic": "news",
        }
    ]
    assert fetch_documents(search, extract, queries, pause=0) == []


def test_fetch_documents_filters_wrong_player():
    def search(query, domains, max_results, topic):
        return [
            SearchResult(
                title="尼古拉斯·凯奇",
                url="https://baike.baidu.com/item/1",
                site="baike.baidu.com",
                snippet="",
                result_type="doc",
            )
        ]

    def extract(urls):
        return {url: "一个演员" for url in urls}

    queries = [
        {
            "doc_type": "player_intro",
            "query": "约基奇",
            "domains": ["baike.baidu.com"],
            "topic": "general",
            "entity_aliases": ["约基奇", "Jokic"],
        }
    ]
    assert fetch_documents(search, extract, queries, pause=0) == []