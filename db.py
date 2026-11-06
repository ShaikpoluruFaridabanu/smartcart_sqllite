import os
import sqlite3
from decimal import Decimal
import config

# Register adapter for Decimal values so SQLite stores amounts as floats
sqlite3.register_adapter(Decimal, lambda d: float(d))

DB_PATH = getattr(config, 'SQLITE_DB_PATH', os.path.join(os.path.abspath(os.path.dirname(__file__)), 'smartcart.db'))

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS admin (
    admin_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    email TEXT UNIQUE,
    password TEXT,
    profile_image TEXT
);

CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    email TEXT UNIQUE,
    phone TEXT,
    password TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    profile_image TEXT
);

CREATE TABLE IF NOT EXISTS products (
    product_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    description TEXT,
    category TEXT,
    price REAL,
    image TEXT,
    admin_id INTEGER,
    FOREIGN KEY (admin_id) REFERENCES admin (admin_id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS orders (
    order_id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_name TEXT,
    phone TEXT NOT NULL,
    email TEXT,
    address TEXT,
    city TEXT NOT NULL,
    state TEXT NOT NULL,
    pincode TEXT NOT NULL,
    total_amount REAL NOT NULL,
    status TEXT DEFAULT 'Placed',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    user_id INTEGER,
    razorpay_order_id TEXT,
    razorpay_payment_id TEXT UNIQUE,
    razorpay_signature TEXT,
    amount REAL,
    currency TEXT DEFAULT 'INR',
    payment_status TEXT DEFAULT 'PAID',
    order_status TEXT DEFAULT 'PLACED',
    full_name TEXT,
    address_line TEXT,
    landmark TEXT,
    FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS order_items (
    order_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    product_id INTEGER,
    product_name TEXT NOT NULL,
    price REAL NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 1,
    subtotal REAL NOT NULL,
    product_image TEXT,
    FOREIGN KEY (order_id) REFERENCES orders (order_id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products (product_id) ON DELETE SET NULL
);
"""


def init_db():
    """Ensure all required SQLite tables exist."""
    db_directory = os.path.dirname(os.path.abspath(DB_PATH))
    os.makedirs(db_directory, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    conn.close()


class SQLiteDictCursor:
    """Cursor wrapper that translates %s to ? and returns dictionary rows."""
    def __init__(self, raw_cursor):
        self._cursor = raw_cursor
        self._custom_rows = None

    def execute(self, query, params=None):
        clean_query = query.strip()
        upper_query = clean_query.upper()

        # Translate MySQL schema inspection to SQLite PRAGMA table_info
        if upper_query.startswith("SHOW COLUMNS FROM") or upper_query.startswith("DESCRIBE") or upper_query.startswith("DESC "):
            parts = clean_query.split()
            table_name = parts[-1].strip("`\"';")
            self._cursor.execute(f"PRAGMA table_info({table_name})")
            self._custom_rows = [{'Field': col[1]} for col in self._cursor.fetchall()]
            return self
        else:
            self._custom_rows = None

        # Convert %s placeholders to SQLite ?
        if "%s" in clean_query:
            clean_query = clean_query.replace("%s", "?")

        # Sanitize parameters (convert Decimal to float)
        clean_params = None
        if params is not None:
            if isinstance(params, (list, tuple)):
                clean_params = tuple(float(p) if isinstance(p, Decimal) else p for p in params)
            elif isinstance(params, dict):
                clean_params = {k: (float(v) if isinstance(v, Decimal) else v) for k, v in params.items()}
            elif isinstance(params, Decimal):
                clean_params = float(params)
            else:
                clean_params = params

        if clean_params is None:
            self._cursor.execute(clean_query)
        else:
            self._cursor.execute(clean_query, clean_params)
        return self

    def fetchone(self):
        if self._custom_rows is not None:
            return self._custom_rows.pop(0) if self._custom_rows else None
        row = self._cursor.fetchone()
        return dict(row) if row is not None else None

    def fetchall(self):
        if self._custom_rows is not None:
            res = self._custom_rows
            self._custom_rows = []
            return res
        return [dict(r) for r in self._cursor.fetchall()]

    @property
    def lastrowid(self):
        return self._cursor.lastrowid

    @property
    def rowcount(self):
        return self._cursor.rowcount

    def __getattr__(self, name):
        return getattr(self._cursor, name)

    def close(self):
        self._cursor.close()


class SQLiteDictConnection:
    """Wraps sqlite3.Connection to provide cursor(dictionary=True) and transactions."""
    def __init__(self, db_path):
        self._conn = sqlite3.connect(db_path, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")

    def cursor(self, dictionary=True):
        return SQLiteDictCursor(self._conn.cursor())

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()


def get_db_connection():
    """Return a database connection using SQLite."""
    return SQLiteDictConnection(DB_PATH)
