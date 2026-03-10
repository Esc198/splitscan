from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any, Mapping

ITEMS_KEY = "items"
PRODUCT_KEY = "product"
PRICE_KEY = "price"
SEPARATOR_TOKEN = "<sep/>"

_WHITESPACE_RE = re.compile(r"\s+")
_ITEMS_SECTION_RE = re.compile(r"<s_items>(?P<body>.*?)</s_items>", re.DOTALL)
_PAIR_SECTION_RE = re.compile(
    r"<s_product>(?P<product>.*?)</s_product>\s*<s_price>(?P<price>.*?)</s_price>",
    re.DOTALL,
)
_TAG_TOKEN_RE = re.compile(r"</?s_[^>]+>")


@dataclass(frozen=True)
class ReceiptItem:
    product: str
    price: str

    def to_dict(self) -> dict[str, str]:
        return {
            PRODUCT_KEY: self.product,
            PRICE_KEY: self.price,
        }


@dataclass(frozen=True)
class ReceiptTable:
    items: tuple[ReceiptItem, ...]

    def to_dict(self) -> dict[str, list[dict[str, str]]]:
        return {
            ITEMS_KEY: [item.to_dict() for item in self.items],
        }


def _collapse_whitespace(value: Any) -> str:
    if value is None:
        return ""
    text = str(value)
    text = text.replace(SEPARATOR_TOKEN, " ")
    text = _TAG_TOKEN_RE.sub(" ", text)
    return _WHITESPACE_RE.sub(" ", text).strip()


def _coerce_payload(raw: Any) -> Any:
    if isinstance(raw, str):
        stripped = raw.strip()
        if not stripped:
            return {}
        return json.loads(stripped)
    return raw


def normalize_receipt_payload(raw: Any) -> dict[str, list[dict[str, str]]]:
    payload = _coerce_payload(raw)

    if isinstance(payload, Mapping) and "gt_parse" in payload:
        payload = payload["gt_parse"]

    if isinstance(payload, list):
        payload = {ITEMS_KEY: payload}

    if not isinstance(payload, Mapping):
        payload = {}

    raw_items = payload.get(ITEMS_KEY, [])
    if not isinstance(raw_items, list):
        raw_items = []

    items: list[ReceiptItem] = []
    for raw_item in raw_items:
        if not isinstance(raw_item, Mapping):
            continue
        product = _collapse_whitespace(raw_item.get(PRODUCT_KEY))
        price = _collapse_whitespace(raw_item.get(PRICE_KEY))
        if not product and not price:
            continue
        items.append(ReceiptItem(product=product, price=price))

    return ReceiptTable(items=tuple(items)).to_dict()


def wrap_gt_parse(raw: Any) -> dict[str, dict[str, list[dict[str, str]]]]:
    return {"gt_parse": normalize_receipt_payload(raw)}


def receipt_to_table(raw: Any) -> list[dict[str, str]]:
    return normalize_receipt_payload(raw)[ITEMS_KEY]


def build_receipt_special_tokens(task_start_token: str | None = None) -> list[str]:
    tokens = [
        "<s_items>",
        "</s_items>",
        "<s_product>",
        "</s_product>",
        "<s_price>",
        "</s_price>",
        SEPARATOR_TOKEN,
    ]
    if task_start_token:
        tokens.insert(0, task_start_token)
    return tokens


def receipt_json_to_tokens(raw: Any, *, sort_json_keys: bool = False) -> str:
    payload = normalize_receipt_payload(raw)
    return _json_to_tokens(payload, sort_json_keys=sort_json_keys)


def _json_to_tokens(value: Any, *, sort_json_keys: bool) -> str:
    if isinstance(value, Mapping):
        keys = sorted(value.keys(), reverse=True) if sort_json_keys else value.keys()
        return "".join(
            f"<s_{key}>{_json_to_tokens(value[key], sort_json_keys=sort_json_keys)}</s_{key}>"
            for key in keys
        )
    if isinstance(value, list):
        return SEPARATOR_TOKEN.join(_json_to_tokens(item, sort_json_keys=sort_json_keys) for item in value)
    return _collapse_whitespace(value)


def receipt_tokens_to_payload(token_sequence: str) -> dict[str, list[dict[str, str]]]:
    sequence = token_sequence.strip()
    if not sequence:
        return {ITEMS_KEY: []}

    items_match = _ITEMS_SECTION_RE.search(sequence)
    if items_match is None:
        return {ITEMS_KEY: []}

    raw_items = [chunk.strip() for chunk in items_match.group("body").split(SEPARATOR_TOKEN)]
    parsed_items: list[dict[str, str]] = []
    for raw_item in raw_items:
        if not raw_item:
            continue
        product = _extract_tag_value(raw_item, PRODUCT_KEY)
        price = _extract_tag_value(raw_item, PRICE_KEY)
        if not product and not price:
            continue
        parsed_items.append(
            {
                PRODUCT_KEY: product,
                PRICE_KEY: price,
            }
        )
    return normalize_receipt_payload({ITEMS_KEY: parsed_items})


def receipt_token_pairs_to_payload(token_sequence: str) -> dict[str, list[dict[str, str]]]:
    parsed_items: list[dict[str, str]] = []
    for match in _PAIR_SECTION_RE.finditer(token_sequence):
        product = _collapse_whitespace(match.group("product"))
        price = _collapse_whitespace(match.group("price"))
        if not product:
            continue
        parsed_items.append(
            {
                PRODUCT_KEY: product,
                PRICE_KEY: price,
            }
        )
    return normalize_receipt_payload({ITEMS_KEY: parsed_items})


def _extract_tag_value(token_sequence: str, key: str) -> str:
    pattern = re.compile(rf"<s_{re.escape(key)}>(?P<value>.*?)</s_{re.escape(key)}>", re.DOTALL)
    match = pattern.search(token_sequence)
    if match is None:
        return ""
    return _collapse_whitespace(match.group("value"))


def parse_receipt_prediction(sequence: str, processor: Any | None = None) -> dict[str, list[dict[str, str]]]:
    cleaned = sequence.strip()
    if not cleaned:
        return {ITEMS_KEY: []}

    if cleaned.startswith("{") or cleaned.startswith("["):
        return normalize_receipt_payload(cleaned)

    pair_payload = receipt_token_pairs_to_payload(cleaned)
    if pair_payload[ITEMS_KEY]:
        return pair_payload

    if processor is not None and hasattr(processor, "token2json"):
        try:
            return normalize_receipt_payload(processor.token2json(cleaned))
        except Exception:
            pass

    return receipt_tokens_to_payload(cleaned)
