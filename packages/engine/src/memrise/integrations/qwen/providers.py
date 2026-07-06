import json
from pathlib import Path

from openai import AsyncOpenAI, AuthenticationError
from openai.types.chat import ChatCompletionMessageParam
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from memrise.graph.schema import GraphSchemaPack
from memrise.integrations.qwen.errors import QwenProviderError
from memrise.ports.providers import (
    AnswerResult,
    CompletionProvider,
    ConsolidationResult,
    DuplicateJudgementResult,
    DuplicateVerdict,
    EmbeddingProvider,
    EmbeddingVector,
    ExtractionResult,
)
from memrise.runtime.settings import MemorySettings

PROMPT_DIR = Path(__file__).parent / "prompts"
MEMORY_EXTRACTION_PROMPT_VERSION = "memory_extraction_v1"
CONSOLIDATION_PROMPT_VERSION = "consolidation_v1"
AGENT_ANSWER_PROMPT_VERSION = "agent_answer_v1"
DUPLICATE_JUDGE_PROMPT_VERSION = "duplicate_judge_v1"


class _JudgeVerdicts(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verdicts: list[DuplicateVerdict] = Field(default_factory=list, max_length=200)


class QwenCompletionProvider(CompletionProvider):
    def __init__(self, settings: MemorySettings) -> None:
        self._settings = settings
        self._client = _client_from_settings(settings)
        self._prompt = (PROMPT_DIR / f"{MEMORY_EXTRACTION_PROMPT_VERSION}.md").read_text(
            encoding="utf-8"
        )
        self._consolidation_prompt = (PROMPT_DIR / f"{CONSOLIDATION_PROMPT_VERSION}.md").read_text(
            encoding="utf-8"
        )
        self._answer_prompt = (PROMPT_DIR / f"{AGENT_ANSWER_PROMPT_VERSION}.md").read_text(
            encoding="utf-8"
        )
        self._judge_prompt = (PROMPT_DIR / f"{DUPLICATE_JUDGE_PROMPT_VERSION}.md").read_text(
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
        parsed = await self._complete_validated_json(
            client,
            system_prompt=self._prompt,
            user_payload={"text": text, "context": context},
            model_cls=ExtractionResult,
            task_label="extraction",
        )
        return parsed.model_copy(
            update={
                "schema_version": MEMORY_EXTRACTION_PROMPT_VERSION,
                "model_name": self._settings.qwen_memory_model,
                "prompt_version": MEMORY_EXTRACTION_PROMPT_VERSION,
            }
        )

    async def judge_duplicate_pairs(
        self, *, pairs: list[dict[str, object]], context: dict[str, object]
    ) -> DuplicateJudgementResult:
        if not pairs:
            return DuplicateJudgementResult(
                verdicts=[],
                model_name=self._settings.qwen_memory_model,
                prompt_version=DUPLICATE_JUDGE_PROMPT_VERSION,
            )
        client = _require_client(self._client)
        try:
            parsed = await self._complete_validated_json(
                client,
                system_prompt=self._judge_prompt,
                user_payload={"pairs": pairs, "context": context},
                model_cls=_JudgeVerdicts,
                task_label="duplicate_judge",
            )
        except AuthenticationError as exc:
            msg = "Qwen duplicate-judge authentication failed; verify ALIBABA_CLOUD_API_KEY"
            raise QwenProviderError(msg) from exc
        return DuplicateJudgementResult(
            verdicts=[DuplicateVerdict.model_validate(v.model_dump()) for v in parsed.verdicts],
            model_name=self._settings.qwen_memory_model,
            prompt_version=DUPLICATE_JUDGE_PROMPT_VERSION,
        )

    async def consolidate_memories(
        self,
        *,
        episodes: list[dict[str, object]],
        existing_memories: list[dict[str, object]],
        context: dict[str, object],
    ) -> ConsolidationResult:
        client = _require_client(self._client)
        try:
            parsed = await self._complete_validated_json(
                client,
                system_prompt=self._consolidation_prompt,
                user_payload={
                    "episodes": episodes,
                    "existing_memories": existing_memories,
                    "context": context,
                },
                model_cls=ConsolidationResult,
                task_label="consolidation",
            )
        except AuthenticationError as exc:
            msg = "Qwen consolidation authentication failed; verify ALIBABA_CLOUD_API_KEY"
            raise QwenProviderError(msg) from exc
        return parsed.model_copy(
            update={
                "schema_version": CONSOLIDATION_PROMPT_VERSION,
                "model_name": self._settings.qwen_memory_model,
                "prompt_version": CONSOLIDATION_PROMPT_VERSION,
            }
        )

    async def answer_question(
        self,
        *,
        query: str,
        context: str,
        memories: list[dict[str, object]],
    ) -> AnswerResult:
        client = _require_client(self._client)
        try:
            completion = await client.chat.completions.create(
                model=self._settings.qwen_memory_model,
                messages=[
                    {"role": "system", "content": self._answer_prompt},
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "query": query,
                                "context": context,
                                "memories": memories,
                            },
                            ensure_ascii=False,
                        ),
                    },
                ],
            )
        except AuthenticationError as exc:
            msg = "Qwen answer authentication failed; verify ALIBABA_CLOUD_API_KEY"
            raise QwenProviderError(msg) from exc
        answer = (completion.choices[0].message.content or "").strip()
        return AnswerResult(
            answer=answer or "I could not produce an answer from the retrieved memory.",
            model_name=self._settings.qwen_memory_model,
            prompt_version=AGENT_ANSWER_PROMPT_VERSION,
        )

    async def _complete_validated_json[ModelT: BaseModel](
        self,
        client: AsyncOpenAI,
        *,
        system_prompt: str,
        user_payload: dict[str, object],
        model_cls: type[ModelT],
        task_label: str,
    ) -> ModelT:
        """Call the model and validate JSON, feeding validation errors back on retry."""
        messages: list[ChatCompletionMessageParam] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
        ]
        last_error: ValidationError | None = None
        for _ in range(self._settings.qwen_max_retries + 1):
            completion = await client.chat.completions.create(
                model=self._settings.qwen_memory_model,
                messages=messages,
                response_format={"type": "json_object"},
            )
            content = completion.choices[0].message.content or "{}"
            try:
                return model_cls.model_validate_json(content)
            except ValidationError as exc:
                last_error = exc
                messages = [
                    *messages,
                    {"role": "assistant", "content": content},
                    {
                        "role": "user",
                        "content": (
                            "Your previous output failed schema validation. "
                            f"Errors: {exc.errors(include_url=False)!r}. "
                            "Return corrected JSON only, matching the schema exactly."
                        ),
                    },
                ]
        msg = f"Qwen {task_label} returned malformed JSON after bounded retries"
        raise ValueError(msg) from last_error


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
