import pytest
from datetime import date, time, timedelta
from config import TestConfig
from app import create_app
from app.models import db, User, Schedule, Seat, Booking, Payment, Route, Bus
from app.utils.helpers import calculate_fare_and_gst, DEFAULT_GST_RATE
from app.services.booking_service import BookingService
from app.services.ticket_service import TicketService


@pytest.fixture
def app():
    test_app = create_app(TestConfig)
    with test_app.app_context():
        db.create_all()

        operator = User(name="Operator User", email="operator@test.com", phone="1234567891", role="operator")
        operator.set_password("Operator@123")

        passenger = User(name="Passenger User", email="passenger@test.com", phone="1234567892", role="passenger")
        passenger.set_password("Passenger@123")

        db.session.add_all([operator, passenger])
        db.session.commit()

        route = Route(source_city="Mumbai", destination_city="Pune", distance_km=150.0, estimated_duration="3h 30m")
        db.session.add(route)
        db.session.commit()

        bus = Bus(bus_number="GST-BUS-01", bus_name="GST Premium Express", bus_type="AC Sleeper", total_seats=20, operator_id=operator.id)
        db.session.add(bus)
        db.session.commit()
        bus.initialize_seats(20)
        db.session.commit()

        sched = Schedule(
            bus_id=bus.id,
            route_id=route.id,
            journey_date=date.today() + timedelta(days=1),
            departure_time=time(10, 0),
            arrival_time=time(14, 0),
            fare=600.0,
            status="SCHEDULED"
        )
        db.session.add(sched)
        db.session.commit()

        yield test_app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


# ==============================================================================
# 1. Unit Tests for calculate_fare_and_gst()
# ==============================================================================
def test_gst_calculation_single_seat():
    """Verify single seat: Base = ₹600, GST(5%) = ₹30, Total = ₹630."""
    pricing = calculate_fare_and_gst(600.0, 1)
    assert pricing['fare_per_seat'] == 600.0
    assert pricing['num_seats'] == 1
    assert pricing['base_fare'] == 600.0
    assert pricing['base_amount'] == 600.0
    assert pricing['gst_rate'] == 5.0
    assert pricing['gst_amount'] == 30.0
    assert pricing['grand_total'] == 630.0
    assert pricing['total_amount'] == 630.0


def test_gst_calculation_multi_seat():
    """Verify multiple seats: 3 seats @ ₹600 = Base ₹1800, GST(5%) = ₹90, Total = ₹1890."""
    pricing = calculate_fare_and_gst(600.0, 3)
    assert pricing['fare_per_seat'] == 600.0
    assert pricing['num_seats'] == 3
    assert pricing['base_fare'] == 1800.0
    assert pricing['base_amount'] == 1800.0
    assert pricing['gst_rate'] == 5.0
    assert pricing['gst_amount'] == 90.0
    assert pricing['grand_total'] == 1890.0
    assert pricing['total_amount'] == 1890.0


def test_gst_calculation_rounding_and_fractions():
    """Verify decimal precision rounding to 2 decimal places."""
    # 1 seat @ 455.50 -> Base: 455.50, GST: 455.50 * 0.05 = 22.775 -> 22.78, Total: 478.28
    pricing = calculate_fare_and_gst(455.50, 1)
    assert pricing['base_fare'] == 455.50
    assert pricing['gst_amount'] == 22.78
    assert pricing['grand_total'] == 478.28

    # 3 seats @ 333.33 -> Base: 999.99, GST: 999.99 * 0.05 = 49.9995 -> 50.00, Total: 1049.99
    pricing2 = calculate_fare_and_gst(333.33, 3)
    assert pricing2['base_fare'] == 999.99
    assert pricing2['gst_amount'] == 50.00
    assert pricing2['grand_total'] == 1049.99


def test_gst_calculation_custom_rate():
    """Verify configurable GST rate override."""
    pricing = calculate_fare_and_gst(1000.0, 2, gst_rate=12.0)
    assert pricing['base_fare'] == 2000.0
    assert pricing['gst_rate'] == 12.0
    assert pricing['gst_amount'] == 240.0
    assert pricing['grand_total'] == 2240.0


