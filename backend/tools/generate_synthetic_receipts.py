from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta
import json
import logging
from pathlib import Path
import random
import re
import sys
from typing import Iterable, Sequence
import uuid

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageFont

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.receipt_json_schema import normalize_receipt_payload

LOGGER = logging.getLogger("generate_synthetic_receipts")

WINDOWS_FONT_CANDIDATES = [
    Path("C:/Windows/Fonts/consola.ttf"),
    Path("C:/Windows/Fonts/consolab.ttf"),
    Path("C:/Windows/Fonts/lucon.ttf"),
    Path("C:/Windows/Fonts/arial.ttf"),
    Path("C:/Windows/Fonts/cour.ttf"),
]
UNIX_FONT_CANDIDATES = [
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"),
    Path("/usr/share/fonts/truetype/liberation2/LiberationMono-Regular.ttf"),
    Path("/Library/Fonts/Courier New.ttf"),
]
STORE_NAMES = [
    "Mercado Luna",
    "Super Centro 24H",
    "Panaderia Sol",
    "Eco Market Norte",
    "La Huerta Express",
    "Bazar Plaza",
    "MiniMarket Alba",
    "Farmacia Central",
    "Cafe Barrio",
    "Fresh&Go",
]
STORE_TAGLINES = [
    "Gracias por su compra",
    "Calidad y precio cada dia",
    "Abierto todos los dias",
    "Compra rapida cerca de ti",
]
STREET_NAMES = [
    "Av. Castilla 12",
    "Calle Burgos 18",
    "Gran Via 4",
    "Calle Mayor 55",
    "Paseo del Norte 7",
    "Calle Real 31",
]
CITY_NAMES = [
    "Burgos",
    "Madrid",
    "Bilbao",
    "Valladolid",
    "Sevilla",
    "Valencia",
]
PAYMENT_METHODS = [
    "VISA",
    "MASTERCARD",
    "DEBITO",
    "CASH",
    "APPLE PAY",
    "GOOGLE PAY",
]
PRODUCT_CATALOG = [
    "Leche Entera",
    "Leche Semidesnatada",
    "Pan de Molde",
    "Barra Integral",
    "Huevos Camperos",
    "Yogur Natural",
    "Queso Curado",
    "Mantequilla",
    "Arroz Largo",
    "Pasta Fusilli",
    "Tomate Frito",
    "Cafe Molido",
    "Agua Mineral 1.5L",
    "Refresco Cola",
    "Zumo Naranja",
    "Cereal Avena",
    "Galletas Maria",
    "Aceite de Oliva",
    "Atun en Lata",
    "Jamon Cocido",
    "Pechuga de Pavo",
    "Detergente Ropa",
    "Papel Higienico",
    "Gel de Ducha",
    "Manzanas Golden",
    "Platanos",
    "Naranjas",
    "Tomates Rama",
    "Patatas 2Kg",
    "Cebollas Dulces",
    "Croissant Mantequilla",
    "Cafe Latte",
    "Tostada Tomate",
    "Sandwich Mixto",
    "Ensalada Cesar",
    "Pizza Margarita",
    "Agua con Gas",
    "Ibuprofeno 400",
    "Vitamina C",
    "Champu Suave",
]
CURRENCY_STYLES = ["eur_suffix", "eur_symbol", "plain_comma", "plain_dot"]


@dataclass(frozen=True)
class SyntheticItem:
    product: str
    quantity: int
    unit_price: float
    total_price: float


@dataclass(frozen=True)
class SyntheticReceipt:
    store_name: str
    tagline: str
    address: str
    city: str
    phone: str
    vat_id: str
    ticket_code: str
    payment_method: str
    timestamp: datetime
    tax_rate: float
    items: tuple[SyntheticItem, ...]
    subtotal: float
    tax_amount: float
    total: float
    price_style: str


