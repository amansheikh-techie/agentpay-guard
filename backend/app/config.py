"""
config.py — Application settings loaded from environment variables.
Secrets never reach the frontend or logs.
"""
from functools import lru_cache
import logging
from pathlib import Path
from typing import Any
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# Load backend/.env relative to the config file location, not the working directory
BACKEND_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BACKEND_DIR / ".env"


def _clean_str(v: Any) -> str:
    if v is None:
        return ""
    s = str(v).strip()
    while len(s) >= 2 and ((s[0] == '"' and s[-1] == '"') or (s[0] == "'" and s[-1] == "'")):
        s = s[1:-1].strip()
    return s


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_PATH,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    app_env: str = "development"
    database_url: str = "sqlite:///./agentpay_guard.db"
    frontend_origin: str = "http://localhost:5173"
    admin_token: str = ""

    # AI
    ai_provider: str = "none"          # "openai" | "gemini" | "none"
    ai_api_key: str = ""
    ai_model: str = ""
    ai_base_url: str = ""

    # PayPal Sandbox
    paypal_mode: str = "sandbox"
    paypal_client_id: str = ""
    paypal_client_secret: str = ""     # NEVER sent to frontend
    paypal_base_url: str = "https://api-m.sandbox.paypal.com"
    paypal_currency: str = "USD"

    @field_validator("ai_provider", mode="before")
    @classmethod
    def _clean_ai_provider(cls, v: Any) -> str:
        s = _clean_str(v).lower()
        return s if s else "none"

    @field_validator("ai_model", mode="before")
    @classmethod
    def _clean_ai_model(cls, v: Any) -> str:
        s = _clean_str(v)
        if s.startswith("models/"):
            s = s[len("models/"):]
        return s

    @field_validator("ai_api_key", "ai_base_url", mode="before")
    @classmethod
    def _clean_ai_text_fields(cls, v: Any) -> str:
        return _clean_str(v)

    @model_validator(mode="after")
    def _validate_ai_settings(self) -> "Settings":
        # If the provider is gemini or openai, a key is set, and AI_MODEL is empty, use default model
        if self.ai_provider in ("gemini", "openai") and self.ai_api_key:
            if not self.ai_model:
                if self.ai_provider == "gemini":
                    self.ai_model = "gemini-2.5-flash"
                elif self.ai_provider == "openai":
                    self.ai_model = "gpt-4o-mini"

        # If a key is set but the provider is none or unknown, log this warning (never the key):
        if self.ai_api_key and self.ai_provider not in ("gemini", "openai"):
            logger.warning(
                "AI key is set but AI_PROVIDER is none or unsupported; running in fallback mode."
            )

        return self

    def get_ai_base_url(self) -> str:
        """
        Return the resolved base URL for the active AI provider.
        If ai_base_url is explicitly configured, use it.
        If ai_provider is 'gemini' and ai_base_url is empty, use the Google Gemini OpenAI-compatible base URL.
        Otherwise defaults to OpenAI's standard v1 endpoint.
        """
        if self.ai_base_url and self.ai_base_url.strip():
            url = self.ai_base_url.strip()
            return url if url.endswith("/") else url + "/"
        if self.ai_provider == "gemini":
            return "https://generativelanguage.googleapis.com/v1beta/openai/"
        return "https://api.openai.com/v1/"

    @property
    def effective_ai_base_url(self) -> str:
        return self.get_ai_base_url()

    @property
    def ai_configured(self) -> bool:
        return bool(self.ai_api_key) and self.ai_provider in ("gemini", "openai")

    @property
    def key_set(self) -> bool:
        return bool(self.ai_api_key)

    @property
    def paypal_configured(self) -> bool:
        return bool(self.paypal_client_id) and bool(self.paypal_client_secret)


@lru_cache
def get_settings() -> Settings:
    return Settings()
