import pytest
from datetime import datetime, date, time, timedelta, timezone
from config import TestConfig
from app import create_app
from app.models import db, User, Bus, Route, Schedule, Seat, Booking, BookingPassenger, Payment
from app.services.booking_service import BookingService, BookingException, SeatAlreadyBookedException
from app.services.ticket_service import TicketService
from app.services.payment_service import PaymentService


@pytest.fixture
def app():
    test_app = create_app(TestConfig)
    with test_app.app_context():
        db.create_all()

        # Seed minimal fixtures
        admin = User(name="Admin User", email="admin@test.com", phone="1234567890", role="admin")
        admin.set_password("Admin@123")

        operator = User(name="Operator User", email="operator@test.com", phone="1234567891", role="operator")
        operator.set_password("Operator@123")

        passenger = User(name="Passenger User", email="passenger@test.com", phone="1234567892", role="passenger")
        passenger.set_password("Passenger@123")

        passenger2 = User(name="Passenger Two", email="passenger2@test.com", phone="1234567893", role="passenger")
        passenger2.set_password("Passenger@123")

        db.session.add_all([admin, operator, passenger, passenger2])
        db.session.commit()

        # Route & Bus
        route = Route(source_city="Mumbai", destination_city="Pune", distance_km=150.0, estimated_duration="3h 30m")
        db.session.add(route)
        db.session.commit()

        bus = Bus(bus_number="TEST-01", bus_name="Express Test Bus", bus_type="AC Seater", total_seats=20, operator_id=operator.id)
        db.session.add(bus)
        db.session.commit()
        bus.initialize_seats(20)
        db.session.commit()

        # Schedule
        sched = Schedule(
            bus_id=bus.id,
            route_id=route.id,
            journey_date=date.today() + timedelta(days=1),
            departure_time=time(9, 0),
            arrival_time=time(12, 30),
            fare=300.0,
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


# ----------------------------------------------------------------------
# 1. Registration Tests
# ----------------------------------------------------------------------
def test_user_registration(client, app):
    with app.app_context():
        response = client.post('/register', data={
            'name': 'New Passenger',
            'email': 'newpassenger@test.com',
            'phone': '9988776655',
            'password': 'Password@123',
            'confirm_password': 'Password@123'
        }, follow_redirects=True)
        assert response.status_code == 200
        user = User.query.filter_by(email='newpassenger@test.com').first()
        assert user is not None
        assert user.name == 'New Passenger'
        assert user.role == 'passenger'
        assert user.check_password('Password@123') is True

        # Test duplicate registration rejection
        dup_resp = client.post('/register', data={
            'name': 'Duplicate User',
            'email': 'newpassenger@test.com',
            'phone': '9988776655',
            'password': 'Password@123',
            'confirm_password': 'Password@123'
        }, follow_redirects=True)
        assert b"already exists" in dup_resp.data


# ----------------------------------------------------------------------
# 2. Login & Authentication Tests
# ----------------------------------------------------------------------
def test_login_and_session(client, app):
    # Valid credentials
    resp = client.post('/login', data={
        'email': 'passenger@test.com',
        'password': 'Passenger@123'
    }, follow_redirects=True)
    assert resp.status_code == 200
    with client.session_transaction() as sess:
        assert sess.get('user_id') is not None
        assert sess.get('role') == 'passenger'

    # Invalid password
    client.get('/logout')
    invalid_resp = client.post('/login', data={
        'email': 'passenger@test.com',
        'password': 'WrongPassword'
    }, follow_redirects=True)
    assert b"Invalid email or password" in invalid_resp.data


# ----------------------------------------------------------------------
# 3. Bus Search Tests
# ----------------------------------------------------------------------
def test_bus_search(client, app):
    with app.app_context():
        tomorrow_str = (date.today() + timedelta(days=1)).strftime('%Y-%m-%d')
        resp = client.get(f'/search?source=Mumbai&destination=Pune&journey_date={tomorrow_str}&bus_type=ALL')
        assert resp.status_code == 200
        assert b"Express Test Bus" in resp.data
        assert b"300.00" in resp.data

        # Empty search / non-existent route
        empty_resp = client.get(f'/search?source=Kolkata&destination=Goa&journey_date={tomorrow_str}')
        assert b"No Buses Found" in empty_resp.data


# ----------------------------------------------------------------------
# 4. Seat Availability Tests
# ----------------------------------------------------------------------
def test_seat_availability(app):
    with app.app_context():
        sched = Schedule.query.first()
        seats_status = BookingService.get_schedule_seat_status(sched.id)
        assert len(seats_status) == 20
        assert all(s['status'] == 'available' for s in seats_status)
        assert sched.available_seats_count == 20


# ----------------------------------------------------------------------
# 5. Atomic Booking & Confirmation Flow
# ----------------------------------------------------------------------
def test_atomic_booking_flow(app):
    with app.app_context():
        sched = Schedule.query.first()
        passenger = User.query.filter_by(email='passenger@test.com').first()
        seats = Seat.query.filter_by(bus_id=sched.bus_id).limit(2).all()

        passengers_data = [
            {'seat_id': seats[0].id, 'passenger_name': 'Passenger One', 'age': 28, 'gender': 'Male'},
            {'seat_id': seats[1].id, 'passenger_name': 'Passenger Two', 'age': 25, 'gender': 'Female'}
        ]

        booking = BookingService.create_booking_atomic(
            schedule_id=sched.id,
            user_id=passenger.id,
            passengers_data=passengers_data,
            payment_method='UPI'
        )

        assert booking is not None
        assert booking.booking_status == 'CONFIRMED'
        assert booking.total_amount == 600.0  # 300 * 2
        assert len(booking.passengers) == 2
        assert sched.available_seats_count == 18

        # Verify seat status reflects booked
        updated_seats = BookingService.get_schedule_seat_status(sched.id)
        booked_seats = [s for s in updated_seats if s['status'] == 'booked']
        assert len(booked_seats) == 2
        assert {b['id'] for b in booked_seats} == {seats[0].id, seats[1].id}


# ----------------------------------------------------------------------
# 6. Double Booking Prevention Test (CRITICAL)
# ----------------------------------------------------------------------
def test_double_booking_prevention(app):
    with app.app_context():
        sched = Schedule.query.first()
        user1 = User.query.filter_by(email='passenger@test.com').first()
        user2 = User.query.filter_by(email='passenger2@test.com').first()
        seats = Seat.query.filter_by(bus_id=sched.bus_id).all()
        target_seat = seats[0]

        # First booking succeeds
        passengers_data_1 = [{'seat_id': target_seat.id, 'passenger_name': 'User One', 'age': 30, 'gender': 'Male'}]
        b1 = BookingService.create_booking_atomic(sched.id, user1.id, passengers_data_1, 'CARD')
        assert b1.booking_status == 'CONFIRMED'

        # Second user tries to book the EXACT SAME SEAT concurrently
        passengers_data_2 = [{'seat_id': target_seat.id, 'passenger_name': 'User Two', 'age': 28, 'gender': 'Female'}]
        with pytest.raises(SeatAlreadyBookedException) as exc_info:
            BookingService.create_booking_atomic(sched.id, user2.id, passengers_data_2, 'UPI')

        assert "already been booked" in str(exc_info.value)

        # Ensure no duplicate booking was created in database
        all_bookings = Booking.query.filter_by(schedule_id=sched.id).all()
        assert len(all_bookings) == 1
        assert sched.available_seats_count == 19


# ----------------------------------------------------------------------
# 7. Cancellation & Seat Release Test
# ----------------------------------------------------------------------
def test_cancellation_and_seat_release(app):
    with app.app_context():
        sched = Schedule.query.first()
        user = User.query.filter_by(email='passenger@test.com').first()
        seat = Seat.query.filter_by(bus_id=sched.bus_id).first()

        # Create booking
        booking = BookingService.create_booking_atomic(
            sched.id, user.id,
            [{'seat_id': seat.id, 'passenger_name': 'Cancel Test', 'age': 35, 'gender': 'Male'}],
            'UPI'
        )
        assert sched.available_seats_count == 19

        # Cancel ticket
        cancelled_booking, refund = BookingService.cancel_booking(booking.booking_id, user, reason="Trip postponed")
        assert cancelled_booking.booking_status == 'CANCELLED'
        assert refund == 270.0  # 90% of 300
        assert cancelled_booking.cancellation.refund_status == 'PROCESSED'

        # Verify seat is immediately released back to available!
        assert sched.available_seats_count == 20
        seat_status = BookingService.get_schedule_seat_status(sched.id)
        target_seat_info = next(s for s in seat_status if s['id'] == seat.id)
        assert target_seat_info['status'] == 'available'


# ----------------------------------------------------------------------
# 8. ReportLab PDF E-Ticket Generation Test
# ----------------------------------------------------------------------
def test_pdf_ticket_generation(app):
    with app.app_context():
        sched = Schedule.query.first()
        user = User.query.filter_by(email='passenger@test.com').first()
        seat = Seat.query.filter_by(bus_id=sched.bus_id).first()

        booking = BookingService.create_booking_atomic(
            sched.id, user.id,
            [{'seat_id': seat.id, 'passenger_name': 'PDF Test Passenger', 'age': 27, 'gender': 'Female'}],
            'UPI'
        )

        pdf_stream = TicketService.generate_pdf(booking)
        assert pdf_stream is not None
        pdf_bytes = pdf_stream.read()
        assert len(pdf_bytes) > 1000
        # Standard PDF magic header
        assert pdf_bytes.startswith(b'%PDF')


# ----------------------------------------------------------------------
# 9. Role-Based Access Control (RBAC) Tests
# ----------------------------------------------------------------------
def test_role_based_access_control(client, app):
    # Log in as passenger
    client.post('/login', data={'email': 'passenger@test.com', 'password': 'Passenger@123'}, follow_redirects=True)

    # Attempt to access Admin routes -> Should be rejected / redirected
    admin_resp = client.get('/admin/dashboard', follow_redirects=True)
    assert b"You do not have permission" in admin_resp.data

    # Attempt to access Operator routes -> Should be rejected
    op_resp = client.get('/operator/dashboard', follow_redirects=True)
    assert b"You do not have permission" in op_resp.data

    # Log in as admin -> Admin routes accessible
    client.get('/logout')
    client.post('/login', data={'email': 'admin@test.com', 'password': 'Admin@123'}, follow_redirects=True)
    admin_ok = client.get('/admin/dashboard')
    assert admin_ok.status_code == 200
    assert b"Admin Dashboard" in admin_ok.data


# ----------------------------------------------------------------------
# 10. Admin Bus Creation & Automatic Seat Generation Test
# ----------------------------------------------------------------------
def test_admin_bus_seat_generation(client, app):
    with app.app_context():
        admin = User.query.filter_by(role='admin').first()
        bus = Bus(
            bus_number="AUTO-SEAT-99",
            bus_name="Fleet Deluxe",
            bus_type="AC Seater",
            total_seats=30
        )
        db.session.add(bus)
        db.session.commit()
        seats = bus.initialize_seats(30)
        db.session.commit()

        assert len(seats) == 30
        assert Seat.query.filter_by(bus_id=bus.id).count() == 30
        assert Seat.query.filter_by(bus_id=bus.id, seat_number='1A').first() is not None
