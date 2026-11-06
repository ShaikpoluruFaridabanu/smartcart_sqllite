from flask import Flask, render_template, request, redirect, session, flash, jsonify, url_for, make_response
from flask_mail import Mail, Message
# Database uses sqlite3 via db.py
import bcrypt
import random
import config
import os
import time
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
import razorpay
import traceback
from decimal import Decimal
from utils.pdf_generator import generate_pdf


app = Flask(__name__)
app.secret_key = config.SECRET_KEY
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    # Enable secure cookies on HTTPS deployments; disable only for local HTTP.
    SESSION_COOKIE_SECURE=os.environ.get("SESSION_COOKIE_SECURE", "false").lower() in ("1", "true", "yes"),
)

# ---------------- EMAIL CONFIGURATION ----------------
app.config['MAIL_SERVER'] = config.MAIL_SERVER
app.config['MAIL_PORT'] = config.MAIL_PORT
app.config['MAIL_USE_TLS'] = config.MAIL_USE_TLS
app.config['MAIL_USERNAME'] = config.MAIL_USERNAME
app.config['MAIL_PASSWORD'] = config.MAIL_PASSWORD

mail = Mail(app)


# ---------------- DB CONNECTION FUNCTION --------------
from db import get_db_connection, init_db

# Initialize SQLite database schema
init_db()
ADMIN_UPLOAD_FOLDER = os.path.join(config.BASE_DIR, 'static', 'uploads', 'admin_profiles')
app.config['ADMIN_UPLOAD_FOLDER'] = ADMIN_UPLOAD_FOLDER

USER_UPLOAD_FOLDER = os.path.join(config.BASE_DIR, 'static', 'uploads', 'user_profiles')
app.config['USER_UPLOAD_FOLDER'] = USER_UPLOAD_FOLDER
os.makedirs(ADMIN_UPLOAD_FOLDER, exist_ok=True)
os.makedirs(USER_UPLOAD_FOLDER, exist_ok=True)
os.makedirs(os.path.join(config.BASE_DIR, 'static', 'uploads', 'product_images'), exist_ok=True)



# ---------------------------------------------------------
# HOME ROUTE (ROOT)
# ---------------------------------------------------------
@app.route('/')
def home():
    """Default landing route redirects to shopping dashboard."""
    return redirect(url_for('user_dashboard'))


# ---------------------------------------------------------
# ROUTE 1: ADMIN SIGNUP (SEND OTP)
# ---------------------------------------------------------
@app.route('/admin-signup', methods=['GET', 'POST'])
def admin_signup():

    # Show form
    if request.method == "GET":
        return render_template("admin/admin_signup.html")

    # POST → Process signup
    name = request.form['name']
    email = request.form['email']

    # 1️⃣ Check if admin email already exists
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT admin_id FROM admin WHERE LOWER(email)=LOWER(%s)", (email.strip(),))
    existing_admin = cursor.fetchone()
    cursor.close()
    conn.close()

    if existing_admin:
        flash("This email is already registered. Please login instead.", "danger")
        return redirect('/admin-signup')

    # 2️⃣ Save user input temporarily in session
    session['signup_name'] = name
    session['signup_email'] = email

    # 3️⃣ Generate OTP and store in session
    otp = random.randint(100000, 999999)
    session['otp'] = otp

    # 4️⃣ Send OTP Email
    message = Message(
        subject="SmartCart Admin OTP",
        sender=config.MAIL_USERNAME,
        recipients=[email]
    )
    message.body = f"Your OTP for SmartCart Admin Registration is: {otp}"
    mail.send(message)

    flash("OTP sent to your email!", "success")
    return redirect('/verify-otp')



# ---------------------------------------------------------
# ROUTE 2: DISPLAY OTP PAGE
# ---------------------------------------------------------
@app.route('/verify-otp', methods=['GET'])
def verify_otp_get():
    return render_template("admin/verify_otp.html")



# ---------------------------------------------------------
# ROUTE 3: VERIFY OTP + SAVE ADMIN
# ---------------------------------------------------------
@app.route('/verify-otp', methods=['POST'])
def verify_otp_post():
    
    # User submitted OTP + Password
    user_otp = request.form['otp']
    password = request.form['password']

    # Compare OTP
    if str(session.get('otp')) != str(user_otp):
        flash("Invalid OTP. Try again!", "danger")
        return redirect('/verify-otp')

    # Hash password using bcrypt
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

    # Insert admin into database
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO admin (name, email, password) VALUES (%s, %s, %s)",
        (session['signup_name'], session['signup_email'], hashed_password)
    )
    conn.commit()
    cursor.close()
    conn.close()

    # Clear temporary session data
    session.pop('otp', None)
    session.pop('signup_name', None)
    session.pop('signup_email', None)

    flash("Admin Registered Successfully!", "success")
    return redirect('/admin-signup')
@app.route('/admin-login', methods=['GET', 'POST'], endpoint='admin_login')
@app.route('/admin/login', methods=['GET', 'POST'])
@app.route('/admin', methods=['GET'])
def admin_login():

    # If already logged in, redirect straight to dashboard
    if 'admin_id' in session:
        return redirect('/admin-dashboard')

    # Show login page
    if request.method == 'GET':
        return render_template("admin/admin_login.html")

    # POST → Validate login
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '')

    if not email or not password:
        flash("Please enter both email and password.", "danger")
        return redirect('/admin-login')

    # Step 1: Check if admin email exists (case-insensitive)
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM admin WHERE LOWER(email)=LOWER(%s)", (email,))
    admin = cursor.fetchone()

    cursor.close()
    conn.close()

    if admin is None:
        flash("Email not found! Please register first.", "danger")
        return redirect('/admin-login')

    # Step 2: Compare entered password with hashed password
    stored_hash = admin['password']
    if isinstance(stored_hash, str):
        stored_hash = stored_hash.encode('utf-8')

    if not bcrypt.checkpw(password.encode('utf-8'), stored_hash):
        flash("Incorrect password! Try again.", "danger")
        return redirect('/admin-login')

    # Step 5: If login success → Create admin session
    session['admin_id'] = admin['admin_id']
    session['admin_name'] = admin['name']
    session['admin_email'] = admin['email']
    session.modified = True

    flash("Login Successful!", "success")
    return redirect('/admin-dashboard')





