from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import logging
import os
from pathlib import Path
import re
import sys
import threading
from typing import Any

from PIL import Image, UnidentifiedImageError
import torch

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from models.donut_model import (  # noqa: E402
    DonutReceiptTaskConfig,
    build_generation_kwargs,
    configure_model,
    configure_processor,
    load_task_config,
    load_workflow_config,
    register_special_tokens,
)
from utils.receipt_json_schema import parse_receipt_prediction, receipt_to_table  # noqa: E402

LOGGER = logging.getLogger("backend.donut_inference")
CHECKPOINT_NAME_RE = re.compile(r"^checkpoint-(?P<step>\d+)$")
NON_NUMERIC_RE = re.compile(r"[^0-9,.\-]+")


@dataclass(frozen=True)
class LoadedDonutArtifacts:
    task_config: DonutReceiptTaskConfig
    processor: Any
    model: Any
    device: torch.device
    model_source: Path
    processor_source: str
    using_checkpoint_fallback: bool


def _resolve_device(device_name: str) -> torch.device:
    normalized = device_name.strip().lower()
    if normalized == "cpu":
        return torch.device("cpu")
    if normalized == "cuda":
        if not torch.cuda.is_available():
            raise RuntimeError("DONUT_DEVICE=cuda was requested but CUDA is not available.")
        return torch.device("cuda")
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def _has_weights(path: Path) -> bool:
    return any((path / file_name).exists() for file_name in ("model.safetensors", "pytorch_model.bin", "model.safetensors.index.json"))


def _has_config(path: Path) -> bool:
    return (path / "config.json").exists()


def _has_processor_files(path: Path) -> bool:
    return ((path / "preprocessor_config.json").exists() or (path / "processor_config.json").exists()) and (
        path / "tokenizer_config.json"
    ).exists()


def _parse_checkpoint_step(path: Path) -> int:
    match = CHECKPOINT_NAME_RE.match(path.name)
    if match is None:
        return -1
    return int(match.group("step"))


def _resolve_model_source(model_root: Path) -> tuple[Path, bool]:
    if _has_config(model_root) and _has_weights(model_root):
        return model_root, False

    checkpoint_dirs = sorted(
        [
            child
            for child in model_root.iterdir()
            if child.is_dir() and _parse_checkpoint_step(child) >= 0 and _has_config(child) and _has_weights(child)
        ],
        key=_parse_checkpoint_step,
        reverse=True,
    ) if model_root.exists() else []

    if checkpoint_dirs:
        return checkpoint_dirs[0], True

    raise RuntimeError(
        "No trained Donut model weights were found. "
        f"Expected either a complete model under {model_root} or at least one checkpoint-* directory with config and weights."
    )


def _clean_generated_sequence(sequence: str, processor: Any, task_start_token: str) -> str:
    cleaned = sequence
    eos_token = getattr(processor.tokenizer, "eos_token", None)
    pad_token = getattr(processor.tokenizer, "pad_token", None)
    if eos_token:
        cleaned = cleaned.replace(eos_token, "")
    if pad_token:
        cleaned = cleaned.replace(pad_token, "")
    cleaned = cleaned.strip()
    if cleaned.startswith(task_start_token):
        cleaned = cleaned[len(task_start_token) :]
    return cleaned.strip()


def parse_price_value(raw_price: str) -> float | None:
    compact = NON_NUMERIC_RE.sub("", str(raw_price or "").strip()).replace(" ", "")
    if not compact:
        return None

    sign = -1 if compact.startswith("-") else 1
    unsigned = compact.lstrip("+-")
    if not unsigned:
        return None

    if "," in unsigned and "." in unsigned:
        last_comma = unsigned.rfind(",")
        last_dot = unsigned.rfind(".")
        decimal_sep = "," if last_comma > last_dot else "."
        thousands_sep = "." if decimal_sep == "," else ","
        normalized = unsigned.replace(thousands_sep, "").replace(decimal_sep, ".")
    elif "," in unsigned:
        head, tail = unsigned.rsplit(",", 1)
        normalized = f"{head.replace(',', '')}.{tail}" if len(tail) in {1, 2} else unsigned.replace(",", "")
    elif "." in unsigned:
        head, tail = unsigned.rsplit(".", 1)
        normalized = f"{head.replace('.', '')}.{tail}" if len(tail) in {1, 2} else unsigned.replace(".", "")
    else:
        normalized = unsigned

    try:
        parsed = float(normalized)
    except ValueError:
        return None

    if not torch.isfinite(torch.tensor(parsed)):
        return None
    return round(parsed * sign, 2)


