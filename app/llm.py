from typing import Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMClient(Protocol):
    def chat_json(self, system: str, user: str, schema: type[T]) -> T: ...

    def chat_text(self, system: str, user: str) -> str: ...


class OpenAICompatibleLLM:
    def __init__(self, api_key: str, base_url: str, model: str):
        from openai import OpenAI

        self._client = OpenAI(api_key=api_key, base_url=base_url)
        self._model = model

    def chat_json(self, system: str, user: str, schema: type[T]) -> T:
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content or "{}"
        return schema.model_validate_json(content)

    def chat_text(self, system: str, user: str) -> str:
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return response.choices[0].message.content or ""