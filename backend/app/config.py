from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent  # backend/
ROOT_DIR = BASE_DIR.parent
APP_DIR = Path(__file__).resolve().parent
CONFIG_DIR = APP_DIR / "definitions"
IS_VERCEL = bool(os.environ.get("VERCEL") or not os.access(BASE_DIR, os.W_OK))
SECRETS_DIR = Path("/tmp/leadsense_secrets") if IS_VERCEL else (BASE_DIR / "secrets")
DEFAULT_DB_PATH = Path("/tmp/leadsense.db") if IS_VERCEL else (BASE_DIR / "leadsense.db")
DEFAULT_CHROMA_DIR = "/tmp/chroma_db" if IS_VERCEL else str(BASE_DIR / "chroma_db")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(ROOT_DIR / ".env"), extra="ignore")

    target_gmail_address: str = "rajurajuu970@gmail.com"
    google_client_id: str = ""
    google_client_secret: str = ""
    google_client_secrets_file: str = str(SECRETS_DIR / "client_secret.json") if IS_VERCEL else "backend/secrets/client_secret.json"
    google_redirect_uri: str = "http://localhost:8000/api/gmail/callback"
    frontend_url: str = "http://localhost:5173"
    token_encryption_key: str = ""
    sync_max_messages: int = 200
    sync_interval_minutes: int = 0

    database_url: str = f"sqlite:///{DEFAULT_DB_PATH}"

    openai_api_key: str = ""
    openai_base_url: str = ""
    llm_model: str = "gpt-4o-mini"
    embedding_provider: str = "local"  # local | openai
    embedding_model: str = "text-embedding-3-small"
    chroma_dir: str = DEFAULT_CHROMA_DIR

    duplicate_threshold: int = 90
    default_phone_region: str = "IN"
    enable_website_check: bool = False
    api_access_key: str = ""
    cors_origins: str = "*" if IS_VERCEL else "http://localhost:5173"
    log_level: str = "INFO"

    @property
    def client_secrets_path(self) -> Path:
        p = Path(self.google_client_secrets_file)
        return p if p.is_absolute() else ROOT_DIR / p

    @property
    def has_oauth_client(self) -> bool:
        return bool(self.google_client_id.strip() and self.google_client_secret.strip()) or self.client_secrets_path.exists()

    @property
    def llm_enabled(self) -> bool:
        return bool(self.openai_api_key.strip())

    @property
    def target_configured(self) -> bool:
        t = self.target_gmail_address.strip().lower()
        return bool(t) and "@" in t and t != "your_full_gmail_address"


@lru_cache
def get_settings() -> Settings:
    return Settings()
