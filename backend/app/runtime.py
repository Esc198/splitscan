from __future__ import annotations

from typing import Any

from .core.config import settings

try:
    from donut_inference import DonutReceiptInferenceService
except ImportError:  # pragma: no cover - alternate launch mode
    from backend.donut_inference import DonutReceiptInferenceService


def multipart_support_available() -> bool:
    """Return whether python-multipart is installed for file upload support."""
    try:
        import multipart  # noqa: F401
    except ImportError:
        return False
    return True


donut_inference_service = DonutReceiptInferenceService(
    model_root=settings.donut_model_dir,
    config_path=settings.donut_config_path,
    device_name=settings.donut_device,
)

MULTIPART_SUPPORT_AVAILABLE = multipart_support_available()
