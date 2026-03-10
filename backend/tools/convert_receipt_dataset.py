from __future__ import annotations

import argparse
from dataclasses import dataclass
from io import BytesIO
import json
import logging
from pathlib import Path
import random
import re
import shutil
import statistics
import sys
from typing import Any, Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PIL import Image, UnidentifiedImageError

from utils.receipt_json_schema import normalize_receipt_payload

LOGGER = logging.getLogger("convert_receipt_dataset")
IMAGE_EXTENSIONS = [".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"]

AMOUNT_REGEX = re.compile(r"[+-]?\s*(?:\d{1,3}(?:[.\s]\d{3})*|\d+)[.,]\d{2}")
HEADER_REGEX = re.compile(
    r"\b(item|product|description|qty|quantity|amount|price|importe|subtotal|unit)\b",
    re.IGNORECASE,
)
TOTAL_REGEX = re.compile(r"\b(total|amount due|balance due|subtotal|tax|iva|vat)\b", re.IGNORECASE)


@dataclass(frozen=True)
class SourceWord:
    text: str
    bbox: tuple[float, float, float, float]
    label: str

    @property
    def x(self) -> float:
        return float(self.bbox[0])

    @property
    def y_center(self) -> float:
        return float(self.bbox[1] + (self.bbox[3] / 2.0))

    @property
    def height(self) -> float:
        return float(self.bbox[3])


@dataclass(frozen=True)
class ConvertedSample:
    sample_id: str
    image_path: Path
    payload: dict[str, list[dict[str, str]]]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert OCR/token-label receipt data into Donut metadata.jsonl splits.")
    parser.add_argument("--source", type=Path, default=Path("dataset"), help="Source dataset directory.")
    parser.add_argument("--output", type=Path, default=Path("dataset"), help="Destination Donut dataset directory.")
    parser.add_argument(
        "--hf-dataset",
        type=str,
        default="naver-clova-ix/cord-v2",
        help="Hugging Face dataset repo to download when the local source is empty.",
    )
    parser.add_argument(
        "--hf-local-dir",
        type=Path,
        default=Path(".hf_dataset_repo"),
        help="Local directory used to mirror the Hugging Face dataset repo.",
    )
    parser.add_argument(
        "--hf-train-limit",
        type=int,
        default=0,
        help="Optional cap for downloaded train samples.",
    )
    parser.add_argument(
        "--hf-validation-limit",
        type=int,
        default=0,
        help="Optional cap for downloaded validation samples.",
    )
    parser.add_argument("--validation-ratio", type=float, default=0.2, help="Used when no split files are present.")
    parser.add_argument("--seed", type=int, default=42, help="Split seed.")
    parser.add_argument("--keep-empty", action="store_true", help="Keep receipts that produce an empty items list.")
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Python logging level.",
    )
    return parser.parse_args()