# ==============================================================================
# 2. Database Persistence & Atomic Booking Tests
# ==============================================================================
def test_atomic_booking_persists_gst_fields(app):
    """Verify create_booking_atomic correctly stores base_amount, gst_rate, gst_amount, and total_amount."""
    with app.app_context():
        sched = Schedule.query.first()
        passenger = User.query.filter_by(email='passenger@test.com').first()
        seats = Seat.query.filter_by(bus_id=sched.bus_id).limit(2).all()

        passengers_data = [
            {'seat_id': seats[0].id, 'passenger_name': 'GST Test 1', 'age': 30, 'gender': 'Male'},
            {'seat_id': seats[1].id, 'passenger_name': 'GST Test 2', 'age': 28, 'gender': 'Female'}
        ]

        booking = BookingService.create_booking_atomic(
            schedule_id=sched.id,
            user_id=passenger.id,
            passengers_data=passengers_data,
            payment_method='DEMO_NETBANKING'
        )

        assert booking is not None
        expected_base = round(sched.fare * 2, 2)
        expected_gst = round(expected_base * 0.05, 2)
        expected_total = round(expected_base + expected_gst, 2)

        assert booking.base_amount == expected_base
        assert booking.gst_rate == 5.0
        assert booking.gst_amount == expected_gst
        assert booking.total_amount == expected_total

        # Verify payment record amount matches grand total
        payment = Payment.query.filter_by(booking_id=booking.id).first()
        assert payment is not None
        assert payment.amount == expected_total
        assert payment.payment_status == 'SUCCESS'


# ==============================================================================
# 3. Backward Compatibility for Legacy Bookings
# ==============================================================================
def test_legacy_booking_computed_properties(app):
    """Verify computed_base_amount and computed_gst_amount on legacy rows where columns are None."""
    with app.app_context():
        legacy_booking = Booking(
            booking_id='BKG-LEGACYTEST',
            user_id=1,
            schedule_id=1,
            total_passengers=1,
            total_amount=630.0,
            booking_status='CONFIRMED',
            base_amount=None,
            gst_rate=None,
            gst_amount=None
        )
        # computed_base_amount should back-calculate Base: 630 / 1.05 = 600.0
        assert legacy_booking.computed_base_amount == 600.0
        # computed_gst_amount should be 630.0 - 600.0 = 30.0
        assert legacy_booking.computed_gst_amount == 30.0


# ==============================================================================
# 4. Cancellation Refund with GST
# ==============================================================================
def test_cancellation_refund_on_total_with_gst(app):
    """Verify 90% refund is calculated against total amount paid including GST."""
    with app.app_context():
        sched = Schedule.query.first()
        user = User.query.filter_by(email='passenger@test.com').first()
        seat = Seat.query.filter_by(bus_id=sched.bus_id).first()

        booking = BookingService.create_booking_atomic(
            sched.id, user.id,
            [{'seat_id': seat.id, 'passenger_name': 'Refund GST Passenger', 'age': 40, 'gender': 'Male'}],
            'DEMO_CARD'
        )

        expected_total = round(sched.fare * 1.05, 2)
        assert booking.total_amount == expected_total

        cancelled_booking, refund = BookingService.cancel_booking(booking.booking_id, user, reason="Plans changed")
        assert cancelled_booking.booking_status == 'CANCELLED'

        expected_refund = round(expected_total * 0.90, 2)
        assert refund == expected_refund
        assert cancelled_booking.cancellation.refund_amount == expected_refund


# ==============================================================================
# 5. PDF E-Ticket Generation with GST
# ==============================================================================
def test_pdf_ticket_contains_gst_details(app):
    """Verify PDF E-Ticket can be generated for a booking with GST fields without errors."""
    with app.app_context():
        sched = Schedule.query.first()
        user = User.query.filter_by(email='passenger@test.com').first()
        seat = Seat.query.filter_by(bus_id=sched.bus_id).first()

        booking = BookingService.create_booking_atomic(
            sched.id, user.id,
            [{'seat_id': seat.id, 'passenger_name': 'PDF GST Passenger', 'age': 32, 'gender': 'Female'}],
            'UPI'
        )

        pdf_stream = TicketService.generate_pdf(booking)
        assert pdf_stream is not None
        pdf_bytes = pdf_stream.read()
        assert len(pdf_bytes) > 1000
        assert pdf_bytes.startswith(b'%PDF')


