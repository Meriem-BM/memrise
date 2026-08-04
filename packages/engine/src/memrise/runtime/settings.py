from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class MemorySettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str | None = Field(default=None, alias="DATABASE_URL")
    memrise_worker_id: str = Field(default="worker-1", alias="MEMRISE_WORKER_ID")
    memrise_job_poll_seconds: float = Field(default=1.0, alias="MEMRISE_JOB_POLL_SECONDS")
    memrise_graph_query_timeout_seconds: float = Field(
        default=2.0,
        alias="MEMRISE_GRAPH_QUERY_TIMEOUT_SECONDS",
    )
    memrise_graph_min_confidence: float = Field(default=0.5, alias="MEMRISE_GRAPH_MIN_CONFIDENCE")
    memrise_lifecycle_interval_seconds: int = Field(
        default=3600,
        alias="MEMRISE_LIFECYCLE_INTERVAL_SECONDS",
    )
    memrise_dedupe_interval_seconds: int = Field(
        default=3600,
        alias="MEMRISE_DEDUPE_INTERVAL_SECONDS",
    )
    memrise_usefulness_half_life_days: float = Field(
        default=30.0,
        alias="MEMRISE_USEFULNESS_HALF_LIFE_DAYS",
    )
    memrise_reranker_enabled: bool = Field(default=False, alias="MEMRISE_RERANKER_ENABLED")
    memrise_reranker_candidate_limit: int = Field(
        default=30,
        ge=1,
        le=100,
        alias="MEMRISE_RERANKER_CANDIDATE_LIMIT",
    )
    memrise_reranker_weight: float = Field(
        default=0.35,
        ge=0,
        le=1,
        alias="MEMRISE_RERANKER_WEIGHT",
    )
    memrise_hnsw_iterative_scan: str = Field(
        default="relaxed_order",
        pattern="^(off|strict_order|relaxed_order)$",
        alias="MEMRISE_HNSW_ITERATIVE_SCAN",
    )
    memrise_hnsw_ef_search: int = Field(
        default=100,
        ge=1,
        le=1000,
        alias="MEMRISE_HNSW_EF_SEARCH",
    )

    alibaba_cloud_api_key: str | None = Field(default=None, alias="ALIBABA_CLOUD_API_KEY")
    alibaba_cloud_base_url: str = Field(
        default="https://dashscope-us.aliyuncs.com/compatible-mode/v1",
        alias="ALIBABA_CLOUD_BASE_URL",
    )
    alibaba_cloud_workspace_id: str | None = Field(default=None, alias="ALIBABA_CLOUD_WORKSPACE_ID")
    alibaba_cloud_region: str = Field(default="us-virginia", alias="ALIBABA_CLOUD_REGION")
    qwen_memory_model: str = Field(default="qwen3.6-flash", alias="QWEN_MEMORY_MODEL")
    qwen_embedding_model: str = Field(default="text-embedding-v4", alias="QWEN_EMBEDDING_MODEL")
    qwen_embedding_dimensions: int = Field(default=1024, alias="QWEN_EMBEDDING_DIMENSIONS")
    qwen_timeout_seconds: float = Field(default=30.0, alias="QWEN_TIMEOUT_SECONDS")
    qwen_max_retries: int = Field(default=2, alias="QWEN_MAX_RETRIES")
