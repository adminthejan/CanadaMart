"""Two-way Shopify ↔ Local inventory sync service."""
import threading
import time
from datetime import datetime, timezone
from typing import Optional, Dict, List, Callable

from PyQt6.QtCore import QObject, pyqtSignal, QThread


class ShopifySyncWorker(QObject):
    """
    Runs Shopify sync in a background QThread.
    Emits signals so the UI can react safely.
    """

    sync_started = pyqtSignal()
    sync_finished = pyqtSignal(int, int)   # pushed, pulled
    sync_error = pyqtSignal(str)
    product_synced = pyqtSignal(str)        # product name
    status_changed = pyqtSignal(str)

    def __init__(self, config, db):
        super().__init__()
        self.config = config
        self.db = db
        self._shopify = None
        self._location_id: Optional[str] = None
        self._stop_flag = threading.Event()
        self._interval = int(config.get("shopify_sync_interval", 300))

    # ------------------------------------------------------------------ #
    #  Shopify session                                                     #
    # ------------------------------------------------------------------ #
    def _init_shopify(self) -> bool:
        try:
            import shopify as shopify_lib
            shop_url = self.config.get("shopify_shop_url", "").strip().rstrip("/")
            token = self.config.get("shopify_access_token", "").strip()
            api_version = self.config.get("shopify_api_version", "2024-01")
            if not shop_url or not token:
                return False
            if not shop_url.startswith("https://"):
                shop_url = f"https://{shop_url}"
            shopify_lib.ShopifyResource.set_site(
                f"{shop_url}/admin/api/{api_version}"
            )
            shopify_lib.ShopifyResource.set_headers(
                {"X-Shopify-Access-Token": token}
            )
            self._shopify = shopify_lib
            # Cache location id
            loc_id = self.config.get("shopify_location_id", "")
            if not loc_id:
                locs = shopify_lib.Location.find()
                if locs:
                    loc_id = str(locs[0].id)
                    self.config.set("shopify_location_id", loc_id)
            self._location_id = loc_id
            return True
        except ImportError:
            self.sync_error.emit("ShopifyAPI package not installed.")
            return False
        except Exception as e:
            self.sync_error.emit(f"Shopify init error: {e}")
            return False

    # ------------------------------------------------------------------ #
    #  Main loop                                                           #
    # ------------------------------------------------------------------ #
    def run(self):
        """Called by QThread.start() → runs the auto-sync loop."""
        if not self.config.get("shopify_enabled", False):
            return
        if not self._init_shopify():
            return
        while not self._stop_flag.is_set():
            self._do_sync()
            for _ in range(self._interval):
                if self._stop_flag.is_set():
                    return
                time.sleep(1)

    def stop(self):
        self._stop_flag.set()

    # ------------------------------------------------------------------ #
    #  Full bidirectional sync                                             #
    # ------------------------------------------------------------------ #
    def _do_sync(self):
        self.sync_started.emit()
        self.status_changed.emit("Syncing with Shopify…")
        pushed = 0
        pulled = 0
        try:
            pushed = self._push_to_shopify()
            pulled = self._pull_from_shopify()
            self.db.log_sync("full", "success", pushed + pulled,
                             f"Pushed {pushed}, Pulled {pulled}")
            self.sync_finished.emit(pushed, pulled)
            self.status_changed.emit(
                f"Sync complete – {datetime.now().strftime('%H:%M')}"
            )
        except Exception as e:
            msg = f"Sync error: {e}"
            self.sync_error.emit(msg)
            self.db.log_sync("full", "error", 0, msg)
            self.status_changed.emit("Sync failed")

    # ------------------------------------------------------------------ #
    #  Push LOCAL → Shopify                                                #
    # ------------------------------------------------------------------ #
    def _push_to_shopify(self) -> int:
        """Push unsynced local products to Shopify."""
        count = 0
        unsynced = self.db.get_unsynced_products()
        for product in unsynced:
            try:
                if product.get("shopify_id"):
                    # Update existing
                    sp = self._shopify.Product.find(product["shopify_id"])
                    if sp:
                        sp.title = product["name"]
                        sp.body_html = product.get("description", "")
                        v = sp.variants[0]
                        v.price = str(product["price"])
                        v.sku = product.get("sku", "")
                        v.barcode = product.get("barcode", "")
                        sp.save()
                        self._update_inventory_level(
                            product["shopify_inventory_item_id"],
                            product["quantity"]
                        )
                else:
                    # Create new
                    sp = self._create_shopify_product(product)
                    if sp:
                        variant = sp.variants[0]
                        self.db.update_product(product["id"], {
                            "shopify_id": str(sp.id),
                            "shopify_variant_id": str(variant.id),
                            "shopify_inventory_item_id": str(variant.inventory_item_id),
                            "shopify_synced": 1,
                            "last_synced": datetime.now(timezone.utc).isoformat(),
                        })
                        self._update_inventory_level(
                            str(variant.inventory_item_id),
                            product["quantity"]
                        )
                        self.product_synced.emit(product["name"])

                self.db.update_product(product["id"], {
                    "shopify_synced": 1,
                    "last_synced": datetime.now(timezone.utc).isoformat(),
                })
                count += 1
            except Exception as e:
                print(f"[Shopify] Push error for '{product['name']}': {e}")
        return count

    def _create_shopify_product(self, product: Dict):
        """Create a new Shopify product from a local product."""
        sp = self._shopify.Product()
        sp.title = product["name"]
        sp.body_html = product.get("description", "")
        sp.product_type = product.get("category_name", "")
        sp.vendor = self.config.get("business_name", "")

        variant = self._shopify.Variant()
        variant.price = str(product["price"])
        variant.sku = product.get("sku", "")
        variant.barcode = product.get("barcode", "")
        variant.inventory_management = "shopify"
        variant.inventory_policy = "deny"

        sp.variants = [variant]
        sp.save()
        return sp if sp.id else None

    def _update_inventory_level(self, inventory_item_id: str, quantity: int):
        if not self._location_id or not inventory_item_id:
            return
        try:
            self._shopify.InventoryLevel.set(
                location_id=self._location_id,
                inventory_item_id=inventory_item_id,
                available=max(0, quantity),
            )
        except Exception as e:
            print(f"[Shopify] Inventory level error: {e}")

    # ------------------------------------------------------------------ #
    #  Pull Shopify → LOCAL                                                #
    # ------------------------------------------------------------------ #
    def _pull_from_shopify(self) -> int:
        """Pull products changed in Shopify since last sync and update local DB."""
        count = 0
        try:
            # Get products updated in Shopify
            shopify_products = self._shopify.Product.find(limit=250)
            for sp in shopify_products:
                local = self.db.get_product_by_shopify_id(str(sp.id))
                variant = sp.variants[0] if sp.variants else None
                if not variant:
                    continue

                price = float(getattr(variant, "price", 0) or 0)
                sku = getattr(variant, "sku", "") or ""
                barcode = getattr(variant, "barcode", "") or ""

                # Get inventory level
                inv_levels = self._shopify.InventoryLevel.find(
                    inventory_item_ids=str(variant.inventory_item_id),
                    location_ids=self._location_id,
                )
                qty = 0
                if inv_levels:
                    qty = int(getattr(inv_levels[0], "available", 0) or 0)

                if local:
                    # Update existing local product
                    self.db.update_product(local["id"], {
                        "name": sp.title,
                        "description": getattr(sp, "body_html", "") or "",
                        "price": price,
                        "sku": sku,
                        "barcode": barcode,
                        "quantity": qty,
                        "shopify_synced": 1,
                        "last_synced": datetime.now(timezone.utc).isoformat(),
                    })
                else:
                    # Add new local product
                    new_id = self.db.add_product({
                        "name": sp.title,
                        "description": getattr(sp, "body_html", "") or "",
                        "price": price,
                        "sku": sku,
                        "barcode": barcode,
                        "quantity": qty,
                        "shopify_id": str(sp.id),
                        "shopify_variant_id": str(variant.id),
                        "shopify_inventory_item_id": str(variant.inventory_item_id),
                        "shopify_synced": 1,
                    })
                    self.product_synced.emit(sp.title)
                count += 1
        except Exception as e:
            print(f"[Shopify] Pull error: {e}")
        return count

    # ------------------------------------------------------------------ #
    #  On-demand sync after sale                                           #
    # ------------------------------------------------------------------ #
    def sync_stock_after_sale(self, items: List[Dict]):
        """
        Called immediately after a sale to push stock deductions to Shopify.
        Runs in a short-lived thread.
        """
        if not self.config.get("shopify_enabled", False):
            return
        if not self.config.get("shopify_sync_inventory", True):
            return

        def _run():
            if not self._init_shopify():
                return
            for item in items:
                pid = item.get("product_id")
                if not pid:
                    continue
                product = self.db.get_product(pid)
                if not product or not product.get("shopify_inventory_item_id"):
                    continue
                self._update_inventory_level(
                    product["shopify_inventory_item_id"],
                    product["quantity"],
                )

        t = threading.Thread(target=_run, daemon=True)
        t.start()


