"""Inventory management module."""
import csv
import io
from typing import Optional, List

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QTableWidget, QTableWidgetItem, QHeaderView,
    QDialog, QFormLayout, QComboBox, QSpinBox, QDoubleSpinBox,
    QMessageBox, QTabWidget, QFileDialog, QDialogButtonBox,
    QTextEdit, QCheckBox, QSizePolicy, QFrame, QInputDialog,
    QColorDialog, QListWidget, QListWidgetItem,
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, QObject
from PyQt6.QtGui import QColor, QBrush, QIcon, QPixmap


# ═══════════════════════════════════════════════════════════════════════════
#  Product Add/Edit dialog
# ═══════════════════════════════════════════════════════════════════════════
class ProductDialog(QDialog):
    """Add or edit a product."""

    def __init__(self, db, product: Optional[dict] = None, parent=None):
        super().__init__(parent)
        self.db = db
        self.product = product
        self.setWindowTitle("Edit Product" if product else "Add Product")
        self.setMinimumWidth(500)
        self._build()
        if product:
            self._populate(product)

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        tabs = QTabWidget()
        layout.addWidget(tabs)

        # ── Basic Info tab ──────────────────────────────────────────────
        basic = QWidget()
        form = QFormLayout(basic)
        form.setSpacing(10)

        self._name = QLineEdit()
        self._name.setPlaceholderText("Required")
        form.addRow("Product Name *", self._name)

        self._sku = QLineEdit()
        self._sku.setPlaceholderText("Auto-generated if blank")
        form.addRow("SKU", self._sku)

        self._barcode = QLineEdit()
        self._barcode.setPlaceholderText("EAN / UPC barcode")
        form.addRow("Barcode", self._barcode)

        self._category = QComboBox()
        self._category.addItem("— Select Category —", None)
        for cat in self.db.get_categories():
            self._category.addItem(cat["name"], cat["id"])
        form.addRow("Category", self._category)

        self._description = QTextEdit()
        self._description.setMaximumHeight(80)
        form.addRow("Description", self._description)

        tabs.addTab(basic, "Basic Info")

        # ── Pricing & Stock tab ─────────────────────────────────────────
        pricing = QWidget()
        pform = QFormLayout(pricing)
        pform.setSpacing(10)

        self._price = QDoubleSpinBox()
        self._price.setRange(0, 999999)
        self._price.setDecimals(2)
        self._price.setPrefix("$ ")
        pform.addRow("Selling Price *", self._price)

        self._cost = QDoubleSpinBox()
        self._cost.setRange(0, 999999)
        self._cost.setDecimals(2)
        self._cost.setPrefix("$ ")
        pform.addRow("Cost Price", self._cost)

        self._quantity = QSpinBox()
        self._quantity.setRange(0, 999999)
        pform.addRow("Stock Quantity", self._quantity)

        self._min_qty = QSpinBox()
        self._min_qty.setRange(0, 9999)
        self._min_qty.setValue(5)
        pform.addRow("Min Stock Alert", self._min_qty)

        self._unit = QLineEdit("pcs")
        pform.addRow("Unit", self._unit)

        self._tax_rate = QDoubleSpinBox()
        self._tax_rate.setRange(-1, 100)
        self._tax_rate.setDecimals(1)
        self._tax_rate.setValue(-1)
        self._tax_rate.setSpecialValueText("Use default")
        self._tax_rate.setSuffix(" %")
        pform.addRow("Tax Rate (-1 = default)", self._tax_rate)

        tabs.addTab(pricing, "Pricing & Stock")

        # Buttons
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _populate(self, p: dict):
        self._name.setText(p.get("name", ""))
        self._sku.setText(p.get("sku", "") or "")
        self._barcode.setText(p.get("barcode", "") or "")
        self._description.setPlainText(p.get("description", "") or "")
        self._price.setValue(float(p.get("price", 0)))
        self._cost.setValue(float(p.get("cost", 0)))
        self._quantity.setValue(int(p.get("quantity", 0)))
        self._min_qty.setValue(int(p.get("min_quantity", 5)))
        self._unit.setText(p.get("unit", "pcs") or "pcs")
        self._tax_rate.setValue(float(p.get("tax_rate", -1) or -1))

        # Category
        cat_id = p.get("category_id")
        if cat_id:
            for i in range(self._category.count()):
                if self._category.itemData(i) == cat_id:
                    self._category.setCurrentIndex(i)
                    break

    def _save(self):
        name = self._name.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation", "Product name is required.")
            return
        price = self._price.value()
        if price <= 0:
            QMessageBox.warning(self, "Validation", "Price must be greater than 0.")
            return

        self.data = {
            "name": name,
            "sku": self._sku.text().strip() or None,
            "barcode": self._barcode.text().strip() or None,
            "description": self._description.toPlainText().strip(),
            "category_id": self._category.currentData(),
            "price": price,
            "cost": self._cost.value(),
            "quantity": self._quantity.value(),
            "min_quantity": self._min_qty.value(),
            "unit": self._unit.text().strip() or "pcs",
            "tax_rate": self._tax_rate.value(),
        }
        self.accept()


