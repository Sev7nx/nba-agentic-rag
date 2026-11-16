from app.rag.ingest import Document, chunk_document


def test_chunk_overlap_and_metadata():
    doc = Document(
        doc_id="1",
        title="库里",
        url="https://example.com",
        text="a" * 1500,
        source_type="doc",
        entity_type="player",
        entity_name="库里",
        date=None,
    )
    chunks = chunk_document(doc, chunk_size=600, overlap=100)
    assert len(chunks) >= 3
    assert chunks[0].metadata["entity_name"] == "库里"
    assert chunks[0].text[:10] == "a" * 10


def test_load_documents_skips_unknown_files(tmp_path):
    (tmp_path / "a.md").write_text(
        "---\nurl: https://example.com/a\nentity_name: 库里\n---\n# 标题\n正文",
        encoding="utf-8",
    )
    (tmp_path / "b.exe").write_bytes(b"x")
    from app.rag.ingest import load_documents

    docs = load_documents(tmp_path)
    assert len(docs) == 1
    assert docs[0].url == "https://example.com/a"
    assert docs[0].entity_name == "库里"


def test_markdown_without_url_is_skipped(tmp_path):
    (tmp_path / "c.md").write_text("# 标题\n正文", encoding="utf-8")
    from app.rag.ingest import load_documents

    assert load_documents(tmp_path) == []


def test_build_index_with_fake_embedder(tmp_path):
    from app.rag.ingest import Chunk, build_index

    class FakeEmbedder:
        def embed(self, texts):
            return [[1.0, 0.0] for _ in texts]

    chunks = [
        Chunk(
            id="1-0",
            text="库里",
            metadata={"title": "t", "url": "https://example.com", "site": "x"},
        )
    ]
    collection = build_index(chunks, FakeEmbedder(), tmp_path)
    assert collection.count() == 1