from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.config import AppSettings


def create_application(*, settings: AppSettings, lifespan: Any) -> FastAPI:
    """Create the FastAPI application with shared middleware configuration."""
    app = FastAPI(title=settings.api_title, version=settings.api_version, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.allow_all_origins else settings.cors_origins,
        allow_credentials=not settings.allow_all_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    return app
