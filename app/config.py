from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List


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
    ai_timeout_seconds: int = 30
    ai_max_retries: int = 2
    ai_enabled: bool = False

    @classmethod
    def from_env(cls) -> "Settings":
        origins = os.getenv("CORS_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000")
        return cls(
            cors_origins=[item.strip() for item in origins.split(",") if item.strip()],
            supabase_url=os.getenv("SUPABASE_URL", ""),
            supabase_key=os.getenv("SUPABASE_ANON_KEY", ""),
            jwt_secret=os.getenv("JWT_SECRET", "dev-only-change-me-please-set-a-real-secret"),
            jwt_expire_minutes=int(os.getenv("JWT_EXPIRE_MINUTES", "1440")),
            ai_provider=os.getenv("AI_PROVIDER", "openai"),
            ai_api_key=os.getenv("AI_API_KEY", ""),
            ai_model=os.getenv("AI_MODEL", "gpt-4.1-mini"),
            ai_timeout_seconds=int(os.getenv("AI_TIMEOUT_SECONDS", "30")),
            ai_max_retries=int(os.getenv("AI_MAX_RETRIES", "2")),
            ai_enabled=os.getenv("AI_ENABLED", "false").lower() == "true",
        )

    def startup_warnings(self) -> List[str]:
        warnings = []
        if self.jwt_secret == "dev-only-change-me-please-set-a-real-secret":
            warnings.append("JWT_SECRET is using the development default.")
        if not self.supabase_url or not self.supabase_key:
            warnings.append("Supabase is not configured; persistence endpoints use local in-memory fallback.")
        if self.ai_enabled and not self.ai_api_key:
            warnings.append("AI_ENABLED=true but AI_API_KEY is missing; deterministic AI fallback will be used.")
        return warnings


settings = Settings.from_env()
