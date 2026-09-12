import os
import sys
sys.stdout.reconfigure(encoding='utf-8')
from app import create_app
from app.models import db, User, Schedule, Booking
from app.services.booking_service import BookingService

app = create_app()

ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD')

with app.app_context():
    client = app.test_client()

    print("\n--- 1. Testing Home Page ---")
    res = client.get('/')
    assert res.status_code == 200, f"Failed Home page: {res.status_code}"
    assert b"Search Available Bus Schedules" in res.data
    print("✓ Home Page loaded successfully.")

    print("\n--- 2. Testing Bus Search ---")
    from datetime import date
    today_str = date.today().strftime('%Y-%m-%d')
    res = client.get(f'/search?source=Mumbai&destination=Pune&journey_date={today_str}')
    assert res.status_code == 200, f"Failed search: {res.status_code}"
    assert b"Volvo 9600" in res.data or b"Scania" in res.data
    print("✓ Bus search returned matching schedules.")

    print("\n--- 3. Testing Seat Map & Real-time Status ---")
    sched = Schedule.query.filter(Schedule.journey_date >= date.today()).first()
    res = client.get(f'/bus/{sched.id}/seats')
    assert res.status_code == 200, f"Failed seat layout: {res.status_code}"
    assert b"busSeatGrid" in res.data
    assert b"FRONT / DRIVER" in res.data
    print("✓ Interactive 2D Seat Layout loaded with seats.")

    print("\n--- 4. Testing Passenger Login ---")
    res = client.post('/login', data={
        'email': 'passenger@busreservation.com',
        'password': 'Passenger@123'
    }, follow_redirects=True)
    assert res.status_code == 200
    assert b"Welcome, Amit Verma" in res.data or b"Dashboard" in res.data
    print("✓ Passenger authenticated & session established.")

    print("\n--- 5. Testing Passenger Details & Checkout ---")
    res = client.post(f'/book/{sched.id}', data={
        'seat_ids[]': ['3', '4'],
        'name_3': 'Test Passenger 1',
        'age_3': '25',
        'gender_3': 'Male',
        'name_4': 'Test Passenger 2',
        'age_4': '24',
        'gender_4': 'Female',
        'contact_email': 'passenger@busreservation.com',
        'contact_phone': '9876543212'
    }, follow_redirects=True)
    assert res.status_code == 200
    assert b"UPI QR Code Payment" in res.data or b"upi_qr.jpeg" in res.data
    print("✓ Passenger details collected and checkout loaded.")

    print("\n--- 6. Testing Payment & Booking Confirmation ---")
    res = client.post('/payment/demo/process', data={
        'payment_method': 'UPI_QR'
    }, follow_redirects=True)
    assert res.status_code == 200
    assert b"Booking Confirmed!" in res.data
    assert b"BRS-" in res.data
    print("✓ Demo Payment verified & atomic booking confirmed.")

    # Find the created booking
    latest_booking = Booking.query.order_by(Booking.id.desc()).first()
    print(f"  Created Booking ID: {latest_booking.booking_id}")

    print("\n--- 7. Testing PDF E-Ticket Download ---")
    res = client.get(f'/ticket/{latest_booking.booking_id}/download')
    assert res.status_code == 200
    assert res.content_type == 'application/pdf'
    assert len(res.data) > 1000
    assert res.data.startswith(b'%PDF')
    print("✓ ReportLab E-Ticket PDF generated and streamed successfully.")

    print("\n--- 8. Testing Ticket Cancellation & Seat Release ---")
    initial_avail = sched.available_seats_count
    res = client.post(f'/booking/{latest_booking.booking_id}/cancel', data={
        'reason': 'Change of travel plans'
    }, follow_redirects=True)
    assert res.status_code == 200
    assert b"cancelled successfully" in res.data
    db.session.refresh(latest_booking)
    assert latest_booking.booking_status == 'CANCELLED'
    db.session.refresh(sched)
    # Seats should be released back!
    assert sched.available_seats_count == initial_avail + latest_booking.total_passengers
    print("✓ Booking cancelled and seats released back to available.")

    print("\n--- 9. Testing Admin Dashboard & Reports ---")
    client.get('/logout')
    assert ADMIN_EMAIL and ADMIN_PASSWORD, "Set ADMIN_EMAIL and ADMIN_PASSWORD to run admin checks."
    client.post('/login', data={'email': ADMIN_EMAIL, 'password': ADMIN_PASSWORD})
    admin_dash = client.get('/admin/dashboard')
    assert admin_dash.status_code == 200
    assert b"Admin Dashboard" in admin_dash.data
    admin_reports = client.get('/admin/reports')
    assert admin_reports.status_code == 200
    assert b"Reports &amp; Revenue Analytics" in admin_reports.data or b"Reports & Revenue Analytics" in admin_reports.data
    print("✓ Admin dashboard, metrics, and reporting verified.")

    print("\n--- 10. Testing Operator Portal ---")
    client.get('/logout')
    client.post('/login', data={'email': 'operator@busreservation.com', 'password': 'Operator@123'})
    op_dash = client.get('/operator/dashboard')
    assert op_dash.status_code == 200
    assert b"Operator Dashboard" in op_dash.data
    manifest = client.get(f'/operator/schedules/{sched.id}/manifest')
    assert manifest.status_code == 200
    assert b"Passenger Boarding Manifest" in manifest.data
    print("✓ Operator dashboard and boarding manifest verified.")

    print("\n=======================================================")
    print(" ALL 10 END-TO-END WORKFLOWS VERIFIED SUCCESSFULLY! ✓")
    print("=======================================================\n")
