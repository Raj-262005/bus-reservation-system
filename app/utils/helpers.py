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


DEFAULT_GST_RATE = 5.0


def calculate_fare_and_gst(fare_per_seat, num_seats, gst_rate=None):
    """
    Single authoritative calculation engine for Base Fare, GST, and Grand Total.
    - Base Fare = fare_per_seat * num_seats
    - GST Amount = round(Base Fare * (gst_rate / 100), 2)
    - Grand Total = round(Base Fare + GST Amount, 2)
    All monetary calculations rounded to 2 decimal places to prevent floating-point drift.
    """
    if gst_rate is None:
        try:
            from flask import current_app
            gst_rate = float(current_app.config.get('GST_RATE', DEFAULT_GST_RATE))
        except Exception:
            gst_rate = DEFAULT_GST_RATE

    fare_per_seat = float(fare_per_seat)
    num_seats = int(num_seats)
    gst_rate = float(gst_rate)

    base_amount = round(fare_per_seat * num_seats, 2)
    gst_amount = round(base_amount * (gst_rate / 100.0), 2)
    total_amount = round(base_amount + gst_amount, 2)

    return {
        'fare_per_seat': fare_per_seat,
        'num_seats': num_seats,
        'base_amount': base_amount,
        'base_fare': base_amount,
        'gst_rate': gst_rate,
        'gst_amount': gst_amount,
        'total_amount': total_amount,
        'grand_total': total_amount,
    }

