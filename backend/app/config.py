"""
config.py — Application settings loaded from environment variables.
Secrets never reach the frontend or logs.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    app_env: str = "development"
    database_url: str = "sqlite:///./agentpay_guard.db"
    frontend_origin: str = "http://localhost:5173"

    # AI
    ai_provider: str = "none"          # "openai" | "gemini" | "none"
    ai_api_key: str = ""
    ai_model: str = ""

    # PayPal Sandbox
    paypal_mode: str = "sandbox"
    paypal_client_id: str = ""
    paypal_client_secret: str = ""     # NEVER sent to frontend
    paypal_base_url: str = "https://api-m.sandbox.paypal.com"
    paypal_currency: str = "USD"

    @property
    def ai_configured(self) -> bool:
        return bool(self.ai_api_key) and self.ai_provider != "none"

    @property
    def paypal_configured(self) -> bool:
        return bool(self.paypal_client_id) and bool(self.paypal_client_secret)


@lru_cache
def get_settings() -> Settings:
    return Settings()