class DonutReceiptInferenceService:
    def __init__(
        self,
        *,
        model_root: Path | None = None,
        config_path: Path | None = None,
        device_name: str | None = None,
    ) -> None:
        self.model_root = (model_root or Path(os.getenv("DONUT_MODEL_DIR", BACKEND_DIR / "models" / "donut_receipt_model"))).resolve()
        self.config_path = (config_path or Path(os.getenv("DONUT_CONFIG_PATH", BACKEND_DIR / "configs" / "donut_config.yaml"))).resolve()
        self.device_name = (device_name or os.getenv("DONUT_DEVICE", "auto")).strip().lower()
        self._lock = threading.Lock()
        self._artifacts: LoadedDonutArtifacts | None = None

    def status(self) -> dict[str, Any]:
        model_exists = self.model_root.exists()
        resolved_model_source: str | None = None
        using_checkpoint_fallback = False
        resolution_error: str | None = None
        try:
            model_source, using_checkpoint_fallback = _resolve_model_source(self.model_root)
            resolved_model_source = str(model_source)
        except RuntimeError as exc:
            resolution_error = str(exc)

        loaded = self._artifacts
        return {
            "configured_model_root": str(self.model_root),
            "resolved_model_source": resolved_model_source,
            "config_path": str(self.config_path),
            "model_root_exists": model_exists,
            "ready": loaded is not None,
            "device": loaded.device.type if loaded is not None else self.device_name,
            "using_checkpoint_fallback": using_checkpoint_fallback if loaded is None else loaded.using_checkpoint_fallback,
            "resolution_error": resolution_error,
        }

    def warmup(self) -> LoadedDonutArtifacts:
        return self._get_artifacts()

    def predict_image_bytes(
        self,
        image_bytes: bytes,
        *,
        file_name: str | None = None,
    ) -> dict[str, Any]:
        if not image_bytes:
            raise RuntimeError("The uploaded image is empty.")

        artifacts = self._get_artifacts()
        image = self._load_image(image_bytes, file_name=file_name)
        pixel_values = artifacts.processor(image, return_tensors="pt").pixel_values.to(artifacts.device)
        decoder_input_ids = artifacts.processor.tokenizer(
            artifacts.task_config.task_start_token,
            add_special_tokens=False,
            return_tensors="pt",
        ).input_ids.to(artifacts.device)

        generation_kwargs = build_generation_kwargs(artifacts.processor, artifacts.task_config)
        with torch.inference_mode():
            generated = artifacts.model.generate(
                pixel_values=pixel_values,
                decoder_input_ids=decoder_input_ids,
                **generation_kwargs,
            )

        sequence = artifacts.processor.batch_decode(generated.sequences, skip_special_tokens=False)[0]
        cleaned_sequence = _clean_generated_sequence(sequence, artifacts.processor, artifacts.task_config.task_start_token)
        parsed_payload = parse_receipt_prediction(cleaned_sequence, processor=artifacts.processor)
        table = receipt_to_table(parsed_payload)

        normalized_items: list[dict[str, Any]] = []
        parsed_amounts: list[float] = []
        for row in table:
            product = str(row.get("product", "")).strip()
            price = str(row.get("price", "")).strip()
            amount = parse_price_value(price)
            if amount is not None:
                parsed_amounts.append(amount)
            normalized_items.append(
                {
                    "product": product,
                    "price": price,
                    "amount": amount,
                }
            )

        total = round(sum(parsed_amounts), 2) if parsed_amounts else None
        self._log_detected_rows(
            file_name=file_name,
            items=normalized_items,
            total=total,
            artifacts=artifacts,
        )

        return {
            "engine": "donut",
            "device": artifacts.device.type,
            "model_source": str(artifacts.model_source),
            "processor_source": artifacts.processor_source,
            "using_checkpoint_fallback": artifacts.using_checkpoint_fallback,
            "items": normalized_items,
            "total": total,
            "raw_prediction": parsed_payload,
        }

    def _get_artifacts(self) -> LoadedDonutArtifacts:
        if self._artifacts is not None:
            return self._artifacts

        with self._lock:
            if self._artifacts is not None:
                return self._artifacts
            self._artifacts = self._load_artifacts()
            return self._artifacts

    def _resolve_task_config(self, model_source: Path) -> DonutReceiptTaskConfig:
        for candidate_dir in (self.model_root, model_source):
            task_config = load_task_config(candidate_dir)
            if task_config is not None:
                return task_config
        workflow_config = load_workflow_config(self.config_path)
        return workflow_config.model

    def _load_artifacts(self) -> LoadedDonutArtifacts:
        model_source, using_checkpoint_fallback = _resolve_model_source(self.model_root)
        task_config = self._resolve_task_config(model_source)
        processor_source = str(task_config.pretrained_model_name_or_path)

        try:
            from transformers import DonutProcessor, VisionEncoderDecoderModel
        except ImportError as exc:
            raise RuntimeError(
                "Missing inference dependencies. Install them with: python -m pip install -r backend/requirements.txt"
            ) from exc

        if _has_processor_files(model_source):
            processor_source = str(model_source)
            processor = DonutProcessor.from_pretrained(processor_source, use_fast=False)
        elif _has_processor_files(self.model_root):
            processor_source = str(self.model_root)
            processor = DonutProcessor.from_pretrained(processor_source, use_fast=False)
        else:
            processor = DonutProcessor.from_pretrained(processor_source, use_fast=False)

        model = VisionEncoderDecoderModel.from_pretrained(str(model_source))
        configure_processor(processor, task_config)
        register_special_tokens(processor, model, task_config)
        configure_model(model, processor, task_config)

        device = _resolve_device(self.device_name)
        model.to(device)
        model.eval()

        LOGGER.info(
            "Loaded Donut receipt model from %s on %s (processor=%s checkpoint_fallback=%s)",
            model_source,
            device.type,
            processor_source,
            using_checkpoint_fallback,
        )
        return LoadedDonutArtifacts(
            task_config=task_config,
            processor=processor,
            model=model,
            device=device,
            model_source=model_source,
            processor_source=processor_source,
            using_checkpoint_fallback=using_checkpoint_fallback,
        )

    def _log_detected_rows(
        self,
        *,
        file_name: str | None,
        items: list[dict[str, Any]],
        total: float | None,
        artifacts: LoadedDonutArtifacts,
    ) -> None:
        receipt_label = file_name or "uploaded receipt"
        LOGGER.info(
            "Receipt inference for %s found %s row(s) on %s using %s",
            receipt_label,
            len(items),
            artifacts.device.type,
            artifacts.model_source,
        )
        if not items:
            LOGGER.warning("Receipt inference for %s returned no rows", receipt_label)
        for index, item in enumerate(items, start=1):
            LOGGER.info(
                "Receipt row %s for %s | product=%r | price=%r | amount=%s",
                index,
                receipt_label,
                item.get("product", ""),
                item.get("price", ""),
                item.get("amount", None),
            )
        LOGGER.info("Receipt total for %s | total=%s", receipt_label, total)

    @staticmethod
    def _load_image(image_bytes: bytes, *, file_name: str | None = None) -> Image.Image:
        try:
            with Image.open(BytesIO(image_bytes)) as image:
                return image.convert("RGB")
        except (OSError, UnidentifiedImageError) as exc:
            label = file_name or "uploaded file"
            raise RuntimeError(f"Failed to open {label} as an image: {exc}") from exc
