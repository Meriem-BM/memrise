import json
from pathlib import Path

from openai import AsyncOpenAI, AuthenticationError
from openai.types.chat import ChatCompletionMessageParam
from pydantic import ValidationError

from memrise.graph.schema import GraphSchemaPack
from memrise.integrations.qwen.errors import QwenProviderError
from memrise.ports.providers import (
    CompletionProvider,
    EmbeddingProvider,
    EmbeddingVector,
    ExtractionResult,
)
from memrise.runtime.settings import MemorySettings

PROMPT_DIR = Path(__file__).parent / "prompts"
MEMORY_EXTRACTION_PROMPT_VERSION = "memory_extraction_v1"


class QwenCompletionProvider(CompletionProvider):
    def __init__(self, settings: MemorySettings) -> None:
        self._settings = settings
        self._client = _client_from_settings(settings)
        self._prompt = (PROMPT_DIR / f"{MEMORY_EXTRACTION_PROMPT_VERSION}.md").read_text(
            encoding="utf-8"
        )

    async def extract_memories(self, *, text: str, context: dict[str, object]) -> ExtractionResult:
        client = _require_client(self._client)
        try:
            return await self._extract_memories(client, text, context)
        except AuthenticationError as exc:
            msg = "Qwen completion authentication failed; verify ALIBABA_CLOUD_API_KEY"
            raise QwenProviderError(msg) from exc

    async def _extract_memories(
        self,
        client: AsyncOpenAI,
        text: str,
        context: dict[str, object],
    ) -> ExtractionResult:
        messages: list[ChatCompletionMessageParam] = [
            {
                "role": "system",
                "content": self._prompt,
            },
            {
                "role": "user",
                "content": json.dumps(
                    {"text": text, "context": context},
                    ensure_ascii=False,
                ),
            },
        ]
        for _ in range(self._settings.qwen_max_retries + 1):
            completion = await client.chat.completions.create(
                model=self._settings.qwen_memory_model,
                messages=messages,
                response_format={"type": "json_object"},
            )
            content = completion.choices[0].message.content or "{}"
            try:
                parsed = ExtractionResult.model_validate_json(content)
            except ValidationError:
                continue
            return parsed.model_copy(
                update={
                    "schema_version": MEMORY_EXTRACTION_PROMPT_VERSION,
                    "model_name": self._settings.qwen_memory_model,
                    "prompt_version": MEMORY_EXTRACTION_PROMPT_VERSION,
                }
            )
        msg = "Qwen extraction returned malformed JSON after bounded retries"
        raise ValueError(msg)


class QwenEmbeddingProvider(EmbeddingProvider):
    def __init__(self, settings: MemorySettings) -> None:
        self._settings = settings
        self._client = _client_from_settings(settings)

    async def embed(self, text: str) -> EmbeddingVector:
        client = _require_client(self._client)
        try:
            response = await client.embeddings.create(
                model=self._settings.qwen_embedding_model,
                input=text,
                dimensions=self._settings.qwen_embedding_dimensions,
                encoding_format="float",
            )
        except AuthenticationError as exc:
            msg = "Qwen embedding authentication failed; verify ALIBABA_CLOUD_API_KEY"
            raise QwenProviderError(msg) from exc
        return EmbeddingVector(
            values=list(response.data[0].embedding),
            model=self._settings.qwen_embedding_model,
            dimensions=self._settings.qwen_embedding_dimensions,
        )


def _client_from_settings(settings: MemorySettings) -> AsyncOpenAI | None:
    if not settings.alibaba_cloud_api_key:
        return None
    return AsyncOpenAI(
        api_key=settings.alibaba_cloud_api_key,
        base_url=settings.alibaba_cloud_base_url,
        timeout=settings.qwen_timeout_seconds,
        max_retries=settings.qwen_max_retries,
    )


def schema_pack_context(packs: list[GraphSchemaPack]) -> list[dict[str, object]]:
    return [
        {
            "domain": pack.domain,
            "version": pack.version,
            "node_types": list(pack.node_types),
            "relationship_patterns": [
                {"source": pattern.source, "type": pattern.type, "target": pattern.target}
                for pattern in pack.relationship_patterns
            ],
            "type_aliases": pack.type_aliases,
        }
        for pack in packs
    ]


def _require_client(client: AsyncOpenAI | None) -> AsyncOpenAI:
    if client is None:
        msg = "ALIBABA_CLOUD_API_KEY is required for Qwen memory extraction and embeddings"
        raise QwenProviderError(msg)
    return client