# ═══════════════════════════════════════════════════════════════════════════
#  Stock Adjustment dialog
# ═══════════════════════════════════════════════════════════════════════════
class StockAdjustDialog(QDialog):
    def __init__(self, product: dict, parent=None):
        super().__init__(parent)
        self.product = product
        self.setWindowTitle(f"Adjust Stock – {product['name']}")
        self.setMinimumWidth(380)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)

        info = QLabel(f"Current Stock: <b>{self.product['quantity']}</b> {self.product.get('unit','pcs')}")
        info.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(info)

        form = QFormLayout()
        self._type = QComboBox()
        self._type.addItems(["add", "subtract", "set"])
        form.addRow("Adjustment Type:", self._type)

        self._qty = QSpinBox()
        self._qty.setRange(0, 999999)
        self._qty.setValue(1)
        form.addRow("Quantity:", self._qty)

        self._notes = QLineEdit()
        self._notes.setPlaceholderText("Reason for adjustment…")
        form.addRow("Notes:", self._notes)

        layout.addLayout(form)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._validate)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _validate(self):
        self.adj_type = self._type.currentText()
        self.adj_qty = self._qty.value()
        self.adj_notes = self._notes.text()
        self.accept()


# ═══════════════════════════════════════════════════════════════════════════
#  Inventory log viewer
# ═══════════════════════════════════════════════════════════════════════════
class InventoryLogDialog(QDialog):
    def __init__(self, db, product: dict = None, parent=None):
        super().__init__(parent)
        self.db = db
        self.product = product
        title = f"Stock Log – {product['name']}" if product else "Inventory Log"
        self.setWindowTitle(title)
        self.resize(700, 450)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        self._table = QTableWidget(0, 6)
        self._table.setHorizontalHeaderLabels([
            "Date/Time", "Product", "Type", "Change", "Before", "After"
        ])
        hh = self._table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._table.verticalHeader().hide()
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        layout.addWidget(self._table)
        self._load()

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

    def _load(self):
        pid = self.product["id"] if self.product else None
        logs = self.db.get_inventory_log(pid)
        self._table.setRowCount(len(logs))
        for row, log in enumerate(logs):
            self._table.setItem(row, 0, QTableWidgetItem(log.get("created_at", "")[:16]))
            self._table.setItem(row, 1, QTableWidgetItem(log.get("product_name", "")))
            self._table.setItem(row, 2, QTableWidgetItem(log.get("change_type", "")))
            change = log.get("quantity_change", 0)
            ch_item = QTableWidgetItem(f"{'+' if change > 0 else ''}{change}")
            ch_item.setForeground(QBrush(QColor("#4ade80" if change > 0 else "#f87171")))
            ch_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(row, 3, ch_item)
            self._table.setItem(row, 4, QTableWidgetItem(str(log.get("quantity_before", ""))))
            self._table.setItem(row, 5, QTableWidgetItem(str(log.get("quantity_after", ""))))


