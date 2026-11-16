from typing import Literal

from pydantic import BaseModel, Field, HttpUrl, TypeAdapter, field_validator

_HTTP_URL = TypeAdapter(HttpUrl)


class Source(BaseModel):
    id: int
    title: str
    url: str
    site: str
    date: str | None = None
    type: Literal["news", "video", "doc"]
    snippet: str | None = None

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        _HTTP_URL.validate_python(value)
        return value


class TraceStep(BaseModel):
    name: str
    detail: str
    duration_ms: int
    tokens: int = 0
    cost_cny: float = 0.0


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class UserProfile(BaseModel):
    favorite_team: str | None = None
    favorite_players: list[str] = Field(default_factory=list)


class ChatRequest(BaseModel):
    question: str = Field(min_length=1)
    history: list[ChatTurn] = Field(default_factory=list)
    profile: UserProfile | None = None

    @field_validator("question")
    @classmethod
    def question_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("question must not be blank")
        return value


class ChatResponse(BaseModel):
    answer: str
    sources: list[Source] = Field(default_factory=list)
    trace: list[TraceStep] = Field(default_factory=list)
    cached: bool = False


class ChatEvent(BaseModel):
    type: Literal["token", "sources", "trace", "done", "error"]
    data: dict = Field(default_factory=dict)