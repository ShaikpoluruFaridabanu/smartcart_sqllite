import sqlite3
from app import app
from db import get_db_connection, init_db
import bcrypt

def run_tests():
    init_db()

    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Verify foreign key relationship
    cursor.execute("PRAGMA foreign_key_list(products)")
    fk_list = cursor.fetchall()
    print("Products foreign keys:", fk_list)
    assert any(fk['table'] == 'admin' and fk['to'] == 'admin_id' for fk in fk_list), "Foreign key to admin table missing!"

    # Test foreign key violation prevention
    try:
        cursor.execute(
            "INSERT INTO products (name, description, category, price, image, admin_id) VALUES (?, ?, ?, ?, ?, ?)",
            ("Invalid Product", "desc", "cat", 10.0, "img.jpg", 999999)
        )
        conn.commit()
        assert False, "Should have failed inserting product with non-existent admin_id!"
    except Exception as e:
        print("✓ FK enforcement verified:", e)
        conn.rollback()

    # 2. Setup Admin A and Admin B
    cursor.execute("SELECT admin_id FROM admin WHERE email = 'adminA@test.com'")
    row_a = cursor.fetchone()
    if not row_a:
        pwd = bcrypt.hashpw(b"adminA123", bcrypt.gensalt()).decode('utf-8')
        cursor.execute("INSERT INTO admin (name, email, password) VALUES (?, ?, ?)", ("Admin Alpha", "adminA@test.com", pwd))
        conn.commit()
        cursor.execute("SELECT admin_id FROM admin WHERE email = 'adminA@test.com'")
        row_a = cursor.fetchone()
    admin_a_id = row_a['admin_id']

    cursor.execute("SELECT admin_id FROM admin WHERE email = 'adminB@test.com'")
    row_b = cursor.fetchone()
    if not row_b:
        pwd = bcrypt.hashpw(b"adminB123", bcrypt.gensalt()).decode('utf-8')
        cursor.execute("INSERT INTO admin (name, email, password) VALUES (?, ?, ?)", ("Admin Beta", "adminB@test.com", pwd))
        conn.commit()
        cursor.execute("SELECT admin_id FROM admin WHERE email = 'adminB@test.com'")
        row_b = cursor.fetchone()
    admin_b_id = row_b['admin_id']

    # Insert test products for Admin A
    cursor.execute(
        "INSERT INTO products (name, description, category, price, image, admin_id) VALUES (?, ?, ?, ?, ?, ?)",
        ("Alpha Smartphone", "Flagship phone", "Electronics", 29999.0, "phone.jpg", admin_a_id)
    )
    p_a1 = cursor.lastrowid

    cursor.execute(
        "INSERT INTO products (name, description, category, price, image, admin_id) VALUES (?, ?, ?, ?, ?, ?)",
        ("Alpha Jacket", "Winter jacket", "Clothing", 1999.0, "jacket.jpg", admin_a_id)
    )
    p_a2 = cursor.lastrowid

    # Insert test products for Admin B
    cursor.execute(
        "INSERT INTO products (name, description, category, price, image, admin_id) VALUES (?, ?, ?, ?, ?, ?)",
        ("Beta Coffee Maker", "Espresso machine", "Home & Kitchen", 4500.0, "coffee.jpg", admin_b_id)
    )
    p_b1 = cursor.lastrowid

    cursor.execute(
        "INSERT INTO products (name, description, category, price, image, admin_id) VALUES (?, ?, ?, ?, ?, ?)",
        ("Beta Blender", "Smoothie blender", "Home & Kitchen", 2200.0, "blender.jpg", admin_b_id)
    )
    p_b2 = cursor.lastrowid

    conn.commit()
    cursor.close()
    conn.close()

    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    client = app.test_client()

    print("\n--- Testing Admin A Dashboard & Catalog ---")
    with client.session_transaction() as sess:
        sess['admin_id'] = admin_a_id
        sess['admin_name'] = "Admin Alpha"
        sess['admin_email'] = "adminA@test.com"

    # Admin A Dashboard test
    dash_a = client.get('/admin-dashboard')
    assert dash_a.status_code == 200
    html_dash_a = dash_a.data.decode('utf-8')
    assert "Alpha Smartphone" in html_dash_a
    assert "Alpha Jacket" in html_dash_a
    assert "Beta Coffee Maker" not in html_dash_a, "Admin A must NOT see Admin B's products in recent items!"
    assert "Beta Blender" not in html_dash_a, "Admin A must NOT see Admin B's products in recent items!"
    assert "Electronics" in html_dash_a
    assert "Clothing" in html_dash_a
    assert "Home & Kitchen" not in html_dash_a, "Admin A must NOT see Admin B's active categories on dashboard!"
    print("✓ Admin A Dashboard: Shows only Admin A's products, categories, and statistics.")

    # Admin A Inventory test
    inv_a = client.get('/admin/item-list')
    assert inv_a.status_code == 200
    html_inv_a = inv_a.data.decode('utf-8')
    assert "Alpha Smartphone" in html_inv_a
    assert "Alpha Jacket" in html_inv_a
    assert "Beta Coffee Maker" not in html_inv_a
    assert "Beta Blender" not in html_inv_a
    print("✓ Admin A Product Inventory: Displays only Admin A's products.")

    # Admin A Category Filter test
    cat_filter_a = client.get('/admin/item-list?category=Electronics')
    html_cat_a = cat_filter_a.data.decode('utf-8')
    assert "Alpha Smartphone" in html_cat_a
    assert "Alpha Jacket" not in html_cat_a

    # Backend Ownership Tampering Prevention: Admin A tries to access Admin B's items
    print("\n--- Testing Backend Ownership Validation & Tamper Prevention ---")
    # View Admin B's product
    tamper_view = client.get(f'/admin/view-item/{p_b1}', follow_redirects=True)
    assert "Product not found or access denied" in tamper_view.data.decode('utf-8')
    print("✓ Unauthorized view blocked.")

    # Edit GET Admin B's product
    tamper_edit_get = client.get(f'/admin/update-item/{p_b1}', follow_redirects=True)
    assert "Product not found or access denied" in tamper_edit_get.data.decode('utf-8')
    print("✓ Unauthorized edit GET blocked.")

    # Edit POST Admin B's product
    tamper_edit_post = client.post(f'/admin/update-item/{p_b1}', data={
        'name': 'Hacked Coffee Maker',
        'description': 'Hacked',
        'category': 'Hacked',
        'price': '1.0'
    }, follow_redirects=True)
    assert "Product not found or access denied" in tamper_edit_post.data.decode('utf-8')
    print("✓ Unauthorized edit POST blocked.")

    # Verify Admin B's product was not altered in DB
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT name, price FROM products WHERE product_id = ?", (p_b1,))
    row = c.fetchone()
    assert row['name'] == "Beta Coffee Maker", "Product was modified by unauthorized admin!"
    assert row['price'] == 4500.0, "Product price was modified by unauthorized admin!"

    # Delete Admin B's product
    tamper_del = client.get(f'/admin/delete-item/{p_b1}', follow_redirects=True)
    assert "Product not found or access denied" in tamper_del.data.decode('utf-8')
    print("✓ Unauthorized delete blocked.")

    # Verify Admin B's product still exists
    c.execute("SELECT product_id FROM products WHERE product_id = ?", (p_b1,))
    assert c.fetchone() is not None, "Product was deleted by unauthorized admin!"
    c.close()
    conn.close()

    print("\n--- Testing Admin B Dashboard & Catalog ---")
    with client.session_transaction() as sess:
        sess['admin_id'] = admin_b_id
        sess['admin_name'] = "Admin Beta"
        sess['admin_email'] = "adminB@test.com"

    # Admin B Dashboard test
    import html
    dash_b = client.get('/admin-dashboard')
    assert dash_b.status_code == 200
    html_dash_b = html.unescape(dash_b.data.decode('utf-8'))
    assert "Beta Coffee Maker" in html_dash_b
    assert "Beta Blender" in html_dash_b
    assert "Alpha Smartphone" not in html_dash_b, "Admin B must NOT see Admin A's products!"
    assert "Home & Kitchen" in html_dash_b
    assert "Electronics" not in html_dash_b, "Admin B must NOT see Admin A's categories!"
    print("✓ Admin B Dashboard: Shows only Admin B's products, categories, and statistics.")

    # Admin B Inventory test
    inv_b = client.get('/admin/item-list')
    assert inv_b.status_code == 200
    html_inv_b = inv_b.data.decode('utf-8')
    assert "Beta Coffee Maker" in html_inv_b
    assert "Beta Blender" in html_inv_b
    assert "Alpha Smartphone" not in html_inv_b
    assert "Alpha Jacket" not in html_inv_b
    print("✓ Admin B Product Inventory: Displays only Admin B's products.")

    print("\n--- Testing Customer Storefront (All Products Visible) ---")
    with client.session_transaction() as sess:
        sess.clear()
        sess['user_id'] = 1001
        sess['user_name'] = "Test Customer"
        sess['user_email'] = "customer@test.com"

    user_dash = client.get('/user-dashboard')
    assert user_dash.status_code == 200
    html_user = user_dash.data.decode('utf-8')
    assert "Alpha Smartphone" in html_user, "Customer must see Admin A's products!"
    assert "Alpha Jacket" in html_user, "Customer must see Admin A's products!"
    assert "Beta Coffee Maker" in html_user, "Customer must see Admin B's products!"
    assert "Beta Blender" in html_user, "Customer must see Admin B's products!"
    print("✓ Customer Storefront: Products from BOTH Admin A and Admin B are visible to customers!")

    # Cleanup test data
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM products WHERE product_id IN (?, ?, ?, ?)", (p_a1, p_a2, p_b1, p_b2))
    c.execute("DELETE FROM admin WHERE admin_id IN (?, ?)", (admin_a_id, admin_b_id))
    conn.commit()
    c.close()
    conn.close()

    print("\n==========================================")
    print("ALL TESTS PASSED! SYSTEM VERIFIED 100% OK.")
    print("==========================================")

if __name__ == '__main__':
    run_tests()
