import re
import uuid
from datetime import datetime


def generate_booking_id():
    """Generates a professional, unique booking reference ID e.g., BRS-20260909-AB12CD."""
    today_str = datetime.now().strftime('%Y%m%d')
    random_part = uuid.uuid4().hex[:6].upper()
    return f"BRS-{today_str}-{random_part}"


def generate_transaction_id():
    """Generates a unique payment transaction ID."""
    today_str = datetime.now().strftime('%Y%m%d%H%M')
    random_part = uuid.uuid4().hex[:8].upper()
    return f"TXN-{today_str}-{random_part}"


def validate_email(email):
    """Validates email format."""
    if not email:
        return False
    pattern = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
    return bool(re.match(pattern, email.strip()))


def validate_phone(phone):
    """Validates 10-15 digit phone format."""
    if not phone:
        return False
    cleaned = re.sub(r'[\s\-\+\(\)]', '', phone)
    return len(cleaned) >= 10 and len(cleaned) <= 15 and cleaned.isdigit()


def validate_password(password):
    """Validates password has at least 6 characters."""
    return bool(password and len(password) >= 6)


def format_currency(amount):
    """Formats amount into standard currency display string."""
    return f"₹{amount:,.2f}"
