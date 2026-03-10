from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import torch

from models.donut_model import load_processor_and_model, load_task_config, load_workflow_config

LOGGER = logging.getLogger("export_onnx")


class DonutOnnxWrapper(torch.nn.Module):
    def __init__(self, model: torch.nn.Module) -> None:
        super().__init__()
        self.model = model

    def forward(
        self,
        pixel_values: torch.Tensor,
        decoder_input_ids: torch.Tensor,
        decoder_attention_mask: torch.Tensor,
    ) -> torch.Tensor:
        outputs = self.model(
            pixel_values=pixel_values,
            decoder_input_ids=decoder_input_ids,
            decoder_attention_mask=decoder_attention_mask,
            use_cache=False,
            return_dict=True,
        )
        return outputs.logits


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export a trained Donut receipt model to ONNX.")
    parser.add_argument(
        "--model-dir",
        type=Path,
        default=PROJECT_ROOT / "models" / "donut_receipt_model",
        help="Directory containing the trained Hugging Face model.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=PROJECT_ROOT / "configs" / "donut_config.yaml",
        help="Fallback YAML config when task metadata is not saved with the model.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional ONNX output path. Defaults to the configured export file inside the model directory.",
    )
    parser.add_argument("--opset", type=int, default=None, help="Override ONNX opset.")
    parser.add_argument("--quantize-int8", action="store_true", help="Also export a dynamic INT8 ONNX model.")
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


def load_effective_configs(model_dir: Path, config_path: Path):
    workflow_config = load_workflow_config(config_path.resolve())
    task_config = load_task_config(model_dir) or workflow_config.model
    export_config = workflow_config.export
    return task_config, export_config


def resolve_output_path(model_dir: Path, configured_name: str, override: Path | None) -> Path:
    if override is not None:
        return override.resolve()
    configured_path = Path(configured_name)
    if configured_path.is_absolute():
        return configured_path
    return (model_dir / configured_path).resolve()


def build_dummy_inputs(task_config, processor) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    channels = int(getattr(processor.image_processor, "num_channels", 3) or 3)
    pixel_values = torch.zeros(
        (1, channels, int(task_config.image_height), int(task_config.image_width)),
        dtype=torch.float32,
    )
    task_token_id = int(processor.tokenizer.convert_tokens_to_ids(task_config.task_start_token))
    decoder_input_ids = torch.tensor([[task_token_id]], dtype=torch.long)
    decoder_attention_mask = torch.ones_like(decoder_input_ids)
    return pixel_values, decoder_input_ids, decoder_attention_mask


def quantize_onnx_model(source_path: Path, target_path: Path) -> None:
    try:
        from onnxruntime.quantization import QuantType, quantize_dynamic
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(
            "INT8 quantization requires onnxruntime. Install with: python -m pip install onnxruntime"
        ) from exc

    quantize_dynamic(
        model_input=str(source_path),
        model_output=str(target_path),
        weight_type=QuantType.QInt8,
    )


def save_export_metadata(model_dir: Path, output_path: Path, task_config, quantized_path: Path | None) -> None:
    metadata_path = model_dir / "donut_receipt_onnx.json"
    payload = {
        "onnx_path": str(output_path),
        "quantized_onnx_path": str(quantized_path) if quantized_path else None,
        "task_start_token": task_config.task_start_token,
        "max_length": int(task_config.max_length),
        "image_height": int(task_config.image_height),
        "image_width": int(task_config.image_width),
        "note": "The ONNX graph exports one decoder step graph. Mobile inference still needs an autoregressive decoding loop.",
    }
    metadata_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")


def main() -> None:
    args = parse_args()
    setup_logging(args.log_level)

    model_dir = args.model_dir.resolve()
    task_config, export_config = load_effective_configs(model_dir, args.config)
    output_path = resolve_output_path(model_dir, export_config.output_file, args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    processor, model = load_processor_and_model(model_dir, task_config)
    model = model.to("cpu")
    model.eval()

    wrapper = DonutOnnxWrapper(model)
    dummy_inputs = build_dummy_inputs(task_config, processor)
    opset = int(args.opset or export_config.opset)

    LOGGER.info("Exporting ONNX model to %s", output_path)
    torch.onnx.export(
        wrapper,
        dummy_inputs,
        str(output_path),
        input_names=["pixel_values", "decoder_input_ids", "decoder_attention_mask"],
        output_names=["logits"],
        dynamic_axes={
            "pixel_values": {0: "batch"},
            "decoder_input_ids": {0: "batch", 1: "decoder_sequence"},
            "decoder_attention_mask": {0: "batch", 1: "decoder_sequence"},
            "logits": {0: "batch", 1: "decoder_sequence"},
        },
        opset_version=opset,
        do_constant_folding=True,
    )

    quantized_path: Path | None = None
    if args.quantize_int8:
        quantized_path = resolve_output_path(model_dir, export_config.quantized_output_file, None)
        LOGGER.info("Exporting quantized INT8 ONNX model to %s", quantized_path)
        quantize_onnx_model(output_path, quantized_path)

    save_export_metadata(model_dir, output_path, task_config, quantized_path)
    LOGGER.info("ONNX export completed")


if __name__ == "__main__":
    main()
