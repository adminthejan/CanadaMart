"""Main application window with sidebar navigation."""
import os
from datetime import datetime

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QLabel, QStackedWidget, QStatusBar,
    QSizePolicy, QFrame, QSpacerItem, QMessageBox,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSlot, QSize, pyqtSignal
from PyQt6.QtGui import QIcon, QPixmap, QFont, QPainter, QColor

from ui.styles import get_stylesheet


# Role → which nav indices are accessible  (0=POS,1=Inv,2=Cust,3=Rep,4=Settings)
ROLE_ACCESS = {
    "admin":   {0, 1, 2, 3, 4},
    "manager": {0, 1, 2, 3, 4},
    "cashier": {0, 2},           # POS + Customers only
}


class SidebarButton(QPushButton):
    """Navigation button for the sidebar."""
    def __init__(self, icon_text: str, label: str, parent=None):
        super().__init__(parent)
        self.setObjectName("SidebarBtn")
        self.setText(f"  {icon_text}  {label}")
        self.setCheckable(False)
        self.setMinimumHeight(44)
        self.setProperty("active", "false")

    def set_active(self, active: bool):
        self.setProperty("active", "true" if active else "false")
        self.style().unpolish(self)
        self.style().polish(self)


class MainWindow(QMainWindow):
    """Main application window."""

    logout_requested = pyqtSignal()   # emitted when user clicks Logout

    NAV_ITEMS = [
        ("🛒", "POS",       0),
        ("📦", "Inventory", 1),
        ("👥", "Customers", 2),
        ("📊", "Reports",   3),
        ("⚙️",  "Settings",  4),
    ]

    def __init__(self, config, db, shopify_service=None, current_user: dict | None = None):
        super().__init__()
        self.config = config
        self.db = db
        self.shopify_service = shopify_service
        self.current_user = current_user or {"username": "admin", "full_name": "Administrator", "role": "admin"}
        self._nav_buttons: list[SidebarButton] = []
        self._modules_loaded = {}

        self._setup_window()
        self._setup_ui()
        self._apply_theme()
        self._start_clock()

        # Navigate to POS on start
        self._navigate(0)

    # ------------------------------------------------------------------ #
    #  Window setup                                                        #
    # ------------------------------------------------------------------ #
    def _setup_window(self):
        app_name = self.config.get("app_name", "CanadaMart POS")
        self.setWindowTitle(app_name)
        self.setMinimumSize(1200, 760)
        self.resize(1440, 900)

        logo_path = self.config.get("logo_path", "")
        if logo_path and os.path.exists(logo_path):
            self.setWindowIcon(QIcon(logo_path))

    # ------------------------------------------------------------------ #
    #  UI construction                                                     #
    # ------------------------------------------------------------------ #
    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Sidebar
        self._sidebar = self._build_sidebar()
        root.addWidget(self._sidebar)

        # Content stack
        self._stack = QStackedWidget()
        root.addWidget(self._stack, 1)

        # Add module placeholders (lazy-load).
        # _slot_widgets maps logical module index → the widget currently
        # occupying that slot in the stack (placeholder or real module).
        self._slot_widgets: dict[int, QWidget] = {}
        for i, _ in enumerate(self.NAV_ITEMS):
            placeholder = QWidget()
            self._stack.addWidget(placeholder)
            self._slot_widgets[i] = placeholder

        # Status bar
        self._statusbar = QStatusBar()
        self.setStatusBar(self._statusbar)

        self._status_sync = QLabel("● Not connected")
        self._status_sync.setStyleSheet("color: #64748b; font-size: 11px;")
        self._status_time = QLabel()
        self._status_time.setStyleSheet("color: #64748b; font-size: 11px;")

        # Show logged-in user in status bar
        role = self.current_user.get("role", "cashier")
        uname = self.current_user.get("full_name", self.current_user.get("username", ""))
        role_color = {"admin": "#f59e0b", "manager": "#3b82f6", "cashier": "#10b981"}.get(role, "#94a3b8")
        self._status_user = QLabel(f"👤 {uname}  [{role.title()}]")
        self._status_user.setStyleSheet(f"color: {role_color}; font-size: 11px; font-weight: 600;")

        # Pause / resume sync button – only visible when Shopify is enabled
        self._sync_pause_btn = QPushButton("⏸  Pause Sync")
        self._sync_pause_btn.setFixedHeight(22)
        self._sync_pause_btn.setFlat(False)
        self._sync_pause_btn.setStyleSheet(
            "QPushButton { background: #1e293b; color: #94a3b8; border: 1px solid #334155; "
            "border-radius: 4px; padding: 0 8px; font-size: 11px; } "
            "QPushButton:hover { background: #334155; color: #f1f5f9; }"
        )
        self._sync_pause_btn.setToolTip("Pause the automatic background sync with Shopify")
        self._sync_pause_btn.clicked.connect(self._toggle_sync_pause)

        self._statusbar.addWidget(self._status_user)
        self._statusbar.addWidget(QLabel("  |  "))
        self._statusbar.addPermanentWidget(self._sync_pause_btn)
        self._statusbar.addPermanentWidget(QLabel("  "))
        self._statusbar.addPermanentWidget(self._status_sync)
        self._statusbar.addPermanentWidget(QLabel("  |  "))
        self._statusbar.addPermanentWidget(self._status_time)

        # Initialise button state
        self._update_sync_pause_btn()

    def _update_sidebar_logo(self):
        """Load the configured logo into the sidebar label (or clear it)."""
        logo_path = self.config.get("logo_path", "").strip()
        if logo_path and os.path.exists(logo_path):
            from PyQt6.QtGui import QImage
            img = QImage(logo_path)
            if not img.isNull():
                pix = QPixmap.fromImage(img)
                self._sidebar_logo_label.setPixmap(
                    pix.scaled(140, 60,
                               Qt.AspectRatioMode.KeepAspectRatio,
                               Qt.TransformationMode.SmoothTransformation)
                )
                self._sidebar_logo_label.setVisible(True)
                return
        self._sidebar_logo_label.clear()
        self._sidebar_logo_label.setVisible(False)

    def _build_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(220)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(12, 16, 12, 16)
        layout.setSpacing(4)

        # Logo area
        logo_container = QWidget()
        logo_layout = QVBoxLayout(logo_container)
        logo_layout.setContentsMargins(8, 0, 8, 8)
        logo_layout.setSpacing(2)

        self._sidebar_logo_label = QLabel()
        self._sidebar_logo_label.setObjectName("SidebarLogo")
        self._sidebar_logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._sidebar_logo_label.setMaximumHeight(64)
        logo_layout.addWidget(self._sidebar_logo_label)
        self._update_sidebar_logo()

        app_title = QLabel(self.config.get("app_name", "CanadaMart POS"))
        app_title.setObjectName("AppTitle")
        app_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_layout.addWidget(app_title)

        biz_name = self.config.get("business_name", "")
        if biz_name:
            sub = QLabel(biz_name)
            sub.setObjectName("AppSubtitle")
            sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
            logo_layout.addWidget(sub)

        layout.addWidget(logo_container)

        # Divider
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setStyleSheet("color: #334155; background: #334155; max-height: 1px;")
        layout.addWidget(divider)
        layout.addSpacing(8)

        # Navigation buttons  (only show items allowed for this role)
        role = self.current_user.get("role", "cashier")
        allowed = ROLE_ACCESS.get(role, {0})
        self._nav_buttons = []
        for icon, label, idx in self.NAV_ITEMS:
            btn = SidebarButton(icon, label)
            btn.clicked.connect(lambda checked, i=idx: self._navigate(i))
            if idx not in allowed:
                btn.setEnabled(False)
                btn.setToolTip(f"Access restricted ({role})")
            layout.addWidget(btn)
            self._nav_buttons.append(btn)

        layout.addStretch()

        # ── User info panel ───────────────────────────────────────────── #
        user_divider = QFrame()
        user_divider.setFrameShape(QFrame.Shape.HLine)
        user_divider.setStyleSheet("color: #334155; background: #334155; max-height: 1px;")
        layout.addWidget(user_divider)
        layout.addSpacing(6)

        user_frame = QFrame()
        user_frame.setObjectName("UserPanel")
        user_frame.setStyleSheet(
            "#UserPanel { background: #0f172a; border-radius: 8px; padding: 4px; }"
        )
        uf_layout = QVBoxLayout(user_frame)
        uf_layout.setContentsMargins(8, 8, 8, 8)
        uf_layout.setSpacing(2)

        full_name = self.current_user.get("full_name", self.current_user.get("username", "User"))
        self._user_name_lbl = QLabel(f"👤  {full_name}")
        self._user_name_lbl.setStyleSheet("color: #f1f5f9; font-weight: 600; font-size: 12px;")
        self._user_name_lbl.setWordWrap(True)
        uf_layout.addWidget(self._user_name_lbl)

        role_label_text = {"admin": "Administrator", "manager": "Manager", "cashier": "Cashier"}.get(role, role.title())
        role_color = {"admin": "#f59e0b", "manager": "#3b82f6", "cashier": "#10b981"}.get(role, "#94a3b8")
        role_lbl = QLabel(f"● {role_label_text}")
        role_lbl.setStyleSheet(f"color: {role_color}; font-size: 11px;")
        uf_layout.addWidget(role_lbl)

        layout.addWidget(user_frame)
        layout.addSpacing(4)

        logout_btn = QPushButton("🚪  Logout")
        logout_btn.setObjectName("DangerBtn")
        logout_btn.setMinimumHeight(36)
        logout_btn.clicked.connect(self._on_logout)
        layout.addWidget(logout_btn)

        layout.addSpacing(4)

        # Bottom: version
        ver = self.config.get("app_version", "1.0.0")
        ver_label = QLabel(f"v{ver}")
        ver_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ver_label.setStyleSheet("color: #475569; font-size: 10px;")
        layout.addWidget(ver_label)

        return sidebar

    # ------------------------------------------------------------------ #
    #  Navigation                                                          #
    # ------------------------------------------------------------------ #
    def _navigate(self, index: int):
        # Enforce role-based access
        role = self.current_user.get("role", "cashier")
        allowed = ROLE_ACCESS.get(role, {0})
        if index not in allowed:
            QMessageBox.warning(
                self, "Access Denied",
                f"Your role ({role.title()}) does not have access to this section."
            )
            return

        # Highlight active button
        for i, btn in enumerate(self._nav_buttons):
            btn.set_active(i == index)

        # Lazy-load the module widget
        if index not in self._modules_loaded:
            widget = self._load_module(index)
            if widget:
                old = self._slot_widgets.get(index)
                if old is not None:
                    stack_pos = self._stack.indexOf(old)
                    self._stack.removeWidget(old)
                    self._stack.insertWidget(stack_pos, widget)
                else:
                    self._stack.addWidget(widget)
                self._slot_widgets[index] = widget
                self._modules_loaded[index] = widget

        target = self._slot_widgets.get(index)
        if target is not None:
            self._stack.setCurrentWidget(target)
            # Refresh data-heavy modules when switching to them
            if hasattr(target, "refresh"):
                target.refresh()

    def _load_module(self, index: int) -> QWidget:
        try:
            if index == 0:
                from modules.pos.pos_widget import POSWidget
                return POSWidget(self.config, self.db, self.shopify_service)
            elif index == 1:
                from modules.inventory.inventory_widget import InventoryWidget
                return InventoryWidget(self.config, self.db, self.shopify_service)
            elif index == 2:
                from modules.customers.customers_widget import CustomersWidget
                return CustomersWidget(self.config, self.db)
            elif index == 3:
                from modules.reports.reports_widget import ReportsWidget
                return ReportsWidget(self.config, self.db)
            elif index == 4:
                from modules.settings.settings_widget import SettingsWidget
                w = SettingsWidget(self.config, self.db, current_user=self.current_user)
                w.settings_saved.connect(self._on_settings_saved)
                return w
        except Exception as e:
            import traceback
            err = QLabel(f"Error loading module:\n{traceback.format_exc()}")
            err.setStyleSheet("color: #f87171; padding: 20px;")
            err.setWordWrap(True)
            return err
        return QWidget()

    # ------------------------------------------------------------------ #
    #  Logout                                                              #
    # ------------------------------------------------------------------ #
    def _on_logout(self):
        reply = QMessageBox.question(
            self, "Logout",
            f"Log out as {self.current_user.get('full_name', 'User')}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.logout_requested.emit()

    # ------------------------------------------------------------------ #
    #  Theme                                                               #
    # ------------------------------------------------------------------ #
    def _apply_theme(self):
        theme = self.config.get("theme", "dark")
        self.setStyleSheet(get_stylesheet(theme))

    # ------------------------------------------------------------------ #
    #  Clock                                                               #
    # ------------------------------------------------------------------ #
    def _start_clock(self):
        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self._update_clock)
        self._clock_timer.start(1000)
        self._update_clock()

    @pyqtSlot()
    def _update_clock(self):
        now = datetime.now().strftime("%a %d %b %Y  %H:%M:%S")
        self._status_time.setText(now)

    # ------------------------------------------------------------------ #
    #  Shopify status                                                      #
    # ------------------------------------------------------------------ #
    def set_shopify_status(self, text: str, ok: bool = True):
        color = "#4ade80" if ok else "#f87171"
        self._status_sync.setText(f"● {text}")
        self._status_sync.setStyleSheet(f"color: {color}; font-size: 11px;")

    # ------------------------------------------------------------------ #
    #  Sync pause / resume                                                 #
    # ------------------------------------------------------------------ #
    @pyqtSlot()
    def _toggle_sync_pause(self):
        if not self.shopify_service:
            return
        if self.shopify_service.is_running:
            # Pause – non-blocking so the UI stays responsive
            self.shopify_service.pause()
            self.set_shopify_status("Sync paused", False)
        else:
            # Resume – creates a fresh worker & thread
            self.shopify_service.resume()
            # Wire up the new worker's signals
            worker = self.shopify_service.worker
            if worker:
                worker.status_changed.connect(
                    lambda txt: self.set_shopify_status(txt, "error" not in txt.lower())
                )
                worker.sync_error.connect(
                    lambda err: self.set_shopify_status(f"Sync error: {err[:40]}", False)
                )
            self.set_shopify_status("Sync resumed…", True)
        self._update_sync_pause_btn()

    def _update_sync_pause_btn(self):
        """Show / hide the button and update its label to match actual state."""
        enabled = self.config.get("shopify_enabled", False) and self.shopify_service is not None
        self._sync_pause_btn.setVisible(enabled)
        if not enabled:
            return
        if self.shopify_service.is_running:
            self._sync_pause_btn.setText("⏸  Pause Sync")
            self._sync_pause_btn.setToolTip("Pause the automatic background sync with Shopify")
            self._sync_pause_btn.setStyleSheet(
                "QPushButton { background: #1e293b; color: #94a3b8; border: 1px solid #334155; "
                "border-radius: 4px; padding: 0 8px; font-size: 11px; } "
                "QPushButton:hover { background: #334155; color: #f1f5f9; }"
            )
        else:
            self._sync_pause_btn.setText("▶  Resume Sync")
            self._sync_pause_btn.setToolTip("Resume the automatic background sync with Shopify")
            self._sync_pause_btn.setStyleSheet(
                "QPushButton { background: #1e293b; color: #f59e0b; border: 1px solid #f59e0b; "
                "border-radius: 4px; padding: 0 8px; font-size: 11px; } "
                "QPushButton:hover { background: #f59e0b; color: #0f172a; }"
            )

    # ------------------------------------------------------------------ #
    #  Settings reload                                                     #
    # ------------------------------------------------------------------ #
    @pyqtSlot()
    def _on_settings_saved(self):
        self._setup_window()
        self._apply_theme()
        # Refresh sidebar title, subtitle, and logo
        self._update_sidebar_logo()
        for w in self._sidebar.findChildren(QLabel):
            if w.objectName() == "AppTitle":
                w.setText(self.config.get("app_name", "CanadaMart POS"))
            elif w.objectName() == "AppSubtitle":
                w.setText(self.config.get("business_name", ""))
        # Restart Shopify sync with the new settings
        if self.shopify_service:
            self.shopify_service.stop()
            if self.config.get("shopify_enabled", False):
                self.shopify_service.start()
                # Reconnect the new worker's signals to the status bar
                worker = self.shopify_service.worker
                if worker:
                    worker.status_changed.connect(
                        lambda txt: self.set_shopify_status(txt, "error" not in txt.lower())
                    )
                    worker.sync_error.connect(
                        lambda err: self.set_shopify_status(f"Sync error: {err[:40]}", False)
                    )
                self.set_shopify_status("Shopify enabled \u2013 sync starting\u2026", True)
            else:
                self.set_shopify_status("Shopify not configured", False)
        # Unload all modules: replace each loaded slot with a fresh placeholder
        for idx in list(self._modules_loaded.keys()):
            old = self._slot_widgets.get(idx)
            if old is not None:
                stack_pos = self._stack.indexOf(old)
                self._stack.removeWidget(old)
                placeholder = QWidget()
                self._stack.insertWidget(stack_pos, placeholder)
                self._slot_widgets[idx] = placeholder
        self._modules_loaded.clear()
        # Re-navigate to the first allowed module
        role = self.current_user.get("role", "cashier")
        allowed = ROLE_ACCESS.get(role, {0})
        self._navigate(min(allowed))
        self._update_sync_pause_btn()

    def closeEvent(self, event):
        if self.shopify_service:
            self.shopify_service.stop()
        super().closeEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            if self.isFullScreen():
                self.showMaximized()
            else:
                self.showFullScreen()
        else:
            super().keyPressEvent(event)
