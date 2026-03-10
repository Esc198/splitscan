from __future__ import annotations

import logging


def configure_backend_logging(level_name: str) -> None:
    """Initialize backend logging and reuse Uvicorn handlers when possible."""
    level = getattr(logging, level_name, logging.INFO)
    backend_logger = logging.getLogger("backend")
    backend_logger.setLevel(level)

    uvicorn_error_logger = logging.getLogger("uvicorn.error")
    if uvicorn_error_logger.handlers:
        backend_logger.handlers = list(uvicorn_error_logger.handlers)
        backend_logger.propagate = False
        return

    root_logger = logging.getLogger()
    if root_logger.handlers:
        backend_logger.propagate = True
        return

    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s"))
    backend_logger.handlers = [handler]
    backend_logger.propagate = False
