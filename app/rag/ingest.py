import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from app.rag.embeddings import Embedder

if TYPE_CHECKING:
    from chromadb.api.models.Collection import Collection


@dataclass
class Document:
    doc_id: str
    title: str
    url: str
    text: str
    source_type: str = "doc"
    entity_type: str = "unknown"
    entity_name: str = ""
    date: str | None = None


@dataclass
class Chunk:
    id: str
    text: str
    metadata: dict = field(default_factory=dict)


def _parse_front_matter(text: str) -> tuple[dict, str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    meta: dict[str, str] = {}
    body_start = None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            body_start = index + 1
            break
        if ":" in line:
            key, value = line.split(":", 1)
            meta[key.strip()] = value.strip().strip('"').strip("'")
    if body_start is None:
        return {}, text
    return meta, "\n".join(lines[body_start:])


def load_documents(corpus_dir: Path) -> list[Document]:
    docs: list[Document] = []
    for path in sorted(corpus_dir.iterdir()):
        suffix = path.suffix.lower()
        if suffix == ".md":
            raw = path.read_text(encoding="utf-8")
            meta, body = _parse_front_matter(raw)
            if path.stem.lower() == "readme" or not meta.get("url"):
                continue
            first_line = body.splitlines()[0] if body else ""
            docs.append(
                Document(
                    doc_id=meta.get("doc_id", path.stem),
                    title=meta.get("title")
                    or first_line.lstrip("# ").strip()
                    or path.stem,
                    url=meta["url"],
                    text=body,
                    source_type=meta.get("source_type", "doc"),
                    entity_type=meta.get("entity_type", "unknown"),
                    entity_name=meta.get("entity_name", ""),
                    date=meta.get("date"),
                )
            )
        elif suffix == ".json":
            payload = json.loads(path.read_text(encoding="utf-8"))
            items = payload if isinstance(payload, list) else [payload]
            for index, item in enumerate(items):
                docs.append(
                    Document(
                        doc_id=item.get("doc_id", f"{path.stem}-{index}"),
                        title=item.get("title", path.stem),
                        url=item.get("url", ""),
                        text=item.get("text", ""),
                        source_type=item.get("source_type", "doc"),
                        entity_type=item.get("entity_type", "unknown"),
                        entity_name=item.get("entity_name", ""),
                        date=item.get("date"),
                    )
                )
    return docs


def chunk_document(doc: Document, chunk_size: int = 600, overlap: int = 100) -> list[Chunk]:
    text = doc.text.strip()
    if not text:
        return []
    step = max(1, chunk_size - overlap)
    chunks: list[Chunk] = []
    for index, start in enumerate(range(0, len(text), step)):
        piece = text[start : start + chunk_size]
        if not piece:
            break
        chunks.append(
            Chunk(
                id=f"{doc.doc_id}-{index}",
                text=piece,
                metadata={
                    "doc_id": doc.doc_id,
                    "title": doc.title,
                    "url": doc.url,
                    "source_type": doc.source_type,
                    "entity_type": doc.entity_type,
                    "entity_name": doc.entity_name,
                    "date": doc.date,
                },
            )
        )
        if start + chunk_size >= len(text):
            break
    return chunks


def _clean_metadata(metadata: dict) -> dict:
    return {key: value for key, value in metadata.items() if value is not None}


def build_index(chunks: list[Chunk], embedder: Embedder, persist_dir: Path) -> "Collection":
    import chromadb

    client = chromadb.PersistentClient(path=str(persist_dir))
    collection = client.get_or_create_collection(name="nba")
    if chunks:
        collection.add(
            ids=[chunk.id for chunk in chunks],
            documents=[chunk.text for chunk in chunks],
            metadatas=[_clean_metadata(chunk.metadata) for chunk in chunks],
            embeddings=embedder.embed([chunk.text for chunk in chunks]),
        )
    return collection