# ==============================================================================
# 6. UPI QR Code Checkout Page & "I Have Paid" Flow Tests
# ==============================================================================
def test_checkout_page_renders_upi_qr(client, app):
    """Verify /checkout displays the UPI QR image, exact total amount, and confirmation button."""
    with app.app_context():
        sched = Schedule.query.first()
        passenger = User.query.filter_by(email='passenger@test.com').first()
        seat = Seat.query.filter_by(bus_id=sched.bus_id).first()

        # Log in passenger
        client.post('/login', data={'email': 'passenger@test.com', 'password': 'Passenger@123'})

        # Establish pending booking session
        with client.session_transaction() as sess:
            sess['pending_booking'] = {
                'schedule_id': sched.id,
                'passengers_data': [{'seat_id': seat.id, 'passenger_name': 'UPI Test Passenger', 'age': 25, 'gender': 'Male'}],
                'contact_email': 'passenger@test.com',
                'contact_phone': '9876543210'
            }

        resp = client.get('/checkout')
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)

        # Verify Dynamic QR data URL or fallback static image is loaded
        assert ('data:image/png;base64,' in html) or ('images/upi_qr.jpeg' in html)
        # Verify UPI instructions and amounts
        assert 'Scan the QR code using any UPI app to pay' in html or 'upi_qr_payment' in html
        assert '₹600.00' in html  # Base fare
        assert '₹30.00' in html   # GST 5%
        assert '₹630.00' in html  # Total amount
        assert 'I Have Paid / Confirm Payment' in html or 'confirm_payment_btn' in html


def test_upi_qr_i_have_paid_confirmation(client, app):
    """Verify clicking 'I Have Paid' creates an atomic confirmed booking with UPI-CONFIRM transaction ID."""
    with app.app_context():
        sched = Schedule.query.first()
        seat = Seat.query.filter_by(bus_id=sched.bus_id).first()

        client.post('/login', data={'email': 'passenger@test.com', 'password': 'Passenger@123'})

        with client.session_transaction() as sess:
            sess['pending_booking'] = {
                'schedule_id': sched.id,
                'passengers_data': [{'seat_id': seat.id, 'passenger_name': 'UPI Confirmed Passenger', 'age': 29, 'gender': 'Female'}],
                'contact_email': 'passenger@test.com',
                'contact_phone': '9876543210'
            }

        # Submit "I Have Paid" confirmation POST
        resp = client.post('/payment/demo/process', data={'payment_method': 'UPI_QR'}, follow_redirects=True)
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)

        # Verify confirmation page reached
        assert 'Booking Confirmed' in html or 'booking_confirmed_title' in html
        assert '₹600.00' in html
        assert '₹30.00' in html
        assert '₹630.00' in html

        # Verify DB records
        booking = Booking.query.order_by(Booking.id.desc()).first()
        assert booking is not None
        assert booking.booking_status == 'CONFIRMED'
        assert booking.base_amount == 600.0
        assert booking.gst_rate == 5.0
        assert booking.gst_amount == 30.0
        assert booking.total_amount == 630.0

        payment = booking.latest_payment
        assert payment is not None
        assert payment.payment_method == 'UPI_QR'
        assert payment.amount == 630.0
        assert payment.payment_status == 'SUCCESS'
        # Verifies transparent audit ID without fake bank UTR claim
        assert payment.gateway_payment_id.startswith('UPI-CONFIRM-')


def test_tampered_browser_amount_ignored(client, app):
    """Verify backend always recalculates final amount from schedule fare + GST, ignoring client inputs."""
    with app.app_context():
        sched = Schedule.query.first()
        seat = Seat.query.filter_by(bus_id=sched.bus_id).all()[1]

        client.post('/login', data={'email': 'passenger@test.com', 'password': 'Passenger@123'})

        with client.session_transaction() as sess:
            sess['pending_booking'] = {
                'schedule_id': sched.id,
                'passengers_data': [{'seat_id': seat.id, 'passenger_name': 'Tamper Test', 'age': 35, 'gender': 'Male'}],
                'contact_email': 'passenger@test.com',
                'contact_phone': '9876543210'
            }

        # Attacker tries to send amount=1.00 via form body
        resp = client.post('/payment/demo/process', data={'payment_method': 'UPI_QR', 'amount': '1.00', 'total_amount': '1.00'}, follow_redirects=True)
        assert resp.status_code == 200

        booking = Booking.query.order_by(Booking.id.desc()).first()
        assert booking.total_amount == 630.0  # Server calculated Base 600 + GST 30, never 1.00!
        assert booking.latest_payment.amount == 630.0


