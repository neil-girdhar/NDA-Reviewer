from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        env_ignore_empty=True,  # ignore empty system env vars so .env file wins
    )

    anthropic_api_key: str
    model: str = "claude-sonnet-4-6"
    high_stakes_model: str = "claude-opus-4-8"
    database_url: str = "sqlite:///./nda_reviews.db"
    max_upload_bytes: int = 20 * 1024 * 1024  # 20 MB


settings = Settings()
