import os
from datetime import timedelta
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'bus-reservation-academic-secret-key-2026'
    PERMANENT_SESSION_LIFETIME = timedelta(days=2)
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Database setup: PostgreSQL (Render / Production), MySQL, or SQLite (Local fallback)
    use_mysql = os.environ.get('USE_MYSQL', 'False').lower() in ('true', '1', 't', 'yes')
    custom_db_url = os.environ.get('DATABASE_URL')

    if custom_db_url:
        # Render provides postgres:// which SQLAlchemy 1.4+ / 2.0+ requires as postgresql://
        if custom_db_url.startswith('postgres://'):
            custom_db_url = custom_db_url.replace('postgres://', 'postgresql://', 1)
        SQLALCHEMY_DATABASE_URI = custom_db_url
    elif use_mysql:
        mysql_user = os.environ.get('MYSQL_USER', 'root')
        mysql_pass = os.environ.get('MYSQL_PASSWORD', 'root')
        mysql_host = os.environ.get('MYSQL_HOST', 'localhost')
        mysql_port = int(os.environ.get('MYSQL_PORT', 3306))
        mysql_db = os.environ.get('MYSQL_DB', 'bus_reservation_db')
        
        # Test MySQL connectivity
        mysql_accessible = False
        try:
            import pymysql
            conn = pymysql.connect(
                host=mysql_host,
                port=mysql_port,
                user=mysql_user,
                password=mysql_pass,
                connect_timeout=2
            )
            # Ensure database exists
            cursor = conn.cursor()
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {mysql_db} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
            conn.close()
            mysql_accessible = True
        except Exception as e:
            print(f"\n[MySQL Notice] Could not connect to MySQL Server ({mysql_user}@{mysql_host}:{mysql_port}): {e}")
            print("[MySQL Notice] To use MySQL, ensure MySQL is running and set your root password in .env (MYSQL_PASSWORD=your_password).")
            print("[MySQL Notice] Gracefully running in SQLite mode for uninterrupted testing.\n")

        if mysql_accessible:
            SQLALCHEMY_DATABASE_URI = f"mysql+pymysql://{mysql_user}:{mysql_pass}@{mysql_host}:{mysql_port}/{mysql_db}?charset=utf8mb4"
        else:
            sqlite_path = os.path.join(basedir, 'bus_reservation.db')
            SQLALCHEMY_DATABASE_URI = f"sqlite:///{sqlite_path}"
    else:
        sqlite_path = os.path.join(basedir, 'bus_reservation.db')
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{sqlite_path}"

    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
    }

    # Payment Settings
    RAZORPAY_KEY_ID = os.environ.get('RAZORPAY_KEY_ID', '')
    RAZORPAY_KEY_SECRET = os.environ.get('RAZORPAY_KEY_SECRET', '')
    DEMO_PAYMENT_MODE = os.environ.get('DEMO_PAYMENT_MODE', 'True').lower() in ('true', '1', 't', 'yes')

    # Uploads & Tickets
    TICKETS_DIR = os.path.join(basedir, 'app', 'static', 'generated_tickets')


class TestConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    DEMO_PAYMENT_MODE = True
