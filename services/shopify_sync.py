"""Two-way Shopify ↔ Local inventory sync service."""
import threading
import time
from datetime import datetime, timezone
from typing import Optional, Dict, List, Callable

from PyQt6.QtCore import QObject, pyqtSignal


class _SyncStopped(Exception):
    """Raised by _api_call when the stop flag is set; always propagates up."""


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
        self._token_expires_at: float = 0.0   # Unix timestamp; 0 = not fetched yet

    # ------------------------------------------------------------------ #
    #  Token helpers (OAuth client credentials)                            #
    # ------------------------------------------------------------------ #
    def _fetch_token_via_oauth(self) -> Optional[str]:
        """POST to /admin/oauth/access_token with client_credentials grant.
        Returns the access token string, or None on failure."""
        import urllib.request, urllib.parse, json
        shop_url = self.config.get("shopify_shop_url", "").strip().rstrip("/")
        client_id = self.config.get("shopify_client_id", "").strip()
        client_secret = self.config.get("shopify_client_secret", "").strip()
        if not shop_url or not client_id or not client_secret:
            return None
        if not shop_url.startswith("https://"):
            shop_url = f"https://{shop_url}"
        url = f"{shop_url}/admin/oauth/access_token"
        data = urllib.parse.urlencode({
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        }).encode()
        req = urllib.request.Request(
            url, data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read())
        token = body.get("access_token", "")
        expires_in = int(body.get("expires_in", 86399))
        self._token_expires_at = time.time() + expires_in - 60   # 1-min safety buffer
        return token or None

    def _ensure_token_fresh(self) -> bool:
        """Re-apply a fresh token when using OAuth client credentials.
        No-op (returns True) when a static shpat_ token is configured."""
        client_id = self.config.get("shopify_client_id", "").strip()
        client_secret = self.config.get("shopify_client_secret", "").strip()
        if not client_id or not client_secret:
            return True                          # static token, never expires
        if time.time() < self._token_expires_at:
            return True                          # OAuth token still valid
        try:
            token = self._fetch_token_via_oauth()
            if not token:
                self.sync_error.emit("Shopify token refresh failed: no token returned.")
                return False
            shop_url = self.config.get("shopify_shop_url", "").strip().rstrip("/")
            if not shop_url.startswith("https://"):
                shop_url = f"https://{shop_url}"
            api_version = self.config.get("shopify_api_version", "2026-01")
            self._shopify.ShopifyResource.set_site(f"{shop_url}/admin/api/{api_version}")
            self._shopify.ShopifyResource.set_headers({"X-Shopify-Access-Token": token})
            return True
        except Exception as e:
            self.sync_error.emit(f"Token refresh error: {e}")
            return False

    # ------------------------------------------------------------------ #
    #  Shopify session                                                     #
    # ------------------------------------------------------------------ #
    def _init_shopify(self) -> bool:
        try:
            import shopify as shopify_lib
            shop_url = self.config.get("shopify_shop_url", "").strip().rstrip("/")
            api_version = self.config.get("shopify_api_version", "2026-01")
            if not shop_url:
                return False

            # Prefer OAuth client credentials; fall back to static token
            client_id = self.config.get("shopify_client_id", "").strip()
            client_secret = self.config.get("shopify_client_secret", "").strip()
            if client_id and client_secret:
                token = self._fetch_token_via_oauth()
                if not token:
                    self.sync_error.emit("Could not obtain Shopify token via OAuth.")
                    return False
            else:
                token = self.config.get("shopify_access_token", "").strip()
                if not token:
                    self.sync_error.emit("No Shopify credentials configured.")
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
    #  Rate-limit-aware API call wrapper                                   #
    # ------------------------------------------------------------------ #
    def _api_call(self, fn, *args, max_retries: int = 5, **kwargs):
        """
        Call any Shopify API function with automatic 429 back-off.
        Sleeps 0.5 s between every successful call to stay inside the
        2-req/s leaky-bucket limit. On a 429 it reads the Retry-After
        header (default 2 s) and waits before retrying.
        Raises the last exception if all retries are exhausted.
        """
        import re as _re
        for attempt in range(max_retries):
            if self._stop_flag.is_set():
                raise _SyncStopped()
            try:
                result = fn(*args, **kwargs)
                time.sleep(0.5)   # steady-state ~2 req/s
                return result
            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "Too Many Requests" in err_str:
                    # Parse Retry-After if present in the error string
                    retry_after = 2.0
                    m = _re.search(r"Retry-After[^0-9]*([0-9]+(?:\.[0-9]+)?)", err_str)
                    if m:
                        retry_after = float(m.group(1))
                    wait = retry_after + attempt * 2   # escalate on repeated 429s
                    self.status_changed.emit(
                        f"Rate limited \u2013 waiting {int(wait)} s\u2026"
                    )
                    time.sleep(wait)
                    continue   # retry
                raise          # any other error propagates immediately
        raise RuntimeError(
            f"Shopify API still rate-limited after {max_retries} attempts."
        )

    # ------------------------------------------------------------------ #
    #  Full bidirectional sync                                             #
    # ------------------------------------------------------------------ #
    def _do_sync(self):
        if not self._ensure_token_fresh():
            return
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
        except _SyncStopped:
            return   # stopped cleanly – not an error
        except Exception as e:
            err_str = str(e)
            # On a 401 / Unauthorized, re-initialise the Shopify session
            # (fetches a fresh token) and retry the full sync once.
            if "401" in err_str or "Unauthorized" in err_str:
                self.status_changed.emit("Token expired – re-authenticating…")
                if self._init_shopify():
                    try:
                        pushed = self._push_to_shopify()
                        pulled = self._pull_from_shopify()
                        self.db.log_sync("full", "success", pushed + pulled,
                                         f"Pushed {pushed}, Pulled {pulled}")
                        self.sync_finished.emit(pushed, pulled)
                        self.status_changed.emit(
                            f"Sync complete – {datetime.now().strftime('%H:%M')}"
                        )
                        return
                    except Exception as retry_err:
                        err_str = str(retry_err)
            msg = f"Sync error: {err_str}"
            self.sync_error.emit(msg)
            self.db.log_sync("full", "error", 0, msg)
            self.status_changed.emit("Sync failed")

    # ------------------------------------------------------------------ #
    #  Push LOCAL → Shopify                                                #
    # ------------------------------------------------------------------ #
    def _push_to_shopify(self) -> int:
        """Push unsynced local products (and their variants) to Shopify."""
        count = 0
        unsynced = self.db.get_unsynced_products()
        for product in unsynced:
            try:
                variants = self.db.get_variants(product["id"])
                sp = None
                if product.get("shopify_id"):
                    sp = self._api_call(
                        self._shopify.Product.find, product["shopify_id"]
                    )
                    if sp:
                        sp.title = product["name"]
                        sp.body_html = product.get("description", "")
                        sp.product_type = product.get("category_name", "") or ""
                        if variants:
                            sp.variants = self._build_shopify_variants(variants)
                        else:
                            v = sp.variants[0]
                            v.price = str(product["price"])
                            v.sku = product.get("sku", "") or ""
                            v.barcode = product.get("barcode", "") or ""
                        self._api_call(sp.save)
                        # Sync inventory for each variant
                        if variants:
                            for lv, sv in zip(variants, sp.variants):
                                self._update_inventory_level(
                                    str(sv.inventory_item_id), lv["quantity"]
                                )
                        else:
                            self._update_inventory_level(
                                product.get("shopify_inventory_item_id", ""),
                                product["quantity"],
                            )
                else:
                    sp = self._create_shopify_product(product, variants)
                    if sp:
                        self._save_shopify_ids_back(product["id"], sp, variants)
                        self.product_synced.emit(product["name"])

                # Link product to its Shopify collection (create collection if needed)
                if sp and product.get("category_id"):
                    col_id = self._ensure_collection_pushed(product["category_id"])
                    if col_id:
                        self._link_product_to_collection(str(sp.id), col_id)

                self.db.update_product(product["id"], {
                    "shopify_synced": 1,
                    "last_synced": datetime.now(timezone.utc).isoformat(),
                })
                count += 1
            except _SyncStopped:
                raise
            except Exception as e:
                err_str = str(e)
                if "401" in err_str or "Unauthorized" in err_str:
                    raise
                print(f"[Shopify] Push error for '{product['name']}': {e}")
        return count

    def _ensure_collection_pushed(self, category_id: int) -> Optional[str]:
        """
        Ensure the local category exists as a Shopify CustomCollection.
        Creates it on Shopify if not yet synced; returns the shopify_collection_id.
        """
        cat = self.db.get_category(category_id)
        if not cat:
            return None
        if cat.get("shopify_collection_id"):
            return cat["shopify_collection_id"]
        # Create the collection on Shopify
        try:
            col = self._shopify.CustomCollection()
            col.title = cat["name"]
            self._api_call(col.save)
            if not col.id:
                return None
            col_id_str = str(col.id)
            self.db.update_category(
                cat["id"], cat["name"], cat.get("color", "#3B82F6"), col_id_str
            )
            return col_id_str
        except _SyncStopped:
            raise
        except Exception as e:
            err_str = str(e)
            if "401" in err_str or "Unauthorized" in err_str:
                raise
            print(f"[Shopify] Could not create collection '{cat['name']}': {e}")
            return None

    def _link_product_to_collection(self, shopify_product_id: str, shopify_collection_id: str):
        """
        Create a Collect join between a Shopify product and a CustomCollection.
        Silently ignores 422 (already collected).
        """
        try:
            collect = self._shopify.Collect()
            collect.product_id = int(shopify_product_id)
            collect.collection_id = int(shopify_collection_id)
            self._api_call(collect.save)
        except _SyncStopped:
            raise
        except Exception as e:
            err_str = str(e)
            if "401" in err_str or "Unauthorized" in err_str:
                raise
            # 422 means the product is already in the collection – that's fine
            if "422" in err_str or "already" in err_str.lower():
                return
            print(f"[Shopify] Could not link product {shopify_product_id} "
                  f"to collection {shopify_collection_id}: {e}")

    def _build_shopify_variants(self, local_variants: list) -> list:
        """Convert local variant dicts into Shopify Variant objects."""
        out = []
        for lv in local_variants:
            sv = self._shopify.Variant()
            sv.price = str(lv["price"])
            sv.sku = lv.get("sku", "") or ""
            sv.barcode = lv.get("barcode", "") or ""
            sv.inventory_management = "shopify"
            sv.inventory_policy = "deny"
            if lv.get("option1_value"):
                sv.option1 = lv["option1_value"]
            if lv.get("option2_value"):
                sv.option2 = lv["option2_value"]
            if lv.get("option3_value"):
                sv.option3 = lv["option3_value"]
            if lv.get("shopify_variant_id"):
                sv.id = int(lv["shopify_variant_id"])
            out.append(sv)
        return out

    def _save_shopify_ids_back(self, product_id: int, sp, local_variants: list):
        """Write Shopify IDs back to local DB after create/push."""
        if local_variants:
            for lv, sv in zip(local_variants, sp.variants):
                self.db.update_variant(lv["id"], {
                    "shopify_variant_id": str(sv.id),
                    "shopify_inventory_item_id": str(sv.inventory_item_id),
                })
                self._update_inventory_level(
                    str(sv.inventory_item_id), lv["quantity"]
                )
            # Store first variant IDs on the parent product as well
            first = sp.variants[0]
            self.db.update_product(product_id, {
                "shopify_id": str(sp.id),
                "shopify_variant_id": str(first.id),
                "shopify_inventory_item_id": str(first.inventory_item_id),
                "shopify_synced": 1,
                "last_synced": datetime.now(timezone.utc).isoformat(),
            })
        else:
            variant = sp.variants[0]
            self.db.update_product(product_id, {
                "shopify_id": str(sp.id),
                "shopify_variant_id": str(variant.id),
                "shopify_inventory_item_id": str(variant.inventory_item_id),
                "shopify_synced": 1,
                "last_synced": datetime.now(timezone.utc).isoformat(),
            })
            self._update_inventory_level(
                str(variant.inventory_item_id),
                self.db.get_product(product_id)["quantity"],
            )

    def _create_shopify_product(self, product: dict, variants: list = None):
        """Create a new Shopify product from a local product."""
        sp = self._shopify.Product()
        sp.title = product["name"]
        sp.body_html = product.get("description", "")
        sp.product_type = product.get("category_name", "")
        sp.vendor = self.config.get("business_name", "")

        if variants:
            # Build option names from the first variant that has options
            option_names = []
            for lv in variants:
                if lv.get("option1_name") and lv["option1_name"] not in option_names:
                    option_names.append(lv["option1_name"])
                if lv.get("option2_name") and lv["option2_name"] not in option_names:
                    option_names.append(lv["option2_name"])
                if lv.get("option3_name") and lv["option3_name"] not in option_names:
                    option_names.append(lv["option3_name"])
            if option_names:
                sp.options = [{"name": n} for n in option_names]
            sp.variants = self._build_shopify_variants(variants)
        else:
            variant = self._shopify.Variant()
            variant.price = str(product["price"])
            variant.sku = product.get("sku", "") or ""
            variant.barcode = product.get("barcode", "") or ""
            variant.inventory_management = "shopify"
            variant.inventory_policy = "deny"
            sp.variants = [variant]

        self._api_call(sp.save)
        return sp if sp.id else None

    def _update_inventory_level(self, inventory_item_id: str, quantity: int):
        if not self._location_id or not inventory_item_id:
            return
        try:
            self._api_call(
                self._shopify.InventoryLevel.set,
                location_id=self._location_id,
                inventory_item_id=inventory_item_id,
                available=max(0, quantity),
            )
        except _SyncStopped:
            raise
        except Exception as e:
            print(f"[Shopify] Inventory level error: {e}")

    # ------------------------------------------------------------------ #
    #  Pull Shopify → LOCAL                                                #
    # ------------------------------------------------------------------ #
    def _pull_from_shopify(self) -> int:
        """Pull products (all variants) and collections from Shopify."""
        # Sync collections → local categories first
        self._sync_collections()

        # Build collection-id → local category-id map from synced categories
        local_cats = self.db.get_categories()
        col_to_cat: Dict[str, int] = {
            cat["shopify_collection_id"]: cat["id"]
            for cat in local_cats
            if cat.get("shopify_collection_id")
        }

        # Fetch all Collect records (product ↔ collection joins) in one call
        product_to_col: Dict[str, str] = {}  # shopify_product_id → shopify_collection_id
        try:
            collects = self._api_call(self._shopify.Collect.find, limit=250)
            for c in collects:
                pid = str(getattr(c, "product_id", "") or "")
                cid = str(getattr(c, "collection_id", "") or "")
                if pid and cid and pid not in product_to_col:
                    product_to_col[pid] = cid
        except _SyncStopped:
            raise
        except Exception as e:
            err_str = str(e)
            if "401" in err_str or "Unauthorized" in err_str:
                raise
            print(f"[Shopify] Could not fetch Collect records: {e}")

        count = 0
        shopify_products = self._api_call(self._shopify.Product.find, limit=250)

        # Batch-fetch all inventory levels (≤50 IDs per call)
        inv_item_ids = []
        for sp in shopify_products:
            for sv in (sp.variants or []):
                iid = str(getattr(sv, "inventory_item_id", "") or "")
                if iid:
                    inv_item_ids.append(iid)

        inventory_map: Dict[str, int] = {}
        if inv_item_ids and self._location_id:
            for i in range(0, len(inv_item_ids), 50):
                batch = inv_item_ids[i: i + 50]
                try:
                    levels = self._api_call(
                        self._shopify.InventoryLevel.find,
                        inventory_item_ids=",".join(batch),
                        location_ids=self._location_id,
                    )
                    for lvl in levels:
                        iid = str(getattr(lvl, "inventory_item_id", ""))
                        if iid:
                            inventory_map[iid] = int(getattr(lvl, "available", 0) or 0)
                except _SyncStopped:
                    raise
                except Exception as inv_err:
                    err_str = str(inv_err)
                    if "401" in err_str or "Unauthorized" in err_str:
                        raise
                    print(f"[Shopify] Inventory batch fetch error: {inv_err}")

        for sp in shopify_products:
            try:
                if not sp.variants:
                    continue

                # Resolve category: try product_type first, then Collect membership
                category_id = None
                if getattr(sp, "product_type", ""):
                    cat = next(
                        (c for c in local_cats
                         if c["name"].lower() == sp.product_type.lower()),
                        None,
                    )
                    if cat:
                        category_id = cat["id"]
                if not category_id:
                    col_id = product_to_col.get(str(sp.id))
                    if col_id:
                        category_id = col_to_cat.get(col_id)

                # Locate / create parent product
                local = self.db.get_product_by_shopify_id(str(sp.id))
                if not local:
                    # Try matching by first variant's SKU or barcode
                    fv = sp.variants[0]
                    fsku = (getattr(fv, "sku", "") or "").strip() or None
                    fbar = (getattr(fv, "barcode", "") or "").strip() or None
                    if fsku:
                        local = self.db.get_product_by_sku(fsku, active_only=False)
                    if not local and fbar:
                        local = self.db.get_product_by_barcode(fbar, active_only=False)

                # Never overwrite a POS-only product from Shopify
                if local and local.get("pos_only"):
                    continue

                parent_id = None
                if local:
                    parent_id = local["id"]
                    self.db.update_product(parent_id, {
                        "name": sp.title,
                        "description": getattr(sp, "body_html", "") or "",
                        "category_id": category_id,
                        "shopify_id": str(sp.id),
                        "shopify_synced": 1,
                        "has_variants": 1 if len(sp.variants) > 1 else 0,
                        "last_synced": datetime.now(timezone.utc).isoformat(),
                    })
                else:
                    fv = sp.variants[0]
                    fsku = (getattr(fv, "sku", "") or "").strip() or None
                    fbar = (getattr(fv, "barcode", "") or "").strip() or None
                    fprice = float(getattr(fv, "price", 0) or 0)
                    try:
                        parent_id = self.db.add_product({
                            "name": sp.title,
                            "description": getattr(sp, "body_html", "") or "",
                            "category_id": category_id,
                            "price": fprice,
                            "sku": fsku,
                            "barcode": fbar,
                            "quantity": 0,
                            "shopify_id": str(sp.id),
                            "shopify_synced": 1,
                            "has_variants": 1 if len(sp.variants) > 1 else 0,
                            "last_synced": datetime.now(timezone.utc).isoformat(),
                        })
                        self.product_synced.emit(sp.title)
                    except Exception as insert_err:
                        if "UNIQUE" not in str(insert_err):
                            raise
                        conflict = (
                            (self.db.get_product_by_sku(fsku, active_only=False) if fsku else None)
                            or (self.db.get_product_by_barcode(fbar, active_only=False) if fbar else None)
                        )
                        if conflict:
                            parent_id = conflict["id"]
                            self.db.update_product(parent_id, {
                                "name": sp.title,
                                "shopify_id": str(sp.id),
                                "shopify_synced": 1,
                                "has_variants": 1 if len(sp.variants) > 1 else 0,
                                "last_synced": datetime.now(timezone.utc).isoformat(),
                            })
                        else:
                            print(f"[Shopify] Skipped '{sp.title}': unresolvable UNIQUE conflict")
                            continue

                # ── Sync each variant ───────────────────────────────────
                for sv in sp.variants:
                    sv_id_str = str(sv.id)
                    sv_inv_id = str(getattr(sv, "inventory_item_id", "") or "")
                    sv_sku = (getattr(sv, "sku", "") or "").strip() or None
                    sv_bar = (getattr(sv, "barcode", "") or "").strip() or None
                    sv_price = float(getattr(sv, "price", 0) or 0)
                    sv_qty = inventory_map.get(sv_inv_id, 0)

                    # Build option values
                    opt = {}
                    for n in sp.options:
                        opt[n.name] = None  # placeholder
                    option_names = [o.name for o in sp.options]

                    def _opt(idx):
                        try:
                            return getattr(sv, f"option{idx}", None)
                        except Exception:
                            return None

                    variant_data = {
                        "product_id": parent_id,
                        "name": " / ".join(
                            filter(None, [_opt(1), _opt(2), _opt(3)])
                        ) or sp.title,
                        "sku": sv_sku,
                        "barcode": sv_bar,
                        "price": sv_price,
                        "quantity": sv_qty,
                        "option1_name": option_names[0] if len(option_names) > 0 else None,
                        "option1_value": _opt(1),
                        "option2_name": option_names[1] if len(option_names) > 1 else None,
                        "option2_value": _opt(2),
                        "option3_name": option_names[2] if len(option_names) > 2 else None,
                        "option3_value": _opt(3),
                        "shopify_variant_id": sv_id_str,
                        "shopify_inventory_item_id": sv_inv_id,
                    }

                    local_variant = self.db.get_variant_by_shopify_id(sv_id_str)
                    if local_variant:
                        self.db.update_variant(local_variant["id"], variant_data)
                    else:
                        # Try SKU match
                        if sv_sku:
                            lv_sku = self.db.get_variant_by_sku(sv_sku)
                            if lv_sku and lv_sku["product_id"] == parent_id:
                                self.db.update_variant(lv_sku["id"], variant_data)
                                continue
                        self.db.add_variant(variant_data)

                    # Update parent product price/qty to reflect first variant
                    if sv == sp.variants[0]:
                        self.db.update_product(parent_id, {
                            "price": sv_price,
                            "quantity": sv_qty,
                            "shopify_variant_id": sv_id_str,
                            "shopify_inventory_item_id": sv_inv_id,
                        })

                count += 1
            except _SyncStopped:
                raise
            except Exception as e:
                err_str = str(e)
                if "401" in err_str or "Unauthorized" in err_str:
                    raise
                print(f"[Shopify] Pull error for '{getattr(sp, 'title', '?')}': {e}")
        return count

    # ------------------------------------------------------------------ #
    #  Collections ↔ Categories                                           #
    # ------------------------------------------------------------------ #
    def _sync_collections(self):
        """Sync Shopify custom collections into local categories."""
        try:
            collections = self._api_call(
                self._shopify.CustomCollection.find, limit=250
            )
            for col in collections:
                col_id_str = str(col.id)
                name = col.title.strip()
                if not name:
                    continue
                local_cat = self.db.get_category_by_shopify_id(col_id_str)
                if local_cat:
                    # Update name if changed
                    if local_cat["name"] != name:
                        self.db.update_category(
                            local_cat["id"], name,
                            local_cat.get("color", "#3B82F6"), col_id_str
                        )
                else:
                    # Check if a category with same name already exists
                    existing = next(
                        (c for c in self.db.get_categories()
                         if c["name"].lower() == name.lower()),
                        None,
                    )
                    if existing:
                        self.db.update_category(
                            existing["id"], existing["name"],
                            existing.get("color", "#3B82F6"), col_id_str
                        )
                    else:
                        self.db.add_category(name, "#3B82F6", col_id_str)
        except _SyncStopped:
            raise
        except Exception as e:
            err_str = str(e)
            if "401" in err_str or "Unauthorized" in err_str:
                raise
            print(f"[Shopify] Collection sync error: {e}")

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
                vid = item.get("variant_id")
                if not pid:
                    continue
                if vid:
                    variant = self.db.get_variant(vid)
                    if variant and variant.get("shopify_inventory_item_id"):
                        self._update_inventory_level(
                            variant["shopify_inventory_item_id"],
                            variant["quantity"],
                        )
                else:
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
    High-level facade that manages the sync thread lifecycle.
    Uses a plain Python daemon thread so the OS cleans it up on exit
    without Qt's SIGABRT assertion firing on an un-joined QThread.
    """

    def __init__(self, config, db):
        self.config = config
        self.db = db
        self._thread: Optional[threading.Thread] = None
        self._worker: Optional[ShopifySyncWorker] = None

    def start(self):
        if not self.config.get("shopify_enabled", False):
            return
        if self._thread and self._thread.is_alive():
            return
        self._worker = ShopifySyncWorker(self.config, self.db)
        self._thread = threading.Thread(
            target=self._worker.run,
            daemon=True,          # killed automatically when the process exits
            name="ShopifySync",
        )
        self._thread.start()

    def stop(self):
        if self._worker:
            self._worker.stop()   # sets the _stop_flag so run() exits cleanly
        if self._thread:
            self._thread.join(timeout=3)   # wait up to 3 s; daemon kills the rest
        self._thread = None
        self._worker = None

    def pause(self):
        """
        Non-blocking pause: signals the sync thread to stop and discards the
        reference immediately.  The daemon thread will exit on its own when it
        next checks _stop_flag.  Avoids freezing the GUI for 3 s.
        """
        if self._worker:
            self._worker.stop()   # sets _stop_flag – thread exits on its own
        self._thread = None       # drop reference (daemon dies with the process)
        self._worker = None

    def resume(self):
        """Resume a paused sync (alias for start – safe to call when running)."""
        self.start()

    @property
    def is_running(self) -> bool:
        """True while the sync thread is alive."""
        return self._thread is not None and self._thread.is_alive()

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
