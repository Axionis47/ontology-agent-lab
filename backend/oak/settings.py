from decimal import Decimal
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
    gemini_project: str = ""
    gemini_location: str = "global"
    gemini_model: str = "gemini-3.8-flash"
    gemini_timeout: float = Field(default=25, gt=0, le=30)
    gemini_max_output_tokens: int = Field(default=4096, ge=32, le=65536)
    gemini_check_budget_usd: Decimal = Field(default=Decimal("0"), ge=0, le=Decimal("0.10"))
    surface_max_cost_usd: Decimal = Field(default=Decimal("10"), gt=0, le=100)
    surface_max_mcp_calls: int = Field(default=100, ge=12, le=200)
    surface_max_model_calls: int = Field(default=100, ge=14, le=200)
    surface_max_active_seconds: int = Field(default=3600, ge=600, le=7200)
    surface_max_clarification_rounds: int = Field(default=10, ge=2, le=20)
    surface_input_tokens: int = Field(default=32768, ge=4096, le=131072)
    surface_probe_output_tokens: int = Field(default=4096, ge=512, le=65536)
    surface_proposal_output_tokens: int = Field(default=16384, ge=512, le=65536)
    surface_model_timeout: float = Field(default=90, gt=0, le=180)
    surface_tool_timeout: float = Field(default=30, gt=0, le=120)

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
