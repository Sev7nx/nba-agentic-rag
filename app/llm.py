from typing import Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMClient(Protocol):
    def chat_json(self, system: str, user: str, schema: type[T]) -> T: ...

    def chat_text(self, system: str, user: str) -> str: ...


class OpenAICompatibleLLM:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        input_price_cny: float = 2.0,
        output_price_cny: float = 8.0,
    ):
        from openai import OpenAI

        self._client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=30.0,
            max_retries=1,
        )
        self._model = model
        self._input_price = input_price_cny
        self._output_price = output_price_cny
        self.last_usage = {"tokens": 0, "cost_cny": 0.0}

    def _usage(self, usage) -> dict:
        if usage is None:
            return {"tokens": 0, "cost_cny": 0.0}
        prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
        completion_tokens = getattr(usage, "completion_tokens", 0) or 0
        cost = (
            prompt_tokens / 1_000_000 * self._input_price
            + completion_tokens / 1_000_000 * self._output_price
        )
        return {
            "tokens": getattr(usage, "total_tokens", 0) or 0,
            "cost_cny": cost,
        }

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
        self.last_usage = self._usage(getattr(response, "usage", None))
        return schema.model_validate_json(content)

    def chat_text(self, system: str, user: str) -> str:
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        content = response.choices[0].message.content or ""
        self.last_usage = self._usage(getattr(response, "usage", None))
        return content