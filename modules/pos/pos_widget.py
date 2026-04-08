"""Full-featured POS (Point of Sale) module – Touch-optimised, real-time stock."""
import os
import re
from datetime import datetime
from typing import Optional, List, Dict

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QGridLayout,
    QLabel, QPushButton, QLineEdit, QScrollArea,
    QFrame, QSplitter, QDialog, QFormLayout,
    QComboBox, QSpinBox, QDoubleSpinBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QMessageBox,
    QButtonGroup, QDialogButtonBox, QSizePolicy, QTextEdit,
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QSize
from PyQt6.QtGui import QFont, QColor, QPalette, QKeySequence, QShortcut, QBrush, QPixmap, QImage

# Module-level thumbnail cache: path → QPixmap (decoded once, reused forever)
_THUMB_CACHE: dict = {}

def _get_thumb(img_path: str, size: int = 56) -> "QPixmap | None":
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
#  Data model
# ═══════════════════════════════════════════════════════════════════════════
class CartItem:
    def __init__(self, product: dict, quantity: int = 1,
                 variant: Optional[dict] = None):
        self.product_id = product["id"]
        self.product_name = product["name"]
        self.variant_id: Optional[int] = variant["id"] if variant else None
        self.variant_name: Optional[str] = variant["name"] if variant else None
        self.sku = (variant or product).get("sku", "") or ""
        self.unit_price = float((variant or product)["price"])
        self.quantity = quantity
        self.discount_percent = 0.0
        self.stock_available = int(
            (variant or product).get("quantity", 9999)
        )

    @property
    def display_name(self) -> str:
        if self.variant_name:
            return f"{self.product_name}  [{self.variant_name}]"
        return self.product_name

    @property
    def line_total(self) -> float:
        return self.unit_price * self.quantity * (1 - self.discount_percent / 100)

    @property
    def discount_amount(self) -> float:
        return self.unit_price * self.quantity * self.discount_percent / 100


# ═══════════════════════════════════════════════════════════════════════════
#  Product card – finger-tap sized
# ═══════════════════════════════════════════════════════════════════════════
class ProductCard(QPushButton):
    """Clickable product tile sized for touch screens."""

    def __init__(self, product: dict, currency_fn, parent=None):
        super().__init__(parent)
        self.product = product
        self.setObjectName("ProductCard")
        self.setFixedSize(180, 138)
        self.setFlat(True)
        self._build(currency_fn)

    def _build(self, currency_fn):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        # ── Thumbnail ──────────────────────────────────────────────────
        img_path = self.product.get("image_path", "") or ""
        pix = _get_thumb(img_path, 56)
        if pix:
            thumb_lbl = QLabel()
            thumb_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            thumb_lbl.setPixmap(pix)
            thumb_lbl.setFixedHeight(60)
            layout.addWidget(thumb_lbl)

        name = QLabel(self.product["name"])
        name.setObjectName("ProductCardName")
        name.setWordWrap(True)
        name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name.setMaximumHeight(46)
        layout.addWidget(name)

        if self.product.get("sku"):
            sku_lbl = QLabel(self.product["sku"])
            sku_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            sku_lbl.setStyleSheet("color:#64748b; font-size:10px;")
            layout.addWidget(sku_lbl)

        price_lbl = QLabel(currency_fn(self.product["price"]))
        price_lbl.setObjectName("ProductCardPrice")
        price_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(price_lbl)

        qty = int(self.product.get("total_stock") if self.product.get("total_stock") is not None else self.product.get("quantity", 0))
        stock_lbl = QLabel(f"Stock: {qty}")
        if qty <= 0:
            stock_lbl.setObjectName("ProductCardStockLow")
            stock_lbl.setText("OUT OF STOCK")
        elif qty <= 5:
            stock_lbl.setObjectName("ProductCardStockLow")
        else:
            stock_lbl.setObjectName("ProductCardStock")
        stock_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(stock_lbl)

        if self.product.get("has_variants"):
            var_lbl = QLabel("▾ variants")
            var_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            var_lbl.setStyleSheet("color:#60a5fa; font-size:10px; font-weight:600;")
            layout.addWidget(var_lbl)

        if qty <= 0:
            self.setEnabled(False)


