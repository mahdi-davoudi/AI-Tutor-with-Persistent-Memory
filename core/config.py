from pydantic import Field
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    debug: bool = False

    mongodb_url: str = "mongodb://localhost:27017"
    database_name: str = "chatapp"

    secret_key: str = Field(..., min_length=20)
    access_token_expire_minutes: int = 30

    anthropic_api_key: str = ""

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()