"""Global QSS stylesheet for the POS application."""


def get_stylesheet(theme: str = "dark") -> str:
    if theme == "light":
        return _LIGHT_QSS
    return _DARK_QSS


# ──────────────────────────────────────────────────────────────────────────
#  DARK THEME
# ──────────────────────────────────────────────────────────────────────────
_DARK_QSS = """
/* ── Base ── */
QWidget {
    background-color: #0f172a;
    color: #e2e8f0;
    font-family: 'Segoe UI', 'SF Pro Display', Arial, sans-serif;
    font-size: 13px;
}

QMainWindow {
    background-color: #0f172a;
}

/* ── Scroll bars ── */
QScrollBar:vertical {
    background: #1e293b;
    width: 8px;
    border-radius: 4px;
}
QScrollBar::handle:vertical {
    background: #475569;
    border-radius: 4px;
    min-height: 20px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal {
    background: #1e293b;
    height: 8px;
    border-radius: 4px;
}
QScrollBar::handle:horizontal {
    background: #475569;
    border-radius: 4px;
    min-width: 20px;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }

/* ── Sidebar ── */
#Sidebar {
    background-color: #1e293b;
    border-right: 1px solid #334155;
}

#SidebarBtn {
    background: transparent;
    color: #94a3b8;
    border: none;
    border-radius: 8px;
    padding: 10px 16px;
    text-align: left;
    font-size: 13px;
    font-weight: 500;
}
#SidebarBtn:hover {
    background-color: #334155;
    color: #f1f5f9;
}
#SidebarBtn[active="true"] {
    background-color: #2563eb;
    color: #ffffff;
    font-weight: 600;
}

#AppTitle {
    color: #f1f5f9;
    font-size: 16px;
    font-weight: 700;
    padding: 4px 0;
}
#AppSubtitle {
    color: #64748b;
    font-size: 11px;
    padding: 0;
}

/* ── Cards / Panels ── */
#Card {
    background-color: #1e293b;
    border: 1px solid #334155;
    border-radius: 10px;
    padding: 12px;
}
#CardTitle {
    color: #f1f5f9;
    font-size: 14px;
    font-weight: 600;
}

/* ── Inputs ── */
QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background-color: #1e293b;
    border: 1px solid #334155;
    border-radius: 6px;
    color: #e2e8f0;
    padding: 6px 10px;
    selection-background-color: #2563eb;
}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus,
QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
    border-color: #3b82f6;
    outline: none;
}
QComboBox::drop-down {
    border: none;
    padding-right: 8px;
}
QComboBox QAbstractItemView {
    background-color: #1e293b;
    border: 1px solid #334155;
    selection-background-color: #2563eb;
    color: #e2e8f0;
}
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
    background: #334155;
    border-radius: 3px;
    width: 18px;
}

/* ── Labels ── */
QLabel {
    color: #e2e8f0;
    background: transparent;
}
#FieldLabel {
    color: #94a3b8;
    font-size: 11px;
    font-weight: 500;
}

/* ── Buttons ── */
QPushButton {
    background-color: #334155;
    color: #e2e8f0;
    border: 1px solid #475569;
    border-radius: 6px;
    padding: 7px 14px;
    font-weight: 500;
}
QPushButton:hover {
    background-color: #475569;
    border-color: #64748b;
}
QPushButton:pressed {
    background-color: #2563eb;
}
QPushButton:disabled {
    background-color: #1e293b;
    color: #475569;
    border-color: #334155;
}

#PrimaryBtn {
    background-color: #2563eb;
    color: #ffffff;
    border: none;
    border-radius: 8px;
    padding: 10px 20px;
    font-weight: 600;
    font-size: 13px;
}
#PrimaryBtn:hover { background-color: #1d4ed8; }
#PrimaryBtn:pressed { background-color: #1e40af; }

#DangerBtn {
    background-color: #dc2626;
    color: #ffffff;
    border: none;
    border-radius: 8px;
    padding: 10px 20px;
    font-weight: 600;
}
#DangerBtn:hover { background-color: #b91c1c; }

#SuccessBtn {
    background-color: #16a34a;
    color: #ffffff;
    border: none;
    border-radius: 8px;
    padding: 10px 20px;
    font-weight: 600;
}
#SuccessBtn:hover { background-color: #15803d; }

#WarningBtn {
    background-color: #d97706;
    color: #ffffff;
    border: none;
    border-radius: 8px;
    padding: 10px 20px;
    font-weight: 600;
}
#WarningBtn:hover { background-color: #b45309; }

#SecondaryBtn {
    background-color: transparent;
    color: #94a3b8;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 7px 14px;
}
#SecondaryBtn:hover {
    background-color: #1e293b;
    color: #e2e8f0;
}

/* ── Product card ── */
#ProductCard {
    background-color: #1e293b;
    border: 1px solid #334155;
    border-radius: 10px;
    padding: 8px;
}
#ProductCard:hover {
    background-color: #293548;
    border-color: #3b82f6;
}
#ProductCard:pressed {
    background-color: #1d3461;
    border-color: #2563eb;
}
#ProductCardName {
    color: #f1f5f9;
    font-weight: 600;
    font-size: 12px;
}
#ProductCardPrice {
    color: #4ade80;
    font-weight: 700;
    font-size: 13px;
}
#ProductCardStock {
    color: #64748b;
    font-size: 10px;
}
#ProductCardStockLow {
    color: #f87171;
    font-size: 10px;
}

/* ── Cart ── */
#CartPanel {
    background-color: #1e293b;
    border-left: 1px solid #334155;
}
#CartItem {
    background-color: #0f172a;
    border: 1px solid #1e293b;
    border-radius: 6px;
    padding: 4px;
}

/* ── Tables ── */
QTableWidget, QTableView {
    background-color: #1e293b;
    alternate-background-color: #162032;
    border: 1px solid #334155;
    border-radius: 8px;
    gridline-color: #334155;
    selection-background-color: #1d3461;
    selection-color: #e2e8f0;
}
QTableWidget::item, QTableView::item {
    padding: 6px 10px;
    border: none;
}
QHeaderView::section {
    background-color: #0f172a;
    color: #94a3b8;
    font-weight: 600;
    font-size: 11px;
    padding: 8px 10px;
    border: none;
    border-bottom: 1px solid #334155;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

/* ── Tab widget ── */
QTabWidget::pane {
    border: 1px solid #334155;
    border-radius: 8px;
    background-color: #1e293b;
}
QTabBar::tab {
    background-color: #0f172a;
    color: #94a3b8;
    border: 1px solid #334155;
    border-bottom: none;
    border-radius: 6px 6px 0 0;
    padding: 8px 16px;
    margin-right: 2px;
    font-weight: 500;
}
QTabBar::tab:selected {
    background-color: #1e293b;
    color: #f1f5f9;
    border-color: #3b82f6;
}
QTabBar::tab:hover:!selected {
    background-color: #1e293b;
    color: #e2e8f0;
}

/* ── Status bar ── */
QStatusBar {
    background-color: #0f172a;
    color: #64748b;
    border-top: 1px solid #334155;
    font-size: 11px;
}

/* ── Message box ── */
QMessageBox {
    background-color: #1e293b;
    color: #e2e8f0;
}
QMessageBox QPushButton {
    min-width: 80px;
    padding: 6px 16px;
}

/* ── Dialog ── */
QDialog {
    background-color: #1e293b;
    color: #e2e8f0;
}

/* ── Group box ── */
QGroupBox {
    border: 1px solid #334155;
    border-radius: 8px;
    margin-top: 16px;
    padding-top: 8px;
    color: #94a3b8;
    font-weight: 600;
    font-size: 11px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 6px;
    color: #94a3b8;
}

/* ── Checkbox / Radio ── */
QCheckBox, QRadioButton {
    color: #e2e8f0;
    spacing: 8px;
}
QCheckBox::indicator, QRadioButton::indicator {
    width: 16px;
    height: 16px;
    border: 2px solid #475569;
    border-radius: 3px;
    background: #0f172a;
}
QCheckBox::indicator:checked {
    background-color: #2563eb;
    border-color: #2563eb;
}

/* ── Progress / Slider ── */
QProgressBar {
    background-color: #0f172a;
    border: 1px solid #334155;
    border-radius: 6px;
    height: 10px;
    text-align: center;
    color: transparent;
}
QProgressBar::chunk {
    background-color: #2563eb;
    border-radius: 5px;
}

/* ── Summary stat cards ── */
#StatCard {
    background-color: #1e293b;
    border-radius: 12px;
    border: 1px solid #334155;
    padding: 16px;
}
#StatValue {
    color: #f1f5f9;
    font-size: 24px;
    font-weight: 700;
}
#StatLabel {
    color: #64748b;
    font-size: 11px;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

/* ── Badges ── */
#BadgeGreen {
    background-color: #064e3b;
    color: #34d399;
    border-radius: 10px;
    padding: 2px 8px;
    font-size: 10px;
    font-weight: 600;
}
#BadgeRed {
    background-color: #450a0a;
    color: #fca5a5;
    border-radius: 10px;
    padding: 2px 8px;
    font-size: 10px;
    font-weight: 600;
}
#BadgeYellow {
    background-color: #422006;
    color: #fcd34d;
    border-radius: 10px;
    padding: 2px 8px;
    font-size: 10px;
    font-weight: 600;
}
"""

