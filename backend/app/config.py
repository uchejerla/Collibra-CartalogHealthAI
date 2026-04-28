"""
app/config.py — Application settings loaded from environment variables.

All secrets must be in backend/.env (gitignored).
Copy backend/.env.example → backend/.env and fill in values before running.
"""
from __future__ import annotations
from functools import lru_cache
from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict

# Always resolve .env relative to this file (backend/app/config.py → backend/.env)
_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ──────────────────────────────────────────────────────────────────
    app_env: str = "development"           # development | staging | production
    log_level: str = "INFO"

    # ── Database (Supabase PostgreSQL) ───────────────────────────────────────
    database_url: str = "postgresql+asyncpg://postgres:password@localhost:5432/catalog_health"

    # ── Anthropic ────────────────────────────────────────────────────────────
    anthropic_api_key: str = "sk-ant-REPLACE_ME"

    # ── CORS ─────────────────────────────────────────────────────────────────
    cors_origins: str = "http://localhost:3000,https://your-app.vercel.app"

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    # ── Governance rules config ───────────────────────────────────────────────
    stale_asset_days: int = 180            # Assets not updated in this many days → stale
    score_weight_high: float = 5.0         # Health score penalty per High finding
    score_weight_medium: float = 3.0       # Penalty per Medium finding
    score_weight_low: float = 1.0          # Penalty per Low finding

    # ── Email (Resend) ────────────────────────────────────────────────────────
    resend_api_key: str = ""
    report_recipient_email: str = ""
    report_sender_email: str = "reports@cataloghealth.ai"

    # ── Notion (for script sync) ─────────────────────────────────────────────
    notion_token: str = ""
    notion_task_db_id: str = "23820100f1ac4fc7b1e80e4b92532f69"
    notion_hub_page_id: str = "34d8afb1a56f8167a074e9bccadc46d2"


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings singleton. Call get_settings() everywhere."""
    return Settings()
