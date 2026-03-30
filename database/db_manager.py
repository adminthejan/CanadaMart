"""SQLite database manager – single source of truth for all data."""
import hashlib
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any


class DatabaseManager:
    """Thread-safe SQLite database manager."""

    def __init__(self):
        self.db_dir = Path.home() / ".canadamart"
        self.db_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = str(self.db_dir / "pos_data.db")
        self._lock = threading.Lock()
        self._local = threading.local()

    # ------------------------------------------------------------------ #
    #  Connection management                                               #
    # ------------------------------------------------------------------ #
    def _conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            self._local.conn = conn
        return self._local.conn

    def _execute(self, sql: str, params=()) -> sqlite3.Cursor:
        with self._lock:
            return self._conn().execute(sql, params)

    def _executemany(self, sql: str, params_list) -> sqlite3.Cursor:
        with self._lock:
            return self._conn().executemany(sql, params_list)

    def _commit(self):
        with self._lock:
            self._conn().commit()

    # ------------------------------------------------------------------ #
    #  Schema initialisation                                               #
    # ------------------------------------------------------------------ #
    def initialize(self):
        with self._lock:
            conn = self._conn()
            conn.executescript("""
                PRAGMA foreign_keys = ON;

                CREATE TABLE IF NOT EXISTS categories (
                    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                    name                TEXT UNIQUE NOT NULL,
                    color               TEXT DEFAULT '#3B82F6',
                    shopify_collection_id TEXT,
                    created_at          TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS products (
                    id                        INTEGER PRIMARY KEY AUTOINCREMENT,
                    sku                       TEXT UNIQUE,
                    barcode                   TEXT,
                    name                      TEXT NOT NULL,
                    description               TEXT,
                    category_id               INTEGER REFERENCES categories(id),
                    price                     REAL NOT NULL DEFAULT 0,
                    cost                      REAL DEFAULT 0,
                    quantity                  INTEGER DEFAULT 0,
                    min_quantity              INTEGER DEFAULT 5,
                    unit                      TEXT DEFAULT 'pcs',
                    tax_rate                  REAL DEFAULT -1,
                    image_path                TEXT,
                    shopify_id                TEXT,
                    shopify_variant_id        TEXT,
                    shopify_inventory_item_id TEXT,
                    shopify_synced            INTEGER DEFAULT 0,
                    has_variants              INTEGER DEFAULT 0,
                    pos_only                  INTEGER DEFAULT 0,
                    last_synced               TEXT,
                    active                    INTEGER DEFAULT 1,
                    created_at                TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at                TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS product_variants (
                    id                        INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id                INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
                    name                      TEXT NOT NULL,
                    sku                       TEXT,
                    barcode                   TEXT,
                    price                     REAL NOT NULL DEFAULT 0,
                    cost                      REAL DEFAULT 0,
                    quantity                  INTEGER DEFAULT 0,
                    option1_name              TEXT,
                    option1_value             TEXT,
                    option2_name              TEXT,
                    option2_value             TEXT,
                    option3_name              TEXT,
                    option3_value             TEXT,
                    shopify_variant_id        TEXT,
                    shopify_inventory_item_id TEXT,
                    active                    INTEGER DEFAULT 1,
                    created_at                TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at                TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS customers (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    name        TEXT NOT NULL,
                    mobile      TEXT UNIQUE,
                    email       TEXT,
                    address     TEXT,
                    city        TEXT,
                    notes       TEXT,
                    points      INTEGER DEFAULT 0,
                    total_spent REAL DEFAULT 0,
                    shopify_id  TEXT,
                    created_at  TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at  TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS sales (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    invoice_number  TEXT UNIQUE NOT NULL,
                    customer_id     INTEGER REFERENCES customers(id),
                    customer_name   TEXT,
                    subtotal        REAL NOT NULL,
                    tax_amount      REAL DEFAULT 0,
                    discount_amount REAL DEFAULT 0,
                    total           REAL NOT NULL,
                    payment_method  TEXT DEFAULT 'cash',
                    amount_paid     REAL DEFAULT 0,
                    change_amount   REAL DEFAULT 0,
                    notes           TEXT,
                    status          TEXT DEFAULT 'completed',
                    shopify_order_id TEXT,
                    created_at      TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS sale_items (
                    id               INTEGER PRIMARY KEY AUTOINCREMENT,
                    sale_id          INTEGER NOT NULL REFERENCES sales(id),
                    product_id       INTEGER REFERENCES products(id),
                    variant_id       INTEGER REFERENCES product_variants(id),
                    product_name     TEXT NOT NULL,
                    sku              TEXT,
                    quantity         INTEGER NOT NULL,
                    unit_price       REAL NOT NULL,
                    discount_percent REAL DEFAULT 0,
                    total            REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS inventory_log (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id      INTEGER NOT NULL REFERENCES products(id),
                    change_type     TEXT NOT NULL,
                    quantity_change INTEGER NOT NULL,
                    quantity_before INTEGER,
                    quantity_after  INTEGER,
                    reference_id    TEXT,
                    notes           TEXT,
                    created_at      TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS sync_log (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    sync_type   TEXT NOT NULL,
                    status      TEXT NOT NULL,
                    items_count INTEGER DEFAULT 0,
                    message     TEXT,
                    created_at  TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS users (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    username      TEXT UNIQUE NOT NULL,
                    full_name     TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    role          TEXT NOT NULL DEFAULT 'cashier',
                    active        INTEGER DEFAULT 1,
                    last_login    TEXT,
                    created_at    TEXT DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.commit()
            # Migration: empty-string SKUs/barcodes must be NULL so that
            # the UNIQUE constraint on sku allows multiple no-SKU products.
            conn.execute("UPDATE products SET sku     = NULL WHERE sku     = ''")
            conn.execute("UPDATE products SET barcode = NULL WHERE barcode = ''")
            conn.commit()
            # Schema migrations for older databases
            for col_sql in [
                "ALTER TABLE categories ADD COLUMN shopify_collection_id TEXT",
                "ALTER TABLE sale_items ADD COLUMN variant_id INTEGER REFERENCES product_variants(id)",
                "ALTER TABLE products ADD COLUMN has_variants INTEGER DEFAULT 0",
                "ALTER TABLE products ADD COLUMN pos_only INTEGER DEFAULT 0",
            ]:
                try:
                    conn.execute(col_sql)
                    conn.commit()
                except Exception:
                    pass  # column already exists
            # Remove the old built-in placeholder categories that have no products.
            for cat_name in ("General", "Food & Beverage", "Electronics",
                             "Clothing", "Health & Beauty"):
                conn.execute(
                    """DELETE FROM categories
                       WHERE name = ?
                         AND id NOT IN (SELECT DISTINCT category_id
                                        FROM products
                                        WHERE category_id IS NOT NULL)""",
                    (cat_name,),
                )
            conn.commit()
            self._seed_defaults(conn)

    def _seed_defaults(self, conn: sqlite3.Connection):
        # Only seed the default admin account – no preset categories.
        pw_hash = hashlib.sha256("admin123".encode()).hexdigest()
        try:
            conn.execute(
                """INSERT OR IGNORE INTO users (username, full_name, password_hash, role)
                   VALUES (?, ?, ?, ?)""",
                ("admin", "Administrator", pw_hash, "admin"),
            )
        except Exception:
            pass
        conn.commit()

    # ================================================================== #
    #  CATEGORIES                                                          #
    # ================================================================== #
    def get_categories(self) -> List[Dict]:
        rows = self._execute("SELECT * FROM categories ORDER BY name").fetchall()
        return [dict(r) for r in rows]

    def get_category(self, cat_id: int) -> Optional[Dict]:
        row = self._execute(
            "SELECT * FROM categories WHERE id = ?", (cat_id,)
        ).fetchone()
        return dict(row) if row else None

    def add_category(self, name: str, color: str = "#3B82F6",
                     shopify_collection_id: str = None) -> int:
        cur = self._execute(
            "INSERT OR IGNORE INTO categories (name, color, shopify_collection_id) VALUES (?, ?, ?)",
            (name, color, shopify_collection_id),
        )
        self._commit()
        return cur.lastrowid

    def update_category(self, cat_id: int, name: str, color: str,
                        shopify_collection_id: str = None):
        self._execute(
            "UPDATE categories SET name=?, color=?, shopify_collection_id=? WHERE id=?",
            (name, color, shopify_collection_id, cat_id),
        )
        self._commit()

    def get_category_by_shopify_id(self, shopify_id: str) -> Optional[Dict]:
        row = self._execute(
            "SELECT * FROM categories WHERE shopify_collection_id = ?", (shopify_id,)
        ).fetchone()
        return dict(row) if row else None

    def delete_category(self, cat_id: int):
        self._execute("DELETE FROM categories WHERE id = ?", (cat_id,))
        self._commit()

    # ================================================================== #
    #  PRODUCT VARIANTS                                                    #
    # ================================================================== #
    def get_variants(self, product_id: int) -> List[Dict]:
        rows = self._execute(
            "SELECT * FROM product_variants WHERE product_id = ? AND active = 1 ORDER BY id",
            (product_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_variant(self, variant_id: int) -> Optional[Dict]:
        row = self._execute(
            "SELECT * FROM product_variants WHERE id = ?", (variant_id,)
        ).fetchone()
        return dict(row) if row else None

    def get_variant_by_shopify_id(self, shopify_variant_id: str) -> Optional[Dict]:
        row = self._execute(
            "SELECT * FROM product_variants WHERE shopify_variant_id = ?",
            (shopify_variant_id,),
        ).fetchone()
        return dict(row) if row else None

    def get_variant_by_sku(self, sku: str) -> Optional[Dict]:
        row = self._execute(
            "SELECT * FROM product_variants WHERE sku = ? AND active = 1", (sku,)
        ).fetchone()
        return dict(row) if row else None

    def add_variant(self, data: dict) -> int:
        cols = [
            "product_id", "name", "sku", "barcode", "price", "cost", "quantity",
            "option1_name", "option1_value", "option2_name", "option2_value",
            "option3_name", "option3_value",
            "shopify_variant_id", "shopify_inventory_item_id",
        ]
        fields = [c for c in cols if c in data]
        placeholders = ", ".join("?" * len(fields))
        values = [data[f] for f in fields]
        cur = self._execute(
            f"INSERT INTO product_variants ({', '.join(fields)}) VALUES ({placeholders})",
            values,
        )
        self._commit()
        return cur.lastrowid

    def update_variant(self, variant_id: int, data: dict):
        data["updated_at"] = datetime.now().isoformat()
        allowed = [
            "name", "sku", "barcode", "price", "cost", "quantity",
            "option1_name", "option1_value", "option2_name", "option2_value",
            "option3_name", "option3_value",
            "shopify_variant_id", "shopify_inventory_item_id",
            "active", "updated_at",
        ]
        fields = [k for k in data if k in allowed]
        sets = ", ".join(f"{f} = ?" for f in fields)
        values = [data[f] for f in fields] + [variant_id]
        self._execute(f"UPDATE product_variants SET {sets} WHERE id = ?", values)
        self._commit()

    def delete_variant(self, variant_id: int):
        self._execute(
            "UPDATE product_variants SET active = 0 WHERE id = ?", (variant_id,)
        )
        self._commit()

    def adjust_variant_stock(self, variant_id: int, delta: int,
                             change_type: str, reference_id: str = None,
                             notes: str = None):
        """Atomically adjust a variant's stock quantity."""
        with self._lock:
            conn = self._conn()
            row = conn.execute(
                "SELECT quantity, product_id FROM product_variants WHERE id = ?",
                (variant_id,),
            ).fetchone()
            if not row:
                return
            before = row["quantity"]
            after = before + delta
            conn.execute(
                "UPDATE product_variants SET quantity = ?, updated_at = ? WHERE id = ?",
                (after, datetime.now().isoformat(), variant_id),
            )
            # Also log against the parent product
            conn.execute(
                """INSERT INTO inventory_log
                   (product_id, change_type, quantity_change, quantity_before,
                    quantity_after, reference_id, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (row["product_id"], change_type, delta, before, after,
                 reference_id, notes),
            )
            conn.commit()
    def get_products(self, active_only=True, category_id=None) -> List[Dict]:
        sql = """
            SELECT p.*,
                   c.name  AS category_name,
                   c.color AS category_color,
                   COUNT(v.id) AS variant_count,
                   CASE
                       WHEN p.has_variants = 1
                       THEN COALESCE(SUM(v.quantity), 0)
                       ELSE p.quantity
                   END AS total_stock
            FROM products p
            LEFT JOIN categories c ON p.category_id = c.id
            LEFT JOIN product_variants v
                   ON v.product_id = p.id AND v.active = 1
            WHERE 1=1
        """
        params = []
        if active_only:
            sql += " AND p.active = 1"
        if category_id:
            sql += " AND p.category_id = ?"
            params.append(category_id)
        sql += " GROUP BY p.id ORDER BY p.name"
        rows = self._execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def search_products(self, query: str) -> List[Dict]:
        q = f"%{query}%"
        sql = """
            SELECT p.*, c.name AS category_name
            FROM products p
            LEFT JOIN categories c ON p.category_id = c.id
            WHERE p.active = 1
              AND (p.name LIKE ? OR p.sku LIKE ? OR p.barcode LIKE ? OR p.description LIKE ?)
            ORDER BY p.name LIMIT 100
        """
        rows = self._execute(sql, (q, q, q, q)).fetchall()
        return [dict(r) for r in rows]

    def get_product(self, product_id: int) -> Optional[Dict]:
        row = self._execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
        return dict(row) if row else None

    def get_product_by_barcode(self, barcode: str, active_only: bool = True) -> Optional[Dict]:
        sql = "SELECT * FROM products WHERE barcode = ?"
        if active_only:
            sql += " AND active = 1"
        row = self._execute(sql, (barcode,)).fetchone()
        return dict(row) if row else None

    def get_product_by_sku(self, sku: str, active_only: bool = True) -> Optional[Dict]:
        sql = "SELECT * FROM products WHERE sku = ?"
        if active_only:
            sql += " AND active = 1"
        row = self._execute(sql, (sku,)).fetchone()
        return dict(row) if row else None

    def get_product_by_shopify_id(self, shopify_id: str) -> Optional[Dict]:
        row = self._execute(
            "SELECT * FROM products WHERE shopify_id = ?", (shopify_id,)
        ).fetchone()
        return dict(row) if row else None

    def add_product(self, data: dict) -> int:
        cols = [
            "sku", "barcode", "name", "description", "category_id",
            "price", "cost", "quantity", "min_quantity", "unit",
            "tax_rate", "image_path", "shopify_id", "shopify_variant_id",
            "shopify_inventory_item_id", "shopify_synced", "pos_only",
        ]
        fields = [c for c in cols if c in data]
        placeholders = ", ".join("?" * len(fields))
        values = [data[f] for f in fields]
        sql = f"INSERT INTO products ({', '.join(fields)}) VALUES ({placeholders})"
        cur = self._execute(sql, values)
        self._commit()
        return cur.lastrowid

    def update_product(self, product_id: int, data: dict):
        data["updated_at"] = datetime.now().isoformat()
        allowed = [
            "sku", "barcode", "name", "description", "category_id",
            "price", "cost", "quantity", "min_quantity", "unit",
            "tax_rate", "image_path", "shopify_id", "shopify_variant_id",
            "shopify_inventory_item_id", "shopify_synced", "has_variants",
            "pos_only", "last_synced", "active", "updated_at",
        ]
        fields = [k for k in data if k in allowed]
        sets = ", ".join(f"{f} = ?" for f in fields)
        values = [data[f] for f in fields] + [product_id]
        self._execute(f"UPDATE products SET {sets} WHERE id = ?", values)
        self._commit()

    def delete_product(self, product_id: int):
        self._execute("UPDATE products SET active = 0 WHERE id = ?", (product_id,))
        self._commit()

    def adjust_stock(self, product_id: int, delta: int, change_type: str,
                     reference_id: str = None, notes: str = None):
        """Atomically adjust stock and log the change."""
        with self._lock:
            conn = self._conn()
            row = conn.execute(
                "SELECT quantity FROM products WHERE id = ?", (product_id,)
            ).fetchone()
            if not row:
                return
            before = row["quantity"]
            after = before + delta
            conn.execute(
                "UPDATE products SET quantity = ?, updated_at = ? WHERE id = ?",
                (after, datetime.now().isoformat(), product_id),
            )
            conn.execute(
                """INSERT INTO inventory_log
                   (product_id, change_type, quantity_change, quantity_before,
                    quantity_after, reference_id, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (product_id, change_type, delta, before, after, reference_id, notes),
            )
            conn.commit()

    def get_low_stock_products(self, threshold: int = None) -> List[Dict]:
        sql = """
            SELECT p.*, c.name AS category_name
            FROM products p
            LEFT JOIN categories c ON p.category_id = c.id
            WHERE p.active = 1 AND p.quantity <= COALESCE(p.min_quantity, ?)
            ORDER BY p.quantity ASC
        """
        rows = self._execute(sql, (threshold or 5,)).fetchall()
        return [dict(r) for r in rows]

    def get_inventory_log(self, product_id: int = None, limit: int = 200) -> List[Dict]:
        if product_id:
            rows = self._execute(
                """SELECT il.*, p.name AS product_name
                   FROM inventory_log il
                   LEFT JOIN products p ON il.product_id = p.id
                   WHERE il.product_id = ?
                   ORDER BY il.created_at DESC LIMIT ?""",
                (product_id, limit),
            ).fetchall()
        else:
            rows = self._execute(
                """SELECT il.*, p.name AS product_name
                   FROM inventory_log il
                   LEFT JOIN products p ON il.product_id = p.id
                   ORDER BY il.created_at DESC LIMIT ?""",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    # ================================================================== #
    #  CUSTOMERS                                                           #
    # ================================================================== #
    def get_customers(self) -> List[Dict]:
        rows = self._execute(
            "SELECT * FROM customers ORDER BY name"
        ).fetchall()
        return [dict(r) for r in rows]

    def search_customers(self, query: str) -> List[Dict]:
        q = f"%{query}%"
        rows = self._execute(
            """SELECT * FROM customers
               WHERE name LIKE ? OR mobile LIKE ? OR email LIKE ?
               ORDER BY name LIMIT 50""",
            (q, q, q),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_customer(self, customer_id: int) -> Optional[Dict]:
        row = self._execute(
            "SELECT * FROM customers WHERE id = ?", (customer_id,)
        ).fetchone()
        return dict(row) if row else None

    def get_customer_by_mobile(self, mobile: str) -> Optional[Dict]:
        row = self._execute(
            "SELECT * FROM customers WHERE mobile = ?", (mobile,)
        ).fetchone()
        return dict(row) if row else None

    def add_customer(self, data: dict) -> int:
        cols = ["name", "mobile", "email", "address", "city", "notes", "shopify_id"]
        fields = [c for c in cols if c in data]
        placeholders = ", ".join("?" * len(fields))
        values = [data[f] for f in fields]
        sql = f"INSERT INTO customers ({', '.join(fields)}) VALUES ({placeholders})"
        cur = self._execute(sql, values)
        self._commit()
        return cur.lastrowid

    def update_customer(self, customer_id: int, data: dict):
        data["updated_at"] = datetime.now().isoformat()
        allowed = ["name", "mobile", "email", "address", "city", "notes",
                   "points", "total_spent", "shopify_id", "updated_at"]
        fields = [k for k in data if k in allowed]
        sets = ", ".join(f"{f} = ?" for f in fields)
        values = [data[f] for f in fields] + [customer_id]
        self._execute(f"UPDATE customers SET {sets} WHERE id = ?", values)
        self._commit()

    def delete_customer(self, customer_id: int):
        self._execute("DELETE FROM customers WHERE id = ?", (customer_id,))
        self._commit()

    def get_customer_sales(self, customer_id: int) -> List[Dict]:
        rows = self._execute(
            "SELECT * FROM sales WHERE customer_id = ? ORDER BY created_at DESC",
            (customer_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    # ================================================================== #
    #  SALES                                                               #
    # ================================================================== #
    def get_next_invoice_number(self, prefix: str, start: int) -> str:
        row = self._execute(
            "SELECT MAX(CAST(SUBSTR(invoice_number, ?) AS INTEGER)) as mx FROM sales",
            (len(prefix) + 1,),
        ).fetchone()
        last = row["mx"] if row and row["mx"] else start - 1
        return f"{prefix}{last + 1}"

    def create_sale(self, sale_data: dict, items: List[dict]) -> int:
        """Create a complete sale with all items."""
        with self._lock:
            conn = self._conn()
            cols = [
                "invoice_number", "customer_id", "customer_name", "subtotal",
                "tax_amount", "discount_amount", "total", "payment_method",
                "amount_paid", "change_amount", "notes", "status",
            ]
            fields = [c for c in cols if c in sale_data]
            placeholders = ", ".join("?" * len(fields))
            values = [sale_data[f] for f in fields]
            cur = conn.execute(
                f"INSERT INTO sales ({', '.join(fields)}) VALUES ({placeholders})",
                values,
            )
            sale_id = cur.lastrowid

            for item in items:
                conn.execute(
                    """INSERT INTO sale_items
                       (sale_id, product_id, variant_id, product_name, sku, quantity,
                        unit_price, discount_percent, total)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        sale_id,
                        item.get("product_id"),
                        item.get("variant_id"),
                        item["product_name"],
                        item.get("sku", ""),
                        item["quantity"],
                        item["unit_price"],
                        item.get("discount_percent", 0),
                        item["total"],
                    ),
                )
                # Deduct variant stock if variant_id present, else deduct product stock
                if item.get("variant_id"):
                    row = conn.execute(
                        "SELECT quantity FROM product_variants WHERE id = ?",
                        (item["variant_id"],),
                    ).fetchone()
                    if row:
                        before = row["quantity"]
                        after = before - item["quantity"]
                        conn.execute(
                            "UPDATE product_variants SET quantity = ?, updated_at = ? WHERE id = ?",
                            (after, datetime.now().isoformat(), item["variant_id"]),
                        )
                        conn.execute(
                            """INSERT INTO inventory_log
                               (product_id, change_type, quantity_change,
                                quantity_before, quantity_after, reference_id)
                               VALUES (?, 'sale', ?, ?, ?, ?)""",
                            (item["product_id"], -item["quantity"],
                             before, after, sale_data.get("invoice_number")),
                        )
                elif item.get("product_id"):
                    row = conn.execute(
                        "SELECT quantity FROM products WHERE id = ?",
                        (item["product_id"],),
                    ).fetchone()
                    if row:
                        before = row["quantity"]
                        after = before - item["quantity"]
                        conn.execute(
                            "UPDATE products SET quantity = ?, updated_at = ? WHERE id = ?",
                            (after, datetime.now().isoformat(), item["product_id"]),
                        )
                        conn.execute(
                            """INSERT INTO inventory_log
                               (product_id, change_type, quantity_change,
                                quantity_before, quantity_after, reference_id)
                               VALUES (?, 'sale', ?, ?, ?, ?)""",
                            (item["product_id"], -item["quantity"],
                             before, after, sale_data.get("invoice_number")),
                        )
            # Update customer totals
            if sale_data.get("customer_id"):
                conn.execute(
                    """UPDATE customers SET
                       total_spent = total_spent + ?,
                       points = points + ?,
                       updated_at = ?
                       WHERE id = ?""",
                    (
                        sale_data["total"],
                        int(sale_data["total"]),
                        datetime.now().isoformat(),
                        sale_data["customer_id"],
                    ),
                )
            conn.commit()
            return sale_id

    def get_sales(self, date_from: str = None, date_to: str = None,
                  limit: int = 500) -> List[Dict]:
        sql = "SELECT * FROM sales WHERE 1=1"
        params = []
        if date_from:
            sql += " AND DATE(created_at) >= ?"
            params.append(date_from)
        if date_to:
            sql += " AND DATE(created_at) <= ?"
            params.append(date_to)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        rows = self._execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def get_sale(self, sale_id: int) -> Optional[Dict]:
        row = self._execute("SELECT * FROM sales WHERE id = ?", (sale_id,)).fetchone()
        return dict(row) if row else None

    def get_sale_by_invoice(self, invoice: str) -> Optional[Dict]:
        row = self._execute(
            "SELECT * FROM sales WHERE invoice_number = ?", (invoice,)
        ).fetchone()
        return dict(row) if row else None

    def get_sale_items(self, sale_id: int) -> List[Dict]:
        rows = self._execute(
            "SELECT * FROM sale_items WHERE sale_id = ?", (sale_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    def update_sale_shopify_id(self, sale_id: int, shopify_order_id: str):
        self._execute(
            "UPDATE sales SET shopify_order_id = ? WHERE id = ?",
            (shopify_order_id, sale_id),
        )
        self._commit()

    # ================================================================== #
    #  REPORTS                                                             #
    # ================================================================== #
    def get_sales_summary(self, date_from: str, date_to: str) -> Dict:
        row = self._execute(
            """SELECT
               COUNT(*) as total_transactions,
               SUM(total) as total_revenue,
               SUM(tax_amount) as total_tax,
               SUM(discount_amount) as total_discounts,
               AVG(total) as avg_transaction,
               SUM(CASE WHEN payment_method='cash' THEN 1 ELSE 0 END) as cash_count,
               SUM(CASE WHEN payment_method='card' THEN 1 ELSE 0 END) as card_count
               FROM sales
               WHERE DATE(created_at) BETWEEN ? AND ?
               AND status = 'completed'""",
            (date_from, date_to),
        ).fetchone()
        return dict(row) if row else {}

    def get_daily_sales(self, date_from: str, date_to: str) -> List[Dict]:
        rows = self._execute(
            """SELECT DATE(created_at) as date,
               COUNT(*) as transactions,
               SUM(total) as revenue
               FROM sales
               WHERE DATE(created_at) BETWEEN ? AND ?
               AND status = 'completed'
               GROUP BY DATE(created_at)
               ORDER BY date""",
            (date_from, date_to),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_top_products(self, date_from: str, date_to: str, limit: int = 10) -> List[Dict]:
        rows = self._execute(
            """SELECT si.product_name, si.sku,
               SUM(si.quantity) as units_sold,
               SUM(si.total) as revenue
               FROM sale_items si
               JOIN sales s ON si.sale_id = s.id
               WHERE DATE(s.created_at) BETWEEN ? AND ?
               AND s.status = 'completed'
               GROUP BY si.product_id, si.product_name
               ORDER BY revenue DESC LIMIT ?""",
            (date_from, date_to, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_payment_breakdown(self, date_from: str, date_to: str) -> List[Dict]:
        rows = self._execute(
            """SELECT payment_method, COUNT(*) as count, SUM(total) as total
               FROM sales
               WHERE DATE(created_at) BETWEEN ? AND ?
               AND status = 'completed'
               GROUP BY payment_method""",
            (date_from, date_to),
        ).fetchall()
        return [dict(r) for r in rows]

    # ================================================================== #
    #  SYNC LOG                                                            #
    # ================================================================== #
    def log_sync(self, sync_type: str, status: str, items_count: int = 0, message: str = ""):
        self._execute(
            "INSERT INTO sync_log (sync_type, status, items_count, message) VALUES (?, ?, ?, ?)",
            (sync_type, status, items_count, message),
        )
        self._commit()

    def get_sync_log(self, limit: int = 50) -> List[Dict]:
        rows = self._execute(
            "SELECT * FROM sync_log ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    def get_unsynced_products(self) -> List[Dict]:
        rows = self._execute(
            """SELECT * FROM products
               WHERE (shopify_synced = 0 OR shopify_synced IS NULL)
                 AND active = 1
                 AND (pos_only = 0 OR pos_only IS NULL)"""
        ).fetchall()
        return [dict(r) for r in rows]

    # ================================================================== #
    #  USERS                                                               #
    # ================================================================== #
    @staticmethod
    def _hash_password(password: str) -> str:
        return hashlib.sha256(password.encode()).hexdigest()

    def authenticate_user(self, username: str, password: str) -> Optional[Dict]:
        """Return user dict if credentials are valid and account is active, else None."""
        pw_hash = self._hash_password(password)
        row = self._execute(
            "SELECT * FROM users WHERE username = ? AND password_hash = ? AND active = 1",
            (username.strip().lower(), pw_hash),
        ).fetchone()
        if row:
            user = dict(row)
            # Update last_login timestamp
            self._execute(
                "UPDATE users SET last_login = ? WHERE id = ?",
                (datetime.now().isoformat(), user["id"]),
            )
            self._commit()
            return user
        return None

    def get_users(self) -> List[Dict]:
        rows = self._execute(
            "SELECT id, username, full_name, role, active, last_login, created_at FROM users ORDER BY username"
        ).fetchall()
        return [dict(r) for r in rows]

    def add_user(self, data: dict) -> int:
        pw_hash = self._hash_password(data["password"])
        cur = self._execute(
            """INSERT INTO users (username, full_name, password_hash, role, active)
               VALUES (?, ?, ?, ?, ?)""",
            (
                data["username"].strip().lower(),
                data["full_name"],
                pw_hash,
                data.get("role", "cashier"),
                1 if data.get("active", True) else 0,
            ),
        )
        self._commit()
        return cur.lastrowid

    def update_user(self, user_id: int, data: dict):
        fields = []
        values = []
        if "full_name" in data:
            fields.append("full_name = ?")
            values.append(data["full_name"])
        if "role" in data:
            fields.append("role = ?")
            values.append(data["role"])
        if "active" in data:
            fields.append("active = ?")
            values.append(1 if data["active"] else 0)
        if "password" in data and data["password"]:
            fields.append("password_hash = ?")
            values.append(self._hash_password(data["password"]))
        if not fields:
            return
        values.append(user_id)
        self._execute(f"UPDATE users SET {', '.join(fields)} WHERE id = ?", values)
        self._commit()

    def delete_user(self, user_id: int):
        self._execute("DELETE FROM users WHERE id = ?", (user_id,))
        self._commit()

    def change_password(self, user_id: int, new_password: str):
        self._execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (self._hash_password(new_password), user_id),
        )
        self._commit()