# ---------------------------------------------------------
# ---------------------------------------------------------
# STEP 1: ADMIN FORGOT PASSWORD - REQUEST OTP
# ---------------------------------------------------------
@app.route('/admin/forgot', methods=['GET', 'POST'], endpoint='admin_forgot')
@app.route('/forgot-password', methods=['GET', 'POST'], endpoint='forgot_password')
@app.route('/admin-forgot-password', methods=['GET', 'POST'])
@app.route('/admin/forgot-password', methods=['GET', 'POST'])
def admin_forgot():
    if request.method == 'GET':
        return render_template('admin/forgot.html')

    email = request.form.get('email', '').strip()
    if not email:
        flash("Please enter your registered admin email.", "danger")
        return redirect(url_for('admin_forgot'))

    # Clear any previous password-reset attempt.
    for key in ('admin_reset_email', 'admin_reset_otp', 'admin_reset_expiry', 'admin_reset_verified',
                'reset_email', 'reset_otp', 'reset_otp_expiry', 'reset_verified'):
        session.pop(key, None)

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT admin_id, name, email FROM admin WHERE LOWER(email)=LOWER(%s)", (email,))
    admin = cursor.fetchone()
    cursor.close()
    conn.close()

    if not admin:
        flash("No admin account found with that email address!", "danger")
        return redirect(url_for('admin_forgot'))

    otp = str(random.SystemRandom().randint(100000, 999999))
    expires_at = int(time.time()) + 300

    session['admin_reset_email'] = admin['email']
    session['admin_reset_otp'] = otp
    session['admin_reset_expiry'] = expires_at
    session['admin_reset_verified'] = False

    # Also keep legacy keys for backwards compatibility
    session['reset_email'] = admin['email']
    session['reset_otp'] = otp
    session['reset_otp_expiry'] = expires_at
    session['reset_verified'] = False
    session.modified = True

    try:
        message = Message(
            subject="SmartCart Admin Password Reset OTP",
            sender=config.MAIL_USERNAME,
            recipients=[admin['email']]
        )
        admin_name = admin.get('name') or 'Admin'
        message.body = (
            f"Hello {admin_name},\n\n"
            f"Your SmartCart admin password reset OTP is: {otp}\n\n"
            "This OTP is valid for 5 minutes. If you did not request a password reset, "
            "please ignore this email.\n"
        )
        mail.send(message)
    except Exception as exc:
        app.logger.exception("Failed to send admin reset OTP: %s", exc)
        for key in ('admin_reset_email', 'admin_reset_otp', 'admin_reset_expiry', 'admin_reset_verified',
                    'reset_email', 'reset_otp', 'reset_otp_expiry', 'reset_verified'):
            session.pop(key, None)
        flash("Unable to send OTP email right now. Please check your internet or try again later.", "danger")
        return redirect(url_for('admin_forgot'))

    flash("A 6-digit password reset OTP has been sent to your email!", "info")
    return redirect('/admin/forgot-otp')


# ---------------------------------------------------------
# STEP 2: ADMIN FORGOT PASSWORD - VERIFY OTP
# ---------------------------------------------------------
@app.route('/admin/forgot-otp', methods=['GET', 'POST'], endpoint='admin_forgot_otp')
@app.route('/admin/verify-reset-otp', methods=['GET', 'POST'])
@app.route('/admin-verify-otp', methods=['GET', 'POST'])
def admin_forgot_otp():
    reset_email = session.get('admin_reset_email') or session.get('reset_email')
    reset_otp = session.get('admin_reset_otp') or session.get('reset_otp')

    if not reset_email or not reset_otp:
        flash("Please request a password reset OTP first.", "danger")
        return redirect('/admin/forgot')

    if request.method == 'GET':
        return render_template('admin/forgot_otp.html')

    # Check OTP expiry
    expiry = session.get('admin_reset_expiry') or session.get('reset_otp_expiry', 0)
    if int(time.time()) > expiry:
        for key in ('admin_reset_email', 'admin_reset_otp', 'admin_reset_expiry', 'admin_reset_verified',
                    'reset_email', 'reset_otp', 'reset_otp_expiry', 'reset_verified'):
            session.pop(key, None)
        flash("OTP has expired. Please request a new one.", "danger")
        return redirect('/admin/forgot')

    entered_otp = request.form.get('otp', '').strip()
    if not entered_otp or entered_otp != str(reset_otp):
        flash("Invalid OTP. Please check the 6-digit code sent to your email and try again.", "danger")
        return redirect('/admin/forgot-otp')

    session['admin_reset_verified'] = True
    session['reset_verified'] = True
    session.modified = True

    flash("OTP verified successfully! You can now create a new password.", "success")
    return redirect('/admin/forgot-reset')


# ---------------------------------------------------------
# STEP 3: ADMIN FORGOT PASSWORD - SET NEW PASSWORD
# ---------------------------------------------------------
@app.route('/admin/forgot-reset', methods=['GET', 'POST'], endpoint='admin_forgot_reset')
@app.route('/reset-password', methods=['GET', 'POST'], endpoint='reset_password')
@app.route('/admin-reset-password', methods=['GET', 'POST'])
@app.route('/admin/reset-password', methods=['GET', 'POST'])
def admin_forgot_reset():
    reset_email = session.get('admin_reset_email') or session.get('reset_email')
    is_verified = session.get('admin_reset_verified') or session.get('reset_verified')

    if not reset_email:
        flash("Please request a password reset OTP first.", "danger")
        return redirect('/admin/forgot')

    if not is_verified:
        flash("Please verify your OTP first.", "danger")
        return redirect('/admin/forgot-otp')

    # Check session expiry
    expiry = session.get('admin_reset_expiry') or session.get('reset_otp_expiry', 0)
    if int(time.time()) > expiry:
        for key in ('admin_reset_email', 'admin_reset_otp', 'admin_reset_expiry', 'admin_reset_verified',
                    'reset_email', 'reset_otp', 'reset_otp_expiry', 'reset_verified'):
            session.pop(key, None)
        flash("Session expired. Please request a new OTP.", "danger")
        return redirect('/admin/forgot')

    if request.method == 'GET':
        return render_template('admin/forgot_reset.html')

    new_password = request.form.get('password') or request.form.get('new_password', '')
    confirm_password = request.form.get('confirm_password', '')

    if len(new_password) < 8:
        flash("Password must contain at least 8 characters.", "danger")
        return redirect('/admin/forgot-reset')

    if new_password != confirm_password:
        flash("Passwords do not match.", "danger")
        return redirect('/admin/forgot-reset')

    hashed_password = bcrypt.hashpw(
        new_password.encode('utf-8'),
        bcrypt.gensalt()
    ).decode('utf-8')

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE admin SET password=%s WHERE LOWER(email)=LOWER(%s)",
        (hashed_password, reset_email)
    )
    conn.commit()
    updated_rows = cursor.rowcount
    cursor.close()
    conn.close()

    for key in ('admin_reset_email', 'admin_reset_otp', 'admin_reset_expiry', 'admin_reset_verified',
                'reset_email', 'reset_otp', 'reset_otp_expiry', 'reset_verified'):
        session.pop(key, None)
    session.modified = True

    if updated_rows:
        flash("Password reset successfully! Please login with your new password.", "success")
        return redirect('/admin-login')

    flash("Unable to reset password. Please try again.", "danger")
    return redirect(url_for('admin_forgot'))



# =================================================================
# ROUTE 5: ADMIN DASHBOARD (PROTECTED ROUTE)
# =================================================================
@app.route('/admin-dashboard')
@app.route('/admin/dashboard')
def admin_dashboard():

    # Protect dashboard → Only logged-in admin can access
    if 'admin_id' not in session:
        flash("Please login to access dashboard!", "danger")
        return redirect('/admin-login')

    # Send admin name to dashboard UI
    return render_template("admin/dashboard.html", admin_name=session['admin_name'])



# =================================================================
# ROUTE 6: ADMIN LOGOUT
# =================================================================
@app.route('/admin-logout')
@app.route('/admin/logout')
def admin_logout():

    # Clear admin session
    session.pop('admin_id', None)
    session.pop('admin_name', None)
    session.pop('admin_email', None)

    flash("Logged out successfully.", "success")
    return redirect('/admin-login')
