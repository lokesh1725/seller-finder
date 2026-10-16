"""Application configuration loaded from environment variables.

Secrets are never hardcoded; sensible development defaults are provided so the
project can run locally without a full .env file. Production deployments must
set MONGODB_URI, SEARCH_API_KEY (optional) and FRONTEND_URL.
"""
from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - dotenv is part of requirements
    def load_dotenv(*_args, **_kwargs):  # type: ignore
        return False

BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BASE_DIR.parent

load_dotenv(BASE_DIR / ".env")


def _split_origins(raw: str) -> list[str]:
    return [item.strip().rstrip("/") for item in raw.split(",") if item.strip()]


class Config:
    """Base configuration shared by all environments."""

    # --- Flask ---
    FLASK_ENV = os.getenv("FLASK_ENV", "development")
    DEBUG = FLASK_ENV == "development"
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
    JSON_SORT_KEYS = False

    # --- MongoDB ---
    MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    MONGODB_DATABASE = os.getenv("MONGODB_DATABASE", "seller_finder")
    MONGODB_TIMEOUT_MS = int(os.getenv("MONGODB_TIMEOUT_MS", "5000"))

    # --- CORS ---
    # Comma separated list. Defaults cover local Vite dev servers.
    _default_origins = (
        "http://localhost:5173,http://127.0.0.1:5173,"
        "http://localhost:4173,http://127.0.0.1:4173"
    )
    CORS_ORIGINS = _split_origins(os.getenv("FRONTEND_URL", _default_origins))

    # --- External search provider ---
    SEARCH_PROVIDER = os.getenv("SEARCH_PROVIDER", "brave")  # brave | bing | none
    SEARCH_API_KEY = os.getenv("SEARCH_API_KEY", "")
    SEARCH_API_ENDPOINT = os.getenv("SEARCH_API_ENDPOINT", "")
    SEARCH_TIMEOUT_SECONDS = float(os.getenv("SEARCH_TIMEOUT_SECONDS", "10"))
    SEARCH_MAX_RESULTS = int(os.getenv("SEARCH_MAX_RESULTS", "10"))
    SEARCH_CACHE_TTL_HOURS = int(os.getenv("SEARCH_CACHE_TTL_HOURS", "24"))

    # --- Admin / import ---
    ADMIN_API_TOKEN = os.getenv("ADMIN_API_TOKEN", "")

    # --- Application login (dummy credentials by default; override via env) ---
    AUTH_EMAIL = os.getenv("AUTH_EMAIL", "admin@gmail.com")
    AUTH_PASSWORD = os.getenv("AUTH_PASSWORD", "Test@123")
    AUTH_TOKEN_MAX_AGE = int(os.getenv("AUTH_TOKEN_MAX_AGE", str(60 * 60 * 24 * 7)))

    # --- Rate limiting (simple in-process limiter) ---
    RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))

    # --- Frontend public URL used for share links / OG metadata ---
    PUBLIC_FRONTEND_URL = os.getenv(
        "PUBLIC_FRONTEND_URL", "http://localhost:5173"
    ).rstrip("/")


class TestConfig(Config):
    """Configuration used by the automated test-suite."""

    TESTING = True
    DEBUG = False
    MONGODB_DATABASE = os.getenv("MONGODB_TEST_DATABASE", "seller_finder_test")
    RATE_LIMIT_PER_MINUTE = 100000
