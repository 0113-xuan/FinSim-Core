from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import List

from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)


@dataclass(frozen=True)
class Settings:
    app_name: str = "FinSim-Core"
    app_version: str = "4.0.0"
    cors_origins: List[str] = None
    supabase_url: str = ""
    supabase_key: str = ""
    jwt_secret: str = "dev-only-change-me-please-set-a-real-secret"
    jwt_expire_minutes: int = 60 * 24
    ai_provider: str = "openai"
    ai_api_key: str = ""
    ai_model: str = "gpt-4.1-mini"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-flash-lite-latest"
    ai_timeout_seconds: int = 30
    ai_onboarding_timeout_seconds: int = 20
    ai_max_retries: int = 2
    ai_enabled: bool = False

    def ai_provider_ready(self) -> bool:
        if not self.ai_enabled:
            return False
        if self.ai_provider == "gemini":
            return bool(self.gemini_api_key)
        if self.ai_provider == "openai":
            return bool(self.ai_api_key)
        return False

    @classmethod
    def from_env(cls) -> "Settings":
        origins = os.getenv("CORS_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000")
        ai_provider = os.getenv("AI_PROVIDER", "openai").strip().lower()
        ai_api_key = os.getenv("AI_API_KEY", "")
        gemini_api_key = os.getenv("GEMINI_API_KEY", "")
        enabled_value = os.getenv("AI_ENABLED", "").strip().lower()
        if enabled_value:
            ai_enabled = enabled_value == "true"
        else:
            ai_enabled = bool(
                gemini_api_key if ai_provider == "gemini" else ai_api_key
            )
        return cls(
            cors_origins=[item.strip() for item in origins.split(",") if item.strip()],
            supabase_url=os.getenv("SUPABASE_URL", ""),
            supabase_key=os.getenv("SUPABASE_ANON_KEY", ""),
            jwt_secret=os.getenv("JWT_SECRET", "dev-only-change-me-please-set-a-real-secret"),
            jwt_expire_minutes=int(os.getenv("JWT_EXPIRE_MINUTES", "1440")),
            ai_provider=ai_provider,
            ai_api_key=ai_api_key,
            ai_model=os.getenv("AI_MODEL", "gpt-4.1-mini"),
            gemini_api_key=gemini_api_key,
            gemini_model=os.getenv("GEMINI_MODEL", "gemini-flash-lite-latest"),
            ai_timeout_seconds=int(os.getenv("AI_TIMEOUT_SECONDS", "30")),
            ai_onboarding_timeout_seconds=int(os.getenv("AI_ONBOARDING_TIMEOUT_SECONDS", "20")),
            ai_max_retries=int(os.getenv("AI_MAX_RETRIES", "2")),
            ai_enabled=ai_enabled,
        )

    def startup_warnings(self) -> List[str]:
        warnings = []
        if self.jwt_secret == "dev-only-change-me-please-set-a-real-secret":
            warnings.append("JWT_SECRET is using the development default.")
        if not self.supabase_url or not self.supabase_key:
            warnings.append("Supabase is not configured; persistence endpoints use local in-memory fallback.")
        if self.ai_enabled and self.ai_provider == "openai" and not self.ai_api_key:
            warnings.append("AI_ENABLED=true 但缺少 AI_API_KEY，將使用確定性 fallback。")
        if self.ai_enabled and self.ai_provider == "gemini" and not self.gemini_api_key:
            warnings.append("AI_ENABLED=true 但缺少 GEMINI_API_KEY，將使用確定性 fallback。")
        return warnings


settings = Settings.from_env()