UPLOAD_FOLDER = os.path.join(config.BASE_DIR, 'static', 'uploads', 'product_images')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


# =================================================================
# ROUTE 7: SHOW ADD PRODUCT PAGE (Protected Route)
# =================================================================
@app.route('/admin/add-item', methods=['GET'])
def add_item_page():

    # Only logged-in admin can access
    if 'admin_id' not in session:
        flash("Please login first!", "danger")
        return redirect('/admin-login')

    return render_template("admin/add_item.html")



# =================================================================
# ROUTE 8: ADD PRODUCT INTO DATABASE
# =================================================================
@app.route('/admin/add-item', methods=['POST'])
def add_item():

    # Check admin session
    if 'admin_id' not in session:
        flash("Please login first!", "danger")
        return redirect('/admin-login')

    # 1️⃣ Get form data
    name = request.form['name']
    description = request.form['description']
    category = request.form['category']
    price = request.form['price']
    image_file = request.files['image']

    # 2️⃣ Validate image upload
    if image_file.filename == "":
        flash("Please upload a product image!", "danger")
        return redirect('/admin/add-item')

    # 3️⃣ Secure the file name
    filename = secure_filename(image_file.filename)

    # 4️⃣ Create full path
    image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

    # 5️⃣ Save image into folder
    image_file.save(image_path)

    # 6️⃣ Insert product into database
    conn = get_db_connection()
    cursor = conn.cursor()
    admin_id = session.get('admin_id')

    cursor.execute(
    """INSERT INTO products
    (name, description, category, price, image, admin_id)
    VALUES (%s, %s, %s, %s, %s, %s)""",
    (name, description, category, price, filename, admin_id)
)
    conn.commit()
    cursor.close()
    conn.close()

    flash("Product added successfully!", "success")
    return redirect('/admin/add-item')
@app.route('/admin/item-list')
@app.route('/admin-itemlist')
@app.route('/admin-item-list')
@app.route('/admin/items')
@app.route('/item-list')
def item_list():

    if 'admin_id' not in session:
        flash("Please login!", "danger")
        return redirect('/admin-login')

    search = request.args.get('search', '')
    category_filter = request.args.get('category', '')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # 1️⃣ Fetch category list for dropdown
    cursor.execute("SELECT DISTINCT category FROM products")
    categories = cursor.fetchall()

    # 2️⃣ Build dynamic query based on filters
    query = "SELECT * FROM products WHERE 1=1"
    params = []

    if search:
        query += " AND name LIKE %s"
        params.append("%" + search + "%")

    if category_filter:
        query += " AND category = %s"
        params.append(category_filter)

    cursor.execute(query, params)
    products = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        "admin/item_list.html",
        products=products,
        categories=categories
    )


# =================================================================
#  route-13 DELETE PRODUCT (DELETE DB ROW + DELETE IMAGE FILE)
# =================================================================
@app.route('/admin/delete-item/<int:item_id>')
def delete_item(item_id):

    if 'admin_id' not in session:
        flash("Please login first!", "danger")
        return redirect('/admin-login')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # 1️⃣ Fetch product to get image name
    cursor.execute("SELECT image FROM products WHERE product_id=%s", (item_id,))
    product = cursor.fetchone()

    if not product:
        flash("Product not found!", "danger")
        return redirect('/admin/item-list')

    image_name = product['image']

    # Delete image from folder
    image_path = os.path.join(app.config['UPLOAD_FOLDER'], image_name)
    if os.path.exists(image_path):
        os.remove(image_path)

    # 2️⃣ Delete product from DB
    cursor.execute("DELETE FROM products WHERE product_id=%s", (item_id,))
    conn.commit()

    cursor.close()
    conn.close()

    flash("Product deleted successfully!", "success")
    return redirect('/admin/item-list')



#=================================================================
# ROUTE 10: VIEW SINGLE PRODUCT DETAILS
# =================================================================
@app.route('/admin/view-item/<int:item_id>')
def view_item(item_id):

    # Check admin session
    if 'admin_id' not in session:
        flash("Please login first!", "danger")
        return redirect('/admin-login')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM products WHERE product_id = %s", (item_id,))
    product = cursor.fetchone()

    cursor.close()
    conn.close()

    if not product:
        flash("Product not found!", "danger")
        return redirect('/admin/item-list')

    return render_template("admin/view_item.html", product=product)

@app.route('/admin/update-item/<int:item_id>', methods=['GET'])
def update_item_page(item_id):

    # Check login
    if 'admin_id' not in session:
        flash("Please login!", "danger")
        return redirect('/admin-login')

    # Fetch product data
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM products WHERE product_id = %s", (item_id,))
    product = cursor.fetchone()

    cursor.close()
    conn.close()

    if not product:
        flash("Product not found!", "danger")
        return redirect('/admin/item-list')

    return render_template("admin/update_item.html", product=product)
@app.route('/admin/update-item/<int:item_id>', methods=['POST'])
def update_item(item_id):

    if 'admin_id' not in session:
        flash("Please login!", "danger")
        return redirect('/admin-login')

    # 1️⃣ Get updated form data
    name = request.form['name']
    description = request.form['description']
    category = request.form['category']
    price = request.form['price']

    new_image = request.files['image']

    # 2️⃣ Fetch old product data
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM products WHERE product_id = %s", (item_id,))
    product = cursor.fetchone()

    if not product:
        flash("Product not found!", "danger")
        return redirect('/admin/item-list')

    old_image_name = product['image']

    # 3️⃣ If admin uploaded a new image → replace it
    if new_image and new_image.filename != "":
        
        # Secure filename
        from werkzeug.utils import secure_filename
        new_filename = secure_filename(new_image.filename)

        # Save new image
        new_image_path = os.path.join(app.config['UPLOAD_FOLDER'], new_filename)
        new_image.save(new_image_path)

        # Delete old image file
        old_image_path = os.path.join(app.config['UPLOAD_FOLDER'], old_image_name)
        if os.path.exists(old_image_path):
            os.remove(old_image_path)

        final_image_name = new_filename

    else:
        # No new image uploaded → keep old one
        final_image_name = old_image_name

    # 4️⃣ Update product in the database
    cursor.execute("""
        UPDATE products
        SET name=%s, description=%s, category=%s, price=%s, image=%s
        WHERE product_id=%s
    """, (name, description, category, price, final_image_name, item_id))

    conn.commit()
    cursor.close()
    conn.close()

    flash("Product updated successfully!", "success")
    return redirect('/admin/item-list')

@app.route('/admin/profile', methods=['GET'])
def admin_profile():
    if 'admin_id' not in session:
        flash("Please login!", "danger")
        return redirect('/admin-login')

    admin_id = session['admin_id']

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM admin WHERE admin_id = %s", (admin_id,))
    admin = cursor.fetchone()

    cursor.close()
    conn.close()

    if not admin:
        flash("Admin account not found!", "danger")
        return redirect('/admin-login')

    return render_template("admin/admin_profile.html", admin=admin)


