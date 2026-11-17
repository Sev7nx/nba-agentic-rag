import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings
from app.rag.embeddings import BGEEmbedder
from app.rag.ingest import build_doc_index, chunk_document, load_jsonl_documents
from app.rag.reranker import BGEReranker


def main() -> None:
    docs = [
        doc
        for doc in load_jsonl_documents(Path(settings.docs_path))
        if len(doc.text) >= 500
    ]
    chunks = [chunk for doc in docs for chunk in chunk_document(doc)]
    collection = build_doc_index(
        chunks,
        BGEEmbedder(settings.embedding_model, local_files_only=False),
        Path(settings.chroma_dir),
    )
    print(
        f"indexed {collection.count()} chunks from {len(docs)} documents "
        f"into {settings.chroma_dir}/nba_docs using {settings.embedding_model}"
    )
    if settings.rerank_enabled:
        BGEReranker(
            settings.rerank_model,
            local_files_only=False,
        ).rerank("warmup", ["warmup"])
        print(f"warmed reranker {settings.rerank_model}")


if __name__ == "__main__":
    main()