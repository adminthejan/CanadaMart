"""Inventory management module."""
import csv
import io
import os
from typing import Optional, List

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QTableWidget, QTableWidgetItem, QHeaderView,
    QDialog, QFormLayout, QComboBox, QSpinBox, QDoubleSpinBox,
    QMessageBox, QTabWidget, QFileDialog, QDialogButtonBox,
    QTextEdit, QCheckBox, QSizePolicy, QFrame, QInputDialog,
    QColorDialog, QListWidget, QListWidgetItem,
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, QObject, QSize
from PyQt6.QtGui import QColor, QBrush, QIcon, QPixmap, QImage

# Module-level thumbnail cache: (path, size) → QPixmap (decoded once, reused forever)
_THUMB_CACHE: dict = {}

def _get_thumb(img_path: str, size: int = 40) -> "QPixmap | None":
    """Return a cached scaled QPixmap for img_path, or None if unavailable."""
    key = (img_path, size)
    if key in _THUMB_CACHE:
        return _THUMB_CACHE[key]
    if not img_path or not os.path.exists(img_path):
        return None
    img = QImage(img_path)
    if img.isNull():
        return None
    pix = QPixmap.fromImage(img).scaled(
        size, size,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    _THUMB_CACHE[key] = pix
    return pix


# ═══════════════════════════════════════════════════════════════════════════
#  Variant Add/Edit dialog
# ═══════════════════════════════════════════════════════════════════════════
class VariantDialog(QDialog):
    """Add or edit a single product variant."""

    def __init__(self, variant: Optional[dict] = None, config=None, parent=None):
        super().__init__(parent)
        self.variant = variant
        self.config = config
        self.setWindowTitle("Edit Variant" if variant else "Add Variant")
        self.setMinimumWidth(420)
        self._build()
        if variant:
            self._populate(variant)

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        form = QFormLayout()
        form.setSpacing(8)

        self._name = QLineEdit()
        self._name.setPlaceholderText("e.g. Small / Red")
        form.addRow("Variant Name *", self._name)

        self._sku = QLineEdit()
        self._sku.setPlaceholderText("Optional")
        form.addRow("SKU", self._sku)

        self._barcode = QLineEdit()
        self._barcode.setPlaceholderText("Optional")
        form.addRow("Barcode", self._barcode)

        sym = self.config.get("currency_symbol", "$") if self.config else "$"
        self._price = QDoubleSpinBox()
        self._price.setRange(0, 999999)
        self._price.setDecimals(2)
        self._price.setPrefix(f"{sym} ")
        form.addRow("Price *", self._price)

        self._cost = QDoubleSpinBox()
        self._cost.setRange(0, 999999)
        self._cost.setDecimals(2)
        self._cost.setPrefix(f"{sym} ")
        form.addRow("Cost", self._cost)

        self._qty = QSpinBox()
        self._qty.setRange(0, 999999)
        form.addRow("Stock Quantity", self._qty)

        # Option axes
        opt_lbl = QLabel("Option Axes  (e.g. Size=Large, Color=Red)")
        opt_lbl.setStyleSheet("color:#94a3b8; font-size:11px;")
        form.addRow(opt_lbl)

        self._opt1_name = QLineEdit(); self._opt1_name.setPlaceholderText("e.g. Size")
        self._opt1_val  = QLineEdit(); self._opt1_val.setPlaceholderText("e.g. Large")
        row1 = QHBoxLayout(); row1.addWidget(self._opt1_name); row1.addWidget(self._opt1_val)
        form.addRow("Option 1", row1)

        self._opt2_name = QLineEdit(); self._opt2_name.setPlaceholderText("e.g. Color")
        self._opt2_val  = QLineEdit(); self._opt2_val.setPlaceholderText("e.g. Red")
        row2 = QHBoxLayout(); row2.addWidget(self._opt2_name); row2.addWidget(self._opt2_val)
        form.addRow("Option 2", row2)

        self._opt3_name = QLineEdit(); self._opt3_name.setPlaceholderText("e.g. Material")
        self._opt3_val  = QLineEdit(); self._opt3_val.setPlaceholderText("e.g. Cotton")
        row3 = QHBoxLayout(); row3.addWidget(self._opt3_name); row3.addWidget(self._opt3_val)
        form.addRow("Option 3", row3)

        layout.addLayout(form)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _populate(self, v: dict):
        self._name.setText(v.get("name", ""))
        self._sku.setText(v.get("sku", "") or "")
        self._barcode.setText(v.get("barcode", "") or "")
        self._price.setValue(float(v.get("price", 0)))
        self._cost.setValue(float(v.get("cost", 0)))
        self._qty.setValue(int(v.get("quantity", 0)))
        self._opt1_name.setText(v.get("option1_name", "") or "")
        self._opt1_val.setText(v.get("option1_value", "") or "")
        self._opt2_name.setText(v.get("option2_name", "") or "")
        self._opt2_val.setText(v.get("option2_value", "") or "")
        self._opt3_name.setText(v.get("option3_name", "") or "")
        self._opt3_val.setText(v.get("option3_value", "") or "")

    def _save(self):
        name = self._name.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation", "Variant name is required.")
            return
        self.data = {
            "name": name,
            "sku": self._sku.text().strip() or None,
            "barcode": self._barcode.text().strip() or None,
            "price": self._price.value(),
            "cost": self._cost.value(),
            "quantity": self._qty.value(),
            "option1_name": self._opt1_name.text().strip() or None,
            "option1_value": self._opt1_val.text().strip() or None,
            "option2_name": self._opt2_name.text().strip() or None,
            "option2_value": self._opt2_val.text().strip() or None,
            "option3_name": self._opt3_name.text().strip() or None,
            "option3_value": self._opt3_val.text().strip() or None,
        }
        self.accept()


# ═══════════════════════════════════════════════════════════════════════════
#  Variants sub-tab used inside ProductDialog
# ═══════════════════════════════════════════════════════════════════════════
class _VariantsTab(QWidget):
    """Embedded variants manager for use inside the ProductDialog tabs."""

    def __init__(self, db, product_id: Optional[int] = None, config=None, parent=None):
        super().__init__(parent)
        self.db = db
        self.product_id = product_id
        self.config = config
        # pending adds/edits before product is saved
        self._pending: List[dict] = []
        self._build()
        if product_id:
            self._reload()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(8)

        tb = QHBoxLayout()
        add_btn = QPushButton("+ Add Variant")
        add_btn.setObjectName("PrimaryBtn")
        add_btn.clicked.connect(self._add)
        tb.addWidget(add_btn)

        self._edit_btn = QPushButton("✏ Edit")
        self._edit_btn.clicked.connect(self._edit)
        tb.addWidget(self._edit_btn)

        self._del_btn = QPushButton("🗑 Remove")
        self._del_btn.setObjectName("DangerBtn")
        self._del_btn.clicked.connect(self._remove)
        tb.addWidget(self._del_btn)
        tb.addStretch()
        layout.addLayout(tb)

        self._table = QTableWidget(0, 7)
        self._table.setHorizontalHeaderLabels(
            ["Name", "SKU", "Price", "Cost", "Stock", "Option 1", "Option 2"]
        )
        hh = self._table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col in range(1, 7):
            hh.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        self._table.verticalHeader().hide()
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.doubleClicked.connect(self._edit)
        layout.addWidget(self._table)

        self._variants: List[dict] = []

    def _reload(self):
        if self.product_id:
            self._variants = self.db.get_variants(self.product_id)
        self._populate()

    def _populate(self):
        rows = self._variants + self._pending
        self._table.setRowCount(len(rows))
        for r, v in enumerate(rows):
            opt1 = " / ".join(filter(None, [v.get("option1_name"), v.get("option1_value")]))
            opt2 = " / ".join(filter(None, [v.get("option2_name"), v.get("option2_value")]))
            cells = [
                v.get("name", ""),
                v.get("sku", "") or "",
                f"{v.get('price', 0):.2f}",
                f"{v.get('cost', 0):.2f}",
                str(v.get("quantity", 0)),
                opt1,
                opt2,
            ]
            for c, val in enumerate(cells):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
                self._table.setItem(r, c, item)
        self._table.resizeRowsToContents()

    def _all_variants(self):
        return self._variants + self._pending

    def _selected_index(self):
        row = self._table.currentRow()
        if 0 <= row < len(self._all_variants()):
            return row
        return -1

    def _add(self):
        dlg = VariantDialog(config=self.config, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._pending.append(dlg.data)
            self._populate()

    def _edit(self):
        idx = self._selected_index()
        if idx < 0:
            QMessageBox.information(self, "Select", "Please select a variant to edit.")
            return
        all_v = self._all_variants()
        dlg = VariantDialog(variant=all_v[idx], config=self.config, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            if idx < len(self._variants):
                # existing DB variant – update immediately if product_id exists
                if self.product_id:
                    self.db.update_variant(self._variants[idx]["id"], dlg.data)
                    self._variants[idx].update(dlg.data)
                else:
                    self._variants[idx].update(dlg.data)
            else:
                pi = idx - len(self._variants)
                self._pending[pi].update(dlg.data)
            self._populate()

    def _remove(self):
        idx = self._selected_index()
        if idx < 0:
            return
        if idx < len(self._variants):
            reply = QMessageBox.question(
                self, "Remove Variant",
                "Remove this variant? Stock history is preserved.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                if self.product_id:
                    self.db.delete_variant(self._variants[idx]["id"])
                self._variants.pop(idx)
                self._populate()
        else:
            pi = idx - len(self._variants)
            self._pending.pop(pi)
            self._populate()

    def flush_pending(self, product_id: int):
        """Called after product save – persist pending new variants to DB."""
        for v in self._pending:
            v["product_id"] = product_id
            self.db.add_variant(v)
        self._pending.clear()
        self.product_id = product_id
        self._reload()

    def has_variants(self) -> bool:
        return bool(self._variants or self._pending)


# ═══════════════════════════════════════════════════════════════════════════
#  Product Add/Edit dialog
# ═══════════════════════════════════════════════════════════════════════════
class ProductDialog(QDialog):
    """Add or edit a product."""

    def __init__(self, db, product: Optional[dict] = None, config=None, parent=None):
        super().__init__(parent)
        self.db = db
        self.product = product
        self.config = config
        self.setWindowTitle("Edit Product" if product else "Add Product")
        self.setMinimumWidth(540)
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

        sym = self.config.get("currency_symbol", "$") if self.config else "$"
        self._price = QDoubleSpinBox()
        self._price.setRange(0, 999999)
        self._price.setDecimals(2)
        self._price.setPrefix(f"{sym} ")
        pform.addRow("Selling Price *", self._price)

        self._cost = QDoubleSpinBox()
        self._cost.setRange(0, 999999)
        self._cost.setDecimals(2)
        self._cost.setPrefix(f"{sym} ")
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

        self._pos_only = QCheckBox("POS Only  (never sync to Shopify)")
        self._pos_only.setStyleSheet("color:#fcd34d;")
        pform.addRow("", self._pos_only)

        tabs.addTab(pricing, "Pricing & Stock")

        # ── Variants tab ────────────────────────────────────────────────
        self._variants_tab = _VariantsTab(self.db, None, config=self.config, parent=self)
        tabs.addTab(self._variants_tab, "Variants")

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
        self._pos_only.setChecked(bool(p.get("pos_only", 0)))

        # Category
        cat_id = p.get("category_id")
        if cat_id:
            for i in range(self._category.count()):
                if self._category.itemData(i) == cat_id:
                    self._category.setCurrentIndex(i)
                    break

        # Load variants for this product
        self._variants_tab.product_id = p.get("id")
        self._variants_tab._reload()

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
            "pos_only": 1 if self._pos_only.isChecked() else 0,
            "has_variants": 1 if self._variants_tab.has_variants() else 0,
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
                self.db.update_category(
                    cat["id"], dlg.data["name"], dlg.data["color"],
                    cat.get("shopify_collection_id")  # preserve existing Shopify link
                )
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
#  Live Shopify Sync dialog
# ═══════════════════════════════════════════════════════════════════════════
class _ShopifySyncDialog(QDialog):
    """Runs a manual Shopify sync and streams live progress into a log view."""

    def __init__(self, shopify_service, parent=None):
        super().__init__(parent)
        self.shopify_service = shopify_service
        self.setWindowTitle("Shopify Sync")
        self.setMinimumSize(520, 380)
        self._finished = False
        self._build()
        self._start_sync()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        self._status_lbl = QLabel("⏳  Connecting to Shopify…")
        self._status_lbl.setStyleSheet("font-size:14px; font-weight:600; color:#f1f5f9;")
        layout.addWidget(self._status_lbl)

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setStyleSheet(
            "background:#0f172a; color:#94a3b8; font-size:12px; border-radius:6px;"
        )
        layout.addWidget(self._log, 1)

        self._close_btn = QPushButton("Close")
        self._close_btn.setEnabled(False)
        self._close_btn.setMinimumHeight(44)
        self._close_btn.clicked.connect(self.accept)
        layout.addWidget(self._close_btn)

    def _log_line(self, text: str, color: str = "#94a3b8"):
        self._log.append(
            f'<span style="color:{color};">{text}</span>'
        )

    def _start_sync(self):
        worker = self.shopify_service.worker
        if worker is None:
            # Service not started – spin up a one-shot worker
            from services.shopify_sync import ShopifySyncWorker
            worker = ShopifySyncWorker(
                self.shopify_service.config,
                self.shopify_service.db,
            )
            import threading
            t = threading.Thread(
                target=lambda: (worker._init_shopify() and worker._do_sync()),
                daemon=True,
            )
            self._one_shot_worker = worker   # keep reference
            self._connect_worker(worker)
            t.start()
        else:
            self._connect_worker(worker)
            import threading
            threading.Thread(
                target=worker._do_sync, daemon=True
            ).start()

    def _connect_worker(self, worker):
        worker.status_changed.connect(self._on_status)
        worker.sync_error.connect(self._on_error)
        worker.sync_finished.connect(self._on_finished)
        worker.product_synced.connect(
            lambda name: self._log_line(f"  ✓  {name}", "#4ade80")
        )

    def _on_status(self, text: str):
        self._status_lbl.setText(f"⏳  {text}")
        self._log_line(text, "#60a5fa")

    def _on_error(self, text: str):
        self._status_lbl.setText(f"❌  Sync error")
        self._log_line(f"ERROR: {text}", "#f87171")
        self._close_btn.setEnabled(True)
        self._finished = True

    def _on_finished(self, pushed: int, pulled: int):
        self._status_lbl.setText(
            f"✅  Sync complete  –  {pushed} pushed, {pulled} pulled"
        )
        self._status_lbl.setStyleSheet(
            "font-size:14px; font-weight:600; color:#4ade80;"
        )
        self._log_line(
            f"Done — pushed {pushed} product(s), pulled {pulled} product(s).",
            "#4ade80",
        )
        self._close_btn.setEnabled(True)
        self._finished = True

    def closeEvent(self, event):
        # Disconnect to avoid dangling signal connections to a dead dialog
        try:
            worker = getattr(self, "_one_shot_worker",
                             self.shopify_service.worker)
            if worker:
                worker.status_changed.disconnect(self._on_status)
                worker.sync_error.disconnect(self._on_error)
                worker.sync_finished.disconnect(self._on_finished)
        except Exception:
            pass
        super().closeEvent(event)


# ═══════════════════════════════════════════════════════════════════════════
#  Barcode Variant Picker dialog  (separate from POS Add-to-Cart picker)
# ═══════════════════════════════════════════════════════════════════════════
class BarcodeVariantPickerDialog(QDialog):
    """Variant selector used exclusively for the Print Barcode flow."""

    variant_selected = pyqtSignal(dict)

    def __init__(self, product: dict, variants: list, currency_fn, parent=None):
        super().__init__(parent)
        self.product = product
        self.variants = variants
        self.currency_fn = currency_fn
        self.setWindowTitle(f"Print Barcode – {product['name']}")
        self.setMinimumSize(420, 380)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        lbl = QLabel(f"<b>{self.product['name']}</b> – select a variant to print:")
        lbl.setStyleSheet("font-size:14px; color:#f1f5f9;")
        layout.addWidget(lbl)

        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["Variant", "SKU", "Price", "Stock"])
        hh = self._table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col in [1, 2, 3]:
            hh.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        self._table.verticalHeader().hide()
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.doubleClicked.connect(self._select)
        layout.addWidget(self._table)

        self._table.setRowCount(len(self.variants))
        for row, v in enumerate(self.variants):
            qty = int(v.get("quantity", 0))
            cells = [
                v.get("name", ""),
                v.get("sku", "") or "",
                self.currency_fn(v.get("price", 0)),
                "OUT" if qty <= 0 else str(qty),
            ]
            for col, val in enumerate(cells):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
                if col == 3 and qty <= 0:
                    item.setForeground(QBrush(QColor("#f87171")))
                elif col == 3:
                    item.setForeground(QBrush(QColor("#4ade80")))
                self._table.setItem(row, col, item)
            self._table.setRowHeight(row, 54)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        btns.rejected.connect(self.reject)
        print_btn = btns.addButton("🖨️ Print", QDialogButtonBox.ButtonRole.AcceptRole)
        print_btn.setMinimumHeight(48)
        print_btn.setObjectName("SuccessBtn")
        print_btn.clicked.connect(self._select)
        layout.addWidget(btns)

    def _select(self):
        row = self._table.currentRow()
        if 0 <= row < len(self.variants):
            v = self.variants[row]
            self.variant_selected.emit(v)
            self.accept()
        else:
            QMessageBox.information(self, "Select Variant", "Please select a variant to print.")


# ═══════════════════════════════════════════════════════════════════════════
#  Barcode Preview dialog
# ═══════════════════════════════════════════════════════════════════════════
class BarcodePreviewDialog(QDialog):
    def __init__(self, pil_image, code_str: str, name: str, price_str: str, config, settings: dict, parent=None):
        super().__init__(parent)
        self.pil_image = pil_image
        self.code_str = code_str
        self.name = name
        self.price_str = price_str
        self.config = config
        self.settings = settings
        self.setWindowTitle(f"Barcode Preview - {name}")
        self.setMinimumWidth(400)
        self._build()

    def _build(self):
        from PIL.ImageQt import ImageQt
        layout = QVBoxLayout(self)
        
        lbl = QLabel()
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        qim = ImageQt(self.pil_image)
        pix = QPixmap.fromImage(qim)
        
        width_mm = float(self.settings.get("barcode_label_width_mm", 50.0))
        height_mm = float(self.settings.get("barcode_label_height_mm", 25.0))
        aspect = width_mm / height_mm if height_mm > 0 else 2.0
        
        preview_width = 380
        preview_height = int(preview_width / aspect)
        
        if pix.width() > preview_width or pix.height() > preview_height:
            pix = pix.scaled(preview_width, preview_height, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            
        lbl.setPixmap(pix)
        
        layout.addWidget(lbl)
        
        info = QLabel(f"<b>Code:</b> {self.code_str}<br><b>Name:</b> {self.name}<br><b>Price:</b> {self.price_str}")
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(info)
        
        form = QFormLayout()
        self.copies = QSpinBox()
        self.copies.setRange(1, 1000)
        self.copies.setValue(int(self.settings.get("barcode_default_copies", 1)))
        form.addRow("Copies to print:", self.copies)
        layout.addLayout(form)
        
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.button(QDialogButtonBox.StandardButton.Ok).setText("🖨️ Print")
        btns.accepted.connect(self._print)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)
        
    def _print(self):
        from services.receipt_printer import ReceiptPrinter
        printer = ReceiptPrinter(self.config)
        success = printer.print_barcode_label(self.pil_image, self.name, self.price_str, self.copies.value(), self.settings)
        if success:
            QMessageBox.information(self, "Success", "Barcode sent to printer successfully.")
            self.accept()
        else:
            QMessageBox.warning(self, "Print Error", "Failed to print barcode. Check printer settings.")



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
            ("🏷 Print Barcode", self._print_barcode, ""),
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
        self._table = QTableWidget(0, 12)
        self._table.setHorizontalHeaderLabels([
            "Img", "SKU", "Name", "Category", "Price", "Cost", "Stock",
            "Min Stock", "Unit", "Variants", "Shopify", "Actions"
        ])
        hh = self._table.horizontalHeader()
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)  # Name
        for col in [0, 1, 3, 4, 5, 6, 7, 8, 9, 10]:
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
            qty = int(p.get("total_stock") if p.get("total_stock") is not None else p.get("quantity", 0))
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
        self._table.setIconSize(QSize(40, 40))
        self._displayed = products

        for row, p in enumerate(products):
            qty = int(p.get("total_stock") if p.get("total_stock") is not None else p.get("quantity", 0))
            variant_count = int(p.get("variant_count") or 0)

            # ── Image thumbnail (col 0) ──────────────────────────────────
            img_item = QTableWidgetItem()
            pix = _get_thumb(p.get("image_path", "") or "", 40)
            if pix:
                img_item.setIcon(QIcon(pix))
            img_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(row, 0, img_item)

            cells = [
                p.get("sku", "") or "",
                p.get("name", ""),
                p.get("category_name", "") or "",
                f"{sym}{p.get('price', 0):.2f}",
                f"{sym}{p.get('cost', 0):.2f}",
                str(qty),
                str(p.get("min_quantity", 5)),
                p.get("unit", "pcs") or "pcs",
                str(variant_count) if variant_count else "—",
                "✓" if p.get("shopify_id") else "—",
                "",
            ]
            for col, val in enumerate(cells):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
                tcol = col + 1  # offset by image column

                if col == 5:  # Stock column (now col 6)
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    if qty <= 0:
                        item.setForeground(QBrush(QColor("#f87171")))
                        item.setText("OUT")
                    elif qty <= threshold:
                        item.setForeground(QBrush(QColor("#fcd34d")))
                    else:
                        item.setForeground(QBrush(QColor("#4ade80")))

                if col == 8:  # Variants column (now col 9)
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    if variant_count > 0:
                        item.setForeground(QBrush(QColor("#60a5fa")))

                if col == 9:  # Shopify column (now col 10)
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    if p.get("pos_only"):
                        item.setText("🔒 POS")
                        item.setForeground(QBrush(QColor("#fcd34d")))
                    elif p.get("shopify_id"):
                        item.setForeground(QBrush(QColor("#4ade80")))

                self._table.setItem(row, tcol, item)

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
        dlg = ProductDialog(self.db, config=self.config, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            product_id = self.db.add_product(dlg.data)
            dlg._variants_tab.flush_pending(product_id)
            self._load_products()

    def _edit_product(self):
        product = self._get_selected_product()
        if not product:
            QMessageBox.information(self, "Select Product", "Please select a product to edit.")
            return
        dlg = ProductDialog(self.db, product, config=self.config, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.data
            data["shopify_synced"] = 0  # mark for re-sync
            self.db.update_product(product["id"], data)
            dlg._variants_tab.flush_pending(product["id"])
            self._load_products()

    def _delete_product(self):
        product = self._get_selected_product()
        if not product:
            return

        if product.get("shopify_id"):
            QMessageBox.warning(
                self, "Cannot Delete Shopify Product",
                f"'{product['name']}' is linked to Shopify.\n\n"
                f"To remove it, delete the product from your Shopify store first.\n"
                f"It will be removed from POS on the next sync."
            )
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
                    self.shopify_service.sync_stock_after_sale([
                        {"product_id": updated["id"]}
                    ])
            self._load_products()

    def _view_log(self):
        product = self._get_selected_product()
        dlg = InventoryLogDialog(self.db, product, parent=self)
        dlg.exec()

    def _print_barcode(self):
        product = self._get_selected_product()
        if not product:
            QMessageBox.information(self, "Select Product", "Please select a product.")
            return

        from services.barcode_utils import encode_product_id, generate_barcode_image

        if product.get("has_variants"):
            variants = self.db.get_variants(product["id"])
            if variants:
                dlg = BarcodeVariantPickerDialog(product, variants, self.config.format_currency, self)
                dlg.variant_selected.connect(
                    lambda v: self._show_barcode_preview(product, v)
                )
                dlg.exec()
            else:
                QMessageBox.warning(self, "No Variants", "This product has variants but none exist.")
        else:
            self._show_barcode_preview(product, None)

    def _show_barcode_preview(self, product, variant):
        from services.barcode_utils import encode_product_id, encode_variant_id, generate_barcode_image
        
        settings = self.db.get_all_settings()
        
        if variant:
            code_str = encode_variant_id(variant["id"])
            name = f"{product['name']} - {variant['name']}" if str(settings.get("barcode_show_variant", "1")) == "1" else product['name']
            price = variant.get('price') or product.get('price', 0)
        else:
            code_str = encode_product_id(product["id"])
            name = product['name']
            price = product.get('price', 0)
            
        sym = self.config.get("currency_symbol", "$")
        price_str = f"{sym}{price:.2f}"
            
        img = generate_barcode_image(code_str, name, settings, price_str)
        
        dlg = BarcodePreviewDialog(img, code_str, name, price_str, self.config, settings, self)
        dlg.exec()

    def _trigger_shopify_sync(self):
        if not self.shopify_service:
            return
        dlg = _ShopifySyncDialog(self.shopify_service, self)
        dlg.exec()
        # Reload products after dialog closes (sync may have pulled new items)
        self._load_products()

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