# ═══════════════════════════════════════════════════════════════════════════
#  Touch NumPad – embedded in right panel
# ═══════════════════════════════════════════════════════════════════════════
class _NumPad(QWidget):
    """
    Three-mode numpad:
      QTY    → sets quantity of the selected cart row
      DISC%  → sets item-level discount % of the selected cart row
      ORDER% → sets the order-level discount percentage
    """

    value_applied = pyqtSignal(str, float)   # (mode, value)

    _MODES = [("QTY", "Qty"), ("DISC%", "Item %"), ("ORDER%", "Order %")]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._input = ""
        self._mode = "QTY"
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setSpacing(4)
        root.setContentsMargins(0, 2, 0, 0)

        # Mode row
        mode_row = QHBoxLayout()
        mode_row.setSpacing(4)
        self._mode_btns: Dict[str, QPushButton] = {}
        for key, label in self._MODES:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setMinimumHeight(38)
            btn.setStyleSheet("font-size:12px; font-weight:600;")
            btn.clicked.connect(lambda _, k=key: self._set_mode(k))
            self._mode_btns[key] = btn
            mode_row.addWidget(btn)
        self._mode_btns["QTY"].setChecked(True)
        root.addLayout(mode_row)

        # Display
        self._display = QLabel("0")
        self._display.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self._display.setStyleSheet(
            "background:#0f172a; color:#f1f5f9; font-size:24px; font-weight:700;"
            "border-radius:6px; padding:4px 12px; min-height:36px;"
        )
        root.addWidget(self._display)

        # Numpad grid  7 8 9 ⌫ / 4 5 6 CLR / 1 2 3 . / 00 0 ✓
        grid = QGridLayout()
        grid.setSpacing(4)
        pad_def = [
            ("7", 0, 0, 1, 1), ("8",  0, 1, 1, 1), ("9",   0, 2, 1, 1), ("⌫",  0, 3, 1, 1),
            ("4", 1, 0, 1, 1), ("5",  1, 1, 1, 1), ("6",   1, 2, 1, 1), ("CLR",1, 3, 1, 1),
            ("1", 2, 0, 1, 1), ("2",  2, 1, 1, 1), ("3",   2, 2, 1, 1), (".",  2, 3, 1, 1),
            ("00",3, 0, 1, 1), ("0",  3, 1, 1, 1), ("✓",   3, 2, 1, 2),
        ]
        for lbl, r, c, rs, cs in pad_def:
            btn = QPushButton(lbl)
            btn.setMinimumSize(48, 44)
            btn.setStyleSheet("font-size:16px; font-weight:600;")
            if lbl == "✓":
                btn.setObjectName("SuccessBtn")
                btn.setMinimumHeight(44)
                btn.clicked.connect(self._apply)
            elif lbl == "⌫":
                btn.clicked.connect(self._backspace)
            elif lbl == "CLR":
                btn.setObjectName("DangerBtn")
                btn.clicked.connect(self._clear_input)
            else:
                d = lbl
                btn.clicked.connect(lambda _, d=d: self._digit(d))
            grid.addWidget(btn, r, c, rs, cs)
        root.addLayout(grid)

    def _set_mode(self, key: str):
        self._mode = key
        for k, btn in self._mode_btns.items():
            btn.setChecked(k == key)
        self._clear_input()

    def _digit(self, d: str):
        if d == "." and "." in self._input:
            return
        if d == "00" and not self._input:
            return
        self._input += d
        self._display.setText(self._input or "0")

    def _backspace(self):
        self._input = self._input[:-1]
        self._display.setText(self._input or "0")

    def _clear_input(self):
        self._input = ""
        self._display.setText("0")

    def _apply(self):
        try:
            val = float(self._input or "0")
        except ValueError:
            val = 0.0
        self.value_applied.emit(self._mode, val)
        self._clear_input()

    def prefill(self, val: float):
        """Pre-load current item value when a cart row is selected."""
        self._input = str(int(val)) if val == int(val) else f"{val:.2f}".rstrip("0")
        self._display.setText(self._input or "0")

    def reset(self):
        self._clear_input()


# ═══════════════════════════════════════════════════════════════════════════
#  Variant picker dialog
# ═══════════════════════════════════════════════════════════════════════════
class VariantPickerDialog(QDialog):
    """Touch-friendly dialog to pick a product variant before adding to cart."""

    variant_selected = pyqtSignal(dict)   # emits the chosen variant dict

    def __init__(self, product: dict, variants: list, currency_fn, parent=None):
        super().__init__(parent)
        self.product = product
        self.variants = variants
        self.currency_fn = currency_fn
        self.setWindowTitle(f"Select Variant – {product['name']}")
        self.setMinimumSize(420, 380)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        lbl = QLabel(f"<b>{self.product['name']}</b> – choose a variant:")
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
        sel_btn = btns.addButton("Add to Cart", QDialogButtonBox.ButtonRole.AcceptRole)
        sel_btn.setMinimumHeight(48)
        sel_btn.setObjectName("SuccessBtn")
        sel_btn.clicked.connect(self._select)
        layout.addWidget(btns)

    def _select(self):
        row = self._table.currentRow()
        if 0 <= row < len(self.variants):
            v = self.variants[row]
            if int(v.get("quantity", 0)) <= 0:
                QMessageBox.warning(self, "Out of Stock",
                                    f"'{v['name']}' is out of stock.")
                return
            self.variant_selected.emit(v)
            self.accept()


