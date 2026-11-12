from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="OAK_", env_file=".env", extra="ignore", validate_by_name=True
    )
    environment: Literal["local", "production"] = "production"
    release_sha: str = Field(
        default="local", validation_alias=AliasChoices("OAK_RELEASE_SHA", "RENDER_GIT_COMMIT")
    )
    database_url: str = "postgresql://localhost:5432/oak"
    api_key: str = ""
    public_api_url: str = Field(
        default="http://localhost:8000",
        validation_alias=AliasChoices("OAK_PUBLIC_API_URL", "RENDER_EXTERNAL_URL"),
    )
    frontend_url: str = "http://localhost:3000"
    allow_local_mcp: bool = False
    secret_backend: Literal["vault", "local"] = "vault"
    local_secret_key: str = ""
    discovery_timeout: float = 30
    oauth_timeout: float = 300

    def validate_runtime(self):
        if len(self.api_key) < 32:
            raise RuntimeError("Set OAK_API_KEY to a random value with at least 32 characters.")
        if self.environment == "production":
            if self.secret_backend != "vault" or self.allow_local_mcp:
                raise RuntimeError("Production requires Vault and public MCP endpoints.")
            if not all(
                url.startswith("https://") for url in [self.public_api_url, self.frontend_url]
            ):
                raise RuntimeError("Production requires HTTPS application URLs.")
        elif self.secret_backend == "local" and not self.local_secret_key:
            raise RuntimeError("Set OAK_LOCAL_SECRET_KEY for the encrypted local secret store.")


@lru_cache
def get_settings() -> Settings:
    return Settings()
