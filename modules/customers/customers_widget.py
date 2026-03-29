"""Customer management module."""
import csv
import os
from typing import Optional, List
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QTableWidget, QTableWidgetItem, QHeaderView,
    QDialog, QFormLayout, QMessageBox, QDialogButtonBox,
    QTextEdit, QFrame, QSplitter, QSizePolicy, QFileDialog,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QBrush, QFont


# ═══════════════════════════════════════════════════════════════════════════
#  Customer Add / Edit dialog
# ═══════════════════════════════════════════════════════════════════════════
class CustomerDialog(QDialog):
    def __init__(self, db, customer: Optional[dict] = None, parent=None):
        super().__init__(parent)
        self.db = db
        self.customer = customer
        self.setWindowTitle("Edit Customer" if customer else "Add Customer")
        self.setMinimumWidth(440)
        self._build()
        if customer:
            self._populate(customer)

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        form = QFormLayout()
        form.setSpacing(10)

        self._name = QLineEdit()
        self._name.setPlaceholderText("Full name (required)")
        form.addRow("Name *", self._name)

        self._mobile = QLineEdit()
        self._mobile.setPlaceholderText("+1 416 000 0000")
        form.addRow("Mobile *", self._mobile)

        self._email = QLineEdit()
        self._email.setPlaceholderText("customer@email.com")
        form.addRow("Email", self._email)

        self._address = QLineEdit()
        self._address.setPlaceholderText("Street address")
        form.addRow("Address", self._address)

        self._city = QLineEdit()
        self._city.setPlaceholderText("City")
        form.addRow("City", self._city)

        self._notes = QTextEdit()
        self._notes.setMaximumHeight(70)
        self._notes.setPlaceholderText("Notes about this customer…")
        form.addRow("Notes", self._notes)

        layout.addLayout(form)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _populate(self, c: dict):
        self._name.setText(c.get("name", ""))
        self._mobile.setText(c.get("mobile", "") or "")
        self._email.setText(c.get("email", "") or "")
        self._address.setText(c.get("address", "") or "")
        self._city.setText(c.get("city", "") or "")
        self._notes.setPlainText(c.get("notes", "") or "")

    def _save(self):
        name = self._name.text().strip()
        mobile = self._mobile.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation", "Customer name is required.")
            return
        if not mobile:
            QMessageBox.warning(self, "Validation", "Mobile number is required.")
            return
        self.data = {
            "name": name,
            "mobile": mobile,
            "email": self._email.text().strip() or None,
            "address": self._address.text().strip() or None,
            "city": self._city.text().strip() or None,
            "notes": self._notes.toPlainText().strip() or None,
        }
        self.accept()