class ShopifySyncService:
    """
    High-level facade that manages the sync QThread lifecycle.
    """

    def __init__(self, config, db):
        self.config = config
        self.db = db
        self._thread: Optional[QThread] = None
        self._worker: Optional[ShopifySyncWorker] = None

    def start(self):
        if not self.config.get("shopify_enabled", False):
            return
        if self._thread and self._thread.isRunning():
            return
        self._thread = QThread()
        self._worker = ShopifySyncWorker(self.config, self.db)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._thread.start()

    def stop(self):
        if self._worker:
            self._worker.stop()
        if self._thread:
            self._thread.quit()
            self._thread.wait(5000)

    def trigger_sync(self):
        """Manually trigger a one-shot sync."""
        if not self.config.get("shopify_enabled", False):
            return
        if self._worker:
            threading.Thread(target=self._worker._do_sync, daemon=True).start()
        else:
            worker = ShopifySyncWorker(self.config, self.db)
            threading.Thread(target=lambda: (
                worker._init_shopify() and worker._do_sync()
            ), daemon=True).start()

    def sync_stock_after_sale(self, items: List[Dict]):
        if self._worker:
            self._worker.sync_stock_after_sale(items)

    @property
    def worker(self) -> Optional[ShopifySyncWorker]:
        return self._worker
