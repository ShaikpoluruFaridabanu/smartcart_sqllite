"""SmartCart configuration. Set these values in environment variables.

Never commit real passwords or Razorpay secrets to source control.
"""
import os
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
SQLITE_DB_PATH = os.environ.get('SQLITE_DB_PATH', os.path.join(BASE_DIR, 'smartcart.db'))

SECRET_KEY = os.environ.get("SECRET_KEY", "your_secret_key")

# Database (SQLite is default for easy deployment)
DB_TYPE = os.environ.get("DB_TYPE", "sqlite")
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_USER = os.environ.get("DB_USER", "root")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "root")
DB_NAME = os.environ.get("DB_NAME", "smartcart_db")

# Email SMTP Settings
MAIL_SERVER = 'smtp.gmail.com'
MAIL_PORT = 587
MAIL_USE_TLS = True
MAIL_USERNAME = 'wajidpro131@gmail.com'
MAIL_PASSWORD = 'jrna ahpk rkou ngtg'   # Gmail App Password

#razor pay
RAZORPAY_KEY_ID = "rzp_test_TvefaOS7vEHSZs"
RAZORPAY_KEY_SECRET = "PNZEvxHNCjTmEXkSSrTTVA8B"