# =================================================================
# ROUTE 2: EDIT / UPDATE ADMIN PROFILE (NAME, EMAIL, PASSWORD, IMAGE)
# =================================================================
@app.route('/admin-edit-profile', methods=['GET', 'POST'])
@app.route('/admin/profile', methods=['POST'])
@app.route('/admin/edit-profile', methods=['GET', 'POST'])
def admin_edit_profile():
    if 'admin_id' not in session:
        flash("Please login!", "danger")
        return redirect('/admin-login')

    admin_id = session['admin_id']
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        # 1️⃣ Get form data
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        new_password = request.form.get('password', '').strip()
        new_image = request.files.get('profile_image')

        if not name or not email:
            cursor.close()
            conn.close()
            flash("Name and email are required!", "danger")
            return redirect(url_for('admin_edit_profile'))

        # 2️⃣ Fetch old admin data
        cursor.execute("SELECT * FROM admin WHERE admin_id = %s", (admin_id,))
        admin = cursor.fetchone()

        if not admin:
            cursor.close()
            conn.close()
            flash("Admin account not found!", "danger")
            return redirect('/admin-login')

        old_image_name = admin.get('profile_image')

        # 3️⃣ Update password only if entered
        if new_password:
            hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        else:
            hashed_password = admin['password']  # keep old password

        # 4️⃣ Process new profile image if uploaded
        if new_image and new_image.filename != "":
            from werkzeug.utils import secure_filename
            new_filename = secure_filename(new_image.filename)

            # Ensure upload folder exists
            os.makedirs(app.config['ADMIN_UPLOAD_FOLDER'], exist_ok=True)

            # Save new image
            image_path = os.path.join(app.config['ADMIN_UPLOAD_FOLDER'], new_filename)
            new_image.save(image_path)

            # Delete old image if it exists
            if old_image_name:
                old_image_path = os.path.join(app.config['ADMIN_UPLOAD_FOLDER'], old_image_name)
                if os.path.exists(old_image_path) and os.path.isfile(old_image_path):
                    try:
                        os.remove(old_image_path)
                    except OSError:
                        pass

            final_image_name = new_filename
        else:
            final_image_name = old_image_name

        # 5️⃣ Update database
        cursor.execute("""
            UPDATE admin
            SET name=%s, email=%s, password=%s, profile_image=%s
            WHERE admin_id=%s
        """, (name, email, hashed_password, final_image_name, admin_id))

        conn.commit()
        cursor.close()
        conn.close()

        # Update session name for UI consistency
        session['admin_name'] = name  
        session['admin_email'] = email

        flash("Profile updated successfully!", "success")
        return redirect(url_for('admin_profile'))

    # GET request: render edit profile page
    cursor.execute("SELECT * FROM admin WHERE admin_id = %s", (admin_id,))
    admin = cursor.fetchone()
    cursor.close()
    conn.close()

    if not admin:
        flash("Admin account not found!", "danger")
        return redirect('/admin-login')

    return render_template("admin/admin_edit_profile.html", admin=admin)


# Backward compatibility alias
admin_profile_update = admin_edit_profile
@app.route('/user-register', methods=['GET', 'POST'])
def user_register():

    if request.method == 'GET':
        return render_template('user/user_register.html')

    name = request.form['name'].strip()
    email = request.form['email'].strip().lower()
    phone = request.form['phone'].strip()
    password = request.form['password']
    confirm_password = request.form['confirm_password']

    if password != confirm_password:
        flash("Passwords do not match!", "danger")
        return redirect('/user-register')

    if len(password) < 8:
        flash("Password must contain at least 8 characters!", "danger")
        return redirect('/user-register')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        "SELECT user_id FROM users WHERE LOWER(email)=LOWER(%s)",
        (email.strip(),)
    )

    existing_user = cursor.fetchone()

    cursor.close()
    conn.close()

    if existing_user:
        flash("Email already registered. Please login!", "danger")
        return redirect('/user-login')

    # Generate OTP
    otp = str(random.randint(100000, 999999))

    # Hash password
    password_hash = bcrypt.hashpw(
        password.encode('utf-8'),
        bcrypt.gensalt()
    ).decode('utf-8')

    # Hash OTP
    otp_hash = bcrypt.hashpw(
        otp.encode('utf-8'),
        bcrypt.gensalt()
    ).decode('utf-8')

    # Store temporary registration in Flask session
    session['user_signup'] = {
        'name': name,
        'email': email,
        'phone': phone,
        'password': password_hash,
        'otp_hash': otp_hash,
        'expires_at': time.time() + 300
    }

    # Send OTP email
    message = Message(
        subject="SmartCart User Registration OTP",
        sender=config.MAIL_USERNAME,
        recipients=[email]
    )

    message.body = f"""
Hello {name},

Your SmartCart registration OTP is: {otp}

This OTP is valid for 5 minutes.

Do not share this OTP with anyone.
"""

    mail.send(message)

    flash("OTP sent successfully to your email!", "success")
    return redirect('/user-verify-otp')


# =====================================================
# USER OTP VERIFICATION
# =====================================================

@app.route('/user-verify-otp', methods=['GET', 'POST'])
def user_verify_otp():

    pending_user = session.get('user_signup')

    if not pending_user:
        flash("Please register first!", "danger")
        return redirect('/user-register')

    if request.method == 'GET':
        return render_template('user/user_verify_otp.html')

    user_otp = request.form['otp'].strip()

    # Check OTP expiry
    if time.time() > pending_user['expires_at']:

        session.pop('user_signup', None)

        flash("OTP expired! Please register again.", "danger")
        return redirect('/user-register')

    # Verify OTP
    if not bcrypt.checkpw(
        user_otp.encode('utf-8'),
        pending_user['otp_hash'].encode('utf-8')
    ):

        flash("Invalid OTP! Please try again.", "danger")
        return redirect('/user-verify-otp')

    # Save verified customer directly into users table
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO users (name, email, phone, password)
        VALUES (%s, %s, %s, %s)
    """, (
        pending_user['name'],
        pending_user['email'],
        pending_user['phone'],
        pending_user['password']
    ))

    conn.commit()

    cursor.close()
    conn.close()

    # Clear temporary session data
    session.pop('user_signup', None)

    flash("Registration successful! Please login.", "success")
    return redirect('/user-login')


# =====================================================
# USER LOGIN
# =====================================================

@app.route('/user-login', methods=['GET', 'POST'])
def user_login():

    if request.method == 'GET':
        return render_template('user/user_login.html')

    email = request.form['email'].strip().lower()
    password = request.form['password']

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        "SELECT * FROM users WHERE LOWER(email)=LOWER(%s)",
        (email.strip(),)
    )

    user = cursor.fetchone()

    cursor.close()
    conn.close()

    if not user:
        flash("Email not registered! Please sign up.", "danger")
        return redirect('/user-login')

    stored_password = user['password']
    if isinstance(stored_password, str):
        stored_password = stored_password.encode('utf-8')

    if not bcrypt.checkpw(
        password.encode('utf-8'),
        stored_password
    ):
        flash("Incorrect password! Try again.", "danger")
        return redirect('/user-login')

    # Create customer session
    session['user_id'] = user['user_id']
    session['user_name'] = user['name']
    session['user_email'] = user['email']

    flash("Login successful! Welcome to SmartCart.", "success")
    return redirect('/user-dashboard')


# =====================================================
# USER FORGOT PASSWORD - SEND OTP
# =====================================================

@app.route('/user-forgot-password', methods=['GET', 'POST'])
def user_forgot_password():

    if request.method == 'GET':
        return render_template('user/user_forgot_password.html')

    email = request.form['email'].strip().lower()

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        "SELECT user_id, name, email FROM users WHERE LOWER(email)=LOWER(%s)",
        (email.strip(),)
    )

    user = cursor.fetchone()
    cursor.close()
    conn.close()

    if not user:
        flash("Email address is not registered!", "danger")
        return redirect('/user-forgot-password')

    otp = str(random.randint(100000, 999999))

    otp_hash = bcrypt.hashpw(
        otp.encode('utf-8'),
        bcrypt.gensalt()
    ).decode('utf-8')

    session['user_password_reset'] = {
        'email': email,
        'otp_hash': otp_hash,
        'expires_at': time.time() + 300,
        'verified': False
    }

    message = Message(
        subject="SmartCart Password Reset OTP",
        sender=config.MAIL_USERNAME,
        recipients=[email]
    )

    message.body = f"""
