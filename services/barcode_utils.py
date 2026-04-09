import io
import os
from PIL import Image, ImageDraw, ImageFont
import barcode
from barcode.writer import ImageWriter
from hashids import Hashids
from config.app_config import AppConfig

# Initialize config
config = AppConfig()

def get_hashids() -> Hashids:
    salt = config.get("barcode_salt", "CanadaMart-POS-2024")
    min_length = config.get("barcode_min_length", 6)
    return Hashids(salt=salt, min_length=min_length)

def encode_product_id(product_id: int, has_variants: bool = False) -> str:
    if has_variants:
        raise ValueError("Cannot encode base product ID for a product that has variants")
    hashids = get_hashids()
    hash_str = hashids.encode(product_id)
    return f"P-{hash_str}"

def encode_variant_id(variant_id: int) -> str:
    hashids = get_hashids()
    hash_str = hashids.encode(variant_id)
    return f"V-{hash_str}"

def decode_barcode(barcode_str: str):
    """
    Returns (table_name, id) if it's a valid internal barcode,
    otherwise returns (None, None).
    """
    if not barcode_str:
        return None, None
    
    parts = barcode_str.split("-", 1)
    if len(parts) != 2:
        return None, None
        
    prefix, hash_str = parts
    hashids = get_hashids()
    decoded = hashids.decode(hash_str)
    
    if not decoded:
        return None, None
        
    db_id = decoded[0]
    
    if prefix == "P":
        return "products", db_id
    elif prefix == "V":
        return "product_variants", db_id
        
    return None, None

def generate_barcode_image(data_str: str, product_name: str, settings: dict = None, price_str: str = "") -> Image.Image:
    """
    Generates a Code 128 barcode image sized to fit entirely within
    a single sticker label (default 30 mm × 20 mm at 300 DPI).
    """
    settings = settings or {}
    width_mm = float(settings.get("barcode_label_width_mm", 30.0))
    height_mm = float(settings.get("barcode_label_height_mm", 20.0))
    show_price = str(settings.get("barcode_show_price", "1")) == "1"

    # Target pixel dimensions at 203 DPI (standard thermal label printer)
    dpi = 203
    target_w = int(width_mm / 25.4 * dpi)   # 30 mm → 240 px
    target_h = int(height_mm / 25.4 * dpi)   # 20 mm → 160 px

    # ── Generate compact Code 128 barcode ────────────────────────────
    # No text below the barcode bars — we only want the barcode image + price
    code128 = barcode.get_barcode_class('code128')
    writer = ImageWriter()
    writer_options = {
        'module_width': 0.2,
        'module_height': max(5.0, height_mm * 0.30),
        'quiet_zone': 1.0,
        'font_size': 0,
        'text_distance': 0,
        'write_text': False,
        'background': 'white',
        'foreground': 'black',
    }

    bc = code128(data_str, writer=writer)
    buffer = io.BytesIO()
    bc.write(buffer, options=writer_options)
    buffer.seek(0)
    bc_img = Image.open(buffer).convert("RGB")

    # ── Create label canvas ──────────────────────────────────────────
    final_img = Image.new("RGB", (target_w, target_h), "white")
    draw = ImageDraw.Draw(final_img)

    # Font for price only
    price_px = max(14, int(target_h * 0.10))
    try:
        font_price = ImageFont.truetype("arialbd.ttf", price_px)
    except (IOError, OSError):
        try:
            wf = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
            font_price = ImageFont.truetype(os.path.join(wf, "arialbd.ttf"), price_px)
        except (IOError, OSError):
            font_price = ImageFont.load_default()

    pad = max(2, int(target_h * 0.015))

    # ── Layout: barcode on top, price at bottom ──────────────────────
    # Measure price height first to reserve space at bottom
    price_h = 0
    if show_price and price_str:
        bbox = draw.textbbox((0, 0), price_str, font=font_price)
        price_h = bbox[3] - bbox[1]

    # Barcode fills from top down, leaving room for price + tiny gap
    y = pad
    gap = 1  # minimal gap between barcode and price
    barcode_avail_h = target_h - y - pad - (price_h + gap if price_h else 0)

    bc_bottom = y  # track where barcode ends
    if barcode_avail_h > 0 and bc_img.width > 0 and bc_img.height > 0:
        max_w = int(target_w * 0.95)
        scale = min(max_w / bc_img.width, barcode_avail_h / bc_img.height)
        new_w = max(1, int(bc_img.width * scale))
        new_h = max(1, int(bc_img.height * scale))
        bc_img = bc_img.resize((new_w, new_h), Image.Resampling.LANCZOS)

        bc_x = (target_w - new_w) // 2
        bc_y = y
        final_img.paste(bc_img, (bc_x, bc_y))
        bc_bottom = bc_y + new_h

    # ── Price centred directly below barcode ─────────────────────────
    if show_price and price_str and price_h:
        bbox = draw.textbbox((0, 0), price_str, font=font_price)
        px = (target_w - (bbox[2] - bbox[0])) // 2
        py = bc_bottom + gap
        draw.text((px, py), price_str, font=font_price, fill="black")

    # Stamp DPI so the image is physically 30×20 mm (or whatever the label is)
    final_img.info['dpi'] = (dpi, dpi)
    return final_img

