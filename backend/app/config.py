"""Application configuration using Pydantic Settings."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Centralized configuration for Supplier Risk Intelligence."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Predictive Supplier Risk Intelligence"
    app_env: str = Field(default="development", alias="APP_ENV")
    debug: bool = Field(default=False, alias="DEBUG")

    # Database: defaults to local SQLite; supports PostgreSQL via DATABASE_URL
    database_url: str = Field(
        default=f"sqlite:///{BASE_DIR / 'data' / 'supplier_risk.db'}",
        alias="DATABASE_URL",
    )

    # Security & JWT
    jwt_secret_key: str = Field(
        default="sri-local-dev-secret-key-change-in-production-9f8e7d6c5b4a",
        alias="JWT_SECRET_KEY",
    )
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 480

    # Artifacts & Data directories (overridable so tests never touch demo data)
    artifacts_dir: Path = Field(default=BASE_DIR / "artifacts", alias="ARTIFACTS_DIR")
    data_dir: Path = Field(default=BASE_DIR / "data", alias="DATA_DIR")

    # Authentication / demo mode
    # When ALLOW_DEMO_MODE is false, X-Demo-Role / X-Demo-User headers are ignored and
    # a valid JWT is mandatory. Keep this true only for local evaluation.
    allow_demo_mode: bool = Field(default=True, alias="ALLOW_DEMO_MODE")
    seed_demo_data: bool = Field(default=True, alias="SEED_DEMO_DATA")
    auto_train_on_startup: bool = Field(default=True, alias="AUTO_TRAIN_ON_STARTUP")

    # Reproducibility seed
    random_seed: int = Field(default=42, alias="RANDOM_SEED")

    # Default Risk & Prioritization Thresholds
    moderate_risk_threshold: float = 0.35
    high_risk_threshold: float = 0.60
    critical_risk_threshold: float = 0.80
    default_reviewer_capacity: int = 25

    # Optional AI / LLM Provider settings (default off / offline)
    ai_provider: str = Field(default="none", alias="AI_PROVIDER")
    ai_base_url: str = Field(default="", alias="AI_BASE_URL")
    ai_api_key: str = Field(default="", alias="AI_API_KEY")
    ai_model: str = Field(default="", alias="AI_MODEL")
    ai_timeout_seconds: int = Field(default=20, alias="AI_TIMEOUT_SECONDS")
    ai_max_retries: int = Field(default=2, alias="AI_MAX_RETRIES")
    ai_max_tokens: int = Field(default=600, alias="AI_MAX_TOKENS")
    ai_budget_limit_usd: float = Field(default=10.0, alias="AI_BUDGET_LIMIT_USD")
    # Optional dedicated key for encrypting provider secrets at rest. Falls back to
    # JWT_SECRET_KEY when unset (see SECURITY.md).
    ai_encryption_key: str = Field(default="", alias="AI_ENCRYPTION_KEY")

    # Reference date for reproducible synthetic operational environment
    reference_date: str = Field(default="2026-10-17", alias="REFERENCE_DATE")

    # CORS Origins
    cors_origins: str = Field(default="*", alias="CORS_ORIGINS")


settings = Settings()
os.makedirs(settings.artifacts_dir, exist_ok=True)
os.makedirs(settings.data_dir, exist_ok=True)