Hello {user['name']},

Your SmartCart password reset OTP is: {otp}

This OTP is valid for 5 minutes.
Do not share this OTP with anyone.
"""

    mail.send(message)

    flash("OTP sent to your registered email!", "success")
    return redirect('/user-verify-reset-otp')


# =====================================================
# STEP 2: VERIFY OTP
# =====================================================

@app.route('/user-verify-reset-otp', methods=['GET', 'POST'])
def user_verify_reset_otp():

    reset_data = session.get('user_password_reset')

    if not reset_data:
        flash("Please request a password reset first!", "danger")
        return redirect('/user-forgot-password')

    if request.method == 'GET':
        return render_template('user/user_verify_reset_otp.html')

    otp = request.form['otp'].strip()

    if time.time() > reset_data['expires_at']:
        session.pop('user_password_reset', None)
        flash("OTP expired! Please request a new OTP.", "danger")
        return redirect('/user-forgot-password')

    if not otp.isdigit() or len(otp) != 6:
        flash("Enter a valid 6-digit OTP!", "danger")
        return redirect('/user-verify-reset-otp')

    if not bcrypt.checkpw(
        otp.encode('utf-8'),
        reset_data['otp_hash'].encode('utf-8')
    ):
        flash("Invalid OTP! Please try again.", "danger")
        return redirect('/user-verify-reset-otp')

    reset_data['verified'] = True
    session['user_password_reset'] = reset_data

    flash("OTP verified successfully! Set your new password.", "success")
    return redirect('/user-set-new-password')


# =====================================================
# STEP 3: SET NEW PASSWORD
# =====================================================

@app.route('/user-set-new-password', methods=['GET', 'POST'])
def user_set_new_password():

    reset_data = session.get('user_password_reset')

    if not reset_data or not reset_data.get('verified'):
        flash("Please verify your OTP first!", "danger")
        return redirect('/user-forgot-password')

    if time.time() > reset_data['expires_at']:
        session.pop('user_password_reset', None)
        flash("OTP expired! Please request a new OTP.", "danger")
        return redirect('/user-forgot-password')

    if request.method == 'GET':
        return render_template('user/user_set_new_password.html')

    new_password = request.form['new_password']
    confirm_password = request.form['confirm_password']

    if len(new_password) < 8:
        flash("Password must contain at least 8 characters!", "danger")
        return redirect('/user-set-new-password')

    if new_password != confirm_password:
        flash("Passwords do not match!", "danger")
        return redirect('/user-set-new-password')

    new_password_hash = bcrypt.hashpw(
        new_password.encode('utf-8'),
        bcrypt.gensalt()
    ).decode('utf-8')

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE users
        SET password = %s
        WHERE LOWER(email) = LOWER(%s)
    """, (
        new_password_hash,
        reset_data['email'].strip()
    ))

    conn.commit()
    cursor.close()
    conn.close()

    session.pop('user_password_reset', None)

    flash("Password reset successful! Please login.", "success")
    return redirect('/user-login')



# =====================================================
# USER DASHBOARD
# =====================================================
@app.route('/user-dashboard')
def user_dashboard():

    if 'user_id' not in session:
        flash("Please login first!", "danger")
        return redirect('/user-login')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT product_id, name, description, category, price, image
        FROM products
        ORDER BY product_id DESC
    """)

    products = cursor.fetchall()

    cursor.close()
    conn.close()

    # Get cart count
    cart = session.get('cart', {})
    cart_count = sum(
        item['quantity'] for item in cart.values()
    )

    return render_template(
        'user/user_dashboard.html',
        user_name=session['user_name'],
        products=products,
        cart_count=cart_count
    )


# =====================================================
# USER LOGOUT
# =====================================================

@app.route('/user-logout')
def user_logout():

    session.pop('user_id', None)
    session.pop('user_name', None)
    session.pop('user_email', None)

    flash("Logged out successfully!", "success")
    return redirect('/user-login')


# =====================================================
# USER - VIEW PRODUCT DETAILS
# =====================================================

@app.route('/user-product/<int:product_id>')
def user_view_product(product_id):

    if 'user_id' not in session:
        flash("Please login first!", "danger")
        return redirect('/user-login')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT product_id, name, description, category, price, image
        FROM products
        WHERE product_id = %s
    """, (product_id,))

    product = cursor.fetchone()

    cursor.close()
    conn.close()

    if not product:
        flash("Product not found!", "danger")
        return redirect('/user-dashboard')

    return render_template(
        'user/view_product.html',
        product=product
    )


# =====================================================
# USER PROFILE
# =====================================================

