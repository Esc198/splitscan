from __future__ import annotations

from dataclasses import dataclass
import json
import logging
from pathlib import Path
from typing import Any

from PIL import Image, UnidentifiedImageError
import torch
from torch.utils.data import Dataset

from models.donut_model import DonutReceiptTaskConfig
from utils.receipt_json_schema import normalize_receipt_payload, receipt_json_to_tokens

LOGGER = logging.getLogger(__name__)
IGNORE_LABEL_ID = -100


@dataclass(frozen=True)
class DonutReceiptSample:
    sample_id: str
    image_path: Path
    target_payload: dict[str, list[dict[str, str]]]


def load_donut_receipt_samples(
    dataset_dir: Path,
    split_name: str,
    *,
    metadata_filename: str = "metadata.jsonl",
    images_subdir: str = "images",
    verify_images: bool = True,
    max_samples: int = 0,
) -> list[DonutReceiptSample]:
    split_dir = dataset_dir / split_name
    metadata_path = split_dir / metadata_filename
    images_dir = split_dir / images_subdir

    if not metadata_path.exists():
        raise FileNotFoundError(f"Metadata file not found for split '{split_name}': {metadata_path}")
    if not images_dir.exists():
        raise FileNotFoundError(f"Images directory not found for split '{split_name}': {images_dir}")

    samples: list[DonutReceiptSample] = []
    with metadata_path.open("r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                if not isinstance(record, dict):
                    raise ValueError("metadata row is not a JSON object")

                file_name = str(record.get("file_name", "")).strip()
                if not file_name:
                    raise ValueError("missing file_name")

                ground_truth = record.get("ground_truth", {})
                target_payload = normalize_receipt_payload(ground_truth)
                image_path = images_dir / file_name
                if not image_path.exists():
                    raise FileNotFoundError(f"image not found: {image_path}")

                if verify_images:
                    _verify_image(image_path)

                samples.append(
                    DonutReceiptSample(
                        sample_id=image_path.stem,
                        image_path=image_path,
                        target_payload=target_payload,
                    )
                )
            except Exception as exc:  # noqa: BLE001
                LOGGER.warning(
                    "Skipping malformed sample in %s at line %s: %s",
                    metadata_path,
                    line_number,
                    exc,
                )

            if max_samples > 0 and len(samples) >= max_samples:
                break

    if not samples:
        raise RuntimeError(f"No valid samples loaded from {metadata_path}")
    return samples


def _verify_image(image_path: Path) -> None:
    try:
        with Image.open(image_path) as image:
            image.verify()
    except (OSError, UnidentifiedImageError) as exc:
        raise RuntimeError(f"corrupted image: {image_path}") from exc


class ReceiptDonutDataset(Dataset[dict[str, torch.Tensor]]):
    def __init__(
        self,
        samples: list[DonutReceiptSample],
        processor: Any,
        task_config: DonutReceiptTaskConfig,
        *,
        split_name: str,
    ) -> None:
        self.samples = samples
        self.processor = processor
        self.task_config = task_config
        self.split_name = split_name
        self.random_padding = split_name.strip().lower().startswith("train")
        self.max_length = int(task_config.max_length)
        self.task_start_token = task_config.task_start_token
        self.prompt_end_token_id = int(processor.tokenizer.convert_tokens_to_ids(task_config.prompt_end_token))

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, index: int) -> dict[str, torch.Tensor]:
        sample = self.samples[index]
        image = self._load_image(sample.image_path)
        pixel_values = self.processor.image_processor(
            image,
            return_tensors="pt",
            random_padding=self.random_padding,
        ).pixel_values
        labels = self._build_labels(sample.target_payload)
        return {
            "pixel_values": pixel_values.squeeze(0),
            "labels": labels,
        }

    def _load_image(self, image_path: Path) -> Image.Image:
        try:
            with Image.open(image_path) as image:
                return image.convert("RGB")
        except (OSError, UnidentifiedImageError) as exc:
            LOGGER.warning("Substituting blank image for unreadable file %s: %s", image_path, exc)
            return Image.new(
                "RGB",
                (int(self.task_config.image_width), int(self.task_config.image_height)),
                color=(255, 255, 255),
            )

    def _build_labels(self, target_payload: dict[str, list[dict[str, str]]]) -> torch.Tensor:
        eos_token = self.processor.tokenizer.eos_token or ""
        target_sequence = (
            self.task_start_token
            + receipt_json_to_tokens(target_payload, sort_json_keys=self.task_config.sort_json_keys)
            + eos_token
        )
        tokenized = self.processor.tokenizer(
            target_sequence,
            add_special_tokens=False,
            max_length=self.max_length,
            padding="max_length",
            truncation=True,
            return_tensors="pt",
        )
        labels = tokenized.input_ids.squeeze(0)
        labels = labels.clone()
        labels[labels == self.processor.tokenizer.pad_token_id] = IGNORE_LABEL_ID

        prompt_positions = (labels == self.prompt_end_token_id).nonzero(as_tuple=False)
        if prompt_positions.numel() > 0:
            prompt_end_index = int(prompt_positions[0].item())
            labels[: prompt_end_index + 1] = IGNORE_LABEL_ID
        return labels


class DonutReceiptCollator:
    def __call__(self, batch: list[dict[str, torch.Tensor]]) -> dict[str, torch.Tensor]:
        return {
            "pixel_values": torch.stack([item["pixel_values"] for item in batch]),
            "labels": torch.stack([item["labels"] for item in batch]),
        }
