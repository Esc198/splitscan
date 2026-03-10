from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["system"])


@router.get("/health")
def health() -> dict[str, str]:
    """Return a basic health response for monitoring probes."""
    return {"status": "ok"}
