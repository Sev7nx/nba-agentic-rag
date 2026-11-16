from typing import Protocol


class Reranker(Protocol):
    def rerank(self, query: str, texts: list[str]) -> list[float]: ...


class BGEReranker:
    def __init__(self, model_name: str = "BAAI/bge-reranker-base"):
        self._model_name = model_name
        self._model = None

    def rerank(self, query: str, texts: list[str]) -> list[float]:
        if self._model is None:
            from sentence_transformers import CrossEncoder

            self._model = CrossEncoder(self._model_name)
        scores = self._model.predict([(query, text) for text in texts])
        return [float(score) for score in scores]