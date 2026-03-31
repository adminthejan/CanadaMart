import io
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
    Generates a Code 128 barcode image matching physical dimensions specified in settings.
    """
    settings = settings or {}
    store_name = settings.get("barcode_store_name", "CanadaMart")
    width_mm = float(settings.get("barcode_label_width_mm", 50.0))
    height_mm = float(settings.get("barcode_label_height_mm", 25.0))
    show_price = str(settings.get("barcode_show_price", "1")) == "1"
    
    # Calculate target pixels assuming 300 DPI
    dpi = 300
    target_w = int(width_mm / 25.4 * dpi)
    target_h = int(height_mm / 25.4 * dpi)

    code128 = barcode.get_barcode_class('code128')
    writer = ImageWriter()
    writer_options = {
        'module_width': 0.3,
        'module_height': max(10.0, height_mm - 15.0),
        'quiet_zone': 6.5,
        'font_size': 10,
        'text_distance': 5.0,
        'background': 'white',
        'foreground': 'black',
        'center_text': True
    }
    
    bc = code128(data_str, writer=writer)
    
    buffer = io.BytesIO()
    bc.write(buffer, options=writer_options)
    buffer.seek(0)
    
    bc_img = Image.open(buffer).convert("RGB")
    
    final_img = Image.new("RGB", (target_w, target_h), "white")
    draw = ImageDraw.Draw(final_img)
    
    try:
        font_large = ImageFont.truetype("arial.ttf", max(16, int(target_h * 0.12)))
        font_small = ImageFont.truetype("arial.ttf", max(12, int(target_h * 0.08)))
    except IOError:
        font_large = ImageFont.load_default()
        font_small = ImageFont.load_default()
        
    y_cursor = int(target_h * 0.05)
    
    # Store Name - Disabled
    # if store_name:
    #     bbox = draw.textbbox((0, 0), store_name, font=font_large)
    #     x = (target_w - (bbox[2] - bbox[0])) / 2
    #     draw.text((x, y_cursor), store_name, font=font_large, fill="black")
    #     y_cursor += (bbox[3] - bbox[1]) + int(target_h * 0.02)
        
    # Product Name
    if product_name:
        bbox = draw.textbbox((0, 0), product_name, font=font_small)
        x = (target_w - (bbox[2] - bbox[0])) / 2
        draw.text((x, y_cursor), product_name, font=font_small, fill="black")
        y_cursor += (bbox[3] - bbox[1]) + int(target_h * 0.02)
        
    # Price
    if show_price and price_str:
        bbox = draw.textbbox((0, 0), price_str, font=font_large)
        x = (target_w - (bbox[2] - bbox[0])) / 2
        draw.text((x, y_cursor), price_str, font=font_large, fill="black")
        y_cursor += (bbox[3] - bbox[1]) + int(target_h * 0.02)
        
    # Paste Barcode
    avail_h = target_h - y_cursor - int(target_h * 0.02)
    if avail_h > 0:
        if bc_img.width > target_w * 0.95 or bc_img.height > avail_h:
            scale = min((target_w * 0.95) / bc_img.width, avail_h / bc_img.height)
            new_w = max(1, int(bc_img.width * scale))
            new_h = max(1, int(bc_img.height * scale))
            bc_img = bc_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            
        bc_x = (target_w - bc_img.width) // 2
        bc_y = y_cursor + max(0, (avail_h - bc_img.height) // 2)
        final_img.paste(bc_img, (bc_x, bc_y))
    
    return final_img