@app.route('/user-profile')
@app.route('/user/profile')
@app.route('/profile')
def user_profile():

    if 'admin_id' in session and 'user_id' not in session:
        return redirect('/admin/profile')

    if 'user_id' not in session:
        flash("Please login first!", "danger")
        return redirect('/user-login')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT *
        FROM users
        WHERE user_id = %s
    """, (session['user_id'],))

    user = cursor.fetchone()

    cursor.close()
    conn.close()

    if not user:
        session.clear()
        flash("User account not found. Please login again.", "danger")
        return redirect('/user-login')

    return render_template('user/user_profile.html', user=user)


# =====================================================
# EDIT USER PROFILE
# =====================================================

@app.route('/user-edit-profile', methods=['GET', 'POST'])
def user_edit_profile():

    if 'user_id' not in session:
        flash("Please login first!", "danger")
        return redirect('/user-login')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':

        name = request.form.get('name', '').strip()
        phone = request.form.get('phone', '').strip()
        new_image = request.files.get('profile_image')

        if not name or not phone:
            cursor.close()
            conn.close()
            flash("All fields are required!", "danger")
            return redirect('/user-edit-profile')

        if not phone.isdigit() or len(phone) != 10:
            cursor.close()
            conn.close()
            flash("Enter a valid 10-digit phone number!", "danger")
            return redirect('/user-edit-profile')

        # Fetch current user to manage existing profile image
        cursor.execute("SELECT * FROM users WHERE user_id = %s", (session['user_id'],))
        current_user = cursor.fetchone()
        old_image = current_user.get('profile_image') if current_user else None

        final_image = old_image
        if new_image and new_image.filename != "":
            orig_filename = secure_filename(new_image.filename)
            ext = os.path.splitext(orig_filename)[1].lower()

            if ext in ['.jpg', '.jpeg', '.png', '.webp']:
                new_filename = f"user_{session['user_id']}_{int(time.time())}{ext}"
                os.makedirs(app.config['USER_UPLOAD_FOLDER'], exist_ok=True)
                image_path = os.path.join(app.config['USER_UPLOAD_FOLDER'], new_filename)
                new_image.save(image_path)

                # Remove previous profile image file if exists
                if old_image:
                    old_path = os.path.join(app.config['USER_UPLOAD_FOLDER'], old_image)
                    if os.path.exists(old_path) and os.path.isfile(old_path):
                        try:
                            os.remove(old_path)
                        except OSError:
                            pass

                final_image = new_filename
            else:
                cursor.close()
                conn.close()
                flash("Invalid image format! Only JPG, PNG, and WebP are allowed.", "danger")
                return redirect('/user-edit-profile')

        cursor.execute("""
            UPDATE users
            SET name = %s, phone = %s, profile_image = %s
            WHERE user_id = %s
        """, (name, phone, final_image, session['user_id']))

        conn.commit()

        # Update the name and image stored in session
        session['user_name'] = name
        session['user_image'] = final_image

        cursor.close()
        conn.close()

        flash("Profile updated successfully!", "success")
        return redirect('/user-profile')

    cursor.execute("""
        SELECT *
        FROM users
        WHERE user_id = %s
    """, (session['user_id'],))

    user = cursor.fetchone()

    cursor.close()
    conn.close()

    if not user:
        flash("User account not found!", "danger")
        return redirect('/user-login')

    return render_template('user/user_edit_profile.html', user=user)


# ==============================
# USER CART SYSTEM - DAY 11
# ==============================


# COMMON CART SUMMARY FUNCTION
def get_cart_summary(cart):

    cart_count = sum(
        int(item['quantity']) for item in cart.values()
    )

    grand_total = sum(
        float(item['price']) * int(item['quantity'])
        for item in cart.values()
    )

    return cart_count, grand_total


# 1. ADD TO CART - AJAX
@app.route('/user/add-to-cart-ajax/<int:product_id>', methods=['POST'])
def add_to_cart_ajax(product_id):

    if 'user_id' not in session:
        return jsonify({
            'success': False,
            'message': 'Please login first!'
        }), 401

    cart = session.get('cart', {})

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(
            "SELECT * FROM products WHERE product_id = %s",
            (product_id,)
        )

        product = cursor.fetchone()

    finally:
        cursor.close()
        conn.close()

    if not product:
        return jsonify({
            'success': False,
            'message': 'Product not found!'
        }), 404

    pid = str(product_id)

    if pid in cart:

        cart[pid]['quantity'] += 1

    else:

        cart[pid] = {
            'name': product['name'],
            'price': float(product['price']),
            'image': product['image'],
            'quantity': 1
        }

    session['cart'] = cart
    session.modified = True

    cart_count, grand_total = get_cart_summary(cart)

    return jsonify({
        'success': True,
        'message': 'Product added successfully!',
        'cart_count': cart_count,
        'grand_total': grand_total
    })


# 2. VIEW CART
@app.route('/user/cart')
@app.route('/cart')
def view_cart():

    if 'user_id' not in session:
        return redirect('/user-login')

    cart = session.get('cart', {})

    print("CART DATA:", cart)

    cart_count, grand_total = get_cart_summary(cart)

    return render_template(
        'user/cart.html',
        cart=cart,
        grand_total=grand_total,
        cart_count=cart_count
    )


# 3. INCREASE QUANTITY - AJAX
@app.route('/user/cart/increase/<pid>', methods=['POST'])
def increase_quantity(pid):

    if 'user_id' not in session:
        return jsonify({
            'success': False,
            'message': 'Please login first!'
        }), 401

    cart = session.get('cart', {})

    if pid not in cart:
        return jsonify({
            'success': False,
            'message': 'Product not found in cart!'
        }), 404

    cart[pid]['quantity'] += 1

    session['cart'] = cart
    session.modified = True

    cart_count, grand_total = get_cart_summary(cart)

    item_total = (
        float(cart[pid]['price']) *
        int(cart[pid]['quantity'])
    )

    return jsonify({
        'success': True,
        'quantity': cart[pid]['quantity'],
        'item_total': item_total,
        'grand_total': grand_total,
        'cart_count': cart_count,
        'removed': False
    })


# 4. DECREASE QUANTITY - AJAX
@app.route('/user/cart/decrease/<pid>', methods=['POST'])
def decrease_quantity(pid):

    if 'user_id' not in session:
        return jsonify({
            'success': False,
            'message': 'Please login first!'
        }), 401

    cart = session.get('cart', {})

    if pid not in cart:
        return jsonify({
            'success': False,
            'message': 'Product not found in cart!'
        }), 404

    if cart[pid]['quantity'] > 1:

        cart[pid]['quantity'] -= 1
        removed = False

        quantity = cart[pid]['quantity']

        item_total = (
            float(cart[pid]['price']) * quantity
        )

    else:

        del cart[pid]

        removed = True
        quantity = 0
        item_total = 0

    session['cart'] = cart
    session.modified = True

    cart_count, grand_total = get_cart_summary(cart)

    return jsonify({
        'success': True,
        'quantity': quantity,
        'item_total': item_total,
        'grand_total': grand_total,
        'cart_count': cart_count,
        'removed': removed
    })


# 5. REMOVE PRODUCT - AJAX
@app.route('/user/cart/remove/<pid>', methods=['POST'])
def remove_from_cart(pid):

    if 'user_id' not in session:
        return jsonify({
            'success': False,
            'message': 'Please login first!'
        }), 401

    cart = session.get('cart', {})

    if pid not in cart:
        return jsonify({
            'success': False,
            'message': 'Product not found in cart!'
        }), 404

    del cart[pid]

    session['cart'] = cart
    session.modified = True

    cart_count, grand_total = get_cart_summary(cart)

    return jsonify({
        'success': True,
        'removed': True,
        'cart_count': cart_count,
        'grand_total': grand_total
    })

# ======================================
# CHECKOUT WITH SESSION ADDRESS
# ======================================

# 1. SELECTED PRODUCTS
@app.route('/user/checkout-selected', methods=['POST'])
def checkout_selected():

    if 'user_id' not in session:
        return redirect('/user-login')

    selected_ids = request.form.getlist('selected_ids')
    cart = session.get('cart', {})

    selected_items = {
        pid: cart[pid]
        for pid in selected_ids
        if pid in cart
    }

    if not selected_items:
        return redirect(url_for('view_cart'))

    # Remember selected products in session
    session['checkout_selected_ids'] = list(selected_items.keys())

    return redirect(url_for('checkout_page'))


# 2. DISPLAY CHECKOUT PAGE
@app.route('/user/checkout')
@app.route('/checkout')
def checkout_page():

    if 'user_id' not in session:
        return redirect('/user-login')

    cart = session.get('cart', {})
    selected_ids = session.get('checkout_selected_ids', [])

    selected_items = {
        pid: cart[pid]
        for pid in selected_ids
        if pid in cart
    }

    if not selected_items:
        return redirect(url_for('view_cart'))

    selected_total = sum(
        float(item['price']) * int(item['quantity'])
        for item in selected_items.values()
    )

    selected_count = sum(
        int(item['quantity'])
        for item in selected_items.values()
    )

    # Retrieve saved address from session
    saved_address = session.get('delivery_address', {})

    return render_template(
        'user/checkout.html',
        selected_items=selected_items,
        selected_total=selected_total,
        selected_count=selected_count,
        saved_address=saved_address
    )


# 3. SAVE DELIVERY ADDRESS IN SESSION

@app.route('/user/save-delivery-address', methods=['POST'])
def save_delivery_address():

    if 'user_id' not in session:
        return redirect('/user-login')

    full_name = request.form.get('full_name', '').strip()
    phone = request.form.get('phone', '').strip()
    address_line = request.form.get('address_line', '').strip()
    city = request.form.get('city', '').strip()
    state = request.form.get('state', '').strip()
    pincode = request.form.get('pincode', '').strip()
    landmark = request.form.get('landmark', '').strip()

    if not all([
        full_name, phone, address_line,
        city, state, pincode
    ]):
        flash('Please fill all required address fields.', 'error')
        return redirect(url_for('checkout_page'))

    if not phone.isdigit() or len(phone) != 10:
        flash('Enter a valid 10-digit mobile number.', 'error')
        return redirect(url_for('checkout_page'))

    if not pincode.isdigit() or len(pincode) != 6:
        flash('Enter a valid 6-digit pincode.', 'error')
        return redirect(url_for('checkout_page'))

    # Save address in session
    session['delivery_address'] = {
        'full_name': full_name,
        'phone': phone,
        'address_line': address_line,
        'city': city,
        'state': state,
        'pincode': pincode,
        'landmark': landmark
    }

    session.modified = True

    flash('Delivery address saved successfully!', 'success')

    # Redirect to payment page
    return redirect(url_for('user_pay'))


#payment

razorpay_client = razorpay.Client(
    auth=(
        config.RAZORPAY_KEY_ID,
        config.RAZORPAY_KEY_SECRET
    )
)

@app.route('/user/pay')
def user_pay():

    if 'user_id' not in session:
        return redirect('/user-login')

    delivery_address = session.get('delivery_address')

    if not delivery_address:
        flash("Please save your delivery address.", "error")
        return redirect(url_for('checkout_page'))

    cart = session.get('cart', {})
    selected_ids = session.get('checkout_selected_ids', [])

    selected_items = {
        str(pid): cart[str(pid)]
        for pid in selected_ids
        if str(pid) in cart
    }

    if not selected_items:
        flash("No products selected.", "error")
        return redirect(url_for('view_cart'))

    if not config.RAZORPAY_KEY_ID or not config.RAZORPAY_KEY_SECRET:
        app.logger.error("Razorpay credentials are not configured.")
        flash("Online payment is temporarily unavailable. Please contact support.", "error")
        return redirect(url_for('checkout_page'))

    total_amount = sum(
        Decimal(str(item['price'])) * int(item['quantity'])
        for item in selected_items.values()
    )

    razorpay_amount = int(total_amount * 100)

    try:
        razorpay_order = razorpay_client.order.create({
            "amount": razorpay_amount,
            "currency": "INR",
            "payment_capture": 1
        })

        session['razorpay_order_id'] = razorpay_order['id']
        session['razorpay_amount'] = razorpay_amount

    except Exception as e:
        print("Razorpay order creation error:", e)
        flash("Unable to create payment. Please try again.", "error")
        return redirect(url_for('checkout_page'))

    return render_template(
        'user/payment.html',
        selected_items=selected_items,
        total_amount=total_amount,
        delivery_address=delivery_address,
        razorpay_key_id=config.RAZORPAY_KEY_ID,
        razorpay_order_id=razorpay_order['id'],
        razorpay_amount=razorpay_amount
    )



@app.route('/verify-payment', methods=['POST'])
@app.route('/payment-success', methods=['POST'])  # Backward-compatible URL

def payment_success():
    """Verify a Razorpay payment and save the order exactly once."""
    if 'user_id' not in session:
        flash("Please login to complete your payment.", "error")
        return redirect(url_for('user_login'))

    payment_id = request.form.get('razorpay_payment_id', '').strip()
    razorpay_order_id = request.form.get('razorpay_order_id', '').strip()
    signature = request.form.get('razorpay_signature', '').strip()

    if not all((payment_id, razorpay_order_id, signature)):
        flash("Payment verification failed because payment details are missing.", "error")
        return redirect(url_for('view_cart'))

    # A server-created order must belong to this user's current checkout session.
    if razorpay_order_id != session.get('razorpay_order_id'):
        flash("This payment order does not match your current checkout. Please contact support before retrying.", "error")
        return redirect(url_for('view_cart'))

    conn = None
    cursor = None
    try:
        expected_amount = session.get('razorpay_amount')
        if expected_amount is None:
            raise ValueError("The expected payment amount is missing from the session.")

        # Never trust the browser's success callback by itself.
        razorpay_client.utility.verify_payment_signature({
            'razorpay_order_id': razorpay_order_id,
            'razorpay_payment_id': payment_id,
            'razorpay_signature': signature
        })

        payment = razorpay_client.payment.fetch(payment_id)
        if payment.get('status') == 'authorized':
            razorpay_client.payment.capture(payment_id, int(expected_amount))
            payment = razorpay_client.payment.fetch(payment_id)

        if payment.get('status') != 'captured':
            raise ValueError("Payment is not captured. Razorpay status: " + str(payment.get('status')))
        if payment.get('order_id') != razorpay_order_id:
            raise ValueError("The payment belongs to a different Razorpay order.")
        if int(payment.get('amount', 0)) != int(expected_amount):
            raise ValueError("The captured amount does not match the server-created order amount.")
        if payment.get('currency') != 'INR':
            raise ValueError("Only INR payments are accepted for this order.")

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Idempotency: a repeated callback must never create a second order.
        cursor.execute(
            """SELECT order_id, user_id FROM orders
               WHERE razorpay_order_id = %s OR razorpay_payment_id = %s
               LIMIT 1""",
            (razorpay_order_id, payment_id)
        )
        existing_order = cursor.fetchone()

        if existing_order:
            if int(existing_order['user_id']) != int(session['user_id']):
                raise ValueError("This payment is already associated with another customer order.")
            order_db_id = existing_order['order_id']
            # The order and its items were already committed on the first callback.
        else:
            cart = session.get('cart', {})
            selected_ids = [str(pid) for pid in session.get('checkout_selected_ids', [])]
            selected_items = {pid: cart[pid] for pid in selected_ids if pid in cart}
            if not selected_items:
                raise ValueError("The selected cart items are no longer available in this session.")

            # Recalculate from the server-side checkout cart, not from form fields.
            total_amount = sum(
                Decimal(str(item['price'])) * int(item['quantity'])
                for item in selected_items.values()
            ).quantize(Decimal('0.01'))
            if int(total_amount * 100) != int(expected_amount):
                raise ValueError("The order total no longer matches the Razorpay payment amount.")

            delivery_address = session.get('delivery_address') or {}
            required_address_fields = ('full_name', 'phone', 'address_line', 'city', 'state', 'pincode')
            if any(not str(delivery_address.get(field, '')).strip() for field in required_address_fields):
                raise ValueError("The delivery address is incomplete. Contact support with your payment ID.")

            cursor.execute("SHOW COLUMNS FROM orders")
            existing_cols = {row['Field'] for row in cursor.fetchall()}

            order_data = {
                'user_id': session['user_id'],
                'razorpay_order_id': razorpay_order_id,
                'razorpay_payment_id': payment_id,
                'razorpay_signature': signature,
                'total_amount': total_amount,
                'currency': 'INR',
                'payment_status': 'PAID',
                'order_status': 'PLACED',
                'full_name': delivery_address['full_name'],
                'phone': delivery_address['phone'],
                'address_line': delivery_address['address_line'],
                'city': delivery_address['city'],
                'state': delivery_address['state'],
                'pincode': delivery_address['pincode'],
                'landmark': delivery_address.get('landmark', '')
            }
            # Populate legacy columns if present in orders table
            if 'customer_name' in existing_cols:
                order_data['customer_name'] = delivery_address['full_name']
            if 'address' in existing_cols:
                order_data['address'] = delivery_address['address_line']
            if 'amount' in existing_cols:
                order_data['amount'] = total_amount

            cols_to_insert = [c for c in order_data if c in existing_cols]
            col_list = ", ".join(cols_to_insert)
            placeholders = ", ".join(["%s"] * len(cols_to_insert))
            values = tuple(float(order_data[c]) if isinstance(order_data[c], Decimal) else order_data[c] for c in cols_to_insert)

            cursor.execute(
                f"INSERT INTO orders ({col_list}) VALUES ({placeholders})",
                values
            )
            order_db_id = cursor.lastrowid

            for product_id, item in selected_items.items():
                item_price = float(Decimal(str(item['price'])).quantize(Decimal('0.01')))
                quantity = int(item['quantity'])
                if quantity < 1:
                    raise ValueError("Invalid product quantity in checkout.")
                subtotal = float(item_price * quantity)
                cursor.execute(
                    """INSERT INTO order_items (
                        order_id, product_id, product_name, product_image,
                        price, quantity, subtotal
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                    (
                        order_db_id, int(product_id), item.get('name', 'Product'),
                        item.get('image', ''), item_price, quantity, subtotal
                    )
                )

            # Both order and order items are saved in one database transaction.
            conn.commit()

        # Day-13 requires clearing the entire session cart after the order
        # transaction succeeds. Failed database writes leave the cart untouched.
        session.pop('cart', None)
        session.pop('checkout_selected_ids', None)
        session.pop('razorpay_order_id', None)
        session.pop('razorpay_amount', None)
        session.modified = True

        return redirect(url_for('order_success', order_db_id=order_db_id))

    except Exception as exc:
        if conn:
            conn.rollback()
        app.logger.exception(
            "Payment verification/order persistence failed. payment_id=%s razorpay_order_id=%s error=%s",
            payment_id, razorpay_order_id, exc
        )
        flash(
            "Payment was received or is being checked, but SmartCart could not finish saving the order. "
            "Do not pay again yet. Contact support with payment ID: " + payment_id,
            "error"
        )
        return redirect(url_for('view_cart'))
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@app.route('/user/order-success/<int:order_db_id>')
def order_success(order_db_id):
    """Show a persisted order only to the customer who owns it."""
    if 'user_id' not in session:
        flash("Please login to view your order.", "error")
        return redirect(url_for('user_login'))

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT * FROM orders WHERE order_id = %s AND user_id = %s",
            (order_db_id, session['user_id'])
        )
        order = cursor.fetchone()
        if not order:
            flash("Order not found.", "error")
            return redirect(url_for('my_orders'))

        cursor.execute(
            "SELECT * FROM order_items WHERE order_id = %s ORDER BY order_item_id",
            (order_db_id,)
        )
        items = cursor.fetchall()
        return render_template('user/order_success.html', order=order, items=items)
    except Exception:
        app.logger.exception("Unable to load order details for order_id=%s", order_db_id)
        flash("Unable to load this order right now.", "error")
        return redirect(url_for('my_orders'))
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@app.route('/user/my-orders')
@app.route('/my-orders')
@app.route('/orders')
def my_orders():
    if 'user_id' not in session:
        flash("Please login to view your orders.", "error")
        return redirect(url_for('user_login'))

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT * FROM orders WHERE user_id = %s ORDER BY created_at DESC",
            (session['user_id'],)
        )
        orders = cursor.fetchall()
        for order in orders:
            cursor.execute(
                "SELECT * FROM order_items WHERE order_id = %s ORDER BY order_item_id",
                (order['order_id'],)
            )
            order['items'] = cursor.fetchall()
            order['item_count'] = sum(int(item.get('quantity', 0)) for item in order['items'])
        return render_template('user/my_orders.html', orders=orders)
    except Exception:
        app.logger.exception("Unable to load orders for user_id=%s", session.get('user_id'))
        flash("Unable to load your orders. Please try again.", "error")
        return redirect(url_for('user_dashboard'))
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