# ═══════════════════════════════════════════════════════════════════════════
#  Category Add / Edit dialog
# ═══════════════════════════════════════════════════════════════════════════
class _CategoryDialog(QDialog):
    """Small dialog to add or rename a category and pick its colour."""

    PRESET_COLORS = [
        "#6B7280", "#10B981", "#3B82F6", "#8B5CF6",
        "#EC4899", "#F59E0B", "#EF4444", "#14B8A6",
        "#F97316", "#06B6D4", "#84CC16", "#A78BFA",
    ]

    def __init__(self, category: Optional[dict] = None, parent=None):
        super().__init__(parent)
        self.category = category
        self._color = (category or {}).get("color", "#3B82F6")
        self.setWindowTitle("Edit Category" if category else "Add Category")
        self.setMinimumWidth(360)
        self._build()
        if category:
            self._name_edit.setText(category["name"])

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        form = QFormLayout()
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("Category name")
        form.addRow("Name *", self._name_edit)
        layout.addLayout(form)

        layout.addWidget(QLabel("Colour:"))

        # Colour preset grid
        grid = QHBoxLayout()
        grid.setSpacing(6)
        self._color_btns = []
        for c in self.PRESET_COLORS:
            btn = QPushButton()
            btn.setFixedSize(28, 28)
            btn.setStyleSheet(
                f"background:{c}; border-radius:14px; border: 2px solid transparent;"
            )
            btn.clicked.connect(lambda _, col=c: self._pick_preset(col))
            grid.addWidget(btn)
            self._color_btns.append((btn, c))
        layout.addLayout(grid)

        # Custom colour picker
        custom_btn = QPushButton("Custom…")
        custom_btn.clicked.connect(self._pick_custom)
        layout.addWidget(custom_btn)

        # Preview swatch
        self._preview = QLabel("  Aa  ")
        self._preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview.setFixedHeight(32)
        self._update_preview()
        layout.addWidget(self._preview)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save |
            QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

        self._highlight_current()

    def _highlight_current(self):
        for btn, c in self._color_btns:
            if c.lower() == self._color.lower():
                btn.setStyleSheet(
                    f"background:{c}; border-radius:14px; border: 2px solid #f1f5f9;"
                )
            else:
                btn.setStyleSheet(
                    f"background:{c}; border-radius:14px; border: 2px solid transparent;"
                )

    def _pick_preset(self, color: str):
        self._color = color
        self._update_preview()
        self._highlight_current()

    def _pick_custom(self):
        col = QColorDialog.getColor(QColor(self._color), self, "Pick Colour")
        if col.isValid():
            self._color = col.name()
            self._update_preview()
            self._highlight_current()

    def _update_preview(self):
        self._preview.setStyleSheet(
            f"background:{self._color}; color:#ffffff; border-radius:6px;"
            f" font-weight:600; font-size:13px;"
        )

    def _save(self):
        name = self._name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation", "Category name is required.")
            return
        self.data = {"name": name, "color": self._color}
        self.accept()


