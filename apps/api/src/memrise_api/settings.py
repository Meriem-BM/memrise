from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ApiSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)

    memrise_api_key: str = Field(default="local-dev-key", alias="MEMRISE_API_KEY")
    memrise_cors_origins: str = Field(
        default="http://localhost:3000",
        alias="MEMRISE_CORS_ORIGINS",
    )
    memrise_request_max_bytes: int = Field(
        default=1_048_576,
        alias="MEMRISE_REQUEST_MAX_BYTES",
    )