# ═══════════════════════════════════════════════════════════════════════════
#  Customer quick-find dialog
# ═══════════════════════════════════════════════════════════════════════════
class CustomerSearchDialog(QDialog):
    customer_selected = pyqtSignal(dict)

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("Select Customer")
        self.resize(520, 460)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)

        row = QHBoxLayout()
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search by name or mobile…")
        self._search.setMinimumHeight(48)
        self._search.setStyleSheet("font-size:15px;")
        self._search.textChanged.connect(self._filter)
        row.addWidget(self._search)

        add_btn = QPushButton("+ New")
        add_btn.setObjectName("PrimaryBtn")
        add_btn.setMinimumHeight(48)
        add_btn.clicked.connect(self._add_new)
        row.addWidget(add_btn)
        layout.addLayout(row)

        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(["Name", "Mobile", "Points"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().hide()
        self._table.doubleClicked.connect(self._select)
        layout.addWidget(self._table)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        btns.rejected.connect(self.reject)
        sel_btn = btns.addButton("Select", QDialogButtonBox.ButtonRole.AcceptRole)
        sel_btn.setMinimumHeight(48)
        sel_btn.clicked.connect(self._select)
        layout.addWidget(btns)

        self._customers = []
        self._filter("")

    def _filter(self, text: str):
        if text.strip():
            self._customers = self.db.search_customers(text)
        else:
            self._customers = self.db.get_customers()
        self._populate()

    def _populate(self):
        self._table.setRowCount(len(self._customers))
        for row, c in enumerate(self._customers):
            self._table.setItem(row, 0, QTableWidgetItem(c["name"]))
            self._table.setItem(row, 1, QTableWidgetItem(c.get("mobile") or ""))
            self._table.setItem(row, 2, QTableWidgetItem(str(c.get("points", 0))))
            self._table.setRowHeight(row, 50)

    def _select(self):
        row = self._table.currentRow()
        if 0 <= row < len(self._customers):
            self.customer_selected.emit(self._customers[row])
            self.accept()

    def _add_new(self):
        from modules.customers.customers_widget import CustomerDialog
        dlg = CustomerDialog(self.db, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._filter(self._search.text())


# ═══════════════════════════════════════════════════════════════════════════
#  Payment dialog – touch-optimised with inline numpad
# ═══════════════════════════════════════════════════════════════════════════
class PaymentDialog(QDialog):
    """Handles payment with a touch numpad for cash entry."""

    def __init__(self, total: float, config, parent=None, db=None):
        super().__init__(parent)
        self.total = total
        self.config = config
        self.db = db
        self.payment_method = "cash"
        self.amount_paid = total
        self.change = 0.0
        self._tendered = total
        self._pad_input = ""
        self.setWindowTitle("Process Payment")
        self.setMinimumWidth(700)
        self._build()

    def _build(self):
        root = QHBoxLayout(self)
        root.setSpacing(16)

        sym = self.config.get("currency_symbol", "$")

        left = QVBoxLayout()
        left.setSpacing(10)

        due_card = QFrame()
        due_card.setObjectName("Card")
        dc = QVBoxLayout(due_card)
        due_lbl = QLabel("AMOUNT DUE")
        due_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        due_lbl.setStyleSheet("color:#94a3b8; font-size:11px; font-weight:600; letter-spacing:1px;")
        due_amt = QLabel(f"{sym}{self.total:.2f}")
        due_amt.setAlignment(Qt.AlignmentFlag.AlignCenter)
        due_amt.setStyleSheet("color:#f1f5f9; font-size:40px; font-weight:700;")
        dc.addWidget(due_lbl)
        dc.addWidget(due_amt)
        left.addWidget(due_card)

        method_row = QHBoxLayout()
        method_row.setSpacing(6)
        self._method_group = QButtonGroup(self)
        for method, label in [("cash", "💵 Cash"), ("card", "💳 Card"), ("split", "⚡ Split")]:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setMinimumHeight(52)
            btn.setStyleSheet("font-size:14px;")
            if method == "cash":
                btn.setChecked(True)
                btn.setObjectName("PrimaryBtn")
            btn.clicked.connect(lambda _, m=method, b=btn: self._set_method(m, b))
            self._method_group.addButton(btn)
            method_row.addWidget(btn)
        left.addLayout(method_row)

        self._tendered_card = QFrame()
        self._tendered_card.setObjectName("Card")
        tc = QVBoxLayout(self._tendered_card)
        tc_lbl = QLabel("AMOUNT TENDERED")
        tc_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tc_lbl.setStyleSheet("color:#94a3b8; font-size:10px; font-weight:600; letter-spacing:1px;")
        self._tendered_lbl = QLabel(f"{sym}{self.total:.2f}")
        self._tendered_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._tendered_lbl.setStyleSheet("color:#facc15; font-size:30px; font-weight:700;")
        tc.addWidget(tc_lbl)
        tc.addWidget(self._tendered_lbl)
        left.addWidget(self._tendered_card)

        change_card = QFrame()
        change_card.setObjectName("Card")
        cc = QVBoxLayout(change_card)
        cc_lbl = QLabel("CHANGE")
        cc_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cc_lbl.setStyleSheet("color:#94a3b8; font-size:10px; font-weight:600; letter-spacing:1px;")
        self._change_lbl = QLabel(f"{sym}0.00")
        self._change_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._change_lbl.setStyleSheet("color:#4ade80; font-size:30px; font-weight:700;")
        cc.addWidget(cc_lbl)
        cc.addWidget(self._change_lbl)
        left.addWidget(change_card)

        quick = QHBoxLayout()
        quick.setSpacing(6)
        for v in [5, 10, 20, 50, 100]:
            b = QPushButton(f"{sym}{v}")
            b.setMinimumHeight(50)
            b.setStyleSheet("font-size:15px; font-weight:600;")
            b.clicked.connect(lambda _, val=float(v): self._set_tendered(val))
            quick.addWidget(b)
        left.addLayout(quick)

        self._print_receipt = QPushButton("🖨️  Print Receipt")
        self._print_receipt.setCheckable(True)
        self._print_receipt.setChecked(True)
        self._print_receipt.setMinimumHeight(48)
        
        # ✓ Show/hide based on auto-print setting
        auto_print = True  # Default to True if no db
        if self.db:
            auto_print = self.db.get_setting("auto_print_receipt", "1") == "1"
        
        # If auto-print is OFF, show the checkbox so user can choose
        if auto_print:
            self._print_receipt.hide()  # Auto-printing is on, hide the button
        else:
            self._print_receipt.show()  # Auto-printing is off, let user decide
            
        left.addWidget(self._print_receipt)

        ok_btn = QPushButton("✓  Complete Sale")
        ok_btn.setObjectName("SuccessBtn")
        ok_btn.setMinimumHeight(60)
        ok_btn.setStyleSheet("font-size:17px; font-weight:700; border-radius:10px; background:#16a34a; color:white;")
        ok_btn.clicked.connect(self._complete)
        left.addWidget(ok_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setMinimumHeight(48)
        cancel_btn.clicked.connect(self.reject)
        left.addWidget(cancel_btn)

        root.addLayout(left, 3)

        right = QVBoxLayout()
        right.setSpacing(6)

        pad_title = QLabel("ENTER CASH AMOUNT")
        pad_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pad_title.setStyleSheet("color:#94a3b8; font-size:10px; font-weight:600; letter-spacing:1px;")
        right.addWidget(pad_title)

        self._pad_display = QLabel("0")
        self._pad_display.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._pad_display.setStyleSheet(
            "background:#0f172a; color:#f1f5f9; font-size:28px; font-weight:700;"
            "border-radius:6px; padding:4px 14px; min-height:52px;"
        )
        right.addWidget(self._pad_display)

        grid = QGridLayout()
        grid.setSpacing(6)
        for lbl, r, c in [
            ("7", 0, 0), ("8", 0, 1), ("9", 0, 2),
            ("4", 1, 0), ("5", 1, 1), ("6", 1, 2),
            ("1", 2, 0), ("2", 2, 1), ("3", 2, 2),
            (".", 3, 0), ("0", 3, 1), ("⌫", 3, 2),
            ("CLR", 4, 0), ("00", 4, 1), ("✓", 4, 2),
        ]:
            btn = QPushButton(lbl)
            btn.setMinimumSize(64, 64)
            btn.setStyleSheet("font-size:18px; font-weight:600;")
            if lbl == "✓":
                btn.setObjectName("SuccessBtn")
                btn.clicked.connect(self._pad_apply)
            elif lbl == "⌫":
                btn.clicked.connect(self._pad_back)
            elif lbl == "CLR":
                btn.setObjectName("DangerBtn")
                btn.clicked.connect(self._pad_clear)
            else:
                d = lbl
                btn.clicked.connect(lambda _, d=d: self._pad_digit(d))
            grid.addWidget(btn, r, c)
        right.addLayout(grid)
        right.addStretch()

        root.addLayout(right, 2)
        self._recalc()

    def _pad_digit(self, d: str):
        if d == "." and "." in self._pad_input:
            return
        if d == "00" and not self._pad_input:
            return
        self._pad_input += d
        self._pad_display.setText(self._pad_input or "0")

    def _pad_back(self):
        self._pad_input = self._pad_input[:-1]
        self._pad_display.setText(self._pad_input or "0")

    def _pad_clear(self):
        self._pad_input = ""
        self._pad_display.setText("0")

    def _pad_apply(self):
        try:
            val = float(self._pad_input or "0")
        except ValueError:
            return
        self._set_tendered(val)
        self._pad_clear()

    def _set_tendered(self, val: float):
        if self.payment_method == "card":
            return
        sym = self.config.get("currency_symbol", "$")
        self._tendered = val
        self._tendered_lbl.setText(f"{sym}{val:.2f}")
        self._recalc()

    def _set_method(self, method: str, btn):
        self.payment_method = method
        sym = self.config.get("currency_symbol", "$")
        if method == "card":
            self._tendered = self.total
            self._tendered_lbl.setText(f"{sym}{self.total:.2f}")
            self._tendered_card.setEnabled(False)
        else:
            self._tendered_card.setEnabled(True)
        self._recalc()

    def _recalc(self):
        sym = self.config.get("currency_symbol", "$")
        change = self._tendered - self.total
        if change < 0:
            self._change_lbl.setTextFormat(Qt.TextFormat.RichText)
            self._change_lbl.setText(f"<span style='color:#f87171'>{sym}{abs(change):.2f} SHORT</span>")
        else:
            self._change_lbl.setTextFormat(Qt.TextFormat.PlainText)
            self._change_lbl.setText(f"{sym}{change:.2f}")

    def _complete(self):
        if self.payment_method != "card" and self._tendered < self.total - 0.001:
            QMessageBox.warning(self, "Insufficient Payment", "Amount tendered is less than total due.")
            return
        self.amount_paid = self._tendered
        self.change = max(0.0, self._tendered - self.total)
        self.should_print = self._print_receipt.isChecked()
        self.accept()


# ═══════════════════════════════════════════════════════════════════════════
#  Main POS Widget
# ═══════════════════════════════════════════════════════════════════════════
class POSWidget(QWidget):
    """Main POS sales interface – touch-optimised with real-time stock refresh."""

    sale_completed = pyqtSignal(dict)

    def __init__(self, config, db, shopify_service=None):
        super().__init__()
        self.config = config
        self.db = db
        self.shopify_service = shopify_service
        self.cart: List[CartItem] = []
        self.selected_customer: Optional[dict] = None
        self._all_products: List[dict] = []
        self._categories: List[dict] = []
        self._active_category_id: Optional[int] = None
        self._order_disc_value: float = 0.0

        self._build_ui()
        self._recalculate()          # apply correct currency symbol before any cart action
        self._load_data()
        self._setup_shortcuts()

        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._silent_refresh)
        self._refresh_timer.start(30_000)

    def showEvent(self, event):
        super().showEvent(event)
        self._silent_refresh()

    def _silent_refresh(self):
        """Reload product list & stock counts without touching the cart."""
        self._all_products = self.db.get_products(active_only=True)
        cats = self.db.get_categories()
        if [c["id"] for c in cats] != [c["id"] for c in self._categories]:
            self._categories = cats
            self._build_category_tabs()
        self._filter_products(self._search.text())

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)
        root.addWidget(splitter)

        # LEFT – product browser
        left = QWidget()
        left.setObjectName("Card")
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(12, 12, 12, 12)
        left_layout.setSpacing(8)

        search_row = QHBoxLayout()
        self._search = QLineEdit()
        self._search.setPlaceholderText("🔍  Search product or scan barcode…")
        self._search.setMinimumHeight(50)
        self._search.setStyleSheet("font-size:15px;")
        self._search.textChanged.connect(self._filter_products)
        self._search.returnPressed.connect(self._on_barcode_scan)
        search_row.addWidget(self._search)

        refresh_btn = QPushButton("⟳")
        refresh_btn.setFixedSize(50, 50)
        refresh_btn.setStyleSheet("font-size:22px;")
        refresh_btn.setToolTip("Refresh products")
        refresh_btn.clicked.connect(self._load_data)
        search_row.addWidget(refresh_btn)
        left_layout.addLayout(search_row)

        self._cat_scroll = QScrollArea()
        self._cat_scroll.setFixedHeight(52)
        self._cat_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._cat_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._cat_scroll.setWidgetResizable(True)
        self._cat_container = QWidget()
        self._cat_layout = QHBoxLayout(self._cat_container)
        self._cat_layout.setContentsMargins(0, 0, 0, 0)
        self._cat_layout.setSpacing(6)
        self._cat_layout.addStretch()
        self._cat_scroll.setWidget(self._cat_container)
        left_layout.addWidget(self._cat_scroll)

        self._product_scroll = QScrollArea()
        self._product_scroll.setWidgetResizable(True)
        self._product_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._grid_container = QWidget()
        self._grid_layout = QGridLayout(self._grid_container)
        self._grid_layout.setSpacing(10)
        self._grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._product_scroll.setWidget(self._grid_container)
        left_layout.addWidget(self._product_scroll, 1)

        splitter.addWidget(left)

        # RIGHT – cart + numpad
        right = QWidget()
        right.setObjectName("CartPanel")
        right.setMinimumWidth(400)
        right.setMaximumWidth(500)
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(12, 12, 12, 12)
        right_layout.setSpacing(6)

        cust_row = QHBoxLayout()
        self._cust_label = QLabel("👤  Walk-in Customer")
        self._cust_label.setStyleSheet("color:#94a3b8; font-size:13px;")
        cust_row.addWidget(self._cust_label, 1)
        cust_btn = QPushButton("Select")
        cust_btn.setObjectName("SecondaryBtn")
        cust_btn.setMinimumHeight(40)
        cust_btn.clicked.connect(self._select_customer)
        cust_row.addWidget(cust_btn)
        clr_cust_btn = QPushButton("✕")
        clr_cust_btn.setFixedSize(40, 40)
        clr_cust_btn.clicked.connect(self._clear_customer)
        cust_row.addWidget(clr_cust_btn)
        right_layout.addLayout(cust_row)

        cart_hdr = QLabel("🛒  ORDER")
        cart_hdr.setStyleSheet("color:#f1f5f9; font-size:13px; font-weight:700; letter-spacing:1px;")
        right_layout.addWidget(cart_hdr)

        self._cart_table = QTableWidget(0, 4)
        self._cart_table.setHorizontalHeaderLabels(["Item", "Qty", "Disc%", "Total"])
        hh = self._cart_table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self._cart_table.setColumnWidth(1, 56)
        self._cart_table.setColumnWidth(2, 62)
        self._cart_table.setColumnWidth(3, 84)
        self._cart_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._cart_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._cart_table.verticalHeader().hide()
        self._cart_table.setAlternatingRowColors(True)
        self._cart_table.setMinimumHeight(160)
        self._cart_table.cellClicked.connect(self._on_cart_row_clicked)
        right_layout.addWidget(self._cart_table, 1)

        cart_actions = QHBoxLayout()
        cart_actions.setSpacing(6)
        for lbl, slot, obj in [
            ("🗑", self._remove_cart_item, "DangerBtn"),
            ("−", lambda: self._change_qty(-1), ""),
            ("+", lambda: self._change_qty(1), ""),
        ]:
            btn = QPushButton(lbl)
            btn.setMinimumSize(58, 52)
            btn.setStyleSheet("font-size:20px; font-weight:700;")
            if obj:
                btn.setObjectName(obj)
            btn.clicked.connect(slot)
            cart_actions.addWidget(btn)
        cart_actions.addStretch()
        right_layout.addLayout(cart_actions)

        sep0 = QFrame()
        sep0.setFrameShape(QFrame.Shape.HLine)
        sep0.setStyleSheet("background:#334155; max-height:1px;")
        right_layout.addWidget(sep0)

        self._numpad = _NumPad()
        self._numpad.value_applied.connect(self._apply_numpad)
        right_layout.addWidget(self._numpad)

        sep1 = QFrame()
        sep1.setFrameShape(QFrame.Shape.HLine)
        sep1.setStyleSheet("background:#334155; max-height:1px;")
        right_layout.addWidget(sep1)

        totals_layout = QFormLayout()
        totals_layout.setSpacing(4)
        self._subtotal_lbl = QLabel("$0.00")
        self._disc_lbl = QLabel("$0.00")
        self._tax_lbl = QLabel("$0.00")
        self._total_lbl = QLabel("$0.00")
        self._total_lbl.setStyleSheet("color:#4ade80; font-size:22px; font-weight:700;")
        for lbl in [self._subtotal_lbl, self._disc_lbl, self._tax_lbl]:
            lbl.setStyleSheet("color:#94a3b8; font-size:13px;")
        totals_layout.addRow("Subtotal:", self._subtotal_lbl)
        totals_layout.addRow("Discount:", self._disc_lbl)
        tname = self.config.get("tax_name", "Tax")
        totals_layout.addRow(f"{tname}:", self._tax_lbl)
        totals_layout.addRow("TOTAL:", self._total_lbl)
        right_layout.addLayout(totals_layout)

        clear_btn = QPushButton("🗑  Clear Order")
        clear_btn.setObjectName("DangerBtn")
        clear_btn.setMinimumHeight(48)
        clear_btn.clicked.connect(self._clear_cart)

        pay_btn = QPushButton("💰  CHARGE CUSTOMER")
        pay_btn.setObjectName("SuccessBtn")
        pay_btn.setMinimumHeight(64)
        pay_btn.setStyleSheet("font-size:17px; font-weight:700; border-radius:10px; background:#16a34a; color:white;")
        pay_btn.clicked.connect(self._process_payment)

        right_layout.addWidget(clear_btn)
        right_layout.addWidget(pay_btn)

        splitter.addWidget(right)
        splitter.setSizes([820, 420])

    def _on_cart_row_clicked(self, row: int, _col: int):
        if 0 <= row < len(self.cart):
            item = self.cart[row]
            mode = self._numpad._mode
            if mode == "QTY":
                self._numpad.prefill(float(item.quantity))
            elif mode == "DISC%":
                self._numpad.prefill(item.discount_percent)
            elif mode == "ORDER%":
                self._numpad.prefill(self._order_disc_value)

    def _apply_numpad(self, mode: str, value: float):
        if mode == "QTY":
            row = self._cart_table.currentRow()
            if 0 <= row < len(self.cart):
                new_qty = max(0, int(round(value)))
                if new_qty == 0:
                    self.cart.pop(row)
                else:
                    item = self.cart[row]
                    allow_neg = self.config.get("allow_negative_stock", False)
                    if not allow_neg and new_qty > item.stock_available:
                        QMessageBox.warning(self, "Stock Limit", f"Only {item.stock_available} units available.")
                        return
                    item.quantity = new_qty
                self._refresh_cart_table()
                self._recalculate()
        elif mode == "DISC%":
            row = self._cart_table.currentRow()
            if 0 <= row < len(self.cart):
                max_disc = float(self.config.get("max_discount_percent", 100))
                self.cart[row].discount_percent = min(value, max_disc)
                self._refresh_cart_table()
                self._recalculate()
        elif mode == "ORDER%":
            max_disc = float(self.config.get("max_discount_percent", 100))
            self._order_disc_value = min(value, max_disc)
            self._recalculate()

    def _load_data(self):
        self._all_products = self.db.get_products(active_only=True)
        self._categories = self.db.get_categories()
        self._build_category_tabs()
        self._render_products(self._all_products)

    def _build_category_tabs(self):
        while self._cat_layout.count() > 1:
            item = self._cat_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        all_btn = QPushButton("All")
        all_btn.setCheckable(True)
        all_btn.setChecked(True)
        all_btn.setMinimumHeight(42)
        all_btn.setStyleSheet("font-size:13px;")
        all_btn.clicked.connect(lambda checked=False: self._filter_by_category(None, all_btn))
        self._cat_layout.insertWidget(0, all_btn)
        self._cat_buttons = [all_btn]

        for cat in self._categories:
            btn = QPushButton(cat["name"])
            btn.setCheckable(True)
            btn.setMinimumHeight(42)
            btn.setStyleSheet("font-size:13px;")
            cat_id = cat["id"]
            btn.clicked.connect(lambda _, cid=cat_id, b=btn: self._filter_by_category(cid, b))
            self._cat_layout.insertWidget(self._cat_layout.count() - 1, btn)
            self._cat_buttons.append(btn)

    def _filter_by_category(self, category_id, clicked_btn):
        self._active_category_id = category_id
        for btn in self._cat_buttons:
            btn.setChecked(btn is clicked_btn)
        self._filter_products(self._search.text())

    def _filter_products(self, text: str):
        query = text.strip().lower()
        filtered = self._all_products
        if self._active_category_id:
            filtered = [p for p in filtered if p.get("category_id") == self._active_category_id]
        if query:
            filtered = [
                p for p in filtered
                if query in p["name"].lower()
                or query in (p.get("sku") or "").lower()
                or query in (p.get("barcode") or "").lower()
            ]
        self._render_products(filtered)

    def _render_products(self, products: List[dict]):
        while self._grid_layout.count():
            item = self._grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        cols = max(1, (self.width() - 500) // 190)
        for idx, product in enumerate(products):
            card = ProductCard(product, self.config.format_currency)
            card.clicked.connect(lambda _, p=product: self._add_to_cart(p))
            r, c = divmod(idx, cols)
            self._grid_layout.addWidget(card, r, c)

        from PyQt6.QtWidgets import QSpacerItem, QSizePolicy as SP
        self._grid_layout.addItem(
            QSpacerItem(0, 0, SP.Policy.Minimum, SP.Policy.Expanding),
            (len(products) // cols + 1) if cols else 1, 0,
        )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._filter_products(self._search.text())

    def _on_barcode_scan(self):
        text = self._search.text().strip()
        
        from services.barcode_utils import decode_barcode
        table, db_id = decode_barcode(text)
        
        product = None
        if table == "products":
            product = self.db.get_product(db_id)
        elif table == "product_variants":
            variant = self.db.get_variant(db_id)
            if variant:
                product = self.db.get_product(variant["product_id"])
                if product:
                    self._add_variant_to_cart(product, variant)
                    self._search.clear()
                    return
        
        if not product:
            product = self.db.get_product_by_barcode(text)
            
        if product:
            self._add_to_cart(product)
            self._search.clear()
        else:
            self._filter_products(text)

    def _add_to_cart(self, product: dict):
        # If the product has variants, show the picker first
        if product.get("has_variants"):
            variants = self.db.get_variants(product["id"])
            if variants:
                dlg = VariantPickerDialog(
                    product, variants, self.config.format_currency, self
                )
                dlg.variant_selected.connect(
                    lambda v: self._add_variant_to_cart(product, v)
                )
                dlg.exec()
                return

        allow_neg = self.config.get("allow_negative_stock", False)
        for item in self.cart:
            if item.product_id == product["id"] and item.variant_id is None:
                if not allow_neg and item.quantity >= item.stock_available:
                    QMessageBox.warning(self, "Stock Limit", f"Only {item.stock_available} units available.")
                    return
                item.quantity += 1
                self._refresh_cart_table()
                self._recalculate()
                return

        if not allow_neg and (product.get("total_stock") if product.get("total_stock") is not None else product.get("quantity", 0)) <= 0:
            QMessageBox.warning(self, "Out of Stock", f"'{product['name']}' is out of stock.")
            return
        self.cart.append(CartItem(product))
        self._refresh_cart_table()
        self._recalculate()

    def _add_variant_to_cart(self, product: dict, variant: dict):
        allow_neg = self.config.get("allow_negative_stock", False)
        for item in self.cart:
            if item.product_id == product["id"] and item.variant_id == variant["id"]:
                if not allow_neg and item.quantity >= item.stock_available:
                    QMessageBox.warning(self, "Stock Limit", f"Only {item.stock_available} units available.")
                    return
                item.quantity += 1
                self._refresh_cart_table()
                self._recalculate()
                return

        self.cart.append(CartItem(product, variant=variant))
        self._refresh_cart_table()
        self._recalculate()

    def _remove_cart_item(self):
        row = self._cart_table.currentRow()
        if 0 <= row < len(self.cart):
            self.cart.pop(row)
            self._refresh_cart_table()
            self._recalculate()

    def _change_qty(self, delta: int):
        row = self._cart_table.currentRow()
        if 0 <= row < len(self.cart):
            item = self.cart[row]
            new_qty = item.quantity + delta
            if new_qty <= 0:
                self.cart.pop(row)
            else:
                if delta > 0 and not self.config.get("allow_negative_stock", False):
                    if new_qty > item.stock_available:
                        QMessageBox.warning(self, "Stock Limit", f"Only {item.stock_available} units available.")
                        return
                item.quantity = new_qty
            self._refresh_cart_table()
            self._recalculate()

    def _refresh_cart_table(self):
        sym = self.config.get("currency_symbol", "$")
        self._cart_table.setRowCount(len(self.cart))
        for row, item in enumerate(self.cart):
            self._cart_table.setItem(row, 0, QTableWidgetItem(item.display_name))
            qty_item = QTableWidgetItem(str(item.quantity))
            qty_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._cart_table.setItem(row, 1, qty_item)
            disc_item = QTableWidgetItem(f"{item.discount_percent:.0f}%")
            disc_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._cart_table.setItem(row, 2, disc_item)
            total_item = QTableWidgetItem(f"{sym}{item.line_total:.2f}")
            total_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._cart_table.setItem(row, 3, total_item)
            self._cart_table.setRowHeight(row, 52)

    def _recalculate(self):
        sym = self.config.get("currency_symbol", "$")
        tax_rate = float(self.config.get("tax_rate", 0)) if self.config.get("tax_enabled", True) else 0
        tax_inclusive = self.config.get("tax_inclusive", False)
        order_disc = self._order_disc_value

        subtotal = sum(i.line_total for i in self.cart)
        item_discounts = sum(i.discount_amount for i in self.cart)
        order_disc_amount = subtotal * order_disc / 100
        discounted = subtotal - order_disc_amount
        total_discount = item_discounts + order_disc_amount

        if tax_inclusive:
            tax_amount = discounted - discounted / (1 + tax_rate / 100)
        else:
            tax_amount = discounted * tax_rate / 100

        total = discounted + (0 if tax_inclusive else tax_amount)

        self._subtotal_lbl.setText(f"{sym}{subtotal:.2f}")
        self._disc_lbl.setText(f"-{sym}{total_discount:.2f}")
        self._tax_lbl.setText(f"{sym}{tax_amount:.2f}")
        self._total_lbl.setText(f"{sym}{total:.2f}")
        self._computed = {"subtotal": subtotal, "discount_amount": total_discount, "tax_amount": tax_amount, "total": total}

    def _select_customer(self):
        dlg = CustomerSearchDialog(self.db, self)
        dlg.customer_selected.connect(self._set_customer)
        dlg.exec()

    def _set_customer(self, customer: dict):
        self.selected_customer = customer
        mobile = f"📱{customer['mobile']}" if customer.get("mobile") else ""
        self._cust_label.setText(f"👤 {customer['name']}  {mobile}  ⭐{customer.get('points', 0)} pts")
        self._cust_label.setStyleSheet("color:#4ade80; font-size:13px;")

    def _clear_customer(self):
        self.selected_customer = None
        self._cust_label.setText("👤  Walk-in Customer")
        self._cust_label.setStyleSheet("color:#94a3b8; font-size:13px;")

    def _process_payment(self):
        if not self.cart:
            QMessageBox.warning(self, "Empty Cart", "Please add items to the cart.")
            return
        if self.config.get("require_customer", False) and not self.selected_customer:
            QMessageBox.warning(self, "Customer Required", "Please select a customer before checkout.")
            return

        computed = getattr(self, "_computed", {})
        total = computed.get("total", 0)

        dlg = PaymentDialog(total, self.config, self, db=self.db)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        prefix = self.config.get("invoice_prefix", "INV")
        start = int(self.config.get("invoice_next_number", 1000))
        invoice_number = self.db.get_next_invoice_number(prefix, start)

        sale_data = {
            "invoice_number": invoice_number,
            "customer_id": self.selected_customer["id"] if self.selected_customer else None,
            "customer_name": self.selected_customer["name"] if self.selected_customer else "Walk-in",
            "subtotal": computed.get("subtotal", 0),
            "tax_amount": computed.get("tax_amount", 0),
            "discount_amount": computed.get("discount_amount", 0),
            "total": computed.get("total", 0),
            "payment_method": dlg.payment_method,
            "amount_paid": dlg.amount_paid,
            "change_amount": dlg.change,
            "notes": "",
            "status": "completed",
        }
        items_data = [
            {"product_id": item.product_id, "variant_id": item.variant_id,
             "product_name": item.display_name, "sku": item.sku,
             "quantity": item.quantity, "unit_price": item.unit_price,
             "discount_percent": item.discount_percent, "total": item.line_total}
            for item in self.cart
        ]

        sale_id = self.db.create_sale(sale_data, items_data)
        sale_data["id"] = sale_id

        if self.shopify_service:
            self.shopify_service.sync_stock_after_sale(items_data)

        self.config.set("invoice_next_number", int(invoice_number.replace(prefix, "")) + 1)

        # ✓ CONFIGURABLE PRINTING: Respect auto-print receipt setting
        auto_print = self.db.get_setting("auto_print_receipt", "1") == "1"
        
        if auto_print:
            # Auto-print enabled: show preview then print
            from services.receipt_printer import ReceiptPrinter, ReceiptPreviewDialog
            should_print = ReceiptPreviewDialog.show(self, self.config, sale_data, items_data, self.selected_customer)
            if should_print:
                ReceiptPrinter(self.config).print_receipt(sale_data, items_data, self.selected_customer)
        else:
            # Auto-print disabled: show preview with option to print
            from services.receipt_printer import ReceiptPrinter, ReceiptPreviewDialog
            should_print = ReceiptPreviewDialog.show(self, self.config, sale_data, items_data, self.selected_customer)
            if should_print:
                ReceiptPrinter(self.config).print_receipt(sale_data, items_data, self.selected_customer)

        sym = self.config.get("currency_symbol", "$")
        msg = QMessageBox(self)
        msg.setWindowTitle("Sale Complete ✓")
        msg.setText(f"<b>Invoice:</b> {invoice_number}<br><b>Total:</b> {sym}{computed['total']:.2f}<br><b>Change:</b> {sym}{dlg.change:.2f}")
        msg.setIcon(QMessageBox.Icon.Information)
        msg.exec()

        self.sale_completed.emit(sale_data)
        self._clear_cart()

    def _clear_cart(self):
        self.cart.clear()
        self._refresh_cart_table()
        self._order_disc_value = 0.0
        self._numpad.reset()
        self._recalculate()
        self._clear_customer()
        self._load_data()

    def _setup_shortcuts(self):
        QShortcut(QKeySequence("F2"), self, self._search.setFocus)
        QShortcut(QKeySequence("F12"), self, self._process_payment)
        QShortcut(QKeySequence("Escape"), self, self._clear_cart)

    @staticmethod
    def _get_double_input(title: str, label: str, value: float, min_val: float, max_val: float):
        from PyQt6.QtWidgets import QInputDialog
        return QInputDialog.getDouble(None, title, label, value, min_val, max_val, 1)