def setup_logging(level_name: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level_name.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def parse_bbox(raw_bbox: Any) -> tuple[float, float, float, float] | None:
    if isinstance(raw_bbox, (list, tuple)) and len(raw_bbox) == 4:
        try:
            x, y, width, height = (float(value) for value in raw_bbox)
        except (TypeError, ValueError):
            return None
        if width > 0 and height > 0:
            return x, y, width, height
    return None


def parse_quad(raw_quad: Any) -> tuple[float, float, float, float] | None:
    if not isinstance(raw_quad, (list, tuple)) or len(raw_quad) != 4:
        return None

    points: list[tuple[float, float]] = []
    for entry in raw_quad:
        if isinstance(entry, dict):
            try:
                points.append((float(entry["x"]), float(entry["y"])))
            except (KeyError, TypeError, ValueError):
                return None
        elif isinstance(entry, (list, tuple)) and len(entry) == 2:
            try:
                points.append((float(entry[0]), float(entry[1])))
            except (TypeError, ValueError):
                return None
        else:
            return None

    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    x_min = min(xs)
    y_min = min(ys)
    width = max(xs) - x_min
    height = max(ys) - y_min
    if width <= 0 or height <= 0:
        return None
    return x_min, y_min, width, height


def normalize_label(raw_label: Any, text: str) -> str:
    label = str(raw_label or "").upper().strip()
    if label in {"ITEM_DESC", "ITEM_QTY", "ITEM_PRICE", "TOTAL", "TAX", "HEADER", "NOISE"}:
        return label
    if TOTAL_REGEX.search(text):
        return "TOTAL"
    if HEADER_REGEX.search(text):
        return "HEADER"
    if AMOUNT_REGEX.search(text):
        return "ITEM_PRICE"
    return "ITEM_DESC"


def load_words(payload: dict[str, Any]) -> list[SourceWord]:
    raw_words = payload.get("words") or payload.get("tokens") or payload.get("ocr_words") or []
    if not isinstance(raw_words, list):
        return []

    words: list[SourceWord] = []
    for raw_word in raw_words:
        if not isinstance(raw_word, dict):
            continue

        text = str(
            raw_word.get("text")
            or raw_word.get("word")
            or raw_word.get("token")
            or raw_word.get("value")
            or ""
        ).strip()
        if not text:
            continue

        bbox = parse_bbox(raw_word.get("bbox") or raw_word.get("box"))
        if bbox is None:
            bbox = parse_quad(raw_word.get("quad"))
        if bbox is None:
            continue

        label = normalize_label(
            raw_word.get("label") or raw_word.get("pred") or raw_word.get("tag"),
            text=text,
        )
        words.append(SourceWord(text=text, bbox=bbox, label=label))
    return words


def resolve_image_path(source_dir: Path, annotation_path: Path, payload: dict[str, Any]) -> Path:
    candidates: list[Path] = []
    for key in ("image", "file_name", "image_path"):
        raw_value = str(payload.get(key, "")).strip()
        if not raw_value:
            continue
        candidate = Path(raw_value)
        if candidate.is_absolute():
            candidates.append(candidate)
        else:
            candidates.extend(
                [
                    source_dir / "images" / candidate,
                    annotation_path.parent / candidate,
                    source_dir / candidate,
                ]
            )

    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()

    for extension in IMAGE_EXTENSIONS:
        candidate = source_dir / "images" / f"{annotation_path.stem}{extension}"
        if candidate.exists():
            return candidate.resolve()

    raise FileNotFoundError(f"Could not resolve image for annotation {annotation_path}")


def verify_image(image_path: Path) -> None:
    try:
        with Image.open(image_path) as image:
            image.verify()
    except (OSError, UnidentifiedImageError) as exc:
        raise RuntimeError(f"Unreadable image: {image_path}") from exc


def extract_existing_payload(payload: dict[str, Any]) -> dict[str, list[dict[str, str]]] | None:
    if "gt_parse" in payload or "items" in payload or "ground_truth" in payload:
        try:
            return normalize_receipt_payload(payload.get("ground_truth", payload))
        except Exception:
            return None
    return None


def cluster_rows(words: list[SourceWord]) -> list[list[SourceWord]]:
    if not words:
        return []

    sorted_words = sorted(words, key=lambda word: (word.y_center, word.x))
    average_height = statistics.mean([max(word.height, 1.0) for word in sorted_words])
    threshold = max(6.0, average_height * 0.75)

    rows: list[list[SourceWord]] = []
    row_means: list[float] = []
    for word in sorted_words:
        placed = False
        for index, mean in enumerate(row_means):
            if abs(mean - word.y_center) <= threshold:
                rows[index].append(word)
                row_means[index] = (row_means[index] + word.y_center) / 2.0
                placed = True
                break
        if not placed:
            rows.append([word])
            row_means.append(word.y_center)

    return [sorted(row, key=lambda word: word.x) for row in rows]


def build_items_from_words(words: list[SourceWord]) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for row in cluster_rows(words):
        row_text = " ".join(word.text for word in row).strip()
        if not row_text:
            continue
        if TOTAL_REGEX.search(row_text):
            continue
        if HEADER_REGEX.search(row_text) and not any(AMOUNT_REGEX.search(word.text) for word in row):
            continue

        price_candidates = [word for word in row if word.label == "ITEM_PRICE" or AMOUNT_REGEX.search(word.text)]
        product_candidates = [word for word in row if word.label == "ITEM_DESC"]
        if not product_candidates:
            product_candidates = [
                word
                for word in row
                if word.label not in {"ITEM_PRICE", "ITEM_QTY", "HEADER", "TOTAL", "TAX", "NOISE"}
                and not AMOUNT_REGEX.search(word.text)
            ]

        if not product_candidates or not price_candidates:
            continue

        product = " ".join(word.text for word in product_candidates).strip()
        price = max(price_candidates, key=lambda word: word.x).text.strip()
        if not product or not price:
            continue

        items.append({"product": product, "price": price})
    return items


def load_annotation_samples(source_dir: Path, keep_empty: bool) -> list[ConvertedSample]:
    annotations_dir = source_dir / "annotations"
    if not annotations_dir.exists():
        raise FileNotFoundError(f"Expected annotations directory: {annotations_dir}")

    annotation_files = sorted(annotations_dir.glob("*.json"))
    if not annotation_files:
        raise RuntimeError(
            "No annotation JSON files were found in "
            f"{annotations_dir}. "
            "Populate dataset/annotations first, point --source to your existing OCR/token-label dataset root, "
            "or generate the legacy dataset with ml_training/prepare_dataset.py before converting."
        )

    samples: list[ConvertedSample] = []
    for annotation_path in annotation_files:
        try:
            payload = json.loads(annotation_path.read_text(encoding="utf-8"))
            if isinstance(payload, list):
                payload = {"words": payload}
            if not isinstance(payload, dict):
                raise ValueError("annotation payload is not a JSON object")

            image_path = resolve_image_path(source_dir, annotation_path, payload)
            verify_image(image_path)

            gt_payload = extract_existing_payload(payload)
            if gt_payload is None:
                words = load_words(payload)
                gt_payload = normalize_receipt_payload({"items": build_items_from_words(words)})

            if not keep_empty and not gt_payload.get("items"):
                LOGGER.warning("Skipping %s because no item rows could be reconstructed.", annotation_path.name)
                continue

            sample_id = str(payload.get("sample_id") or annotation_path.stem)
            samples.append(
                ConvertedSample(
                    sample_id=sample_id,
                    image_path=image_path,
                    payload=gt_payload,
                )
            )
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Skipping %s: %s", annotation_path, exc)

    if not samples:
        raise RuntimeError(f"No convertible samples found in {annotations_dir}")
    return samples


def source_is_donut(source_dir: Path) -> bool:
    return (source_dir / "train" / "metadata.jsonl").exists() and (source_dir / "validation" / "metadata.jsonl").exists()


def has_local_annotations(source_dir: Path) -> bool:
    annotations_dir = source_dir / "annotations"
    return annotations_dir.exists() and any(annotations_dir.glob("*.json"))


def reset_output_split(output_dir: Path, split_name: str) -> Path:
    split_dir = output_dir / split_name
    if split_dir.exists():
        shutil.rmtree(split_dir)
    images_dir = split_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    return split_dir


def copy_existing_donut_split(source_dir: Path, output_dir: Path, split_name: str) -> int:
    source_split_dir = source_dir / split_name
    source_images_dir = source_split_dir / "images"
    metadata_path = source_split_dir / "metadata.jsonl"
    same_root = source_dir.resolve() == output_dir.resolve()
    if same_root:
        target_split_dir = source_split_dir
        target_images_dir = source_images_dir
    else:
        target_split_dir = reset_output_split(output_dir, split_name)
        target_images_dir = target_split_dir / "images"

    converted_rows: list[str] = []
    with metadata_path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            record = json.loads(line)
            if not isinstance(record, dict):
                continue
            file_name = str(record.get("file_name", "")).strip()
            if not file_name:
                continue

            source_image_path = source_images_dir / file_name
            verify_image(source_image_path)
            target_image_path = target_images_dir / file_name
            if source_image_path.resolve() != target_image_path.resolve():
                shutil.copy2(source_image_path, target_image_path)

            normalized_record = {
                "file_name": file_name,
                "ground_truth": json.dumps(normalize_receipt_payload(record.get("ground_truth", {})), ensure_ascii=False),
            }
            converted_rows.append(json.dumps(normalized_record, ensure_ascii=False))

    (target_split_dir / "metadata.jsonl").write_text("\n".join(converted_rows) + "\n", encoding="utf-8")
    return len(converted_rows)


def read_split_keys(path: Path) -> set[str]:
    if not path.exists():
        return set()
    keys: set[str] = set()
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        keys.add(line)
        keys.add(Path(line).stem)
    return keys


def assign_splits(samples: list[ConvertedSample], source_dir: Path, validation_ratio: float, seed: int) -> dict[str, list[ConvertedSample]]:
    splits_dir = source_dir / "splits"
    train_keys = read_split_keys(splits_dir / "train.txt")
    validation_keys = read_split_keys(splits_dir / "validation.txt") | read_split_keys(splits_dir / "val.txt")

    if train_keys or validation_keys:
        assignments = {"train": [], "validation": []}
        for sample in samples:
            sample_keys = {sample.sample_id, sample.image_path.name, sample.image_path.stem}
            if sample_keys & validation_keys:
                assignments["validation"].append(sample)
            else:
                assignments["train"].append(sample)
        if not assignments["validation"]:
            LOGGER.warning("Split files were found but no validation samples matched. Falling back to random split.")
        else:
            return assignments

    shuffled_samples = list(samples)
    random.Random(seed).shuffle(shuffled_samples)
    validation_count = max(1, int(round(len(shuffled_samples) * validation_ratio))) if len(shuffled_samples) > 1 else 0
    return {
        "validation": shuffled_samples[:validation_count],
        "train": shuffled_samples[validation_count:],
    }


def write_split(output_dir: Path, split_name: str, samples: Iterable[ConvertedSample]) -> int:
    split_dir = reset_output_split(output_dir, split_name)
    images_dir = split_dir / "images"

    rows: list[str] = []
    count = 0
    for sample in samples:
        file_name = f"{sample.sample_id}{sample.image_path.suffix.lower()}"
        target_image_path = images_dir / file_name
        if sample.image_path.resolve() != target_image_path.resolve():
            shutil.copy2(sample.image_path, target_image_path)
        rows.append(
            json.dumps(
                {
                    "file_name": file_name,
                    "ground_truth": json.dumps(sample.payload, ensure_ascii=False),
                },
                ensure_ascii=False,
            )
        )
        count += 1

    (split_dir / "metadata.jsonl").write_text("\n".join(rows) + ("\n" if rows else ""), encoding="utf-8")
    return count


def download_hf_dataset_repo(repo_id: str, local_dir: Path) -> Path:
    try:
        from huggingface_hub import snapshot_download
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(
            "Downloading from Hugging Face requires huggingface_hub. Install it in the active environment first."
        ) from exc

    local_dir = local_dir.resolve()
    local_dir.mkdir(parents=True, exist_ok=True)
    LOGGER.info("Downloading dataset repo %s into %s", repo_id, local_dir)
    snapshot_download(
        repo_id=repo_id,
        repo_type="dataset",
        local_dir=str(local_dir),
        allow_patterns=["data/*.parquet", "README.md", "dataset_infos.json"],
    )
    return local_dir


def resolve_parquet_files(repo_dir: Path, split_name: str) -> list[Path]:
    data_dir = repo_dir / "data"
    if not data_dir.exists():
        raise FileNotFoundError(f"Hugging Face dataset repo has no data directory: {data_dir}")
    parquet_files = sorted(data_dir.glob(f"{split_name}-*.parquet"))
    if not parquet_files:
        raise FileNotFoundError(f"No parquet files found for split '{split_name}' in {data_dir}")
    return parquet_files


def collapse_spaces(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def extract_nested_names(raw_node: Any) -> list[str]:
    names: list[str] = []
    if isinstance(raw_node, dict):
        candidate_name = collapse_spaces(raw_node.get("nm") or raw_node.get("sub_nm") or raw_node.get("name"))
        if candidate_name:
            names.append(candidate_name)
        for key in ("sub", "menu", "items"):
            child = raw_node.get(key)
            if child is not None:
                names.extend(extract_nested_names(child))
    elif isinstance(raw_node, list):
        for child in raw_node:
            names.extend(extract_nested_names(child))
    return names


def extract_cord_items_from_ground_truth(raw_ground_truth: str) -> dict[str, list[dict[str, str]]]:
    payload = json.loads(raw_ground_truth)
    gt_parse = payload.get("gt_parse", {}) if isinstance(payload, dict) else {}
    raw_menu = gt_parse.get("menu", []) if isinstance(gt_parse, dict) else []

    items: list[dict[str, str]] = []
    if isinstance(raw_menu, list):
        for raw_item in raw_menu:
            if not isinstance(raw_item, dict):
                continue

            product_parts = [part for part in extract_nested_names(raw_item) if part]
            if not product_parts:
                primary_name = collapse_spaces(raw_item.get("nm") or raw_item.get("sub_nm") or raw_item.get("num"))
                if primary_name:
                    product_parts.append(primary_name)

            price = collapse_spaces(
                raw_item.get("price") or raw_item.get("unitprice") or raw_item.get("discountprice")
            )
            product = " - ".join(dict.fromkeys(product_parts))

            if not product and not price:
                continue
            items.append(
                {
                    "product": product,
                    "price": price,
                }
            )

    return normalize_receipt_payload({"items": items})


def save_hf_image(raw_image: Any, target_path: Path) -> None:
    if not isinstance(raw_image, dict):
        raise ValueError("Unsupported image payload from Hugging Face dataset")

    image_bytes = raw_image.get("bytes")
    if not isinstance(image_bytes, (bytes, bytearray)):
        raise ValueError("Image payload does not contain raw bytes")

    with Image.open(BytesIO(image_bytes)) as image:
        image.save(target_path)


def convert_hf_split(
    repo_dir: Path,
    output_dir: Path,
    split_name: str,
    *,
    output_split_name: str | None = None,
    max_samples: int = 0,
    keep_empty: bool = False,
) -> int:
    try:
        import pandas as pd
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("Reading Hugging Face parquet files requires pandas.") from exc

    split_dir = reset_output_split(output_dir, output_split_name or split_name)
    images_dir = split_dir / "images"
    metadata_rows: list[str] = []
    sample_count = 0

    for parquet_path in resolve_parquet_files(repo_dir, split_name):
        frame = pd.read_parquet(parquet_path, columns=["image", "ground_truth"])
        for row_index, row in enumerate(frame.itertuples(index=False), start=1):
            payload = extract_cord_items_from_ground_truth(row.ground_truth)
            if not keep_empty and not payload.get("items"):
                continue

            sample_id = f"{split_name}_{sample_count:06d}"
            image_suffix = ".png"
            raw_image = row.image
            if isinstance(raw_image, dict):
                try:
                    with Image.open(BytesIO(raw_image.get("bytes", b""))) as image:
                        image_suffix = f".{(image.format or 'PNG').lower()}"
                except Exception:
                    image_suffix = ".png"

            file_name = f"{sample_id}{image_suffix}"
            save_hf_image(raw_image, images_dir / file_name)
            metadata_rows.append(
                json.dumps(
                    {
                        "file_name": file_name,
                        "ground_truth": json.dumps(payload, ensure_ascii=False),
                    },
                    ensure_ascii=False,
                )
            )
            sample_count += 1

            if max_samples > 0 and sample_count >= max_samples:
                break
        if max_samples > 0 and sample_count >= max_samples:
            break

    if sample_count <= 0:
        raise RuntimeError(f"No Hugging Face samples were converted for split '{split_name}'")

    (split_dir / "metadata.jsonl").write_text("\n".join(metadata_rows) + "\n", encoding="utf-8")
    return sample_count


def convert_hf_dataset(
    repo_id: str,
    local_dir: Path,
    output_dir: Path,
    *,
    train_split_name: str = "train",
    validation_split_name: str = "validation",
    train_limit: int = 0,
    validation_limit: int = 0,
    keep_empty: bool = False,
) -> tuple[int, int]:
    repo_dir = download_hf_dataset_repo(repo_id, local_dir)
    train_count = convert_hf_split(
        repo_dir,
        output_dir,
        "train",
        output_split_name=train_split_name,
        max_samples=train_limit,
        keep_empty=keep_empty,
    )
    validation_count = convert_hf_split(
        repo_dir,
        output_dir,
        "validation",
        output_split_name=validation_split_name,
        max_samples=validation_limit,
        keep_empty=keep_empty,
    )
    return train_count, validation_count


def main() -> None:
    args = parse_args()
    setup_logging(args.log_level)

    source_dir = args.source.resolve()
    output_dir = args.output.resolve()

    if source_is_donut(source_dir):
        train_count = copy_existing_donut_split(source_dir, output_dir, "train")
        validation_count = copy_existing_donut_split(source_dir, output_dir, "validation")
        LOGGER.info(
            "Normalized existing Donut dataset into %s (train=%s validation=%s)",
            output_dir,
            train_count,
            validation_count,
        )
        return

    if has_local_annotations(source_dir):
        samples = load_annotation_samples(source_dir, keep_empty=args.keep_empty)
        split_assignments = assign_splits(
            samples,
            source_dir=source_dir,
            validation_ratio=float(args.validation_ratio),
            seed=int(args.seed),
        )
        train_count = write_split(output_dir, "train", split_assignments["train"])
        validation_count = write_split(output_dir, "validation", split_assignments["validation"])
        LOGGER.info(
            "Converted %s local samples into Donut format at %s (train=%s validation=%s)",
            len(samples),
            output_dir,
            train_count,
            validation_count,
        )
        return

    if args.hf_dataset.strip():
        train_count, validation_count = convert_hf_dataset(
            args.hf_dataset.strip(),
            args.hf_local_dir,
            output_dir,
            train_limit=int(args.hf_train_limit),
            validation_limit=int(args.hf_validation_limit),
            keep_empty=args.keep_empty,
        )
        LOGGER.info(
            "Downloaded and converted Hugging Face dataset %s into %s (train=%s validation=%s)",
            args.hf_dataset,
            output_dir,
            train_count,
            validation_count,
        )
        return

    raise RuntimeError(
        f"No local annotations were found in {source_dir / 'annotations'}, and no --hf-dataset was provided."
    )


if __name__ == "__main__":
    main()
