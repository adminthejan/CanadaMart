"""Full application settings module."""
import os
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QFormLayout, QTabWidget, QComboBox, QSpinBox,
    QDoubleSpinBox, QCheckBox, QFileDialog, QMessageBox,
    QTextEdit, QGroupBox, QScrollArea, QFrame, QDialog,
    QDialogButtonBox, QTableWidget, QTableWidgetItem, QHeaderView,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap, QFont


class SettingsWidget(QWidget):
    """Complete settings panel with tabs for every configuration group."""

    settings_saved = pyqtSignal()

    def __init__(self, config, db, current_user: dict | None = None):
        super().__init__()
        self.config = config
        self.db = db
        self.current_user = current_user or {"role": "cashier"}
        self._build_ui()
        self._load_settings()

    # ------------------------------------------------------------------ #
    #  UI                                                                  #
    # ------------------------------------------------------------------ #
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header
        hdr = QHBoxLayout()
        title = QLabel("⚙️  Settings")
        title.setStyleSheet("font-size:20px; font-weight:700; color:#f1f5f9;")
        hdr.addWidget(title)
        hdr.addStretch()

        save_btn = QPushButton("💾 Save All Settings")
        save_btn.setObjectName("PrimaryBtn")
        save_btn.setMinimumHeight(40)
        save_btn.clicked.connect(self._save_all)
        hdr.addWidget(save_btn)
        layout.addLayout(hdr)

        tabs = QTabWidget()
        layout.addWidget(tabs, 1)

        tabs.addTab(self._build_business_tab(),  "🎪 Business")
        tabs.addTab(self._build_receipt_tab(),   "🧾 Receipt")
        tabs.addTab(self._build_pos_tab(),       "🛒 POS")
        tabs.addTab(self._build_tax_tab(),       "💰 Tax")
        tabs.addTab(self._build_shopify_tab(),   "🛔 Shopify")
        tabs.addTab(self._build_hardware_tab(),  "🖨 Hardware")
        tabs.addTab(self._build_barcode_label_tab(), "🏷 Barcode Labels")
        # Users tab – admin/manager only
        if self.current_user.get("role") in ("admin", "manager"):
            tabs.addTab(self._build_users_tab(), "👥 Users")
        tabs.addTab(self._build_about_tab(),     "ℹ️ About")

    # ── Business ─────────────────────────────────────────────────────────
    def _build_business_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(14)

        form = QFormLayout()
        form.setSpacing(10)

        self._app_name = QLineEdit()
        form.addRow("Application Name", self._app_name)

        self._app_desc = QLineEdit()
        form.addRow("App Description", self._app_desc)

        self._business_name = QLineEdit()
        form.addRow("Business Name", self._business_name)

        self._business_tagline = QLineEdit()
        form.addRow("Business Tagline", self._business_tagline)

        self._business_address = QLineEdit()
        form.addRow("Address", self._business_address)

        self._business_phone = QLineEdit()
        form.addRow("Phone", self._business_phone)

        self._business_email = QLineEdit()
        form.addRow("Email", self._business_email)

        self._business_website = QLineEdit()
        form.addRow("Website", self._business_website)

        self._business_reg = QLineEdit()
        form.addRow("Registration No.", self._business_reg)

        self._business_tax_no = QLineEdit()
        form.addRow("Tax Number", self._business_tax_no)

        layout.addLayout(form)

        # Logo
        logo_group = QGroupBox("Logo")
        logo_layout = QVBoxLayout(logo_group)
        self._logo_preview = QLabel()
        self._logo_preview.setFixedSize(200, 80)
        self._logo_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._logo_preview.setStyleSheet("border:1px dashed #475569; border-radius:6px;")
        logo_layout.addWidget(self._logo_preview)
        logo_row = QHBoxLayout()
        browse_logo = QPushButton("Browse Logo…")
        browse_logo.clicked.connect(self._browse_logo)
        clear_logo = QPushButton("Clear")
        clear_logo.clicked.connect(self._clear_logo)
        logo_row.addWidget(browse_logo)
        logo_row.addWidget(clear_logo)
        logo_layout.addLayout(logo_row)
        self._logo_path = QLineEdit()
        self._logo_path.setPlaceholderText("Path to logo image (PNG/JPG)")
        self._logo_path.setReadOnly(True)
        logo_layout.addWidget(self._logo_path)
        layout.addWidget(logo_group)

        # Theme
        theme_row = QFormLayout()
        self._theme = QComboBox()
        self._theme.addItems(["dark", "light"])
        theme_row.addRow("UI Theme", self._theme)
        layout.addLayout(theme_row)

        layout.addStretch()
        scroll.setWidget(w)
        return scroll

    # ── Receipt ──────────────────────────────────────────────────────────
    def _build_receipt_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        w = QWidget()
        layout = QVBoxLayout(w)
        form = QFormLayout()
        form.setSpacing(10)

        self._receipt_header = QTextEdit()
        self._receipt_header.setMaximumHeight(60)
        form.addRow("Receipt Header", self._receipt_header)

        self._receipt_footer = QTextEdit()
        self._receipt_footer.setMaximumHeight(80)
        form.addRow("Receipt Footer", self._receipt_footer)

        self._receipt_copies = QSpinBox()
        self._receipt_copies.setRange(1, 5)
        form.addRow("Copies to Print", self._receipt_copies)

        self._receipt_paper_width = QComboBox()
        self._receipt_paper_width.addItems(["58", "80"])
        self._receipt_paper_width.setCurrentText("80")
        form.addRow("Paper Width (mm)", self._receipt_paper_width)

        self._receipt_show_logo = QCheckBox("Show logo on receipt")
        form.addRow("", self._receipt_show_logo)

        self._receipt_show_barcode = QCheckBox("Show barcode on receipt")
        form.addRow("", self._receipt_show_barcode)

        layout.addLayout(form)

        # Invoice
        inv_group = QGroupBox("Invoice Numbering")
        inv_form = QFormLayout(inv_group)
        self._inv_prefix = QLineEdit()
        inv_form.addRow("Invoice Prefix (e.g. INV)", self._inv_prefix)
        self._inv_next = QSpinBox()
        self._inv_next.setRange(1, 9999999)
        inv_form.addRow("Next Invoice Number", self._inv_next)
        self._inv_show_sku = QCheckBox("Show SKU on invoice")
        inv_form.addRow("", self._inv_show_sku)
        layout.addWidget(inv_group)

        layout.addStretch()
        scroll.setWidget(w)
        return scroll

    # ── POS ──────────────────────────────────────────────────────────────
    def _build_pos_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        w = QWidget()
        form = QFormLayout(w)
        form.setSpacing(12)

        self._currency_symbol = QLineEdit()
        form.addRow("Currency Symbol", self._currency_symbol)

        self._currency_code = QLineEdit()
        form.addRow("Currency Code", self._currency_code)

        self._currency_position = QComboBox()
        self._currency_position.addItems(["before", "after"])
        form.addRow("Symbol Position", self._currency_position)

        self._default_payment = QComboBox()
        self._default_payment.addItems(["cash", "card"])
        form.addRow("Default Payment", self._default_payment)

        self._allow_neg_stock = QCheckBox("Allow negative stock (oversell)")
        form.addRow("", self._allow_neg_stock)

        self._require_customer = QCheckBox("Require customer selection before checkout")
        form.addRow("", self._require_customer)

        self._low_stock_threshold = QSpinBox()
        self._low_stock_threshold.setRange(0, 9999)
        form.addRow("Low Stock Alert Threshold", self._low_stock_threshold)

        self._max_discount = QDoubleSpinBox()
        self._max_discount.setRange(0, 100)
        self._max_discount.setSuffix(" %")
        form.addRow("Max Discount Allowed", self._max_discount)

        self._enable_loyalty = QCheckBox("Enable customer loyalty points")
        form.addRow("", self._enable_loyalty)

        self._points_per_dollar = QSpinBox()
        self._points_per_dollar.setRange(0, 100)
        form.addRow("Points per dollar spent", self._points_per_dollar)

        scroll.setWidget(w)
        return scroll

    # ── Tax ──────────────────────────────────────────────────────────────
    def _build_tax_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        w = QWidget()
        form = QFormLayout(w)
        form.setSpacing(12)

        self._tax_enabled = QCheckBox("Enable Tax")
        form.addRow("", self._tax_enabled)

        self._tax_name = QLineEdit()
        form.addRow("Tax Name (e.g. HST, GST, VAT)", self._tax_name)

        self._tax_rate = QDoubleSpinBox()
        self._tax_rate.setRange(0, 100)
        self._tax_rate.setDecimals(2)
        self._tax_rate.setSuffix(" %")
        form.addRow("Tax Rate", self._tax_rate)

        self._tax_inclusive = QCheckBox("Prices are tax-inclusive")
        form.addRow("", self._tax_inclusive)

        scroll.setWidget(w)
        return scroll

    # ── Shopify ───────────────────────────────────────────────────────────
    def _build_shopify_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        w = QWidget()
        layout = QVBoxLayout(w)

        self._shopify_enabled = QCheckBox("Enable Shopify Integration")
        self._shopify_enabled.setStyleSheet("font-weight:600;")
        layout.addWidget(self._shopify_enabled)

        form = QFormLayout()
        form.setSpacing(10)

        self._shopify_url = QLineEdit()
        self._shopify_url.setPlaceholderText("your-store.myshopify.com")
        form.addRow("Shop URL", self._shopify_url)

        # OAuth client credentials (preferred – auto-refreshes every 24 h)
        cred_note = QLabel(
            "<i>Enter Client ID + Secret from your Shopify Partners dashboard.<br>"
            "A token is fetched automatically and refreshed every 24 h.</i>"
        )
        cred_note.setWordWrap(True)
        form.addRow("", cred_note)

        self._shopify_client_id = QLineEdit()
        self._shopify_client_id.setPlaceholderText("Client ID from Partners dashboard")
        form.addRow("Client ID", self._shopify_client_id)

        self._shopify_client_secret = QLineEdit()
        self._shopify_client_secret.setEchoMode(QLineEdit.EchoMode.Password)
        self._shopify_client_secret.setPlaceholderText("Client Secret from Partners dashboard")
        form.addRow("Client Secret", self._shopify_client_secret)

        show_secret = QCheckBox("Show secret")
        show_secret.toggled.connect(
            lambda v: self._shopify_client_secret.setEchoMode(
                QLineEdit.EchoMode.Normal if v else QLineEdit.EchoMode.Password
            )
        )
        form.addRow("", show_secret)

        # Optional static token override (for permanent / custom-app tokens)
        static_note = QLabel(
            "<i>OR enter a static <b>shpat_</b> token below (leave blank when using Client ID/Secret).</i>"
        )
        static_note.setWordWrap(True)
        form.addRow("", static_note)

        self._shopify_token = QLineEdit()
        self._shopify_token.setEchoMode(QLineEdit.EchoMode.Password)
        self._shopify_token.setPlaceholderText("shpat_xxxxxxxxxx  (optional override)")
        form.addRow("Static Token", self._shopify_token)

        show_token = QCheckBox("Show token")
        show_token.toggled.connect(
            lambda v: self._shopify_token.setEchoMode(
                QLineEdit.EchoMode.Normal if v else QLineEdit.EchoMode.Password
            )
        )
        form.addRow("", show_token)

        self._shopify_api_version = QLineEdit()
        self._shopify_api_version.setPlaceholderText("2024-01")
        form.addRow("API Version", self._shopify_api_version)

        self._shopify_location_id = QLineEdit()
        self._shopify_location_id.setPlaceholderText("Leave blank to auto-detect")
        form.addRow("Location ID", self._shopify_location_id)

        self._shopify_sync_interval = QSpinBox()
        self._shopify_sync_interval.setRange(60, 86400)
        self._shopify_sync_interval.setSuffix(" seconds")
        form.addRow("Auto-Sync Interval", self._shopify_sync_interval)

        self._shopify_sync_products = QCheckBox("Sync product catalogue")
        form.addRow("", self._shopify_sync_products)

        self._shopify_sync_inventory = QCheckBox("Sync stock to Shopify after each sale")
        self._shopify_sync_inventory.setToolTip(
            "When enabled, stock levels are pushed to Shopify immediately after a sale is processed.\n"
            "Disable this if you want to prevent real-time stock updates (e.g. while testing)."
        )
        form.addRow("", self._shopify_sync_inventory)

        layout.addLayout(form)

        test_btn = QPushButton("🔗 Test Connection")
        test_btn.clicked.connect(self._test_shopify)
        layout.addWidget(test_btn)

        # Sync log
        log_lbl = QLabel("Recent Sync Log:")
        log_lbl.setStyleSheet("font-weight:600; margin-top:12px;")
        layout.addWidget(log_lbl)

        self._sync_log_table = QTableWidget(0, 4)
        self._sync_log_table.setHorizontalHeaderLabels(["Time", "Type", "Status", "Details"])
        hh = self._sync_log_table.horizontalHeader()
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self._sync_log_table.verticalHeader().hide()
        self._sync_log_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._sync_log_table.setMaximumHeight(200)
        layout.addWidget(self._sync_log_table)

        refresh_log = QPushButton("🔄 Refresh Log")
        refresh_log.clicked.connect(self._load_sync_log)
        layout.addWidget(refresh_log)

        layout.addStretch()
        scroll.setWidget(w)
        return scroll

    # ── Hardware ──────────────────────────────────────────────────────────
    def _build_hardware_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        w = QWidget()
        layout = QVBoxLayout(w)

        # Receipt Printer
        printer_group = QGroupBox("Receipt Printer")
        pform = QFormLayout(printer_group)

        self._printer_type = QComboBox()
        self._printer_type.addItems([
            "none", "pdf", "escpos_usb", "escpos_serial", "escpos_network"
        ])
        self._printer_type.currentTextChanged.connect(self._update_printer_ui)
        pform.addRow("Printer Type", self._printer_type)

        self._printer_port = QLineEdit()
        self._printer_port.setPlaceholderText("COM3 or /dev/ttyUSB0")
        pform.addRow("Serial Port", self._printer_port)

        self._printer_baudrate = QComboBox()
        self._printer_baudrate.addItems(["9600", "19200", "38400", "57600", "115200"])
        pform.addRow("Baud Rate", self._printer_baudrate)

        self._printer_network_ip = QLineEdit()
        self._printer_network_ip.setPlaceholderText("192.168.1.100")
        pform.addRow("Network IP", self._printer_network_ip)

        self._printer_network_port = QSpinBox()
        self._printer_network_port.setRange(1, 65535)
        self._printer_network_port.setValue(9100)
        pform.addRow("Network Port", self._printer_network_port)

        self._printer_usb_vendor = QLineEdit()
        self._printer_usb_vendor.setPlaceholderText("0x04b8 (Epson)")
        pform.addRow("USB Vendor ID", self._printer_usb_vendor)

        self._printer_usb_product = QLineEdit()
        self._printer_usb_product.setPlaceholderText("0x0202")
        pform.addRow("USB Product ID", self._printer_usb_product)

        test_print_btn = QPushButton("🖨 Print Test Receipt")
        test_print_btn.clicked.connect(self._test_print)
        pform.addRow("", test_print_btn)

        layout.addWidget(printer_group)

        # VFD Display
        vfd_group = QGroupBox("VFD Customer Display")
        vform = QFormLayout(vfd_group)

        self._vfd_enabled = QCheckBox("Enable VFD Display")
        vform.addRow("", self._vfd_enabled)

        self._vfd_port = QLineEdit()
        self._vfd_port.setPlaceholderText("COM4 or /dev/ttyUSB1")
        vform.addRow("Serial Port", self._vfd_port)

        self._vfd_baudrate = QComboBox()
        self._vfd_baudrate.addItems(["9600", "19200", "38400"])
        vform.addRow("Baud Rate", self._vfd_baudrate)

        self._vfd_type = QComboBox()
        self._vfd_type.addItems(["epson", "bixolon", "generic"])
        vform.addRow("Display Type", self._vfd_type)

        self._vfd_cols = QSpinBox()
        self._vfd_cols.setRange(16, 40)
        self._vfd_cols.setValue(20)
        vform.addRow("Display Columns", self._vfd_cols)

        self._vfd_welcome1 = QLineEdit()
        self._vfd_welcome1.setPlaceholderText("Welcome!")
        vform.addRow("Welcome Line 1", self._vfd_welcome1)

        self._vfd_welcome2 = QLineEdit()
        self._vfd_welcome2.setPlaceholderText("Please wait…")
        vform.addRow("Welcome Line 2", self._vfd_welcome2)

        test_vfd_btn = QPushButton("📺 Test VFD")
        test_vfd_btn.clicked.connect(self._test_vfd)
        vform.addRow("", test_vfd_btn)

        layout.addWidget(vfd_group)
        layout.addStretch()
        scroll.setWidget(w)
        return scroll

    # ── Barcode Labels ────────────────────────────────────────────────────
    def _build_barcode_label_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        w = QWidget()
        form = QFormLayout(w)
        form.setSpacing(12)

        self._bc_store_name = QLineEdit()
        self._bc_store_name.setPlaceholderText("Store name on label")
        form.addRow("Store Name", self._bc_store_name)

        self._bc_label_width = QDoubleSpinBox()
        self._bc_label_width.setRange(10, 300)
        self._bc_label_width.setDecimals(1)
        self._bc_label_width.setSuffix(" mm")
        form.addRow("Label Width", self._bc_label_width)

        self._bc_label_height = QDoubleSpinBox()
        self._bc_label_height.setRange(10, 300)
        self._bc_label_height.setDecimals(1)
        self._bc_label_height.setSuffix(" mm")
        form.addRow("Label Height", self._bc_label_height)

        self._bc_cols = QSpinBox()
        self._bc_cols.setRange(1, 10)
        form.addRow("Columns Per Row", self._bc_cols)

        self._bc_gap_x = QDoubleSpinBox()
        self._bc_gap_x.setRange(0, 50)
        self._bc_gap_x.setDecimals(1)
        self._bc_gap_x.setSuffix(" mm")
        form.addRow("Horizontal Gap", self._bc_gap_x)

        self._bc_gap_y = QDoubleSpinBox()
        self._bc_gap_y.setRange(0, 50)
        self._bc_gap_y.setDecimals(1)
        self._bc_gap_y.setSuffix(" mm")
        form.addRow("Vertical Gap", self._bc_gap_y)

        self._bc_show_price = QCheckBox("Show Product Price on Label")
        form.addRow("", self._bc_show_price)

        self._bc_show_variant = QCheckBox("Show Variant Details on Label")
        form.addRow("", self._bc_show_variant)

        self._bc_default_copies = QSpinBox()
        self._bc_default_copies.setRange(1, 100)
        form.addRow("Default Number of Copies", self._bc_default_copies)

        scroll.setWidget(w)
        return scroll

    # ── About ─────────────────────────────────────────────────────────────
    def _build_about_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lbl = QLabel()
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setText(
            f"<center>"
            f"<p style='font-size:32px;'>🏪</p>"
            f"<p style='font-size:20px; font-weight:700; color:#f1f5f9;'>"
            f"{self.config.get('app_name', 'CanadaMart POS')}</p>"
            f"<p style='color:#94a3b8;'>{self.config.get('app_description', 'Point of Sale System')}</p>"
            f"<p style='color:#64748b;'>Version {self.config.get('app_version', '1.0.0')}</p>"
            f"<br>"
            f"<p style='color:#64748b; font-size:11px;'>"
            f"Built with Python · PyQt6 · Shopify API</p>"
            f"</center>"
        )
        lbl.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(lbl)
        return w

    # ------------------------------------------------------------------ #
    #  Load / Save                                                         #
    # ------------------------------------------------------------------ #
    def _load_settings(self):
        c = self.config

        # Business
        self._app_name.setText(c.get("app_name", ""))
        self._app_desc.setText(c.get("app_description", ""))
        self._business_name.setText(c.get("business_name", ""))
        self._business_tagline.setText(c.get("business_tagline", ""))
        self._business_address.setText(c.get("business_address", ""))
        self._business_phone.setText(c.get("business_phone", ""))
        self._business_email.setText(c.get("business_email", ""))
        self._business_website.setText(c.get("business_website", ""))
        self._business_reg.setText(c.get("business_reg_no", ""))
        self._business_tax_no.setText(c.get("business_tax_no", ""))
        self._logo_path.setText(c.get("logo_path", ""))
        self._refresh_logo_preview()
        idx = self._theme.findText(c.get("theme", "dark"))
        self._theme.setCurrentIndex(max(0, idx))

        # Receipt
        self._receipt_header.setPlainText(c.get("receipt_header", ""))
        self._receipt_footer.setPlainText(c.get("receipt_footer", ""))
        self._receipt_copies.setValue(int(c.get("receipt_copies", 1)))
        self._receipt_paper_width.setCurrentText(str(c.get("receipt_paper_width", 80)))
        self._receipt_show_logo.setChecked(bool(c.get("receipt_show_logo", True)))
        self._receipt_show_barcode.setChecked(bool(c.get("receipt_show_barcode", False)))
        self._inv_prefix.setText(c.get("invoice_prefix", "INV"))
        self._inv_next.setValue(int(c.get("invoice_next_number", 1000)))
        self._inv_show_sku.setChecked(bool(c.get("invoice_show_sku", True)))

        # POS
        self._currency_symbol.setText(c.get("currency_symbol", "$"))
        self._currency_code.setText(c.get("currency_code", "CAD"))
        idx = self._currency_position.findText(c.get("currency_position", "before"))
        self._currency_position.setCurrentIndex(max(0, idx))
        idx = self._default_payment.findText(c.get("default_payment_method", "cash"))
        self._default_payment.setCurrentIndex(max(0, idx))
        self._allow_neg_stock.setChecked(bool(c.get("allow_negative_stock", False)))
        self._require_customer.setChecked(bool(c.get("require_customer", False)))
        self._low_stock_threshold.setValue(int(c.get("low_stock_threshold", 5)))
        self._max_discount.setValue(float(c.get("max_discount_percent", 100)))
        self._enable_loyalty.setChecked(bool(c.get("enable_loyalty", True)))
        self._points_per_dollar.setValue(int(c.get("points_per_dollar", 1)))

        # Tax
        self._tax_enabled.setChecked(bool(c.get("tax_enabled", True)))
        self._tax_name.setText(c.get("tax_name", "HST"))
        self._tax_rate.setValue(float(c.get("tax_rate", 13)))
        self._tax_inclusive.setChecked(bool(c.get("tax_inclusive", False)))

        # Shopify
        self._shopify_enabled.setChecked(bool(c.get("shopify_enabled", False)))
        self._shopify_url.setText(c.get("shopify_shop_url", ""))
        self._shopify_client_id.setText(c.get("shopify_client_id", ""))
        self._shopify_client_secret.setText(c.get("shopify_client_secret", ""))
        self._shopify_token.setText(c.get("shopify_access_token", ""))
        self._shopify_api_version.setText(c.get("shopify_api_version", "2026-01"))
        self._shopify_location_id.setText(c.get("shopify_location_id", ""))
        self._shopify_sync_interval.setValue(int(c.get("shopify_sync_interval", 300)))
        self._shopify_sync_products.setChecked(bool(c.get("shopify_sync_products", True)))
        self._shopify_sync_inventory.setChecked(bool(c.get("shopify_sync_inventory", True)))

        # Hardware – Printer
        idx = self._printer_type.findText(c.get("printer_type", "none"))
        self._printer_type.setCurrentIndex(max(0, idx))
        self._printer_port.setText(c.get("printer_port", ""))
        self._printer_baudrate.setCurrentText(str(c.get("printer_baudrate", 9600)))
        self._printer_network_ip.setText(c.get("printer_network_ip", ""))
        self._printer_network_port.setValue(int(c.get("printer_network_port", 9100)))
        self._printer_usb_vendor.setText(c.get("printer_usb_vendor", "0x04b8"))
        self._printer_usb_product.setText(c.get("printer_usb_product", "0x0202"))

        # Hardware – VFD
        self._vfd_enabled.setChecked(bool(c.get("vfd_enabled", False)))
        self._vfd_port.setText(c.get("vfd_port", "COM3"))
        self._vfd_baudrate.setCurrentText(str(c.get("vfd_baudrate", 9600)))
        idx = self._vfd_type.findText(c.get("vfd_type", "epson"))
        self._vfd_type.setCurrentIndex(max(0, idx))
        self._vfd_cols.setValue(int(c.get("vfd_cols", 20)))
        self._vfd_welcome1.setText(c.get("vfd_welcome_line1", "Welcome!"))
        self._vfd_welcome2.setText(c.get("vfd_welcome_line2", "Please wait..."))

        # Barcode Labels
        self._bc_store_name.setText(self.db.get_setting("barcode_store_name", c.get("business_name", "CanadaMart")))
        self._bc_label_width.setValue(float(self.db.get_setting("barcode_label_width_mm", "50.0")))
        self._bc_label_height.setValue(float(self.db.get_setting("barcode_label_height_mm", "25.0")))
        self._bc_cols.setValue(int(self.db.get_setting("barcode_columns_per_row", "1")))
        self._bc_gap_x.setValue(float(self.db.get_setting("barcode_gap_x_mm", "2.0")))
        self._bc_gap_y.setValue(float(self.db.get_setting("barcode_gap_y_mm", "2.0")))
        self._bc_show_price.setChecked(self.db.get_setting("barcode_show_price", "1") == "1")
        self._bc_show_variant.setChecked(self.db.get_setting("barcode_show_variant", "1") == "1")
        self._bc_default_copies.setValue(int(self.db.get_setting("barcode_default_copies", "1")))

        self._load_sync_log()

    def _save_all(self):
        data = {
            # Business
            "app_name": self._app_name.text().strip() or "CanadaMart POS",
            "app_description": self._app_desc.text().strip(),
            "business_name": self._business_name.text().strip(),
            "business_tagline": self._business_tagline.text().strip(),
            "business_address": self._business_address.text().strip(),
            "business_phone": self._business_phone.text().strip(),
            "business_email": self._business_email.text().strip(),
            "business_website": self._business_website.text().strip(),
            "business_reg_no": self._business_reg.text().strip(),
            "business_tax_no": self._business_tax_no.text().strip(),
            "logo_path": self._logo_path.text().strip(),
            "theme": self._theme.currentText(),
            # Receipt
            "receipt_header": self._receipt_header.toPlainText().strip(),
            "receipt_footer": self._receipt_footer.toPlainText().strip(),
            "receipt_copies": self._receipt_copies.value(),
            "receipt_paper_width": int(self._receipt_paper_width.currentText()),
            "receipt_show_logo": self._receipt_show_logo.isChecked(),
            "receipt_show_barcode": self._receipt_show_barcode.isChecked(),
            "invoice_prefix": self._inv_prefix.text().strip() or "INV",
            "invoice_next_number": self._inv_next.value(),
            "invoice_show_sku": self._inv_show_sku.isChecked(),
            # POS
            "currency_symbol": self._currency_symbol.text().strip() or "$",
            "currency_code": self._currency_code.text().strip() or "CAD",
            "currency_position": self._currency_position.currentText(),
            "default_payment_method": self._default_payment.currentText(),
            "allow_negative_stock": self._allow_neg_stock.isChecked(),
            "require_customer": self._require_customer.isChecked(),
            "low_stock_threshold": self._low_stock_threshold.value(),
            "max_discount_percent": self._max_discount.value(),
            "enable_loyalty": self._enable_loyalty.isChecked(),
            "points_per_dollar": self._points_per_dollar.value(),
            # Tax
            "tax_enabled": self._tax_enabled.isChecked(),
            "tax_name": self._tax_name.text().strip() or "Tax",
            "tax_rate": self._tax_rate.value(),
            "tax_inclusive": self._tax_inclusive.isChecked(),
            # Shopify
            "shopify_enabled": self._shopify_enabled.isChecked(),
            "shopify_shop_url": self._shopify_url.text().strip(),
            "shopify_client_id": self._shopify_client_id.text().strip(),
            "shopify_client_secret": self._shopify_client_secret.text().strip(),
            "shopify_access_token": self._shopify_token.text().strip(),
            "shopify_api_version": self._shopify_api_version.text().strip() or "2026-01",
            "shopify_location_id": self._shopify_location_id.text().strip(),
            "shopify_sync_interval": self._shopify_sync_interval.value(),
            "shopify_sync_products": self._shopify_sync_products.isChecked(),
            "shopify_sync_inventory": self._shopify_sync_inventory.isChecked(),
            # Hardware – Printer
            "printer_type": self._printer_type.currentText(),
            "printer_port": self._printer_port.text().strip(),
            "printer_baudrate": int(self._printer_baudrate.currentText()),
            "printer_network_ip": self._printer_network_ip.text().strip(),
            "printer_network_port": self._printer_network_port.value(),
            "printer_usb_vendor": self._printer_usb_vendor.text().strip() or "0x04b8",
            "printer_usb_product": self._printer_usb_product.text().strip() or "0x0202",
            # Hardware – VFD
            "vfd_enabled": self._vfd_enabled.isChecked(),
            "vfd_port": self._vfd_port.text().strip(),
            "vfd_baudrate": int(self._vfd_baudrate.currentText()),
            "vfd_type": self._vfd_type.currentText(),
            "vfd_cols": self._vfd_cols.value(),
            "vfd_welcome_line1": self._vfd_welcome1.text(),
            "vfd_welcome_line2": self._vfd_welcome2.text(),
        }
        self.config.update(data)
        
        # Save Barcode Label Settings to DB
        self.db.set_setting("barcode_store_name", self._bc_store_name.text().strip())
        self.db.set_setting("barcode_label_width_mm", str(self._bc_label_width.value()))
        self.db.set_setting("barcode_label_height_mm", str(self._bc_label_height.value()))
        self.db.set_setting("barcode_columns_per_row", str(self._bc_cols.value()))
        self.db.set_setting("barcode_gap_x_mm", str(self._bc_gap_x.value()))
        self.db.set_setting("barcode_gap_y_mm", str(self._bc_gap_y.value()))
        self.db.set_setting("barcode_show_price", "1" if self._bc_show_price.isChecked() else "0")
        self.db.set_setting("barcode_show_variant", "1" if self._bc_show_variant.isChecked() else "0")
        self.db.set_setting("barcode_default_copies", str(self._bc_default_copies.value()))

        QMessageBox.information(self, "Settings Saved", "All settings have been saved successfully.")
        self.settings_saved.emit()

    # ------------------------------------------------------------------ #
    #  Logo helpers                                                        #
    # ------------------------------------------------------------------ #
    def _browse_logo(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Logo", "",
            "Images (*.png *.jpg *.jpeg *.bmp *.svg)"
        )
        if path:
            self._logo_path.setText(path)
            self._refresh_logo_preview()

    def _clear_logo(self):
        self._logo_path.clear()
        self._logo_preview.clear()
        self._logo_preview.setText("No Logo")

    def _refresh_logo_preview(self):
        path = self._logo_path.text()
        if path and os.path.exists(path):
            pix = QPixmap(path)
            if not pix.isNull():
                self._logo_preview.setPixmap(pix.scaled(
                    196, 76,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                ))
            else:
                self._logo_preview.setText("⚠ Cannot load image")
        else:
            self._logo_preview.setText("No Logo")

    # ------------------------------------------------------------------ #
    #  Tests                                                               #
    # ------------------------------------------------------------------ #
    def _test_shopify(self):
        import urllib.request, urllib.parse, json
        url = self._shopify_url.text().strip()
        version = self._shopify_api_version.text().strip() or "2026-01"
        client_id = self._shopify_client_id.text().strip()
        client_secret = self._shopify_client_secret.text().strip()
        static_token = self._shopify_token.text().strip()

        if not url:
            QMessageBox.warning(self, "Missing Info", "Please enter the Shop URL.")
            return
        if not client_id and not static_token:
            QMessageBox.warning(
                self, "Missing Credentials",
                "Enter Client ID + Client Secret, or a Static Access Token."
            )
            return

        if not url.startswith("https://"):
            url = f"https://{url}"

        try:
            # ── Step 1: obtain token ──────────────────────────────────
            if client_id and client_secret:
                oauth_url = f"{url}/admin/oauth/access_token"
                data = urllib.parse.urlencode({
                    "grant_type": "client_credentials",
                    "client_id": client_id,
                    "client_secret": client_secret,
                }).encode()
                req = urllib.request.Request(
                    oauth_url, data=data,
                    headers={"Content-Type": "application/x-www-form-urlencoded"}
                )
                with urllib.request.urlopen(req, timeout=15) as resp:
                    body = json.loads(resp.read())
                token = body.get("access_token", "")
                if not token:
                    QMessageBox.critical(
                        self, "Token Error",
                        f"Shopify did not return a token.\nResponse: {body}"
                    )
                    return
            else:
                token = static_token

            # ── Step 2: verify connection ─────────────────────────────
            import shopify
            shopify.ShopifyResource.set_site(f"{url}/admin/api/{version}")
            shopify.ShopifyResource.set_headers({"X-Shopify-Access-Token": token})
            shop = shopify.Shop.current()

            # ── Step 3: save credentials and auto-enable only on success ─
            self._shopify_enabled.setChecked(True)
            self.config.update({
                "shopify_enabled":        True,
                "shopify_shop_url":       url,
                "shopify_client_id":      client_id,
                "shopify_client_secret":  client_secret,
                "shopify_access_token":   static_token,
                "shopify_api_version":    version,
                "shopify_location_id":    self._shopify_location_id.text().strip(),
                "shopify_sync_interval":  self._shopify_sync_interval.value(),
                "shopify_sync_products":  self._shopify_sync_products.isChecked(),
                "shopify_sync_inventory": self._shopify_sync_inventory.isChecked(),
            })

            QMessageBox.information(
                self, "Connection Successful",
                f"✓ Connected to: {shop.name}\n"
                f"Domain: {shop.domain}\n"
                f"Currency: {shop.currency}\n\n"
                f"Credentials saved and Shopify integration enabled.\n"
                f"Click 'Save All Settings' to start the sync."
            )
        except ImportError:
            QMessageBox.warning(self, "Package Missing", "Install ShopifyAPI:\npip install ShopifyAPI")
        except urllib.error.HTTPError as e:
            err_body = e.read().decode() if hasattr(e, 'read') else str(e)
            QMessageBox.critical(self, "Connection Failed", f"HTTP {e.code}:\n{err_body}")
        except Exception as e:
            QMessageBox.critical(self, "Connection Failed", str(e))

    def _test_print(self):
        import datetime
        from services.receipt_printer import ReceiptPrinter
        printer = ReceiptPrinter(self.config)
        test_sale = {
            "invoice_number": "TEST-001",
            "subtotal": 10.00,
            "tax_amount": 1.30,
            "discount_amount": 0.00,
            "total": 11.30,
            "payment_method": "cash",
            "amount_paid": 20.00,
            "change_amount": 8.70,
        }
        test_items = [{
            "product_name": "Test Product",
            "quantity": 1,
            "unit_price": 10.00,
            "discount_percent": 0,
            "total": 10.00,
        }]
        ok = printer.print_receipt(test_sale, test_items)
        if ok:
            QMessageBox.information(self, "Test Print", "Test receipt sent to printer.")
        else:
            QMessageBox.warning(self, "Test Print", "Print failed – check printer settings.")

    def _test_vfd(self):
        from services.vfd_display import VFDDisplay
        vfd = VFDDisplay(self.config)
        ok = vfd.connect()
        if ok:
            vfd.show_message("VFD TEST", "Connected OK!")
            vfd.disconnect()
            QMessageBox.information(self, "VFD Test", "VFD connected and test message sent.")
        else:
            QMessageBox.warning(self, "VFD Test",
                                "Could not connect to VFD. Check port and settings.")

    def _update_printer_ui(self, ptype: str):
        pass  # Could show/hide fields based on type

    def _load_sync_log(self):
        logs = self.db.get_sync_log(30)
        self._sync_log_table.setRowCount(len(logs))
        for row, log in enumerate(logs):
            self._sync_log_table.setItem(row, 0, QTableWidgetItem(log.get("created_at", "")[:16]))
            self._sync_log_table.setItem(row, 1, QTableWidgetItem(log.get("sync_type", "")))
            status = log.get("status", "")
            si = QTableWidgetItem(status)
            si.setForeground(
                __import__("PyQt6.QtGui", fromlist=["QColor"]).QColor(
                    "#4ade80" if status == "success" else "#f87171"
                )
            )
            self._sync_log_table.setItem(row, 2, si)
            self._sync_log_table.setItem(row, 3, QTableWidgetItem(log.get("message", "")))

    # ================================================================== #
    #  USERS TAB                                                           #
    # ================================================================== #
    def _build_users_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Toolbar
        tb = QHBoxLayout()
        tb.addWidget(QLabel("System Users"))
        tb.addStretch()

        add_u = QPushButton("+ Add User")
        add_u.setObjectName("PrimaryBtn")
        add_u.clicked.connect(self._add_user)
        tb.addWidget(add_u)

        edit_u = QPushButton("✏ Edit")
        edit_u.clicked.connect(self._edit_user)
        tb.addWidget(edit_u)

        chpw_u = QPushButton("🔑 Change Password")
        chpw_u.clicked.connect(self._change_password)
        tb.addWidget(chpw_u)

        del_u = QPushButton("🗑 Delete")
        del_u.setObjectName("DangerBtn")
        del_u.clicked.connect(self._delete_user)
        tb.addWidget(del_u)

        layout.addLayout(tb)

        self._users_table = QTableWidget(0, 5)
        self._users_table.setHorizontalHeaderLabels(
            ["Username", "Full Name", "Role", "Active", "Last Login"]
        )
        hh = self._users_table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self._users_table.verticalHeader().hide()
        self._users_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._users_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._users_table.setAlternatingRowColors(True)
        layout.addWidget(self._users_table)

        note = QLabel("\u26a0\ufe0f  Never share passwords. The default admin password should be changed immediately.")
        note.setStyleSheet("color: #f59e0b; font-size: 11px;")
        note.setWordWrap(True)
        layout.addWidget(note)

        self._reload_users()
        return w

    def _reload_users(self):
        if not hasattr(self, "_users_table"):
            return
        users = self.db.get_users()
        self._users_data = users
        self._users_table.setRowCount(len(users))
        from PyQt6.QtGui import QColor
        for row, u in enumerate(users):
            self._users_table.setItem(row, 0, QTableWidgetItem(u.get("username", "")))
            self._users_table.setItem(row, 1, QTableWidgetItem(u.get("full_name", "")))
            role = u.get("role", "cashier")
            role_lbl = {"admin": "Administrator", "manager": "Manager", "cashier": "Cashier"}.get(role, role.title())
            ri = QTableWidgetItem(role_lbl)
            ri.setForeground(QColor({"admin": "#f59e0b", "manager": "#3b82f6", "cashier": "#10b981"}.get(role, "#94a3b8")))
            self._users_table.setItem(row, 2, ri)
            active_item = QTableWidgetItem("Yes" if u.get("active") else "No")
            active_item.setForeground(QColor("#4ade80" if u.get("active") else "#f87171"))
            self._users_table.setItem(row, 3, active_item)
            last = (u.get("last_login") or "")[:16]
            self._users_table.setItem(row, 4, QTableWidgetItem(last or "Never"))

    def _get_selected_user(self):
        if not hasattr(self, "_users_data"):
            return None
        row = self._users_table.currentRow()
        if 0 <= row < len(self._users_data):
            return self._users_data[row]
        return None

    def _add_user(self):
        dlg = _UserDialog(parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            try:
                self.db.add_user(dlg.data)
                self._reload_users()
            except Exception as e:
                if "UNIQUE" in str(e):
                    QMessageBox.warning(self, "Duplicate", "Username already exists.")
                else:
                    QMessageBox.critical(self, "Error", str(e))

    def _edit_user(self):
        user = self._get_selected_user()
        if not user:
            QMessageBox.information(self, "Select User", "Please select a user to edit.")
            return
        dlg = _UserDialog(user=user, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.db.update_user(user["id"], dlg.data)
            self._reload_users()

    def _change_password(self):
        user = self._get_selected_user()
        if not user:
            QMessageBox.information(self, "Select User", "Please select a user.")
            return
        dlg = _ChangePasswordDialog(user["full_name"], parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.db.change_password(user["id"], dlg.new_password)
            QMessageBox.information(self, "Password Changed",
                                    f"Password updated for {user['full_name']}.")

    def _delete_user(self):
        user = self._get_selected_user()
        if not user:
            return
        if user["username"] == "admin":
            QMessageBox.warning(self, "Cannot Delete", "The admin account cannot be deleted.")
            return
        # Prevent deleting yourself
        if user["username"] == self.current_user.get("username"):
            QMessageBox.warning(self, "Cannot Delete", "You cannot delete your own account.")
            return
        reply = QMessageBox.question(
            self, "Delete User",
            f"Delete user '{user['full_name']}' ({user['username']})?\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.db.delete_user(user["id"])
            self._reload_users()


# ───────────────────────────────────────────────────────────────────────────
#  Helper dialogs for user management
# ───────────────────────────────────────────────────────────────────────────
class _UserDialog(QDialog):
    """Add / edit a user account."""
    ROLES = [("admin", "Administrator"), ("manager", "Manager"), ("cashier", "Cashier")]

    def __init__(self, user: dict | None = None, parent=None):
        super().__init__(parent)
        self.user = user
        self.setWindowTitle("Edit User" if user else "Add User")
        self.setMinimumWidth(380)
        self._build()
        if user:
            self._populate(user)

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        form = QFormLayout()
        form.setSpacing(8)

        self._username = QLineEdit()
        self._username.setPlaceholderText("lowercase, no spaces")
        form.addRow("Username *", self._username)

        self._full_name = QLineEdit()
        self._full_name.setPlaceholderText("Display name")
        form.addRow("Full Name *", self._full_name)

        self._role = QComboBox()
        for val, label in self.ROLES:
            self._role.addItem(label, val)
        form.addRow("Role *", self._role)

        self._active = QCheckBox("Account active")
        self._active.setChecked(True)
        form.addRow("", self._active)

        pw_note = "" if self.user else "Password *"
        self._password = QLineEdit()
        self._password.setEchoMode(QLineEdit.EchoMode.Password)
        self._password.setPlaceholderText("Leave blank to keep current" if self.user else "Set initial password")
        form.addRow(pw_note or "New Password", self._password)

        layout.addLayout(form)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _populate(self, u: dict):
        self._username.setText(u.get("username", ""))
        self._full_name.setText(u.get("full_name", ""))
        for i, (val, _) in enumerate(self.ROLES):
            if val == u.get("role"):
                self._role.setCurrentIndex(i)
        self._active.setChecked(bool(u.get("active", True)))

    def _save(self):
        username = self._username.text().strip().lower()
        full_name = self._full_name.text().strip()
        password = self._password.text()

        if not username:
            QMessageBox.warning(self, "Validation", "Username is required.")
            return
        if not full_name:
            QMessageBox.warning(self, "Validation", "Full name is required.")
            return
        if not self.user and not password:
            QMessageBox.warning(self, "Validation", "Password is required for new users.")
            return

        self.data = {
            "username":  username,
            "full_name": full_name,
            "role":      self._role.currentData(),
            "active":    self._active.isChecked(),
        }
        if password:
            self.data["password"] = password
        self.accept()


class _ChangePasswordDialog(QDialog):
    """Dialog to set a new password for a user."""
    def __init__(self, full_name: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Change Password – {full_name}")
        self.setMinimumWidth(360)
        self.new_password = ""
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        form = QFormLayout()

        self._pw1 = QLineEdit()
        self._pw1.setEchoMode(QLineEdit.EchoMode.Password)
        self._pw1.setPlaceholderText("New password (min 6 chars)")
        form.addRow("New Password", self._pw1)

        self._pw2 = QLineEdit()
        self._pw2.setEchoMode(QLineEdit.EchoMode.Password)
        self._pw2.setPlaceholderText("Confirm new password")
        form.addRow("Confirm", self._pw2)
        layout.addLayout(form)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _save(self):
        pw1 = self._pw1.text()
        pw2 = self._pw2.text()
        if len(pw1) < 6:
            QMessageBox.warning(self, "Too Short", "Password must be at least 6 characters.")
            return
        if pw1 != pw2:
            QMessageBox.warning(self, "Mismatch", "Passwords do not match.")
            return
        self.new_password = pw1
        self.accept()
