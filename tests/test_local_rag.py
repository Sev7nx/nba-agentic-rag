from app.tools.local_rag import local_rag


class FakeEmbedder:
    def embed(self, texts):
        return [[1.0, 0.0] for _ in texts]


class FakeReranker:
    def rerank(self, query, texts):
        return [float(len(t)) for t in texts]


def test_local_rag_returns_top_n(monkeypatch, tmp_path):
    from app.rag.ingest import Chunk, build_index

    chunks = [
        Chunk(id="1", text="库里 三分", metadata={"title": "a", "url": "https://a", "site": "x"}),
        Chunk(id="2", text="库里 冠军", metadata={"title": "b", "url": "https://b", "site": "x"}),
        Chunk(id="3", text="勇士 交易", metadata={"title": "c", "url": "https://c", "site": "x"}),
    ]
    build_index(chunks, FakeEmbedder(), tmp_path)
    monkeypatch.setenv("CHROMA_DIR", str(tmp_path))
    monkeypatch.setattr("app.tools.local_rag.get_embedder", lambda: FakeEmbedder())
    monkeypatch.setattr("app.tools.local_rag.get_reranker", lambda: FakeReranker())
    results = local_rag("库里", top_k=3, rerank_top_n=2)
    assert len(results) == 2
    assert all(r.url.startswith("https://") for r in results)


def test_local_rag_returns_empty_when_index_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("CHROMA_DIR", str(tmp_path / "missing"))
    monkeypatch.setattr("app.tools.local_rag.get_embedder", lambda: FakeEmbedder())
    assert local_rag("库里") == []