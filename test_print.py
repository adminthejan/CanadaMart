#!/usr/bin/env python3
"""Test script to verify receipt printing functionality."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

# CRITICAL: Initialize Qt application FIRST
from PyQt6.QtWidgets import QApplication
app = QApplication(sys.argv)

from config.app_config import AppConfig
from database.db_manager import DatabaseManager
from services.receipt_printer import ReceiptPrinter

# Initialize
config = AppConfig()
db = DatabaseManager()
db.initialize()

# CRITICAL FIX: Set printer type to windows_native
config.set("printer_type", "windows_native")
print("[INIT] Setting printer_type to 'windows_native'...\n")

# Test printer configuration
print("=" * 60)
print("RECEIPT PRINTING TEST")
print("=" * 60)

print("\n[1] Config Check:")
print(f"  printer_type: {config.get('printer_type')}")
print(f"  receipt_copies: {config.get('receipt_copies')}")
print(f"  business_name: {config.get('business_name')}")

print("\n[2] Database Check:")
auto_print = db.get_setting("auto_print_receipt", "1")
print(f"  auto_print_receipt: {auto_print} (1=enabled, 0=disabled)")

print("\n[3] PyQt6 Imports Check:")
try:
    from PyQt6.QtPrintSupport import QPrinter, QPrinterInfo
    from PyQt6.QtGui import QTextDocument
    print("  ✓ PyQt6.QtPrintSupport available")
    print("  ✓ QTextDocument available")
    
    # Check for default printer - use correct API
    try:
        default_printer = QPrinterInfo.defaultPrinter()
        if default_printer and default_printer.printerName():
            print(f"  ✓ Default printer found: {default_printer.printerName()}")
        else:
            print("  ✗ No default printer configured!")
            print("     → Set a default printer in Windows Settings")
            print("     → Go to Settings → Devices → Printers & scanners")
    except Exception as e:
        print(f"  ⚠ Could not check default printer: {e}")
except ImportError as e:
    print(f"  ✗ PyQt6 import failed: {e}")
    sys.exit(1)

print("\n[4] Test Receipt Data:")
test_sale = {
    "invoice_number": "INV-9999",
    "subtotal": 50.00,
    "tax_amount": 6.50,
    "discount_amount": 5.00,
    "total": 51.50,
    "payment_method": "cash",
    "amount_paid": 60.00,
    "change_amount": 8.50,
    "notes": "",
}

test_items = [
    {
        "product_name": "Test Product 1",
        "quantity": 2,
        "unit_price": 10.00,
        "discount_percent": 10,
        "total": 18.00,
    },
    {
        "product_name": "Test Product 2",
        "quantity": 1,
        "unit_price": 32.00,
        "discount_percent": 0,
        "total": 32.00,
    },
]

test_customer = {
    "name": "Test Customer",
    "mobile": "+1-555-0123",
}

print("  ✓ Test data prepared")

print("\n[5] Attempting to print receipt...")
printer = ReceiptPrinter(config)

try:
    result = printer.print_receipt(test_sale, test_items, test_customer)
    if result:
        print("  ✓ Receipt sent to printer successfully!")
    else:
        print("  ✗ Receipt printing failed (returned False)")
except Exception as e:
    print(f"  ✗ Exception during printing: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("TEST COMPLETE")
print("=" * 60)
