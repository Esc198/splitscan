from __future__ import annotations

from collections.abc import Callable
from contextlib import asynccontextmanager
import logging
from typing import Any

from fastapi import FastAPI


def build_lifespan(
    *,
    ensure_schema: Callable[[], None],
    preload_model: bool,
    inference_service: Any,
    logger: logging.Logger,
):
    """Build the FastAPI lifespan handler for startup resource initialization."""

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        """Prepare shared backend resources during the FastAPI application lifespan."""
        ensure_schema()
        if preload_model:
            try:
                inference_service.warmup()
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to preload Donut model: %s", exc)
        yield

    return lifespan