# ═══════════════════════════════════════════════════════════════════════════
#  Category Manager dialog (full CRUD list)
# ═══════════════════════════════════════════════════════════════════════════
class CategoryManagerDialog(QDialog):
    """Full category CRUD manager."""

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("Manage Categories")
        self.setMinimumSize(400, 460)
        self._build()
        self._reload()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Toolbar
        tb = QHBoxLayout()
        add_btn = QPushButton("+ Add")
        add_btn.setObjectName("PrimaryBtn")
        add_btn.clicked.connect(self._add)
        tb.addWidget(add_btn)

        edit_btn = QPushButton("✏ Edit")
        edit_btn.clicked.connect(self._edit)
        tb.addWidget(edit_btn)

        del_btn = QPushButton("🗑 Delete")
        del_btn.setObjectName("DangerBtn")
        del_btn.clicked.connect(self._delete)
        tb.addWidget(del_btn)
        tb.addStretch()
        layout.addLayout(tb)

        # List
        self._list = QListWidget()
        self._list.setAlternatingRowColors(True)
        self._list.doubleClicked.connect(self._edit)
        layout.addWidget(self._list, 1)

        note = QLabel("⚠\ufe0f  Deleting a category un-assigns it from all products.")
        note.setStyleSheet("color:#94a3b8; font-size:11px;")
        note.setWordWrap(True)
        layout.addWidget(note)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

    def _reload(self):
        self._categories = self.db.get_categories()
        self._list.clear()
        for cat in self._categories:
            item = QListWidgetItem(f"  {cat['name']}")
            # Colour swatch via icon
            pix = QPixmap(16, 16)
            pix.fill(QColor(cat.get("color", "#6B7280")))
            item.setIcon(QIcon(pix))
            item.setData(Qt.ItemDataRole.UserRole, cat)
            self._list.addItem(item)

    def _selected(self) -> Optional[dict]:
        item = self._list.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _add(self):
        dlg = _CategoryDialog(parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            try:
                self.db.add_category(dlg.data["name"], dlg.data["color"])
                self._reload()
            except Exception as e:
                if "UNIQUE" in str(e):
                    QMessageBox.warning(self, "Duplicate", "A category with that name already exists.")
                else:
                    QMessageBox.critical(self, "Error", str(e))

    def _edit(self):
        cat = self._selected()
        if not cat:
            QMessageBox.information(self, "Select", "Please select a category to edit.")
            return
        dlg = _CategoryDialog(category=cat, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            try:
                self.db.update_category(cat["id"], dlg.data["name"], dlg.data["color"])
                self._reload()
            except Exception as e:
                if "UNIQUE" in str(e):
                    QMessageBox.warning(self, "Duplicate", "A category with that name already exists.")
                else:
                    QMessageBox.critical(self, "Error", str(e))

    def _delete(self):
        cat = self._selected()
        if not cat:
            return
        reply = QMessageBox.question(
            self, "Delete Category",
            f"Delete category \u2018{cat['name']}\u2019?\n"
            "Products in this category will become uncategorized.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.db.delete_category(cat["id"])
            self._reload()


# ═══════════════════════════════════════════════════════════════════════════
#  Main Inventory Widget
# ═══════════════════════════════════════════════════════════════════════════
class InventoryWidget(QWidget):
    def __init__(self, config, db, shopify_service=None):
        super().__init__()
        self.config = config
        self.db = db
        self.shopify_service = shopify_service
        self._products: List[dict] = []
        self._build_ui()
        self._load_products()

    # ------------------------------------------------------------------ #
    #  UI                                                                  #
    # ------------------------------------------------------------------ #
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # ── Top toolbar ─────────────────────────────────────────────────
        toolbar = QHBoxLayout()

        title = QLabel("📦  Inventory")
        title.setStyleSheet("font-size:20px; font-weight:700; color:#f1f5f9;")
        toolbar.addWidget(title)
        toolbar.addStretch()

        for label, slot, obj_name in [
            ("+ Add Product", self._add_product, "PrimaryBtn"),
            ("✏ Edit", self._edit_product, ""),
            ("🗑 Delete", self._delete_product, "DangerBtn"),
            ("📊 Adjust Stock", self._adjust_stock, "WarningBtn"),
            ("📜 Log", self._view_log, ""),
            ("📤 Export CSV", self._export_csv, ""),
            ("📥 Import CSV", self._import_csv, ""),
        ]:
            btn = QPushButton(label)
            if obj_name:
                btn.setObjectName(obj_name)
            btn.clicked.connect(slot)
            toolbar.addWidget(btn)

        cat_btn = QPushButton("🏷 Categories")
        cat_btn.setObjectName("SecondaryBtn")
        cat_btn.clicked.connect(self._manage_categories)
        toolbar.addWidget(cat_btn)

        if self.shopify_service:
            sync_btn = QPushButton("🔄 Sync Shopify")
            sync_btn.setObjectName("SecondaryBtn")
            sync_btn.clicked.connect(self._trigger_shopify_sync)
            toolbar.addWidget(sync_btn)

        layout.addLayout(toolbar)

        # ── Filter row ──────────────────────────────────────────────────
        filter_row = QHBoxLayout()
        self._search = QLineEdit()
        self._search.setPlaceholderText("🔍  Search products…")
        self._search.setMaximumWidth(300)
        self._search.textChanged.connect(self._filter)
        filter_row.addWidget(self._search)

        self._cat_filter = QComboBox()
        self._cat_filter.addItem("All Categories", None)
        for cat in self.db.get_categories():
            self._cat_filter.addItem(cat["name"], cat["id"])
        self._cat_filter.currentIndexChanged.connect(self._filter)
        filter_row.addWidget(self._cat_filter)

        self._stock_filter = QComboBox()
        self._stock_filter.addItems(["All Stock", "Low Stock", "Out of Stock", "In Stock"])
        self._stock_filter.currentIndexChanged.connect(self._filter)
        filter_row.addWidget(self._stock_filter)

        filter_row.addStretch()

        self._count_lbl = QLabel("0 products")
        self._count_lbl.setStyleSheet("color:#64748b; font-size:12px;")
        filter_row.addWidget(self._count_lbl)

        layout.addLayout(filter_row)

        # ── Products table ──────────────────────────────────────────────
        self._table = QTableWidget(0, 10)
        self._table.setHorizontalHeaderLabels([
            "SKU", "Name", "Category", "Price", "Cost", "Stock",
            "Min Stock", "Unit", "Shopify", "Actions"
        ])
        hh = self._table.horizontalHeader()
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for col in [0, 2, 3, 4, 5, 6, 7, 8]:
            hh.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        self._table.verticalHeader().hide()
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.doubleClicked.connect(self._edit_product)
        layout.addWidget(self._table)

        # Low stock summary
        self._low_stock_lbl = QLabel()
        self._low_stock_lbl.setStyleSheet("color:#fcd34d; font-size:11px;")
        layout.addWidget(self._low_stock_lbl)

    # ------------------------------------------------------------------ #
    #  Data                                                                #
    # ------------------------------------------------------------------ #
    def _load_products(self):
        self._products = self.db.get_products(active_only=True)
        self._filter()
        low = self.db.get_low_stock_products()
        if low:
            self._low_stock_lbl.setText(
                f"⚠  {len(low)} product(s) below minimum stock level"
            )
        else:
            self._low_stock_lbl.clear()

    def _refresh_category_combos(self):
        """Rebuild category filter bar after a category add/edit/delete."""
        cats = self.db.get_categories()
        self._cat_filter.blockSignals(True)
        self._cat_filter.clear()
        self._cat_filter.addItem("All Categories", None)
        for cat in cats:
            self._cat_filter.addItem(cat["name"], cat["id"])
        self._cat_filter.blockSignals(False)

    def _manage_categories(self):
        dlg = CategoryManagerDialog(self.db, parent=self)
        dlg.exec()
        # Refresh filter bar and reload products so new category names show
        self._refresh_category_combos()
        self._load_products()

    def _filter(self):
        query = self._search.text().strip().lower()
        cat_id = self._cat_filter.currentData()
        stock_filt = self._stock_filter.currentText()
        threshold = int(self.config.get("low_stock_threshold", 5))

        filtered = []
        for p in self._products:
            if cat_id and p.get("category_id") != cat_id:
                continue
            qty = int(p.get("quantity", 0))
            if stock_filt == "Low Stock" and not (0 < qty <= threshold):
                continue
            if stock_filt == "Out of Stock" and qty > 0:
                continue
            if stock_filt == "In Stock" and qty <= 0:
                continue
            if query and query not in (p.get("name", "")).lower() \
                    and query not in (p.get("sku", "") or "").lower() \
                    and query not in (p.get("barcode", "") or "").lower():
                continue
            filtered.append(p)

        self._populate_table(filtered)
        self._count_lbl.setText(f"{len(filtered)} product(s)")

    def _populate_table(self, products: List[dict]):
        sym = self.config.get("currency_symbol", "$")
        threshold = int(self.config.get("low_stock_threshold", 5))
        self._table.setRowCount(len(products))
        self._displayed = products

        for row, p in enumerate(products):
            qty = int(p.get("quantity", 0))

            cells = [
                p.get("sku", "") or "",
                p.get("name", ""),
                p.get("category_name", "") or "",
                f"{sym}{p.get('price', 0):.2f}",
                f"{sym}{p.get('cost', 0):.2f}",
                str(qty),
                str(p.get("min_quantity", 5)),
                p.get("unit", "pcs") or "pcs",
                "✓" if p.get("shopify_id") else "—",
                "",
            ]
            for col, val in enumerate(cells):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)

                if col == 5:  # Stock column
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    if qty <= 0:
                        item.setForeground(QBrush(QColor("#f87171")))
                        item.setText("OUT")
                    elif qty <= threshold:
                        item.setForeground(QBrush(QColor("#fcd34d")))
                    else:
                        item.setForeground(QBrush(QColor("#4ade80")))

                if col == 8:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    if p.get("shopify_id"):
                        item.setForeground(QBrush(QColor("#4ade80")))

                self._table.setItem(row, col, item)

        self._table.resizeRowsToContents()

    # ------------------------------------------------------------------ #
    #  Actions                                                             #
    # ------------------------------------------------------------------ #
    def _get_selected_product(self) -> Optional[dict]:
        row = self._table.currentRow()
        if 0 <= row < len(getattr(self, "_displayed", [])):
            return self._displayed[row]
        return None

    def _add_product(self):
        dlg = ProductDialog(self.db, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.db.add_product(dlg.data)
            self._load_products()

    def _edit_product(self):
        product = self._get_selected_product()
        if not product:
            QMessageBox.information(self, "Select Product", "Please select a product to edit.")
            return
        dlg = ProductDialog(self.db, product, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.data
            data["shopify_synced"] = 0  # mark for re-sync
            self.db.update_product(product["id"], data)
            self._load_products()

    def _delete_product(self):
        product = self._get_selected_product()
        if not product:
            return
        reply = QMessageBox.question(
            self, "Delete Product",
            f"Delete '{product['name']}'?\nThis will hide it from POS but keep sales history.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.db.delete_product(product["id"])
            self._load_products()

    def _adjust_stock(self):
        product = self._get_selected_product()
        if not product:
            QMessageBox.information(self, "Select Product", "Please select a product.")
            return
        dlg = StockAdjustDialog(product, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            adj_type = dlg.adj_type
            qty = dlg.adj_qty
            notes = dlg.adj_notes

            if adj_type == "add":
                self.db.adjust_stock(product["id"], qty, "adjustment", notes=notes)
            elif adj_type == "subtract":
                self.db.adjust_stock(product["id"], -qty, "adjustment", notes=notes)
            elif adj_type == "set":
                current = int(product.get("quantity", 0))
                delta = qty - current
                self.db.adjust_stock(product["id"], delta, "set", notes=notes)

            # Sync to Shopify
            if self.shopify_service:
                updated = self.db.get_product(product["id"])
                if updated and updated.get("shopify_inventory_item_id"):
                    self.shopify_service.sync_stock_after_sale([])
            self._load_products()

    def _view_log(self):
        product = self._get_selected_product()
        dlg = InventoryLogDialog(self.db, product, parent=self)
        dlg.exec()

    def _trigger_shopify_sync(self):
        if self.shopify_service:
            self.shopify_service.trigger_sync()
            QMessageBox.information(self, "Sync Triggered",
                                    "Shopify sync has been triggered in the background.")

    # ------------------------------------------------------------------ #
    #  CSV import / export                                                 #
    # ------------------------------------------------------------------ #
    def _export_csv(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Products", "products.csv", "CSV Files (*.csv)"
        )
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["SKU", "Barcode", "Name", "Description", "Category",
                                  "Price", "Cost", "Quantity", "Min Quantity", "Unit"])
                for p in self._products:
                    writer.writerow([
                        p.get("sku", ""), p.get("barcode", ""), p.get("name", ""),
                        p.get("description", ""), p.get("category_name", ""),
                        p.get("price", 0), p.get("cost", 0),
                        p.get("quantity", 0), p.get("min_quantity", 5),
                        p.get("unit", "pcs"),
                    ])
            QMessageBox.information(self, "Export Complete",
                                    f"Exported {len(self._products)} products to:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", str(e))

    def _import_csv(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Products", "", "CSV Files (*.csv)"
        )
        if not path:
            return
        try:
            imported = 0
            with open(path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    data = {
                        "sku": row.get("SKU", "").strip() or None,
                        "barcode": row.get("Barcode", "").strip() or None,
                        "name": row.get("Name", "").strip(),
                        "description": row.get("Description", "").strip(),
                        "price": float(row.get("Price", 0) or 0),
                        "cost": float(row.get("Cost", 0) or 0),
                        "quantity": int(row.get("Quantity", 0) or 0),
                        "min_quantity": int(row.get("Min Quantity", 5) or 5),
                        "unit": row.get("Unit", "pcs").strip() or "pcs",
                    }
                    if not data["name"]:
                        continue
                    self.db.add_product(data)
                    imported += 1
            self._load_products()
            QMessageBox.information(self, "Import Complete",
                                    f"Imported {imported} products successfully.")
        except Exception as e:
            QMessageBox.critical(self, "Import Error", str(e))
