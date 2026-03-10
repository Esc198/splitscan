from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile

from ...runtime import MULTIPART_SUPPORT_AVAILABLE, donut_inference_service

LOGGER = logging.getLogger("backend.api.receipt_inference")
router = APIRouter(prefix="/api", tags=["receipt-inference"])


@router.get("/receipt-inference/status")
def receipt_inference_status() -> dict[str, Any]:
    """Expose the current receipt inference service status."""
    status = donut_inference_service.status()
    status["multipart_support_available"] = MULTIPART_SUPPORT_AVAILABLE
    return status


if MULTIPART_SUPPORT_AVAILABLE:

    @router.post("/receipt-inference")
    async def infer_receipt_from_image(file: UploadFile = File(...)) -> dict[str, Any]:
        """Run receipt OCR inference for an uploaded image file."""
        file_name = file.filename or "receipt-image"
        content_type = (file.content_type or "").strip().lower()
        if content_type and not content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail=f"Unsupported content type for receipt image: {content_type}")

        image_bytes = await file.read()
        if not image_bytes:
            raise HTTPException(status_code=400, detail="The uploaded receipt image is empty")

        try:
            LOGGER.info(
                "Receipt inference request received | file=%s | content_type=%s | bytes=%s",
                file_name,
                content_type or "unknown",
                len(image_bytes),
            )
            result = donut_inference_service.predict_image_bytes(image_bytes, file_name=file_name)
            LOGGER.info(
                "Receipt inference request completed | file=%s | rows=%s | total=%s",
                file_name,
                len(result.get("items", [])),
                result.get("total"),
            )
            return result
        except RuntimeError as exc:
            detail = str(exc)
            lowered = detail.lower()
            if "failed to open" in lowered or "uploaded image is empty" in lowered:
                raise HTTPException(status_code=400, detail=detail) from exc
            raise HTTPException(status_code=503, detail=detail) from exc

else:

    @router.post("/receipt-inference")
    async def infer_receipt_from_image_unavailable() -> dict[str, Any]:
        """Report that receipt upload inference is disabled in this environment."""
        raise HTTPException(
            status_code=503,
            detail="Receipt inference upload support requires python-multipart. Install backend/requirements.txt first.",
        )
