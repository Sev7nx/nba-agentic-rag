from typing import Protocol


class Reranker(Protocol):
    def rerank(self, query: str, texts: list[str]) -> list[float]: ...


class BGEReranker:
    def __init__(
        self,
        model_name: str = "BAAI/bge-reranker-base",
        local_files_only: bool = False,
    ):
        self._model_name = model_name
        self._local_files_only = local_files_only
        self._model = None

    def rerank(self, query: str, texts: list[str]) -> list[float]:
        if self._model is None:
            from sentence_transformers import CrossEncoder

            self._model = CrossEncoder(
                self._model_name,
                local_files_only=self._local_files_only,
            )
        scores = self._model.predict([(query, text) for text in texts])
        return [float(score) for score in scores]