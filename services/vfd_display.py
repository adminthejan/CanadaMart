"""VFD (Vacuum Fluorescent Display) customer display service."""
import threading
import time
from typing import Optional


class VFDDisplay:
    """
    Drives a customer-facing VFD display via serial port.
    Supports Epson, Bixolon and generic ESC/POS-compatible displays.
    Falls back to no-op when serial is unavailable or disabled.
    """

    # VFD type command profiles
    PROFILES = {
        "epson": {
            "init": b"\x1b\x40",
            "clear": b"\x0c",
            "move_home": b"\x0b",
            "move_line2": b"\x0c\x0b",
            "brightness": b"\x1b\x60\x04",
        },
        "bixolon": {
            "init": b"\x1b\x40",
            "clear": b"\x0c",
            "move_home": b"\x1b\x48",
            "move_line2": b"\x1b\x4c",
            "brightness": b"",
        },
        "generic": {
            "init": b"\x1b\x40",
            "clear": b"\x0c",
            "move_home": b"\x0b",
            "move_line2": b"\x0c\x0b",
            "brightness": b"",
        },
    }

    def __init__(self, config):
        self.config = config
        self._serial = None
        self._lock = threading.Lock()
        self._connected = False
        self._cols = config.get("vfd_cols", 20)
        self._rows = config.get("vfd_rows", 2)
        self._type = config.get("vfd_type", "epson")
        self._profile = self.PROFILES.get(self._type, self.PROFILES["generic"])

    # ------------------------------------------------------------------ #
    #  Connection                                                          #
    # ------------------------------------------------------------------ #
    def connect(self) -> bool:
        if not self.config.get("vfd_enabled", False):
            return False
        try:
            import serial
            port = self.config.get("vfd_port", "COM1")
            baud = int(self.config.get("vfd_baudrate", 9600))
            self._serial = serial.Serial(port, baud, timeout=1)
            self._connected = True
            self._send(self._profile["init"])
            self._send(self._profile.get("brightness", b""))
            self.show_welcome()
            return True
        except Exception as e:
            print(f"[VFD] Connect failed: {e}")
            self._connected = False
            return False

    def disconnect(self):
        if self._serial and self._serial.is_open:
            try:
                self.clear()
                self._serial.close()
            except Exception:
                pass
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    # ------------------------------------------------------------------ #
    #  Primitives                                                          #
    # ------------------------------------------------------------------ #
    def _send(self, data: bytes):
        if self._serial and self._serial.is_open:
            with self._lock:
                try:
                    self._serial.write(data)
                except Exception as e:
                    print(f"[VFD] Write error: {e}")

    def _pad(self, text: str) -> bytes:
        return text.ljust(self._cols)[: self._cols].encode("ascii", errors="replace")

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #
    def clear(self):
        self._send(self._profile["clear"])

    def show_welcome(self):
        line1 = self.config.get("vfd_welcome_line1", "Welcome!")
        line2 = self.config.get("vfd_welcome_line2", "Please wait...")
        self.display_two_lines(line1, line2)

    def display_two_lines(self, line1: str, line2: str):
        self._send(self._profile["move_home"])
        self._send(self._pad(line1))
        self._send(self._profile["move_line2"])
        self._send(self._pad(line2))

    def show_item(self, name: str, price: float, currency_symbol: str = "$"):
        line1 = name[: self._cols]
        line2 = f"{currency_symbol}{price:.2f}".rjust(self._cols)
        self.display_two_lines(line1, line2)

    def show_total(self, total: float, currency_symbol: str = "$"):
        line1 = "TOTAL AMOUNT"
        line2 = f"{currency_symbol}{total:.2f}".rjust(self._cols)
        self.display_two_lines(line1, line2)

    def show_change(self, change: float, currency_symbol: str = "$"):
        line1 = "CHANGE DUE"
        line2 = f"{currency_symbol}{change:.2f}".rjust(self._cols)
        self.display_two_lines(line1, line2)

    def show_thank_you(self):
        self.display_two_lines("  THANK YOU!  ", " Have a nice day ")
        time.sleep(3)
        self.show_welcome()

    def show_message(self, line1: str, line2: str = ""):
        self.display_two_lines(line1, line2)
