from pathlib import Path

from app.rag.embeddings import BGEEmbedder
from app.rag.ingest import build_index, chunk_document, load_documents


def main() -> None:
    corpus_dir = Path("data/corpus")
    persist_dir = Path("data/chroma")
    docs = load_documents(corpus_dir)
    chunks = [chunk for doc in docs for chunk in chunk_document(doc)]
    build_index(chunks, BGEEmbedder(), persist_dir)
    print(f"indexed {len(chunks)} chunks from {len(docs)} documents")


if __name__ == "__main__":
    main()