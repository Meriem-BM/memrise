from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ApiSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)

    # Unset by default so auth fails closed (no shipped default credential).
    memrise_api_key: str | None = Field(default=None, alias="MEMRISE_API_KEY")
    memrise_auth_disabled: bool = Field(default=False, alias="MEMRISE_AUTH_DISABLED")
    memrise_cors_origins: str = Field(
        default="http://localhost:3000",
        alias="MEMRISE_CORS_ORIGINS",
    )
    memrise_request_max_bytes: int = Field(
        default=1_048_576,
        alias="MEMRISE_REQUEST_MAX_BYTES",
    )
