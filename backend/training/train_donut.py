from __future__ import annotations

import argparse
import inspect
import json
import logging
from pathlib import Path
import random
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import torch

from models.donut_model import (
    DonutTrainingConfig,
    DonutWorkflowConfig,
    load_processor_and_model,
    load_workflow_config,
    save_task_config,
)
from training.dataset_donut import DonutReceiptCollator, ReceiptDonutDataset, load_donut_receipt_samples

LOGGER = logging.getLogger("train_donut")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train a Donut model for receipt item extraction.")
    parser.add_argument("--dataset", type=Path, required=True, help="Dataset root with train/ and validation/ folders.")
    parser.add_argument(
        "--config",
        type=Path,
        default=PROJECT_ROOT / "configs" / "donut_config.yaml",
        help="Path to the Donut YAML config.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Optional override for the trained model directory.",
    )
    parser.add_argument(
        "--resume-from-checkpoint",
        type=str,
        default=None,
        help="Checkpoint path or last-checkpoint alias supported by Hugging Face Trainer.",
    )
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


def resolve_output_dir(output_dir_arg: Path | None, training_config: DonutTrainingConfig) -> Path:
    if output_dir_arg is not None:
        return output_dir_arg.resolve()
    configured_path = Path(training_config.output_dir)
    if configured_path.is_absolute():
        return configured_path
    return (PROJECT_ROOT / configured_path).resolve()


def set_reproducible_seed(seed: int) -> None:
    random.seed(seed)
    try:
        import numpy as np

        np.random.seed(seed)
    except Exception:
        pass

    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)

    try:
        from transformers import set_seed

        set_seed(seed)
    except Exception:
        pass


def resolve_precision_flags() -> tuple[bool, bool]:
    if not torch.cuda.is_available():
        return False, False
    supports_bf16 = bool(getattr(torch.cuda, "is_bf16_supported", lambda: False)())
    return (not supports_bf16), supports_bf16


def build_training_arguments(
    workflow_config: DonutWorkflowConfig,
    *,
    output_dir: Path,
) -> Any:
    try:
        from transformers import TrainingArguments
    except ImportError as exc:  # pragma: no cover - dependency check
        raise RuntimeError(
            "Missing dependency 'transformers'. Install with: python -m pip install -r backend/requirements.txt"
        ) from exc

    fp16, bf16 = resolve_precision_flags()
    training_config = workflow_config.training
    signature = inspect.signature(TrainingArguments.__init__)
    parameter_names = signature.parameters

    kwargs: dict[str, Any] = {
        "output_dir": str(output_dir),
        "overwrite_output_dir": True,
        "per_device_train_batch_size": int(training_config.per_device_train_batch_size),
        "per_device_eval_batch_size": int(training_config.per_device_eval_batch_size),
        "learning_rate": float(training_config.learning_rate),
        "num_train_epochs": int(training_config.num_train_epochs),
        "warmup_steps": int(training_config.warmup_steps),
        "gradient_accumulation_steps": int(training_config.gradient_accumulation_steps),
        "weight_decay": float(training_config.weight_decay),
        "logging_steps": int(training_config.logging_steps),
        "save_total_limit": int(training_config.save_total_limit),
        "dataloader_num_workers": int(training_config.dataloader_num_workers),
        "seed": int(training_config.seed),
        "fp16": fp16,
        "bf16": bf16,
        "remove_unused_columns": False,
        "save_strategy": "epoch",
        "logging_strategy": "steps",
        "load_best_model_at_end": True,
        "metric_for_best_model": "eval_loss",
        "greater_is_better": False,
        "report_to": [],
        "dataloader_pin_memory": torch.cuda.is_available(),
    }

    eval_strategy_key = "eval_strategy" if "eval_strategy" in parameter_names else "evaluation_strategy"
    kwargs[eval_strategy_key] = "epoch"

    if "save_safetensors" in parameter_names:
        kwargs["save_safetensors"] = True
    if "gradient_checkpointing" in parameter_names:
        kwargs["gradient_checkpointing"] = bool(training_config.gradient_checkpointing)
    if "optim" in parameter_names:
        kwargs["optim"] = "adamw_torch"
    if "do_train" in parameter_names:
        kwargs["do_train"] = True
    if "do_eval" in parameter_names:
        kwargs["do_eval"] = True

    supported_kwargs = {key: value for key, value in kwargs.items() if key in parameter_names}
    dropped_kwargs = sorted(set(kwargs) - set(supported_kwargs))
    if dropped_kwargs:
        LOGGER.info("Skipping unsupported TrainingArguments fields for transformers %s", dropped_kwargs)

    return TrainingArguments(**supported_kwargs)


