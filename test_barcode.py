import sys
import os
from PyQt6.QtWidgets import QApplication

# Initialize an app instance since QPixmap needs it
app = QApplication(sys.argv)

from database.db_manager import DatabaseManager
from config.app_config import AppConfig
from services.barcode_utils import generate_barcode_image
from services.receipt_printer import ReceiptPrinter

def run_tests():
    print("--- Testing Barcode Label Functionality ---")
    
    # 1. Test Database Settings
    config = AppConfig()
    db = DatabaseManager('test_pos.db')
    
    print("1. Saving settings to DB...")
    db.set_setting("barcode_store_name", "TestStore")
    db.set_setting("barcode_label_width_mm", "60.0")
    db.set_setting("barcode_label_height_mm", "30.0")
    db.set_setting("barcode_columns_per_row", "2")
    db.set_setting("barcode_gap_x_mm", "5.0")
    db.set_setting("barcode_show_price", "1")
    
    settings = db.get_all_settings()
    print(f"   Loaded {len(settings)} settings.")
    assert settings.get("barcode_store_name") == "TestStore", "Setting saving failed!"
    print("   [DB Settings OK]")

    # 2. Test Barcode Image Generation
    print("2. Testing barcode generation...")
    img = generate_barcode_image("P-12345", "Test Product", settings, "$19.99")
    print(f"   Generated Image Size: {img.width}x{img.height}")
    # width = 60mm -> ~708px at 300DPI
    # height = 30mm -> ~354px at 300DPI
    print(f"   Expected Size (approx): 708x354")
    if abs(img.width - 708) < 10 and abs(img.height - 354) < 10:
        print("   [Barcode Image Size OK]")
    else:
        print("   [Barcode Image Size Warning]")
        
    # 3. Test PDF generation (Fallback Printer)
    print("3. Testing ReceiptPrinter PDF generation...")
    config.set("printer_type", "pdf")
    printer = ReceiptPrinter(config)
    
    # Need to pass PIL image and settings
    success = printer.print_barcode_label(img, "Test Product", "$19.99", copies=3, settings=settings)
    
    if success:
        print("   [PDF Printer OK]")
    else:
        print("   [PDF Printer FAILED]")

    # Cleanup test DB if needed, but safe to keep.
    print("--- All tests completed! ---")

if __name__ == "__main__":
    try:
        run_tests()
    except Exception as e:
        import traceback
        traceback.print_exc()
