from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_DIR.parent
PROJECT_ROOT = BACKEND_DIR


def _load_env_files() -> None:
    """Load backend and repository env files without overriding explicit shell values."""
    load_dotenv(BACKEND_DIR / ".env")
    load_dotenv(REPO_ROOT / ".env")


def _parse_bool(value: str | None, *, default: bool = False) -> bool:
    """Parse common truthy string values from environment variables."""
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_origins(value: str | None) -> list[str]:
    """Normalize the comma-separated CORS origin list."""
    raw_value = value if value is not None else "*"
    origins = [origin.strip() for origin in raw_value.split(",") if origin.strip()]
    return origins or ["*"]


@dataclass(frozen=True)
class AppSettings:
    """Centralized runtime settings for the backend application."""

    project_root: Path
    backend_dir: Path
    database_path: Path
    cors_origins: list[str]
    allow_all_origins: bool
    donut_model_dir: Path
    donut_config_path: Path
    donut_device: str
    donut_preload_model: bool
    backend_log_level: str
    api_title: str = "SplitScan API"
    api_version: str = "1.0.0"


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    """Build the application settings object from environment variables."""
    _load_env_files()

    cors_origins = _parse_origins(os.getenv("CORS_ORIGINS"))
    return AppSettings(
        project_root=PROJECT_ROOT,
        backend_dir=BACKEND_DIR,
        database_path=Path(os.getenv("DATABASE_PATH", PROJECT_ROOT / "data" / "gastosmart.db")),
        cors_origins=cors_origins,
        allow_all_origins=len(cors_origins) == 1 and cors_origins[0] == "*",
        donut_model_dir=Path(os.getenv("DONUT_MODEL_DIR", PROJECT_ROOT / "models" / "donut_receipt_model")),
        donut_config_path=Path(os.getenv("DONUT_CONFIG_PATH", PROJECT_ROOT / "configs" / "donut_config.yaml")),
        donut_device=os.getenv("DONUT_DEVICE", "auto").strip().lower(),
        donut_preload_model=_parse_bool(os.getenv("DONUT_PRELOAD_MODEL")),
        backend_log_level=os.getenv("BACKEND_LOG_LEVEL", "INFO").strip().upper(),
    )


settings = get_settings()
