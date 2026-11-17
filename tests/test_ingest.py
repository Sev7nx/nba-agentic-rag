from app.rag.ingest import Document, chunk_document, clean_text, load_jsonl_documents


def test_clean_text_removes_nav_and_images():
    raw = (
        "* [手机虎扑](javascript:void(0))\n"
        "![](data:image/svg+xml;base64,AAAA)\n"
        "库里在 2026 年总决赛拿下 40 分，带领勇士夺冠。\n"
        "登录 | 注册 | 更多\n"
    )
    cleaned = clean_text(raw)
    assert "手机虎扑" not in cleaned
    assert "data:image" not in cleaned
    assert "库里在 2026 年总决赛拿下 40 分" in cleaned


def test_clean_text_removes_link_heavy_nav():
    raw = (
        "[新浪微博](//weibo.com) [官方微信](https://x) [Instagram](https://y)\n"
        "库里在总决赛拿下 40 分。\n"
        "## 相关作品\n"
        "6/6184780512/810a19d8bc3eb13533fa26fa5745bfd3fd1f4134ee64?fr=lemma\n"
    )
    cleaned = clean_text(raw)
    assert "新浪微博" not in cleaned
    assert "相关作品" not in cleaned
    assert "fr=lemma" not in cleaned
    assert "库里在总决赛拿下 40 分" in cleaned


def test_load_jsonl_documents(tmp_path):
    path = tmp_path / "documents.jsonl"
    path.write_text(
        "\n".join(
            [
                '{"doc_id":"d1","title":"库里","url":"https://a.example",'
                '"text":"库里 三分\\n手机虎扑","doc_type":"player_intro",'
                '"source":"a.example","date":"2026-01-01"}',
                '{"doc_id":"d2","title":"bad","url":"","text":"x"}',
            ]
        ),
        encoding="utf-8",
    )
    docs = load_jsonl_documents(path)
    assert len(docs) == 1
    assert docs[0].doc_type == "player_intro"
    assert docs[0].source == "a.example"
    assert "手机虎扑" not in docs[0].text


def test_chunk_document_includes_doc_type():
    doc = Document(
        doc_id="1",
        title="库里",
        url="https://example.com",
        text="库里 三分 " * 100,
        doc_type="player_intro",
        source="example.com",
    )
    chunks = chunk_document(doc)
    assert chunks[0].metadata["doc_type"] == "player_intro"
    assert chunks[0].metadata["source"] == "example.com"


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