# ──────────────────────────────────────────────────────────────────────────
#  LIGHT THEME
# ──────────────────────────────────────────────────────────────────────────
_LIGHT_QSS = """
QWidget {
    background-color: #f8fafc;
    color: #1e293b;
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 13px;
}
QMainWindow { background-color: #f8fafc; }

QScrollBar:vertical {
    background: #e2e8f0; width: 8px; border-radius: 4px;
}
QScrollBar::handle:vertical {
    background: #94a3b8; border-radius: 4px; min-height: 20px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal {
    background: #e2e8f0; height: 8px; border-radius: 4px;
}
QScrollBar::handle:horizontal {
    background: #94a3b8; border-radius: 4px; min-width: 20px;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }

#Sidebar {
    background-color: #1e293b;
    border-right: 1px solid #334155;
}
#SidebarBtn {
    background: transparent;
    color: #94a3b8;
    border: none;
    border-radius: 8px;
    padding: 10px 16px;
    text-align: left;
    font-size: 13px;
    font-weight: 500;
}
#SidebarBtn:hover { background-color: #334155; color: #f1f5f9; }
#SidebarBtn[active="true"] { background-color: #2563eb; color: #fff; font-weight: 600; }

#AppTitle { color: #f1f5f9; font-size: 16px; font-weight: 700; }
#AppSubtitle { color: #64748b; font-size: 11px; }

#Card {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 12px;
}

QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background-color: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    color: #1e293b;
    padding: 6px 10px;
    selection-background-color: #2563eb;
}
QLineEdit:focus, QTextEdit:focus, QComboBox:focus {
    border-color: #3b82f6;
}
QComboBox QAbstractItemView {
    background: #fff;
    border: 1px solid #cbd5e1;
    selection-background-color: #2563eb;
    color: #1e293b;
}

QPushButton {
    background-color: #e2e8f0;
    color: #1e293b;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 7px 14px;
    font-weight: 500;
}
QPushButton:hover { background-color: #cbd5e1; }
QPushButton:pressed { background-color: #2563eb; color: #fff; }
QPushButton:disabled { background-color: #f1f5f9; color: #94a3b8; }

#PrimaryBtn {
    background-color: #2563eb; color: #fff;
    border: none; border-radius: 8px; padding: 10px 20px; font-weight: 600;
}
#PrimaryBtn:hover { background-color: #1d4ed8; }

#DangerBtn { background-color: #dc2626; color: #fff; border: none; border-radius: 8px; padding: 10px 20px; font-weight: 600; }
#SuccessBtn { background-color: #16a34a; color: #fff; border: none; border-radius: 8px; padding: 10px 20px; font-weight: 600; }
#WarningBtn { background-color: #d97706; color: #fff; border: none; border-radius: 8px; padding: 10px 20px; font-weight: 600; }
#SecondaryBtn { background-color: transparent; color: #64748b; border: 1px solid #cbd5e1; border-radius: 6px; padding: 7px 14px; }

#ProductCard {
    background-color: #fff;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 8px;
}
#ProductCard:hover { border-color: #3b82f6; }

QTableWidget, QTableView {
    background-color: #fff;
    alternate-background-color: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    gridline-color: #f1f5f9;
    selection-background-color: #dbeafe;
    selection-color: #1e293b;
}
QHeaderView::section {
    background-color: #f8fafc;
    color: #64748b;
    font-weight: 600;
    font-size: 11px;
    padding: 8px 10px;
    border: none;
    border-bottom: 1px solid #e2e8f0;
}
QTabWidget::pane { border: 1px solid #e2e8f0; border-radius: 8px; background: #fff; }
QTabBar::tab { background: #f1f5f9; color: #64748b; border: 1px solid #e2e8f0; border-bottom: none; border-radius: 6px 6px 0 0; padding: 8px 16px; margin-right: 2px; }
QTabBar::tab:selected { background: #fff; color: #1e293b; border-color: #3b82f6; }

QStatusBar { background: #f1f5f9; color: #64748b; border-top: 1px solid #e2e8f0; font-size: 11px; }
QDialog { background: #fff; }
QGroupBox { border: 1px solid #e2e8f0; border-radius: 8px; margin-top: 16px; color: #64748b; font-weight: 600; }
QCheckBox::indicator { width: 16px; height: 16px; border: 2px solid #cbd5e1; border-radius: 3px; background: #fff; }
QCheckBox::indicator:checked { background: #2563eb; border-color: #2563eb; }

#StatCard { background: #fff; border-radius: 12px; border: 1px solid #e2e8f0; padding: 16px; }
#StatValue { color: #1e293b; font-size: 24px; font-weight: 700; }
#StatLabel { color: #94a3b8; font-size: 11px; font-weight: 500; }

#BadgeGreen { background: #dcfce7; color: #16a34a; border-radius: 10px; padding: 2px 8px; font-size: 10px; font-weight: 600; }
#BadgeRed { background: #fee2e2; color: #dc2626; border-radius: 10px; padding: 2px 8px; font-size: 10px; font-weight: 600; }
#BadgeYellow { background: #fef9c3; color: #d97706; border-radius: 10px; padding: 2px 8px; font-size: 10px; font-weight: 600; }
"""
