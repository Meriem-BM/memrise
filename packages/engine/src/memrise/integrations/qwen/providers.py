import json
from pathlib import Path

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam
from pydantic import ValidationError

from memrise.ports.providers import (
    CompletionProvider,
    EmbeddingProvider,
    ExtractionResult,
)
from memrise.runtime.settings import MemorySettings

PROMPT_DIR = Path(__file__).parent / "prompts"


class QwenCompletionProvider(CompletionProvider):
    def __init__(self, settings: MemorySettings) -> None:
        if not settings.alibaba_cloud_api_key:
            msg = "ALIBABA_CLOUD_API_KEY is required when MEMRISE_USE_FAKE_MODEL=false"
            raise ValueError(msg)
        self._settings = settings
        self._client = AsyncOpenAI(
            api_key=settings.alibaba_cloud_api_key,
            base_url=settings.alibaba_cloud_base_url,
            timeout=settings.qwen_timeout_seconds,
            max_retries=settings.qwen_max_retries,
        )
        self._prompt = (PROMPT_DIR / "memory_extraction_v1.md").read_text(encoding="utf-8")

    async def extract_memories(self, *, text: str, context: dict[str, object]) -> ExtractionResult:
        messages: list[ChatCompletionMessageParam] = [
            {
                "role": "system",
                "content": self._prompt,
            },
            {
                "role": "user",
                "content": json.dumps({"text": text, "context": context}, ensure_ascii=False),
            },
        ]
        for _ in range(self._settings.qwen_max_retries + 1):
            completion = await self._client.chat.completions.create(
                model=self._settings.qwen_memory_model,
                messages=messages,
                response_format={"type": "json_object"},
            )
            content = completion.choices[0].message.content or "{}"
            try:
                parsed = ExtractionResult.model_validate_json(content)
            except ValidationError:
                continue
            return parsed
        msg = "Qwen extraction returned malformed JSON after bounded retries"
        raise ValueError(msg)


class QwenEmbeddingProvider(EmbeddingProvider):
    def __init__(self, settings: MemorySettings) -> None:
        if not settings.alibaba_cloud_api_key:
            msg = "ALIBABA_CLOUD_API_KEY is required when MEMRISE_USE_FAKE_MODEL=false"
            raise ValueError(msg)
        self._settings = settings
        self._client = AsyncOpenAI(
            api_key=settings.alibaba_cloud_api_key,
            base_url=settings.alibaba_cloud_base_url,
            timeout=settings.qwen_timeout_seconds,
            max_retries=settings.qwen_max_retries,
        )

    async def embed(self, text: str) -> list[float]:
        response = await self._client.embeddings.create(
            model=self._settings.qwen_embedding_model,
            input=text,
            dimensions=self._settings.qwen_embedding_dimensions,
            encoding_format="float",
        )
        return list(response.data[0].embedding)
