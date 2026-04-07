"""
CanadaMart POS – Application entry point.
"""
import sys
import os

# ── Make sure the project root is in Python path ─────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# ── Use certifi CA bundle for ALL SSL connections (inc. third-party libs) ─
try:
    import certifi
    os.environ.setdefault("SSL_CERT_FILE", certifi.where())
    os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())
except ImportError:
    pass

# Suppress the harmless Qt/X11 clipboard-manager timeout warning on Linux
os.environ.setdefault("QT_LOGGING_RULES", "qt.qpa.clipboard=false")

from PyQt6.QtWidgets import QApplication, QSplashScreen, QLabel
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPixmap, QColor, QFont, QPainter

from config.app_config import AppConfig
from database.db_manager import DatabaseManager
from services.shopify_sync import ShopifySyncService
from ui.login_dialog import LoginDialog
from ui.main_window import MainWindow
from ui.styles import get_stylesheet


def build_splash(config: AppConfig) -> QSplashScreen:
    """Create a simple branded splash screen."""
    pix = QPixmap(480, 280)
    pix.fill(QColor("#0f172a"))

    painter = QPainter(pix)
    painter.setPen(QColor("#f1f5f9"))

    font_big = QFont("Segoe UI", 28, QFont.Weight.Bold)
    font_sub = QFont("Segoe UI", 12)

    logo_path = config.get("logo_path", "")
    if logo_path and os.path.exists(logo_path):
        logo = QPixmap(logo_path)
        if not logo.isNull():
            logo = logo.scaled(
                200, 80, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            painter.drawPixmap((480 - logo.width()) // 2, 40, logo)
            y_start = 140
        else:
            y_start = 80
    else:
        y_start = 80

    painter.setFont(font_big)
    name = config.get("app_name", "CanadaMart POS")
    painter.drawText(pix.rect().adjusted(0, y_start, 0, 0),
                     Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, name)

    painter.setFont(font_sub)
    painter.setPen(QColor("#94a3b8"))
    desc = config.get("app_description", "Point of Sale System")
    painter.drawText(pix.rect().adjusted(0, y_start + 50, 0, 0),
                     Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, desc)

    painter.setPen(QColor("#3b82f6"))
    biz = config.get("business_name", "")
    if biz:
        painter.drawText(pix.rect().adjusted(0, y_start + 80, 0, 0),
                         Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, biz)

    painter.setPen(QColor("#475569"))
    painter.setFont(QFont("Segoe UI", 9))
    painter.drawText(pix.rect().adjusted(0, 0, 0, -12),
                     Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom,
                     "Loading, please wait…")
    painter.end()

    splash = QSplashScreen(pix)
    splash.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint)
    return splash


def main():
    # ── High-DPI support ─────────────────────────────────────────────────
    os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")

    app = QApplication(sys.argv)

    # Allow Ctrl+C to cleanly quit instead of causing SIGABRT
    import signal
    signal.signal(signal.SIGINT, lambda *_: app.quit())
    app.setApplicationName("CanadaMart POS")
    app.setOrganizationName("CanadaMart")
    app.setStyle("Fusion")

    # ── Config ───────────────────────────────────────────────────────────
    config = AppConfig()
    app.setApplicationName(config.get("app_name", "CanadaMart POS"))

    # Apply theme early so splash looks right
    app.setStyleSheet(get_stylesheet(config.get("theme", "dark")))

    # ── Splash ───────────────────────────────────────────────────────────
    splash = build_splash(config)
    splash.show()
    app.processEvents()

    # ── Database ─────────────────────────────────────────────────────────
    db = DatabaseManager()
    db.initialize()

    # ── Shopify sync service ──────────────────────────────────────────────
    shopify_service = ShopifySyncService(config, db)

    # ── Login ─────────────────────────────────────────────────────────────
    splash.finish(None)   # hide splash before showing login

    def _launch_main(user: dict):
        """Build and show main window for the authenticated user."""
        window = MainWindow(config, db, shopify_service, current_user=user)

        if config.get("shopify_enabled", False):
            window.set_shopify_status("Shopify enabled – starting sync…", True)
            shopify_service.start()
            # Connect signals AFTER start() so the worker object exists.
            if shopify_service.worker:
                shopify_service.worker.status_changed.connect(
                    lambda txt: window.set_shopify_status(txt, "error" not in txt.lower())
                )
                shopify_service.worker.sync_error.connect(
                    lambda err: window.set_shopify_status(f"Sync error: {err[:40]}", False)
                )
        else:
            window.set_shopify_status("Shopify not configured", False)

        window.show()
        window.showFullScreen()

        # Connect logout signal to re-show login
        window.logout_requested.connect(lambda: _show_login(window))

    def _show_login(old_window=None):
        """Show login dialog; on success open a fresh main window."""
        if old_window:
            shopify_service.stop()
            old_window.close()

        login = LoginDialog(config, db)
        if login.exec() == LoginDialog.DialogCode.Accepted and login.user:
            _launch_main(login.user)
        else:
            # User closed login dialog → quit
            app.quit()

    _show_login()

    exit_code = app.exec()

    # Cleanup
    shopify_service.stop()

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