@dataclass(frozen=True)
class FontSet:
    title: ImageFont.ImageFont
    header: ImageFont.ImageFont
    body: ImageFont.ImageFont
    small: ImageFont.ImageFont


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate synthetic receipt images in Donut metadata.jsonl format.")
    parser.add_argument("--output", type=Path, default=Path("dataset_synthetic"), help="Output dataset root.")
    parser.add_argument("--train-count", type=int, default=2000, help="Number of synthetic train samples.")
    parser.add_argument("--validation-count", type=int, default=200, help="Number of synthetic validation samples.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed.")
    parser.add_argument("--append", action="store_true", help="Append to an existing dataset instead of requiring an empty destination.")
    parser.add_argument(
        "--image-format",
        type=str,
        default="mix",
        choices=["mix", "png", "jpg"],
        help="Image output format.",
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


def choose_font_path() -> Path | None:
    for candidate in [*WINDOWS_FONT_CANDIDATES, *UNIX_FONT_CANDIDATES]:
        if candidate.exists():
            return candidate
    return None


def load_font_set() -> FontSet:
    font_path = choose_font_path()
    if font_path is None:
        default_font = ImageFont.load_default()
        return FontSet(title=default_font, header=default_font, body=default_font, small=default_font)

    return FontSet(
        title=ImageFont.truetype(str(font_path), size=32),
        header=ImageFont.truetype(str(font_path), size=22),
        body=ImageFont.truetype(str(font_path), size=24),
        small=ImageFont.truetype(str(font_path), size=18),
    )


def ensure_split_ready(output_dir: Path, split_name: str, *, append: bool) -> tuple[Path, Path, list[str], int]:
    split_dir = output_dir / split_name
    images_dir = split_dir / "images"
    metadata_path = split_dir / "metadata.jsonl"

    if append:
        split_dir.mkdir(parents=True, exist_ok=True)
        images_dir.mkdir(parents=True, exist_ok=True)
        existing_rows = metadata_path.read_text(encoding="utf-8").splitlines() if metadata_path.exists() else []
        return split_dir, images_dir, [row for row in existing_rows if row.strip()], len(existing_rows)

    if split_dir.exists() and any(split_dir.iterdir()):
        raise RuntimeError(
            f"Output split already exists and is not empty: {split_dir}. "
            "Use --append to add synthetic tickets to an existing dataset."
        )

    split_dir.mkdir(parents=True, exist_ok=True)
    images_dir.mkdir(parents=True, exist_ok=True)
    return split_dir, images_dir, [], 0


def random_phone(rng: random.Random) -> str:
    return f"+34 {rng.randint(600, 799)} {rng.randint(100, 999)} {rng.randint(100, 999)}"


def random_vat_id(rng: random.Random) -> str:
    return f"B-{rng.randint(10000000, 99999999)}"


def random_ticket_code(rng: random.Random) -> str:
    return f"TK-{rng.randint(10000, 99999)}-{uuid.UUID(int=rng.getrandbits(128)).hex[:6].upper()}"


def random_timestamp(rng: random.Random) -> datetime:
    base = datetime(2024, 1, 1, 8, 0, 0)
    return base + timedelta(days=rng.randint(0, 730), minutes=rng.randint(0, 14 * 60))


def build_synthetic_receipt(rng: random.Random) -> SyntheticReceipt:
    item_count = rng.randint(2, 12)
    items: list[SyntheticItem] = []
    for _ in range(item_count):
        product = rng.choice(PRODUCT_CATALOG)
        if rng.random() < 0.2:
            product = f"{product} {rng.choice(['Oferta', 'Promo', 'XL', 'Eco', 'Bio'])}"
        quantity = rng.choices([1, 2, 3, 4], weights=[0.65, 0.2, 0.1, 0.05])[0]
        unit_price = round(rng.uniform(0.65, 24.90), 2)
        total_price = round(unit_price * quantity, 2)
        items.append(
            SyntheticItem(
                product=product,
                quantity=quantity,
                unit_price=unit_price,
                total_price=total_price,
            )
        )

    subtotal = round(sum(item.total_price for item in items), 2)
    tax_rate = rng.choice([0.04, 0.10, 0.21])
    tax_amount = round(subtotal * tax_rate, 2)
    include_tax_line = rng.random() < 0.8
    total = round(subtotal + tax_amount, 2) if include_tax_line else subtotal

    return SyntheticReceipt(
        store_name=rng.choice(STORE_NAMES),
        tagline=rng.choice(STORE_TAGLINES),
        address=rng.choice(STREET_NAMES),
        city=rng.choice(CITY_NAMES),
        phone=random_phone(rng),
        vat_id=random_vat_id(rng),
        ticket_code=random_ticket_code(rng),
        payment_method=rng.choice(PAYMENT_METHODS),
        timestamp=random_timestamp(rng),
        tax_rate=tax_rate,
        items=tuple(items),
        subtotal=subtotal,
        tax_amount=tax_amount,
        total=total,
        price_style=rng.choice(CURRENCY_STYLES),
    )


def format_price(value: float, style: str) -> str:
    if style == "eur_symbol":
        return f"EUR {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    if style == "eur_suffix":
        return f"{value:,.2f} EUR".replace(",", "X").replace(".", ",").replace("X", ".")
    if style == "plain_dot":
        return f"{value:,.2f}"
    return f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    words = text.split()
    if not words:
        return [""]

    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if draw.textlength(candidate, font=font) <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def draw_right_aligned(
    draw: ImageDraw.ImageDraw,
    *,
    x_right: int,
    y: int,
    text: str,
    font: ImageFont.ImageFont,
    fill: int,
) -> None:
    width = int(draw.textlength(text, font=font))
    draw.text((x_right - width, y), text, font=font, fill=fill)


def render_receipt_image(receipt: SyntheticReceipt, rng: random.Random, fonts: FontSet) -> Image.Image:
    paper_width = rng.randint(640, 760)
    margin = rng.randint(26, 42)
    bg_level = rng.randint(246, 255)
    image = Image.new("L", (paper_width, 1800), color=bg_level)
    draw = ImageDraw.Draw(image)

    y = margin
    fill = rng.randint(5, 32)
    line_gap = rng.randint(8, 12)
    right_col = paper_width - margin
    desc_width = int(paper_width * 0.64)

    draw.text((margin, y), receipt.store_name.upper(), font=fonts.title, fill=fill)
    y += 46
    draw.text((margin, y), receipt.tagline, font=fonts.small, fill=fill)
    y += 28
    draw.text((margin, y), receipt.address, font=fonts.small, fill=fill)
    y += 24
    draw.text((margin, y), f"{receipt.city}  Tel: {receipt.phone}", font=fonts.small, fill=fill)
    y += 24
    draw.text((margin, y), f"NIF: {receipt.vat_id}", font=fonts.small, fill=fill)
    y += 22
    draw.text((margin, y), f"Ticket: {receipt.ticket_code}", font=fonts.small, fill=fill)
    y += 28

    timestamp_text = receipt.timestamp.strftime("%d/%m/%Y %H:%M")
    draw.text((margin, y), timestamp_text, font=fonts.body, fill=fill)
    y += 34
    draw.line((margin, y, right_col, y), fill=fill, width=1)
    y += 14
    draw.text((margin, y), "ITEM", font=fonts.header, fill=fill)
    draw_right_aligned(draw, x_right=right_col - 120, y=y, text="QTY", font=fonts.header, fill=fill)
    draw_right_aligned(draw, x_right=right_col, y=y, text="TOTAL", font=fonts.header, fill=fill)
    y += 32
    draw.line((margin, y, right_col, y), fill=fill, width=1)
    y += 12

    for item in receipt.items:
        wrapped_product = wrap_text(draw, item.product, fonts.body, max_width=desc_width)
        draw.text((margin, y), wrapped_product[0], font=fonts.body, fill=fill)
        draw_right_aligned(draw, x_right=right_col - 120, y=y, text=str(item.quantity), font=fonts.body, fill=fill)
        draw_right_aligned(
            draw,
            x_right=right_col,
            y=y,
            text=format_price(item.total_price, receipt.price_style),
            font=fonts.body,
            fill=fill,
        )
        y += 30
        for continuation in wrapped_product[1:]:
            draw.text((margin + 20, y), continuation, font=fonts.body, fill=fill)
            y += 28
        if rng.random() < 0.18:
            draw.text(
                (margin + 12, y),
                f"{item.quantity} x {format_price(item.unit_price, receipt.price_style)}",
                font=fonts.small,
                fill=fill,
            )
            y += 22
        y += line_gap

    draw.line((margin, y, right_col, y), fill=fill, width=1)
    y += 14
    draw.text((margin, y), "SUBTOTAL", font=fonts.header, fill=fill)
    draw_right_aligned(
        draw,
        x_right=right_col,
        y=y,
        text=format_price(receipt.subtotal, receipt.price_style),
        font=fonts.header,
        fill=fill,
    )
    y += 30
    if receipt.total != receipt.subtotal:
        draw.text((margin, y), f"IVA {int(receipt.tax_rate * 100)}%", font=fonts.header, fill=fill)
        draw_right_aligned(
            draw,
            x_right=right_col,
            y=y,
            text=format_price(receipt.tax_amount, receipt.price_style),
            font=fonts.header,
            fill=fill,
        )
        y += 30
    draw.text((margin, y), "TOTAL", font=fonts.header, fill=fill)
    draw_right_aligned(
        draw,
        x_right=right_col,
        y=y,
        text=format_price(receipt.total, receipt.price_style),
        font=fonts.header,
        fill=fill,
    )
    y += 34
    draw.line((margin, y, right_col, y), fill=fill, width=1)
    y += 16
    draw.text((margin, y), f"PAGO: {receipt.payment_method}", font=fonts.body, fill=fill)
    y += 28
    draw.text((margin, y), rng.choice(["Operacion aprobada", "Vuelva pronto", "Ticket no reembolsable"]), font=fonts.small, fill=fill)
    y += 24
    draw.text((margin, y), "Gracias por su visita", font=fonts.small, fill=fill)
    y += 26

    cropped = image.crop((0, 0, paper_width, min(y + margin, image.height)))
    return augment_receipt_image(cropped, rng)


def augment_receipt_image(image: Image.Image, rng: random.Random) -> Image.Image:
    working = image.convert("L")

    if rng.random() < 0.65:
        noise = Image.effect_noise(working.size, rng.uniform(3.0, 9.0))
        noise = ImageEnhance.Contrast(noise).enhance(rng.uniform(0.3, 0.8))
        working = ImageChops.add_modulo(working, noise)

    if rng.random() < 0.55:
        working = working.filter(ImageFilter.GaussianBlur(radius=rng.uniform(0.1, 0.8)))

    if rng.random() < 0.45:
        working = ImageEnhance.Contrast(working).enhance(rng.uniform(0.9, 1.25))

    if rng.random() < 0.5:
        working = ImageEnhance.Brightness(working).enhance(rng.uniform(0.92, 1.05))

    tilt = rng.uniform(-2.7, 2.7)
    background = rng.randint(238, 252)
    working = working.rotate(tilt, resample=Image.Resampling.BICUBIC, expand=True, fillcolor=background)

    pad = rng.randint(24, 52)
    canvas = Image.new("L", (working.width + pad * 2, working.height + pad * 2), color=background)
    offset = (pad + rng.randint(-8, 8), pad + rng.randint(-8, 8))
    canvas.paste(working, offset)
    return canvas.convert("RGB")


def build_payload(receipt: SyntheticReceipt) -> dict[str, list[dict[str, str]]]:
    return normalize_receipt_payload(
        {
            "items": [
                {
                    "product": item.product,
                    "price": format_price(item.total_price, receipt.price_style),
                }
                for item in receipt.items
            ]
        }
    )


def choose_extension(rng: random.Random, image_format: str) -> str:
    if image_format == "png":
        return ".png"
    if image_format == "jpg":
        return ".jpg"
    return ".jpg" if rng.random() < 0.55 else ".png"


def save_image(image: Image.Image, target_path: Path) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    if target_path.suffix.lower() == ".jpg":
        image.save(target_path, format="JPEG", quality=88)
        return
    image.save(target_path, format="PNG")


def synthesize_split(
    output_dir: Path,
    split_name: str,
    *,
    count: int,
    rng: random.Random,
    fonts: FontSet,
    append: bool,
    image_format: str,
) -> int:
    _, images_dir, metadata_rows, start_index = ensure_split_ready(output_dir, split_name, append=append)
    for index in range(count):
        global_index = start_index + index
        receipt = build_synthetic_receipt(rng)
        payload = build_payload(receipt)
        extension = choose_extension(rng, image_format)
        file_name = f"{split_name}_synth_{global_index:06d}{extension}"
        image_path = images_dir / file_name
        image = render_receipt_image(receipt, rng, fonts)
        save_image(image, image_path)

        metadata_rows.append(
            json.dumps(
                {
                    "file_name": file_name,
                    "ground_truth": json.dumps(payload, ensure_ascii=False),
                },
                ensure_ascii=False,
            )
        )
        if (index + 1) % 100 == 0 or index + 1 == count:
            LOGGER.info("Generated %s/%s synthetic receipts for split %s", index + 1, count, split_name)

    metadata_path = output_dir / split_name / "metadata.jsonl"
    metadata_path.write_text("\n".join(metadata_rows) + "\n", encoding="utf-8")
    return count


def main() -> None:
    args = parse_args()
    setup_logging(args.log_level)

    output_dir = args.output.resolve()
    rng = random.Random(int(args.seed))
    fonts = load_font_set()

    train_count = synthesize_split(
        output_dir,
        "train",
        count=int(args.train_count),
        rng=rng,
        fonts=fonts,
        append=bool(args.append),
        image_format=str(args.image_format),
    )
    validation_count = synthesize_split(
        output_dir,
        "validation",
        count=int(args.validation_count),
        rng=rng,
        fonts=fonts,
        append=bool(args.append),
        image_format=str(args.image_format),
    )

    LOGGER.info(
        "Synthetic dataset ready at %s (train=%s validation=%s append=%s)",
        output_dir,
        train_count,
        validation_count,
        bool(args.append),
    )


if __name__ == "__main__":
    main()