# ==============================================================================
# 7. Dynamic UPI URI & Pre-Filled Amount Calculations (₹630.00 and ₹892.50)
# ==============================================================================
def test_dynamic_upi_uri_and_qr_generation_amounts(app):
    """
    Verify UPI URI contains payee, UPI ID, and exact pre-filled amounts:
    - Case 1: ₹630.00 (Base: ₹600.00, GST 5%: ₹30.00)
    - Case 2: ₹892.50 (Base: ₹850.00, GST 5%: ₹42.50)
    """
    from app.services.payment_service import PaymentService

    # Case 1: ₹630.00
    pricing1 = calculate_fare_and_gst(600.0, 1)
    assert pricing1['base_fare'] == 600.00
    assert pricing1['gst_amount'] == 30.00
    assert pricing1['grand_total'] == 630.00

    uri1 = PaymentService.build_upi_uri(
        amount=pricing1['grand_total'],
        note="BRS-Booking",
        upi_id="rajthakare2005@oksbi",
        payee_name="Raj Thakare"
    )
    assert "pa=rajthakare2005@oksbi" in uri1
    assert "pn=Raj%20Thakare" in uri1
    assert "am=630.00" in uri1
    assert "cu=INR" in uri1
    assert "tn=BRS-Booking" in uri1

    qr_b64_1 = PaymentService.generate_dynamic_upi_qr(
        amount=pricing1['grand_total'],
        upi_id="rajthakare2005@oksbi",
        payee_name="Raj Thakare"
    )
    assert qr_b64_1 is not None
    assert qr_b64_1.startswith("data:image/png;base64,")

    # Case 2: ₹892.50 (Base ₹850.00, GST 5% = ₹42.50)
    pricing2 = calculate_fare_and_gst(850.0, 1)
    assert pricing2['base_fare'] == 850.00
    assert pricing2['gst_amount'] == 42.50
    assert pricing2['grand_total'] == 892.50

    uri2 = PaymentService.build_upi_uri(
        amount=pricing2['grand_total'],
        note="BRS-Test",
        upi_id="rajthakare2005@oksbi",
        payee_name="Raj Thakare"
    )
    assert "pa=rajthakare2005@oksbi" in uri2
    assert "pn=Raj%20Thakare" in uri2
    assert "am=892.50" in uri2
    assert "cu=INR" in uri2

    qr_b64_2 = PaymentService.generate_dynamic_upi_qr(
        amount=pricing2['grand_total'],
        upi_id="rajthakare2005@oksbi",
        payee_name="Raj Thakare"
    )
    assert qr_b64_2 is not None
    assert qr_b64_2.startswith("data:image/png;base64,")


def test_dynamic_qr_custom_schedule_fare_892_50(client, app):
    """Verify that a schedule with fare ₹850.00 generates dynamic QR pre-filling ₹892.50 on checkout page."""
    with app.app_context():
        bus = Bus.query.first()
        route = Route.query.first()
        user = User.query.filter_by(email='passenger@test.com').first()
        seats = Seat.query.filter_by(bus_id=bus.id).limit(1).all()

        sched850 = Schedule(
            bus_id=bus.id,
            route_id=route.id,
            journey_date=date.today() + timedelta(days=2),
            departure_time=time(11, 0),
            arrival_time=time(15, 0),
            fare=850.0,
            status="SCHEDULED"
        )
        db.session.add(sched850)
        db.session.commit()

        client.post('/login', data={'email': 'passenger@test.com', 'password': 'Passenger@123'})

        with client.session_transaction() as sess:
            sess['pending_booking'] = {
                'schedule_id': sched850.id,
                'passengers_data': [{'seat_id': seats[0].id, 'passenger_name': 'Dynamic Passenger', 'age': 28, 'gender': 'Female'}],
                'contact_email': 'passenger@test.com',
                'contact_phone': '9876543210'
            }

        resp = client.get('/checkout')
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)

        # Verify Base Fare ₹850.00, GST ₹42.50, and Grand Total ₹892.50
        assert '₹850.00' in html
        assert '₹42.50' in html
        assert '₹892.50' in html
        assert 'data:image/png;base64,' in html


