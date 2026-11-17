from app.rag.ingest import Chunk, build_doc_index
from app.tools import doc_search as doc_tool


class FakeEmbedder:
    def embed(self, texts):
        vectors = []
        for text in texts:
            if "库里" in text:
                vectors.append([1.0, 0.0, 0.0])
            elif "勇士" in text:
                vectors.append([0.0, 1.0, 0.0])
            else:
                vectors.append([0.0, 0.0, 1.0])
        return vectors


class FakeReranker:
    def rerank(self, query, texts):
        return [10.0 if "库里" in text else 1.0 for text in texts]


class FlatEmbedder:
    def embed(self, texts):
        return [[1.0, 0.0] for _ in texts]


def _index(tmp_path):
    chunks = [
        Chunk(
            id="1-0",
            text="库里 三分 绝杀",
            metadata={
                "title": "库里经典比赛",
                "url": "https://a.example/curry",
                "site": "a.example",
                "source": "a.example",
                "date": "2026-01-01",
                "doc_type": "player_intro",
            },
        ),
        Chunk(
            id="1-1",
            text="库里 冠军 勇士",
            metadata={
                "title": "库里经典比赛",
                "url": "https://a.example/curry",
                "site": "a.example",
                "source": "a.example",
                "doc_type": "player_intro",
            },
        ),
        Chunk(
            id="2-0",
            text="勇士 交易 消息",
            metadata={
                "title": "勇士新闻",
                "url": "https://b.example/warriors",
                "site": "b.example",
                "source": "b.example",
                "doc_type": "game_report",
            },
        ),
    ]
    return build_doc_index(chunks, FakeEmbedder(), tmp_path)


def test_doc_search_returns_deduped_sources(tmp_path, monkeypatch):
    collection = _index(tmp_path)
    monkeypatch.setattr(doc_tool, "get_collection", lambda: collection)
    monkeypatch.setattr(doc_tool, "get_embedder", lambda: FakeEmbedder())
    monkeypatch.setattr(doc_tool, "get_reranker", lambda: FakeReranker())

    results = doc_tool.doc_search("库里", limit=5)

    assert [result.url for result in results] == [
        "https://a.example/curry",
        "https://b.example/warriors",
    ]
    assert results[0].result_type == "doc"
    assert results[0].title == "库里经典比赛"


def test_doc_search_respects_limit(tmp_path, monkeypatch):
    collection = _index(tmp_path)
    monkeypatch.setattr(doc_tool, "get_collection", lambda: collection)
    monkeypatch.setattr(doc_tool, "get_embedder", lambda: FakeEmbedder())
    monkeypatch.setattr(doc_tool, "get_reranker", lambda: FakeReranker())

    assert len(doc_tool.doc_search("库里", limit=1)) == 1


def test_doc_search_filters_by_doc_type(tmp_path, monkeypatch):
    chunks = [
        Chunk(
            id="rules-1",
            text="三分线规则：弧线区 7.25 米，直线区 6.70 米。",
            metadata={
                "title": "三分线",
                "url": "https://rules.example/three-point",
                "doc_type": "rules",
            },
        ),
        Chunk(
            id="game-1",
            text="库里在比赛中命中 12 记三分。",
            metadata={
                "title": "库里比赛",
                "url": "https://game.example/curry",
                "doc_type": "game_report",
            },
        ),
    ]
    collection = build_doc_index(chunks, FakeEmbedder(), tmp_path)
    monkeypatch.setattr(doc_tool, "get_collection", lambda: collection)
    monkeypatch.setattr(doc_tool, "get_embedder", lambda: FakeEmbedder())
    monkeypatch.setattr(doc_tool, "get_reranker", lambda: FakeReranker())

    results = doc_tool.doc_search("三分线规则是什么", limit=5)

    assert [result.title for result in results] == ["三分线"]


def test_doc_search_prefers_entity_match(tmp_path, monkeypatch):
    chunks = [
        Chunk(
            id="other",
            text="湖人最近赢了比赛。",
            metadata={
                "title": "湖人新闻",
                "url": "https://lakers.example",
                "doc_type": "game_report",
            },
        ),
        Chunk(
            id="curry",
            text="库里砍下 56 分，命中 12 记三分。",
            metadata={
                "title": "勇士比赛",
                "url": "https://warriors.example",
                "doc_type": "game_report",
            },
        ),
    ]
    collection = build_doc_index(chunks, FlatEmbedder(), tmp_path)
    monkeypatch.setattr(doc_tool, "get_collection", lambda: collection)
    monkeypatch.setattr(doc_tool, "get_embedder", lambda: FlatEmbedder())
    monkeypatch.setattr(doc_tool, "get_reranker", lambda: FakeReranker())

    results = doc_tool.doc_search("库里哪场比赛最经典", limit=1)

    assert results[0].url == "https://warriors.example"


def test_doc_search_ranks_history_topic_over_entity_title(tmp_path, monkeypatch):
    chunks = [
        Chunk(
            id="kobe-81",
            text="Kobe Bryant scored 81 points against the Raptors in 2006.",
            metadata={
                "title": "Top Moments: Kobe Bryant drops 81 points",
                "url": "https://nba.example/kobe-81",
                "doc_type": "game_report",
            },
        ),
        Chunk(
            id="kobe-final",
            text="Kobe Bryant scored 60 points in his final game against the Jazz.",
            metadata={
                "title": "Lakers 101-96 Jazz (Apr 13, 2016) Game Recap",
                "url": "https://espn.example/kobe-final",
                "doc_type": "game_report",
            },
        ),
    ]
    collection = build_doc_index(chunks, FlatEmbedder(), tmp_path)
    monkeypatch.setattr(doc_tool, "get_collection", lambda: collection)
    monkeypatch.setattr(doc_tool, "get_embedder", lambda: FlatEmbedder())
    monkeypatch.setattr(doc_tool, "get_reranker", lambda: FakeReranker())

    results = doc_tool.doc_search("科比退役战得了多少分", limit=1)

    assert results[0].url == "https://espn.example/kobe-final"


def test_doc_search_returns_empty_when_index_missing(monkeypatch):
    def missing():
        raise ValueError("collection missing")

    monkeypatch.setattr(doc_tool, "get_collection", missing)
    assert doc_tool.doc_search("库里") == []


def test_doc_search_returns_empty_for_empty_collection(tmp_path, monkeypatch):
    collection = build_doc_index([], FakeEmbedder(), tmp_path)
    monkeypatch.setattr(doc_tool, "get_collection", lambda: collection)
    assert doc_tool.doc_search("库里") == []


def test_site_falls_back_to_url_host():
    assert doc_tool._site("https://www.espn.com/story") == "espn.com"
    assert doc_tool._site("https://a.example/x", "www.a.example") == "a.example"