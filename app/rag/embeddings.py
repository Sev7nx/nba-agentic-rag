from typing import Protocol


class Embedder(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...


class BGEEmbedder:
    def __init__(
        self,
        model_name: str = "BAAI/bge-m3",
        local_files_only: bool = False,
    ):
        self._model_name = model_name
        self._local_files_only = local_files_only
        self._model = None

    def embed(self, texts: list[str]) -> list[list[float]]:
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(
                self._model_name,
                local_files_only=self._local_files_only,
            )
        vectors = self._model.encode(texts, normalize_embeddings=True)
        return [vector.tolist() for vector in vectors]