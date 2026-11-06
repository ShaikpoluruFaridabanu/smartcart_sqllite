import sqlite3
import mysql.connector
import os
import config

DB_PATH = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'smartcart.db')

def create_sqlite_schema(sqlite_conn):
    cursor = sqlite_conn.cursor()
    cursor.executescript("""
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
        FOREIGN KEY (admin_id) REFERENCES admin (admin_id) ON DELETE CASCADE
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
    """)
    sqlite_conn.commit()
    print("SQLite schema created successfully.")

def migrate_data():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    sqlite_conn = sqlite3.connect(DB_PATH)
    create_sqlite_schema(sqlite_conn)

    try:
        mysql_conn = mysql.connector.connect(
            host=config.DB_HOST,
            user=config.DB_USER,
            password=config.DB_PASSWORD,
            database=config.DB_NAME
        )
        mysql_cursor = mysql_conn.cursor(dictionary=True)
        sqlite_cursor = sqlite_conn.cursor()

        tables = ['admin', 'users', 'products', 'orders', 'order_items']
        for table in tables:
            mysql_cursor.execute(f"SELECT * FROM {table}")
            rows = mysql_cursor.fetchall()
            if not rows:
                print(f"Table '{table}' has 0 rows.")
                continue

            columns = list(rows[0].keys())
            col_str = ", ".join(columns)
            placeholders = ", ".join(["?"] * len(columns))

            for r in rows:
                values = []
                for col in columns:
                    val = r[col]
                    # Convert Decimals to float
                    if hasattr(val, 'as_tuple'):
                        val = float(val)
                    # Convert timestamps / datetime to ISO string
                    elif hasattr(val, 'isoformat'):
                        val = val.strftime('%Y-%m-%d %H:%M:%S')
                    values.append(val)

                sqlite_cursor.execute(
                    f"INSERT OR REPLACE INTO {table} ({col_str}) VALUES ({placeholders})",
                    values
                )
            sqlite_conn.commit()
            print(f"Migrated {len(rows)} rows for table '{table}'.")

        mysql_cursor.close()
        mysql_conn.close()
        print("Data migration from MySQL to SQLite completed successfully!")

    except Exception as e:
        print("Notice: MySQL connection failed or skipped:", e)
        print("SQLite database is initialized and ready with schema.")
    finally:
        sqlite_conn.close()

if __name__ == '__main__':
    migrate_data()