def save_runtime_snapshot(output_dir: Path, workflow_config: DonutWorkflowConfig) -> None:
    snapshot_path = output_dir / "donut_workflow_config.json"
    snapshot_path.write_text(json.dumps(workflow_config.to_dict(), indent=2, ensure_ascii=True), encoding="utf-8")


def main() -> None:
    args = parse_args()
    setup_logging(args.log_level)

    workflow_config = load_workflow_config(args.config.resolve())
    output_dir = resolve_output_dir(args.output_dir, workflow_config.training)
    set_reproducible_seed(int(workflow_config.training.seed))

    dataset_dir = args.dataset.resolve()
    dataset_config = workflow_config.dataset
    LOGGER.info("Loading dataset from %s", dataset_dir)
    try:
        train_samples = load_donut_receipt_samples(
            dataset_dir,
            dataset_config.train_split,
            metadata_filename=dataset_config.metadata_filename,
            images_subdir=dataset_config.images_subdir,
            verify_images=dataset_config.verify_images,
            max_samples=dataset_config.max_train_samples,
        )
        validation_samples = load_donut_receipt_samples(
            dataset_dir,
            dataset_config.validation_split,
            metadata_filename=dataset_config.metadata_filename,
            images_subdir=dataset_config.images_subdir,
            verify_images=dataset_config.verify_images,
            max_samples=dataset_config.max_validation_samples,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            f"{exc}\n"
            "Expected Donut-ready splits under dataset/train and dataset/validation. "
            "Run the dataset converter first, or point --dataset to a directory that already contains metadata.jsonl files."
        ) from exc

    LOGGER.info("Loaded %s training samples and %s validation samples", len(train_samples), len(validation_samples))
    output_dir.mkdir(parents=True, exist_ok=True)
    LOGGER.info("Loading processor and model from %s", workflow_config.model.pretrained_model_name_or_path)
    processor, model = load_processor_and_model(
        workflow_config.model.pretrained_model_name_or_path,
        workflow_config.model,
    )
    train_dataset = ReceiptDonutDataset(
        train_samples,
        processor,
        workflow_config.model,
        split_name=dataset_config.train_split,
    )
    validation_dataset = ReceiptDonutDataset(
        validation_samples,
        processor,
        workflow_config.model,
        split_name=dataset_config.validation_split,
    )

    training_arguments = build_training_arguments(workflow_config, output_dir=output_dir)

    try:
        from transformers import Trainer
    except ImportError as exc:  # pragma: no cover - dependency check
        raise RuntimeError(
            "Missing dependency 'transformers'. Install with: python -m pip install -r backend/requirements.txt"
        ) from exc

    trainer = Trainer(
        model=model,
        args=training_arguments,
        train_dataset=train_dataset,
        eval_dataset=validation_dataset,
        data_collator=DonutReceiptCollator(),
    )

    LOGGER.info(
        "Starting training: batch_size=%s grad_accum=%s epochs=%s",
        workflow_config.training.per_device_train_batch_size,
        workflow_config.training.gradient_accumulation_steps,
        workflow_config.training.num_train_epochs,
    )
    train_result = trainer.train(resume_from_checkpoint=args.resume_from_checkpoint)

    trainer.save_model(str(output_dir))
    processor.save_pretrained(str(output_dir))
    save_task_config(output_dir, workflow_config.model)
    save_runtime_snapshot(output_dir, workflow_config)

    train_metrics = dict(train_result.metrics)
    train_metrics["train_samples"] = len(train_dataset)
    trainer.log_metrics("train", train_metrics)
    trainer.save_metrics("train", train_metrics)
    trainer.save_state()

    eval_metrics = trainer.evaluate(eval_dataset=validation_dataset)
    eval_metrics["eval_samples"] = len(validation_dataset)
    trainer.log_metrics("eval", eval_metrics)
    trainer.save_metrics("eval", eval_metrics)

    LOGGER.info("Training artifacts saved to %s", output_dir)


if __name__ == "__main__":
    main()
