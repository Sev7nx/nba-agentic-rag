from typing import Literal, Protocol

from pydantic import BaseModel, HttpUrl, TypeAdapter, field_validator

_HTTP_URL = TypeAdapter(HttpUrl)


class SearchResult(BaseModel):
    title: str
    url: str
    site: str
    snippet: str = ""
    published_date: str | None = None
    result_type: Literal["news", "video", "doc"]

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        _HTTP_URL.validate_python(value)
        return value


class SearchProvider(Protocol):
    def search(
        self,
        query: str,
        include_domains: list[str],
        max_results: int = 5,
        topic: str = "general",
    ) -> list[SearchResult]: ...