# ----------------------------
# DAY 14: GENERATE INVOICE PDF
# ----------------------------
@app.route("/user/download-invoice/<int:order_id>")
def download_invoice(order_id):
    """Generate and download a professional PDF invoice for a customer's order."""
    if 'user_id' not in session:
        flash("Please login to download your invoice.", "error")
        return redirect(url_for('user_login'))

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT * FROM orders WHERE order_id = %s AND user_id = %s",
            (order_id, session['user_id'])
        )
        order = cursor.fetchone()

        if not order:
            flash("Order not found or you do not have permission to view it.", "error")
            return redirect(url_for('my_orders'))

        cursor.execute(
            "SELECT * FROM order_items WHERE order_id = %s ORDER BY order_item_id",
            (order_id,)
        )
        items = cursor.fetchall()

        # Render HTML invoice template
        html = render_template("user/invoice.html", order=order, items=items)

        # Convert HTML to PDF using xhtml2pdf
        pdf = generate_pdf(html)
        if not pdf:
            flash("Error generating PDF invoice. Please try again.", "error")
            return redirect(url_for('my_orders'))

        # Prepare HTTP response with PDF headers for direct browser download
        response = make_response(pdf.getvalue())
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f"attachment; filename=invoice_{order_id}.pdf"
        return response

    except Exception:
        app.logger.exception("Failed to generate invoice for order_id=%s user_id=%s", order_id, session.get('user_id'))
        flash("Failed to generate invoice. Please try again.", "error")
        return redirect(url_for('my_orders'))
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()



# ---------------------------------------------------------
# CONVENIENCE REDIRECT ROUTES
# ---------------------------------------------------------
@app.route('/login')
def general_login():
    if 'admin_id' in session:
        return redirect('/admin-dashboard')
    if 'user_id' in session:
        return redirect('/user-dashboard')
    return redirect('/user-login')


@app.route('/logout')
def general_logout():
    if 'admin_id' in session:
        return redirect('/admin-logout')
    return redirect('/user-logout')


@app.route('/signup')
@app.route('/register')
def general_signup():
    return redirect('/user-register')


# RUN APP
if __name__ == '__main__':
    app.run(debug=os.environ.get('FLASK_DEBUG', '0') == '1')



