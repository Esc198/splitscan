from __future__ import annotations

from fastapi import FastAPI

from .routers.auth import router as auth_router
from .routers.categories import router as categories_router
from .routers.groups import router as groups_router
from .routers.health import router as health_router
from .routers.receipt_inference import router as receipt_inference_router
from .routers.summary import router as summary_router
from .routers.sync import router as sync_router
from .routers.users import router as users_router


def register_routers(app: FastAPI) -> None:
    """Register the currently extracted API routers on the application."""
    app.include_router(health_router)
    app.include_router(receipt_inference_router)
    app.include_router(users_router)
    app.include_router(auth_router)
    app.include_router(categories_router)
    app.include_router(sync_router)
    app.include_router(summary_router)
    app.include_router(groups_router)
