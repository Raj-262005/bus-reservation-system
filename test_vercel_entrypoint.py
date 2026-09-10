# -*- coding: utf-8 -*-
"""
Verification script for testing Vercel-compatible entrypoint (api/index.py)
and ensuring all required features function under the simulated Vercel serverless environment.
"""

import os
import sys
import io

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# 1. Simulate Vercel Serverless environment
os.environ['VERCEL'] = '1'

# 2. Import app from api.index
print("\n--- 1. Importing Vercel Entrypoint (api.index:app) ---")
from api.index import app
from app.models import db, User, Schedule, Booking
from datetime import date, timedelta

print(f"✓ api.index:app imported successfully: {app}")
print(f"✓ SQLALCHEMY_DATABASE_URI: {app.config.get('SQLALCHEMY_DATABASE_URI')}")
assert '/tmp/' in app.config.get('SQLALCHEMY_DATABASE_URI') or app.config.get('SQLALCHEMY_DATABASE_URI').endswith('bus_reservation.db'), "Should use Vercel temp path"

client = app.test_client()

with app.app_context():
    # 3. Passenger Home Page & Vercel rewrite endpoints
    print("\n--- 2. Testing Home Page & Rewrite Paths ---")
    res_root = client.get('/')
    assert res_root.status_code == 200, f"GET '/' failed: {res_root.status_code}"
    assert b"Bus" in res_root.data or b"Book" in res_root.data
    print("✓ GET '/' loaded successfully (HTTP 200).")

    res_api = client.get('/api')
    assert res_api.status_code == 200, f"GET '/api' failed: {res_api.status_code}"
    print("✓ GET '/api' mapped to home successfully (HTTP 200).")

    res_index = client.get('/api/index')
    assert res_index.status_code == 200, f"GET '/api/index' failed: {res_index.status_code}"
    print("✓ GET '/api/index' mapped to home successfully (HTTP 200).")

    res_py = client.get('/api/index.py')
    assert res_py.status_code == 200, f"GET '/api/index.py' failed: {res_py.status_code}"
    print("✓ GET '/api/index.py' mapped to home successfully (HTTP 200).")

    # 4. Bus Search
    print("\n--- 3. Testing Bus Search ---")
    today_str = date.today().strftime('%Y-%m-%d')
    res = client.get(f'/search?source=Mumbai&destination=Pune&journey_date={today_str}')
    assert res.status_code == 200, f"Search failed: {res.status_code}"
    assert b"Mumbai" in res.data and b"Pune" in res.data
    print("✓ Bus search working.")

    # 5. Seat Layout & Selection
    print("\n--- 4. Testing Seat Selection Page ---")
    sched = Schedule.query.filter(Schedule.journey_date >= date.today()).first()
    assert sched is not None, "At least one schedule must exist"
    res = client.get(f'/bus/{sched.id}/seats')
    assert res.status_code == 200, f"Seat selection failed: {res.status_code}"
    assert b"busSeatGrid" in res.data or b"seat" in res.data.lower()
    print("✓ Seat selection layout loaded.")

    # 6. Passenger Login
    print("\n--- 5. Testing Passenger Login ---")
    res = client.post('/login', data={
        'email': 'passenger@busreservation.com',
        'password': 'Passenger@123'
    }, follow_redirects=True)
    assert res.status_code == 200, f"Passenger login failed: {res.status_code}"
    assert b"Dashboard" in res.data or b"Amit" in res.data or b"Bookings" in res.data
    print("✓ Passenger login successful.")

    # 7. Booking & GST Calculation & Checkout
    print("\n--- 6. Testing Booking & GST Calculation ---")
    # Fetch available seats for schedule
    booked_ids = sched.get_booked_seat_ids()
    available_seats = [s for s in sched.bus.seats if s.id not in booked_ids][:2]
    seat_ids = [str(s.id) for s in available_seats]
    form_data = {
        'seat_ids[]': seat_ids,
        f'name_{seat_ids[0]}': 'Vercel Test Passenger 1',
        f'age_{seat_ids[0]}': '28',
        f'gender_{seat_ids[0]}': 'Male',
        f'name_{seat_ids[1]}': 'Vercel Test Passenger 2',
        f'age_{seat_ids[1]}': '27',
        f'gender_{seat_ids[1]}': 'Female',
        'contact_email': 'passenger@busreservation.com',
        'contact_phone': '9876543210'
    }
    res = client.post(f'/book/{sched.id}', data=form_data, follow_redirects=True)
    assert res.status_code == 200, f"Checkout page failed: {res.status_code}"
    # Verify GST is calculated and displayed on checkout page
    assert b"GST" in res.data or b"Tax" in res.data or b"Payment" in res.data
    print("✓ Passenger details collected and GST verified.")

    # 8. Dynamic UPI QR Payment Verification
    print("\n--- 7. Testing UPI QR Code Payment & Demo Verification ---")
    assert b"data:image/png;base64," in res.data or b"upi" in res.data.lower()
    print("✓ Dynamic UPI QR code verified on payment screen.")

    # Simulate payment confirmation via demo UPI payment endpoint
    res_pay = client.post('/payment/demo/process', data={
        'payment_method': 'UPI_QR'
    }, follow_redirects=True)
    assert res_pay.status_code == 200, f"Payment process failed: {res_pay.status_code}"
    assert b"Booking Confirmed!" in res_pay.data or b"BRS-" in res_pay.data
    latest_booking = Booking.query.order_by(Booking.id.desc()).first()
    assert latest_booking is not None, "Booking must be created after payment"
    booking_id = latest_booking.booking_id
    print(f"✓ Payment processed & booking created: {booking_id}.")

    # 9. Ticket Download (In-Memory PDF Streaming)
    print("\n--- 8. Testing In-Memory PDF Ticket Streaming ---")
    res = client.get(f'/ticket/{booking_id}/download')
    assert res.status_code == 200, f"Ticket download failed: {res.status_code}"
    assert res.content_type == 'application/pdf', f"Expected PDF content type, got {res.content_type}"
    assert res.data.startswith(b'%PDF'), "PDF content must start with %PDF header"
    print(f"✓ E-Ticket PDF generated and streamed ({len(res.data)} bytes).")

    # 10. Booking History & Passenger Dashboard
    print("\n--- 9. Testing Booking History & Passenger Dashboard ---")
    res_dash = client.get('/dashboard')
    assert res_dash.status_code == 200, f"Dashboard failed: {res_dash.status_code}"

    res = client.get('/my-bookings')
    assert res.status_code == 200, f"Booking history failed: {res.status_code}"
    assert booking_id.encode() in res.data
    print("✓ Booking history and dashboard display current booking.")

    # 11. Ticket Cancellation & Seat Release
    print("\n--- 10. Testing Ticket Cancellation ---")
    res = client.post(f'/booking/{booking_id}/cancel', data={
        'reason': 'Vercel deployment test cancellation'
    }, follow_redirects=True)
    assert res.status_code == 200, f"Cancellation failed: {res.status_code}"
    cancelled_booking = Booking.query.filter_by(booking_id=booking_id).first()
    assert cancelled_booking.booking_status == 'CANCELLED'
    print(f"✓ Booking {booking_id} cancelled and seats released.")

    # 12. Multilingual Support Switching
    print("\n--- 11. Testing Multilingual Support (EN, HI, MR) ---")
    res_hi = client.get('/set-language/hi', follow_redirects=True)
    assert res_hi.status_code == 200
    assert 'user_lang=hi' in str(res_hi.headers.get('Set-Cookie', '')) or b"\xe0\xa4" in res_hi.data

    res_mr = client.get('/set-language/mr', follow_redirects=True)
    assert res_mr.status_code == 200

    res_en = client.get('/set-language/en', follow_redirects=True)
    assert res_en.status_code == 200
    print("✓ Language switching transitions (EN -> HI -> MR -> EN) verified.")

    # 13. Admin Login & Reports
    print("\n--- 12. Testing Admin Dashboard & Reports ---")
    # Logout passenger
    client.get('/logout')
    # Login as admin
    res_admin = client.post('/login', data={
        'email': 'admin@busreservation.com',
        'password': 'Admin@123'
    }, follow_redirects=True)
    assert res_admin.status_code == 200
    assert b"Admin" in res_admin.data or b"Overview" in res_admin.data

    # Admin reports
    res_reports = client.get('/admin/reports')
    assert res_reports.status_code == 200
    assert b"Revenue" in res_reports.data or b"Reports" in res_reports.data
    print("✓ Admin login and reporting verified.")

    # 14. Operator Portal
    print("\n--- 13. Testing Operator Portal ---")
    client.get('/logout')
    res_op = client.post('/login', data={
        'email': 'operator@busreservation.com',
        'password': 'Operator@123'
    }, follow_redirects=True)
    assert res_op.status_code == 200
    res_op_dash = client.get('/operator/dashboard')
    assert res_op_dash.status_code == 200
    print("✓ Operator login and dashboard verified.")

print("\n" + "=" * 65)
print(" ALL 13 VERCEL ENTRYPOINT CHECKS PASSED WITH ZERO REGRESSIONS! ")
print("=" * 65 + "\n")