# ═══════════════════════════════════════════════════════════════════════════
#  Customer detail panel (right side)
# ═══════════════════════════════════════════════════════════════════════════
class CustomerDetailPanel(QWidget):
    def __init__(self, config, db):
        super().__init__()
        self.config = config
        self.db = db
        self._customer: Optional[dict] = None
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header
        self._avatar = QLabel("👤")
        self._avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._avatar.setStyleSheet("font-size:48px;")
        layout.addWidget(self._avatar)

        self._name_lbl = QLabel("Select a customer")
        self._name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._name_lbl.setStyleSheet("font-size:18px; font-weight:700; color:#f1f5f9;")
        layout.addWidget(self._name_lbl)

        self._mobile_lbl = QLabel()
        self._mobile_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._mobile_lbl.setStyleSheet("color:#94a3b8; font-size:13px;")
        layout.addWidget(self._mobile_lbl)

        # Stats cards
        stats_row = QHBoxLayout()
        self._total_lbl = self._stat_card("Total Spent", "$0.00", stats_row)
        self._points_lbl = self._stat_card("Points", "0", stats_row)
        self._orders_lbl = self._stat_card("Orders", "0", stats_row)
        layout.addLayout(stats_row)

        # Info
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("background:#334155; max-height:1px;")
        layout.addWidget(sep)

        self._info_layout = QFormLayout()
        self._info_layout.setSpacing(8)
        self._email_row = QLabel()
        self._email_row.setStyleSheet("color:#94a3b8;")
        self._addr_row = QLabel()
        self._addr_row.setStyleSheet("color:#94a3b8;")
        self._member_row = QLabel()
        self._member_row.setStyleSheet("color:#94a3b8;")
        self._notes_row = QLabel()
        self._notes_row.setStyleSheet("color:#94a3b8;")
        self._notes_row.setWordWrap(True)
        self._info_layout.addRow("Email:", self._email_row)
        self._info_layout.addRow("Address:", self._addr_row)
        self._info_layout.addRow("Member Since:", self._member_row)
        self._info_layout.addRow("Notes:", self._notes_row)
        layout.addLayout(self._info_layout)

        # Purchase history
        hist_lbl = QLabel("Purchase History")
        hist_lbl.setStyleSheet("font-weight:600; color:#f1f5f9; margin-top:8px;")
        layout.addWidget(hist_lbl)

        self._hist_table = QTableWidget(0, 3)
        self._hist_table.setHorizontalHeaderLabels(["Invoice", "Date", "Total"])
        hh = self._hist_table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._hist_table.verticalHeader().hide()
        self._hist_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._hist_table.setMinimumHeight(120)
        layout.addWidget(self._hist_table, 1)   # stretch=1 → fills remaining space

    def _stat_card(self, label: str, value: str, parent_layout: QHBoxLayout) -> QLabel:
        card = QFrame()
        card.setObjectName("StatCard")
        cl = QVBoxLayout(card)
        cl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        val_lbl = QLabel(value)
        val_lbl.setObjectName("StatValue")
        val_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        val_lbl.setStyleSheet("font-size:16px; font-weight:700;")
        lbl = QLabel(label)
        lbl.setObjectName("StatLabel")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cl.addWidget(val_lbl)
        cl.addWidget(lbl)
        parent_layout.addWidget(card)
        return val_lbl

    def show_customer(self, customer: dict):
        self._customer = customer
        sym = self.config.get("currency_symbol", "$")

        self._name_lbl.setText(customer.get("name", ""))
        self._mobile_lbl.setText(f"📱 {customer.get('mobile', '')}")
        self._email_row.setText(customer.get("email", "") or "—")
        addr_parts = [p for p in [customer.get("address", ""), customer.get("city", "")] if p]
        self._addr_row.setText(", ".join(addr_parts) or "—")
        raw_date = customer.get("created_at", "") or ""
        self._member_row.setText(raw_date[:10] if raw_date else "—")
        self._notes_row.setText(customer.get("notes", "") or "—")

        total_spent = float(customer.get("total_spent", 0))
        self._total_lbl.setText(f"{sym}{total_spent:.2f}")
        self._points_lbl.setText(str(customer.get("points", 0)))

        # Purchase history
        sales = self.db.get_customer_sales(customer["id"])
        self._orders_lbl.setText(str(len(sales)))
        self._hist_table.setRowCount(len(sales))
        for row, sale in enumerate(sales):
            self._hist_table.setItem(row, 0, QTableWidgetItem(sale.get("invoice_number", "")))
            dt = sale.get("created_at", "")[:10]
            self._hist_table.setItem(row, 1, QTableWidgetItem(dt))
            total_item = QTableWidgetItem(f"{sym}{sale.get('total', 0):.2f}")
            total_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._hist_table.setItem(row, 2, total_item)


