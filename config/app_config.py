"""Application configuration manager."""
import json
import os
from pathlib import Path


class AppConfig:
    """Manages all application configuration with persistence."""

    DEFAULT_CONFIG = {
        # Business Info
        "app_name": "CanadaMart POS",
        "app_version": "1.0.0",
        "app_description": "Point of Sale System",
        "logo_path": "",
        "theme": "dark",
        "business_name": "CanadaMart",
        "business_tagline": "Your Neighbourhood Store",
        "business_address": "123 Main Street, Toronto, ON",
        "business_phone": "+1 (416) 000-0000",
        "business_email": "info@canadamart.ca",
        "business_website": "www.canadamart.ca",
        "business_reg_no": "",
        "business_tax_no": "",
        # Currency & Tax
        "currency_symbol": "$",
        "currency_code": "CAD",
        "currency_position": "before",  # before / after
        "tax_enabled": True,
        "tax_name": "HST",
        "tax_rate": 13.0,
        "tax_inclusive": False,
        # Receipt
        "receipt_header": "Thank you for visiting CanadaMart!",
        "receipt_footer": "Goods once sold are not returnable.\nHave a great day!",
        "receipt_show_logo": True,
        "receipt_show_barcode": True,
        "receipt_copies": 1,
        "receipt_paper_width": 80,  # mm
        # Printer
        "printer_type": "none",  # none | escpos_usb | escpos_serial | escpos_network | pdf
        "printer_port": "",
        "printer_baudrate": 9600,
        "printer_network_ip": "",
        "printer_network_port": 9100,
        "printer_usb_vendor": "0x04b8",
        "printer_usb_product": "0x0202",
        # VFD Display
        "vfd_enabled": False,
        "vfd_port": "COM3",
        "vfd_baudrate": 9600,
        "vfd_type": "epson",  # epson | bixolon | generic
        "vfd_cols": 20,
        "vfd_rows": 2,
        "vfd_welcome_line1": "Welcome!",
        "vfd_welcome_line2": "Please wait...",
        # Shopify
        "shopify_enabled": False,
        "shopify_shop_url": "",
        "shopify_access_token": "",
        "shopify_api_version": "2024-01",
        "shopify_location_id": "",
        "shopify_sync_interval": 300,
        "shopify_sync_products": True,
        "shopify_sync_inventory": True,
        # Invoicing
        "invoice_prefix": "INV",
        "invoice_next_number": 1000,
        "invoice_show_sku": True,
        "invoice_show_barcode": False,
        # POS Settings
        "low_stock_threshold": 5,
        "allow_negative_stock": False,
        "require_customer": False,
        "default_payment_method": "cash",
        "points_per_dollar": 1,
        "enable_loyalty": True,
        "discount_requires_pin": False,
        "discount_pin": "1234",
        "max_discount_percent": 100.0,
        # Barcode Obfuscation
        "barcode_salt": "CanadaMart-POS-2024",
        "barcode_min_length": 6,
    }

    def __init__(self):
        self.config_dir = Path.home() / ".canadamart"
        self.config_file = self.config_dir / "config.json"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self._config = self.DEFAULT_CONFIG.copy()
        self.load()

    def load(self):
        if self.config_file.exists():
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    self._config.update(saved)
            except Exception:
                pass

    def save(self):
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self._config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Config save error: {e}")

    def get(self, key, default=None):
        return self._config.get(key, default if default is not None else self.DEFAULT_CONFIG.get(key))

    def set(self, key, value):
        self._config[key] = value
        self.save()

    def update(self, data: dict):
        self._config.update(data)
        self.save()

    def get_all(self) -> dict:
        return self._config.copy()

    def format_currency(self, amount: float) -> str:
        symbol = self._config.get("currency_symbol", "$")
        position = self._config.get("currency_position", "before")
        formatted = f"{amount:,.2f}"
        if position == "before":
            return f"{symbol}{formatted}"
        return f"{formatted}{symbol}"
