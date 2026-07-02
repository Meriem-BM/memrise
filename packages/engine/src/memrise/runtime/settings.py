from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class MemorySettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str | None = Field(default=None, alias="DATABASE_URL")
    memrise_use_fake_model: bool = Field(default=True, alias="MEMRISE_USE_FAKE_MODEL")
    memrise_api_key: str = Field(default="local-dev-key", alias="MEMRISE_API_KEY")
    memrise_request_max_bytes: int = Field(
        default=1_048_576,
        alias="MEMRISE_REQUEST_MAX_BYTES",
    )
    memrise_worker_id: str = Field(default="worker-1", alias="MEMRISE_WORKER_ID")
    memrise_job_poll_seconds: float = Field(default=1.0, alias="MEMRISE_JOB_POLL_SECONDS")

    alibaba_cloud_api_key: str | None = Field(default=None, alias="ALIBABA_CLOUD_API_KEY")
    alibaba_cloud_base_url: str = Field(
        default="https://dashscope-us.aliyuncs.com/compatible-mode/v1",
        alias="ALIBABA_CLOUD_BASE_URL",
    )
    alibaba_cloud_workspace_id: str | None = Field(default=None, alias="ALIBABA_CLOUD_WORKSPACE_ID")
    alibaba_cloud_region: str = Field(default="us-virginia", alias="ALIBABA_CLOUD_REGION")
    qwen_memory_model: str = Field(default="qwen-flash", alias="QWEN_MEMORY_MODEL")
    qwen_embedding_model: str = Field(default="text-embedding-v4", alias="QWEN_EMBEDDING_MODEL")
    qwen_embedding_dimensions: int = Field(default=1024, alias="QWEN_EMBEDDING_DIMENSIONS")
    qwen_timeout_seconds: float = Field(default=30.0, alias="QWEN_TIMEOUT_SECONDS")
    qwen_max_retries: int = Field(default=2, alias="QWEN_MAX_RETRIES")