# ═══════════════════════════════════════════════════════════════════════════
#  Main Customers Widget
# ═══════════════════════════════════════════════════════════════════════════
class CustomersWidget(QWidget):
    def __init__(self, config, db):
        super().__init__()
        self.config = config
        self.db = db
        self._customers: List[dict] = []
        self._build_ui()
        self._load_customers()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Toolbar
        toolbar = QHBoxLayout()
        title = QLabel("👥  Customers")
        title.setStyleSheet("font-size:20px; font-weight:700; color:#f1f5f9;")
        toolbar.addWidget(title)
        toolbar.addStretch()

        add_btn = QPushButton("+ Add Customer")
        add_btn.setObjectName("PrimaryBtn")
        add_btn.clicked.connect(self._add_customer)
        toolbar.addWidget(add_btn)

        edit_btn = QPushButton("✏ Edit")
        edit_btn.clicked.connect(self._edit_customer)
        toolbar.addWidget(edit_btn)

        del_btn = QPushButton("🗑 Delete")
        del_btn.setObjectName("DangerBtn")
        del_btn.clicked.connect(self._delete_customer)
        toolbar.addWidget(del_btn)

        export_btn = QPushButton("⬇ Export CSV")
        export_btn.setObjectName("SecondaryBtn")
        export_btn.clicked.connect(self._export_csv)
        toolbar.addWidget(export_btn)

        layout.addLayout(toolbar)

        # Search bar
        search_row = QHBoxLayout()
        self._search = QLineEdit()
        self._search.setPlaceholderText("🔍  Search by name, mobile or email…")
        self._search.textChanged.connect(self._filter)
        search_row.addWidget(self._search)

        self._count_lbl = QLabel("0 customers")
        self._count_lbl.setStyleSheet("color:#64748b; font-size:12px;")
        search_row.addWidget(self._count_lbl)
        layout.addLayout(search_row)

        # Main split: list | detail
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: customer list
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)

        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(
            ["Name", "Mobile", "Email", "Points", "Total Spent"]
        )
        hh = self._table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self._table.verticalHeader().hide()
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.selectionModel().selectionChanged.connect(self._on_selection)
        self._table.doubleClicked.connect(self._edit_customer)
        ll.addWidget(self._table)
        splitter.addWidget(left)

        # Right: detail panel (no scroll area – panel fills its slot naturally)
        self._detail = CustomerDetailPanel(self.config, self.db)
        self._detail.setMinimumWidth(300)
        splitter.addWidget(self._detail)
        splitter.setSizes([9999, 340])   # left takes all available, right starts at 340
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)

        layout.addWidget(splitter, 1)   # stretch=1 → splitter fills all remaining height

    # ------------------------------------------------------------------ #
    #  Data                                                                #
    # ------------------------------------------------------------------ #
    def _load_customers(self):
        self._customers = self.db.get_customers()
        self._filter()

    def _filter(self):
        query = self._search.text().strip()
        if query:
            filtered = self.db.search_customers(query)
        else:
            filtered = self._customers
        self._populate_table(filtered)
        self._count_lbl.setText(f"{len(filtered)} customer(s)")

    def _populate_table(self, customers: List[dict]):
        sym = self.config.get("currency_symbol", "$")
        self._displayed = customers
        self._table.setRowCount(len(customers))
        for row, c in enumerate(customers):
            self._table.setItem(row, 0, QTableWidgetItem(c.get("name", "")))
            self._table.setItem(row, 1, QTableWidgetItem(c.get("mobile", "") or ""))
            self._table.setItem(row, 2, QTableWidgetItem(c.get("email", "") or ""))
            pts_item = QTableWidgetItem(str(c.get("points", 0)))
            pts_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(row, 3, pts_item)
            total_item = QTableWidgetItem(f"{sym}{c.get('total_spent', 0):.2f}")
            total_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._table.setItem(row, 4, total_item)
        self._table.resizeRowsToContents()

    def _on_selection(self):
        row = self._table.currentRow()
        if 0 <= row < len(getattr(self, "_displayed", [])):
            self._detail.show_customer(self._displayed[row])

    def _get_selected(self) -> Optional[dict]:
        row = self._table.currentRow()
        if 0 <= row < len(getattr(self, "_displayed", [])):
            return self._displayed[row]
        return None

    # ------------------------------------------------------------------ #
    #  Export                                                              #
    # ------------------------------------------------------------------ #
    def _export_csv(self):
        if not getattr(self, "_displayed", []):
            QMessageBox.information(self, "No Data", "No customers to export.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Customers", "customers.csv", "CSV Files (*.csv)"
        )
        if not path:
            return
        sym = self.config.get("currency_symbol", "$")
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Name", "Mobile", "Email", "Address", "City",
                             "Points", "Total Spent", "Notes", "Member Since"])
            for c in self._displayed:
                writer.writerow([
                    c.get("name", ""),
                    c.get("mobile", "") or "",
                    c.get("email", "") or "",
                    c.get("address", "") or "",
                    c.get("city", "") or "",
                    c.get("points", 0),
                    f"{c.get('total_spent', 0):.2f}",
                    c.get("notes", "") or "",
                    (c.get("created_at", "") or "")[:10],
                ])
        QMessageBox.information(self, "Exported",
                                f"Exported {len(self._displayed)} customer(s) to:\n{path}")

    # ------------------------------------------------------------------ #
    #  CRUD                                                                #
    # ------------------------------------------------------------------ #
    def _add_customer(self):
        # Pre-fill mobile if search looks like a number
        dlg = CustomerDialog(self.db, parent=self)
        query = self._search.text().strip()
        if query.replace("+", "").replace(" ", "").replace("-", "").isdigit():
            dlg._mobile.setText(query)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            try:
                self.db.add_customer(dlg.data)
            except Exception as e:
                if "UNIQUE" in str(e):
                    QMessageBox.warning(self, "Duplicate Mobile",
                                        "A customer with this mobile number already exists.")
                    return
                raise
            self._load_customers()

    def _edit_customer(self):
        customer = self._get_selected()
        if not customer:
            QMessageBox.information(self, "Select Customer", "Please select a customer to edit.")
            return
        dlg = CustomerDialog(self.db, customer, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.db.update_customer(customer["id"], dlg.data)
            self._load_customers()

    def _delete_customer(self):
        customer = self._get_selected()
        if not customer:
            return
        reply = QMessageBox.question(
            self, "Delete Customer",
            f"Delete customer '{customer['name']}'?\nSales history will be preserved.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.db.delete_customer(customer["id"])
            self._load_customers()
