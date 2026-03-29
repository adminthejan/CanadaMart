"""Login dialog – shown on application startup and after logout."""
import os

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QMessageBox, QCheckBox, QSizePolicy,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QSize
from PyQt6.QtGui import QPixmap, QColor, QFont, QIcon, QKeyEvent


class LoginDialog(QDialog):
    """
    Branded login screen.

    Accepted result means `self.user` contains the authenticated user dict
    with keys: id, username, full_name, role.
    """

    login_successful = pyqtSignal(dict)   # emits user dict

    # Roles that are allowed to use this system
    ROLE_LABELS = {
        "admin":    "Administrator",
        "manager":  "Manager",
        "cashier":  "Cashier",
    }

    def __init__(self, config, db, parent=None):
        super().__init__(parent)
        self.config = config
        self.db = db
        self.user: dict | None = None
        self._attempts = 0

        self.setWindowTitle(config.get("app_name", "CanadaMart POS") + " – Login")
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.MSWindowsFixedSizeDialogHint)
        self.setFixedSize(420, 560)
        self.setModal(True)

        self._build_ui()
        self._apply_style()

    # ------------------------------------------------------------------ #
    #  UI                                                                  #
    # ------------------------------------------------------------------ #
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Top banner ────────────────────────────────────────────────── #
        banner = QFrame()
        banner.setObjectName("LoginBanner")
        banner.setFixedHeight(180)
        banner_layout = QVBoxLayout(banner)
        banner_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        banner_layout.setSpacing(6)

        logo_path = self.config.get("logo_path", "")
        if logo_path and os.path.exists(logo_path):
            logo_lbl = QLabel()
            pix = QPixmap(logo_path).scaled(
                160, 70, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            logo_lbl.setPixmap(pix)
            logo_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            banner_layout.addWidget(logo_lbl)
        else:
            icon_lbl = QLabel("🏪")
            icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            icon_lbl.setStyleSheet("font-size: 48px; background: transparent;")
            banner_layout.addWidget(icon_lbl)

        app_name = QLabel(self.config.get("app_name", "CanadaMart POS"))
        app_name.setObjectName("LoginAppName")
        app_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        banner_layout.addWidget(app_name)

        biz = self.config.get("business_name", "")
        if biz:
            biz_lbl = QLabel(biz)
            biz_lbl.setObjectName("LoginBizName")
            biz_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            banner_layout.addWidget(biz_lbl)

        root.addWidget(banner)

        # ── Form card ─────────────────────────────────────────────────── #
        card = QFrame()
        card.setObjectName("LoginCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(36, 32, 36, 32)
        card_layout.setSpacing(16)

        # Title
        sign_in = QLabel("Sign In")
        sign_in.setObjectName("LoginTitle")
        card_layout.addWidget(sign_in)

        # Username
        user_lbl = QLabel("Username")
        user_lbl.setObjectName("LoginFieldLabel")
        card_layout.addWidget(user_lbl)

        self._username = QLineEdit()
        self._username.setObjectName("LoginInput")
        self._username.setPlaceholderText("Enter your username")
        self._username.setMinimumHeight(42)
        self._username.returnPressed.connect(self._on_login)
        card_layout.addWidget(self._username)

        # Password
        pw_lbl = QLabel("Password")
        pw_lbl.setObjectName("LoginFieldLabel")
        card_layout.addWidget(pw_lbl)

        pw_row = QHBoxLayout()
        pw_row.setSpacing(6)
        self._password = QLineEdit()
        self._password.setObjectName("LoginInput")
        self._password.setPlaceholderText("Enter your password")
        self._password.setEchoMode(QLineEdit.EchoMode.Password)
        self._password.setMinimumHeight(42)
        self._password.returnPressed.connect(self._on_login)
        pw_row.addWidget(self._password)

        self._show_pw = QPushButton("👁")
        self._show_pw.setObjectName("ShowPwBtn")
        self._show_pw.setFixedSize(42, 42)
        self._show_pw.setCheckable(True)
        self._show_pw.toggled.connect(self._toggle_pw_visibility)
        pw_row.addWidget(self._show_pw)
        card_layout.addLayout(pw_row)

        # Error label
        self._error_lbl = QLabel()
        self._error_lbl.setObjectName("LoginError")
        self._error_lbl.setWordWrap(True)
        self._error_lbl.hide()
        card_layout.addWidget(self._error_lbl)

        card_layout.addSpacing(4)

        # Login button
        self._login_btn = QPushButton("Login")
        self._login_btn.setObjectName("LoginBtn")
        self._login_btn.setMinimumHeight(46)
        self._login_btn.clicked.connect(self._on_login)
        card_layout.addWidget(self._login_btn)

        # Hint
        hint = QLabel("Default: admin / admin123")
        hint.setObjectName("LoginHint")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(hint)

        card_layout.addStretch()
        root.addWidget(card, 1)

        # ── Footer ────────────────────────────────────────────────────── #
        footer = QLabel(
            f"v{self.config.get('app_version', '1.0.0')}  ·  "
            f"{self.config.get('app_name', 'CanadaMart POS')}"
        )
        footer.setObjectName("LoginFooter")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setFixedHeight(32)
        root.addWidget(footer)

        # Focus
        self._username.setFocus()

    # ------------------------------------------------------------------ #
    #  Styling                                                             #
    # ------------------------------------------------------------------ #
    def _apply_style(self):
        theme = self.config.get("theme", "dark")
        if theme == "light":
            bg, banner_bg, card_bg, fg, sub, border, btn = (
                "#f1f5f9", "#2563eb", "#ffffff",
                "#0f172a", "#475569", "#e2e8f0", "#2563eb"
            )
            inp_bg, inp_fg = "#f8fafc", "#0f172a"
            footer_fg = "#94a3b8"
        else:
            bg, banner_bg, card_bg, fg, sub, border, btn = (
                "#0f172a", "#1e293b", "#1e293b",
                "#f1f5f9", "#94a3b8", "#334155", "#2563eb"
            )
            inp_bg, inp_fg = "#0f172a", "#f1f5f9"
            footer_fg = "#475569"

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {bg};
            }}
            #LoginBanner {{
                background-color: {banner_bg};
                border: none;
            }}
            #LoginAppName {{
                color: #ffffff;
                font-size: 22px;
                font-weight: 700;
                background: transparent;
            }}
            #LoginBizName {{
                color: rgba(255,255,255,0.75);
                font-size: 12px;
                background: transparent;
            }}
            #LoginCard {{
                background-color: {card_bg};
                border: none;
            }}
            #LoginTitle {{
                color: {fg};
                font-size: 20px;
                font-weight: 700;
            }}
            #LoginFieldLabel {{
                color: {sub};
                font-size: 12px;
                font-weight: 600;
                text-transform: uppercase;
                letter-spacing: 1px;
            }}
            #LoginInput {{
                background-color: {inp_bg};
                color: {inp_fg};
                border: 1.5px solid {border};
                border-radius: 8px;
                padding: 0 12px;
                font-size: 14px;
            }}
            #LoginInput:focus {{
                border-color: {btn};
            }}
            #ShowPwBtn {{
                background-color: {inp_bg};
                color: {sub};
                border: 1.5px solid {border};
                border-radius: 8px;
                font-size: 16px;
            }}
            #ShowPwBtn:hover {{
                background-color: {border};
            }}
            #LoginBtn {{
                background-color: {btn};
                color: #ffffff;
                border: none;
                border-radius: 8px;
                font-size: 15px;
                font-weight: 600;
            }}
            #LoginBtn:hover {{
                background-color: #1d4ed8;
            }}
            #LoginBtn:pressed {{
                background-color: #1e40af;
            }}
            #LoginBtn:disabled {{
                background-color: #334155;
                color: #64748b;
            }}
            #LoginError {{
                color: #f87171;
                font-size: 12px;
                background: rgba(239,68,68,0.12);
                border-radius: 6px;
                padding: 8px 10px;
            }}
            #LoginHint {{
                color: {sub};
                font-size: 11px;
            }}
            #LoginFooter {{
                color: {footer_fg};
                font-size: 11px;
                background-color: {bg};
            }}
        """)

    # ------------------------------------------------------------------ #
    #  Logic                                                               #
    # ------------------------------------------------------------------ #
    def _toggle_pw_visibility(self, checked: bool):
        mode = QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
        self._password.setEchoMode(mode)
        self._show_pw.setText("🙈" if checked else "👁")

    def _on_login(self):
        username = self._username.text().strip()
        password = self._password.text()

        if not username:
            self._show_error("Please enter your username.")
            self._username.setFocus()
            return
        if not password:
            self._show_error("Please enter your password.")
            self._password.setFocus()
            return

        self._login_btn.setEnabled(False)
        self._login_btn.setText("Signing in…")

        # Small delay for UX feedback
        QTimer.singleShot(300, lambda: self._check_credentials(username, password))

    def _check_credentials(self, username: str, password: str):
        try:
            user = self.db.authenticate_user(username, password)
        except Exception as e:
            self._show_error(f"Database error: {e}")
            self._reset_btn()
            return

        if user:
            self._attempts = 0
            self.user = user
            self.login_successful.emit(user)
            self.accept()
        else:
            self._attempts += 1
            if self._attempts >= 5:
                self._show_error(
                    "Too many failed attempts.\nPlease contact your administrator."
                )
                self._login_btn.setEnabled(False)
                self._login_btn.setText("Locked")
                # Unlock after 30 seconds
                QTimer.singleShot(30_000, self._unlock)
            else:
                remaining = 5 - self._attempts
                self._show_error(
                    f"Invalid username or password.\n"
                    f"{remaining} attempt(s) remaining."
                )
                self._password.clear()
                self._password.setFocus()
                self._reset_btn()

    def _show_error(self, msg: str):
        self._error_lbl.setText(msg)
        self._error_lbl.show()

    def _reset_btn(self):
        self._login_btn.setEnabled(True)
        self._login_btn.setText("Login")

    def _unlock(self):
        self._attempts = 0
        self._reset_btn()
        self._error_lbl.hide()
        self._username.setFocus()
