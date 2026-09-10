import json
from datetime import datetime, date
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify, current_app
from app.models import db, User, Bus, Route, Schedule, Seat, Booking, BookingPassenger, Payment, Cancellation
from app.utils.decorators import login_required, roles_accepted, get_current_user
from app.utils.helpers import validate_email, validate_phone, validate_password
from app.services.booking_service import BookingService, BookingException, SeatAlreadyBookedException
from app.services.payment_service import PaymentService

passenger_bp = Blueprint('passenger', __name__)


# -------------------------------------------------------------------
# 1. Public Home & Search
# -------------------------------------------------------------------
@passenger_bp.route('/')
def home():
    # Fetch distinct sources and destinations for quick dropdown suggestions
    routes = Route.query.filter_by(is_active=True).all()
    sources = sorted(list(set(r.source_city for r in routes)))
    destinations = sorted(list(set(r.destination_city for r in routes)))
    today_str = date.today().strftime('%Y-%m-%d')
    return render_template('index.html', sources=sources, destinations=destinations, today_str=today_str, routes=routes)


@passenger_bp.route('/search')
def search():
    source = request.args.get('source', '').strip()
    destination = request.args.get('destination', '').strip()
    journey_date_str = request.args.get('journey_date', '').strip()
    bus_type = request.args.get('bus_type', '').strip()

    errors = []
    if not source or not destination:
        errors.append("Please select both source and destination cities.")
    elif source.lower() == destination.lower():
        errors.append("Source and destination cannot be the same city.")

    parsed_date = None
    if journey_date_str:
        try:
            parsed_date = datetime.strptime(journey_date_str, '%Y-%m-%d').date()
            if parsed_date < date.today():
                errors.append("Journey date cannot be in the past.")
        except ValueError:
            errors.append("Invalid date format.")
    else:
        # Default to today's date if not supplied
        parsed_date = date.today()
        journey_date_str = parsed_date.strftime('%Y-%m-%d')

    routes = Route.query.filter_by(is_active=True).all()
    sources = sorted(list(set(r.source_city for r in routes)))
    destinations = sorted(list(set(r.destination_city for r in routes)))

    if errors:
        for err in errors:
            flash(err, 'danger')
        return render_template('passenger/search_results.html',
                               schedules=[], source=source, destination=destination,
                               journey_date=journey_date_str, bus_type=bus_type,
                               sources=sources, destinations=destinations)

    # Query matching schedules
    query = (
        Schedule.query.join(Route, Schedule.route_id == Route.id)
        .join(Bus, Schedule.bus_id == Bus.id)
        .filter(
            Route.source_city.ilike(source),
            Route.destination_city.ilike(destination),
            Schedule.journey_date == parsed_date,
            Schedule.status == 'SCHEDULED',
            Bus.is_active == True
        )
    )

    if bus_type and bus_type != 'ALL':
        bus_type_clean = bus_type.strip()
        if bus_type_clean == 'AC':
            query = query.filter(Bus.bus_type.ilike('%AC%'), ~Bus.bus_type.ilike('%Non-AC%'))
        elif bus_type_clean == 'Non-AC':
            query = query.filter(Bus.bus_type.ilike('%Non-AC%'))
        elif bus_type_clean == 'AC Sleeper':
            query = query.filter(Bus.bus_type.ilike('%AC%'), ~Bus.bus_type.ilike('%Non-AC%'), Bus.bus_type.ilike('%Sleeper%'))
        elif bus_type_clean == 'Non-AC Sleeper':
            query = query.filter(Bus.bus_type.ilike('%Non-AC%'), Bus.bus_type.ilike('%Sleeper%'))
        elif bus_type_clean == 'AC Seater':
            query = query.filter(Bus.bus_type.ilike('%AC%'), ~Bus.bus_type.ilike('%Non-AC%'), Bus.bus_type.ilike('%Seater%'))
        elif bus_type_clean == 'Non-AC Seater':
            query = query.filter(Bus.bus_type.ilike('%Non-AC%'), Bus.bus_type.ilike('%Seater%'))
        elif bus_type_clean == 'Sleeper':
            query = query.filter(Bus.bus_type.ilike('%Sleeper%'))
        elif bus_type_clean == 'Seater':
            query = query.filter(Bus.bus_type.ilike('%Seater%'))
        else:
            query = query.filter(Bus.bus_type.ilike(f"%{bus_type_clean}%"))

    schedules = query.order_by(Schedule.departure_time).all()

    return render_template('passenger/search_results.html',
                           schedules=schedules, source=source, destination=destination,
                           journey_date=journey_date_str, bus_type=bus_type,
                           sources=sources, destinations=destinations)


# -------------------------------------------------------------------
# 2. Seat Selection
# -------------------------------------------------------------------
@passenger_bp.route('/bus/<int:schedule_id>/seats')
def seat_selection(schedule_id):
    schedule = Schedule.query.get_or_404(schedule_id)
    seats_data = BookingService.get_schedule_seat_status(schedule_id)
    return render_template('passenger/seat_selection.html', schedule=schedule, seats_data=seats_data)


# -------------------------------------------------------------------
# 3. Passenger Details Form
# -------------------------------------------------------------------
@passenger_bp.route('/book/<int:schedule_id>', methods=['GET', 'POST'])
def passenger_details(schedule_id):
    schedule = Schedule.query.get_or_404(schedule_id)

    if request.method == 'GET':
        selected_seat_ids_str = request.args.get('seats', '')
        if not selected_seat_ids_str:
            flash("Please select at least one seat first.", "warning")
            return redirect(url_for('passenger.seat_selection', schedule_id=schedule_id))

        try:
            seat_ids = [int(s) for s in selected_seat_ids_str.split(',') if s.strip()]
        except ValueError:
            flash("Invalid seat selection.", "danger")
            return redirect(url_for('passenger.seat_selection', schedule_id=schedule_id))

        seats = Seat.query.filter(Seat.id.in_(seat_ids), Seat.bus_id == schedule.bus_id).all()
        booked_ids = schedule.get_booked_seat_ids()

        # Check if any seat was booked in the interim
        for s in seats:
            if s.id in booked_ids:
                flash(f"Seat {s.seat_number} was just booked by another user. Please choose another seat.", "danger")
                return redirect(url_for('passenger.seat_selection', schedule_id=schedule_id))

        # Pass current user info if logged in
        current_user = get_current_user()
        total_fare = schedule.fare * len(seats)

        return render_template('passenger/passenger_details.html',
                               schedule=schedule,
                               seats=seats,
                               total_fare=total_fare,
                               current_user=current_user)

    # POST: User submits passenger information for the selected seats
    if 'user_id' not in session:
        flash("Please log in or create an account to finalize your booking.", "info")
        return redirect(url_for('auth.login', next=request.url))

    seat_ids = request.form.getlist('seat_ids[]')
    if not seat_ids:
        flash("No seats were selected.", "danger")
        return redirect(url_for('passenger.seat_selection', schedule_id=schedule_id))

    passengers_data = []
    for s_id in seat_ids:
        p_name = request.form.get(f'name_{s_id}', '').strip()
        p_age = request.form.get(f'age_{s_id}', '').strip()
        p_gender = request.form.get(f'gender_{s_id}', '').strip()

        if not p_name or not p_age or not p_gender:
            flash("Please provide full name, age, and gender for all passengers.", "danger")
            return redirect(url_for('passenger.passenger_details', schedule_id=schedule_id, seats=",".join(seat_ids)))

        passengers_data.append({
            'seat_id': int(s_id),
            'passenger_name': p_name,
            'age': int(p_age),
            'gender': p_gender
        })

    # Save provisional booking data in session for checkout
    session['pending_booking'] = {
        'schedule_id': schedule_id,
        'passengers_data': passengers_data,
        'contact_email': request.form.get('contact_email', session.get('user_email')),
        'contact_phone': request.form.get('contact_phone', '')
    }

    return redirect(url_for('passenger.checkout'))


# -------------------------------------------------------------------
# 4. Checkout & Payment
# -------------------------------------------------------------------
@passenger_bp.route('/checkout')
@login_required
def checkout():
    pending = session.get('pending_booking')
    if not pending:
        flash("No active booking session found. Please start a new search.", "warning")
        return redirect(url_for('passenger.home'))

    schedule = Schedule.query.get_or_404(pending['schedule_id'])
    seat_ids = [p['seat_id'] for p in pending['passengers_data']]
    seats = Seat.query.filter(Seat.id.in_(seat_ids)).all()
    seat_map = {s.id: s.seat_number for s in seats}

    for p in pending['passengers_data']:
        p['seat_number'] = seat_map.get(p['seat_id'], 'N/A')

    total_amount = schedule.fare * len(pending['passengers_data'])
    demo_mode = current_app.config.get('DEMO_PAYMENT_MODE', True)
    razorpay_configured = PaymentService.is_razorpay_configured()
    razorpay_key_id = current_app.config.get('RAZORPAY_KEY_ID', '')

    razorpay_order = None
    if razorpay_configured and not demo_mode:
        razorpay_order = PaymentService.create_razorpay_order(
            amount=total_amount,
            receipt=f"rcpt_{session['user_id']}_{schedule.id}"
        )

    return render_template('passenger/payment.html',
                           schedule=schedule,
                           passengers=pending['passengers_data'],
                           total_amount=total_amount,
                           demo_mode=demo_mode,
                           razorpay_configured=razorpay_configured,
                           razorpay_key_id=razorpay_key_id,
                           razorpay_order=razorpay_order)


@passenger_bp.route('/payment/demo/process', methods=['POST'])
@login_required
def process_demo_payment():
    pending = session.get('pending_booking')
    if not pending:
        flash("Your booking session has expired. Please select your seats again.", "danger")
        return redirect(url_for('passenger.home'))

    method = request.form.get('payment_method', 'UPI')
    simulate_failure = request.form.get('simulate_failure') == '1'

    # Check simulated payment status
    success, txn_id, msg = PaymentService.process_demo_payment(method, simulate_failure=simulate_failure)

    if not success:
        flash(f"Payment Failed: {msg}. No seats were reserved. Please try again.", "danger")
        return redirect(url_for('passenger.checkout'))

    # Atomic Booking Execution
    try:
        booking = BookingService.create_booking_atomic(
            schedule_id=pending['schedule_id'],
            user_id=session['user_id'],
            passengers_data=pending['passengers_data'],
            payment_method=method,
            gateway_payment_id=txn_id,
            payment_status='SUCCESS'
        )

        # Clear provisional session data
        session.pop('pending_booking', None)

        flash("Payment successful! Your booking is confirmed.", "success")
        return redirect(url_for('passenger.booking_confirmed', booking_id=booking.booking_id))

    except SeatAlreadyBookedException as e:
        flash(str(e), "danger")
        return redirect(url_for('passenger.seat_selection', schedule_id=pending['schedule_id']))
    except BookingException as e:
        flash(f"Booking error: {str(e)}", "danger")
        return redirect(url_for('passenger.checkout'))


@passenger_bp.route('/payment/razorpay/verify', methods=['POST'])
@login_required
def verify_razorpay_payment():
    pending = session.get('pending_booking')
    if not pending:
        return jsonify({'status': 'error', 'message': 'Booking session expired'}), 400

    data = request.get_json() or {}
    order_id = data.get('razorpay_order_id')
    payment_id = data.get('razorpay_payment_id')
    signature = data.get('razorpay_signature')

    if not order_id or not payment_id or not signature:
        return jsonify({'status': 'error', 'message': 'Missing payment verification tokens'}), 400

    is_valid = PaymentService.verify_razorpay_signature(order_id, payment_id, signature)
    if not is_valid:
        return jsonify({'status': 'error', 'message': 'Invalid payment signature. Transaction rejected.'}), 400

    try:
        booking = BookingService.create_booking_atomic(
            schedule_id=pending['schedule_id'],
            user_id=session['user_id'],
            passengers_data=pending['passengers_data'],
            payment_method='RAZORPAY',
            gateway_payment_id=payment_id,
            gateway_order_id=order_id,
            payment_status='SUCCESS'
        )
        session.pop('pending_booking', None)
        return jsonify({
            'status': 'success',
            'redirect_url': url_for('passenger.booking_confirmed', booking_id=booking.booking_id)
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400


# -------------------------------------------------------------------
# 5. Confirmation Page
# -------------------------------------------------------------------
@passenger_bp.route('/booking/confirmed/<booking_id>')
@login_required
def booking_confirmed(booking_id):
    booking = Booking.query.filter_by(booking_id=booking_id).first_or_404()
    # Check authorization
    if booking.user_id != session['user_id'] and session.get('role') != 'admin':
        flash("Unauthorized access.", "danger")
        return redirect(url_for('passenger.dashboard'))

    return render_template('passenger/confirmation.html', booking=booking)


@passenger_bp.route('/booking/<booking_id>')
@login_required
def view_booking(booking_id):
    booking = Booking.query.filter_by(booking_id=booking_id).first_or_404()
    # Strict user ownership check: passenger can access ONLY their own bookings
    if booking.user_id != session['user_id'] and session.get('role') != 'admin':
        flash("Unauthorized: You can only view your own bookings.", "danger")
        return redirect(url_for('passenger.my_bookings'))

    return render_template('passenger/confirmation.html', booking=booking)


# -------------------------------------------------------------------
# 6. Passenger Dashboard & Booking Management
# -------------------------------------------------------------------
@passenger_bp.route('/dashboard')
@login_required
@roles_accepted('passenger', 'admin', 'operator')
def dashboard():
    user_id = session['user_id']
    user = User.query.get_or_404(user_id)

    # If admin or operator visits directly, redirect to their dedicated panel
    if user.role == 'admin':
        return redirect(url_for('admin.dashboard'))
    elif user.role == 'operator':
        return redirect(url_for('operator.dashboard'))

    # Passenger dashboard metrics
    bookings = Booking.query.filter_by(user_id=user_id).order_by(Booking.created_at.desc()).all()
    total_bookings = len(bookings)
    confirmed_bookings = sum(1 for b in bookings if b.booking_status == 'CONFIRMED')
    cancelled_bookings = sum(1 for b in bookings if b.booking_status == 'CANCELLED')

    today = date.today()
    upcoming_journeys = [b for b in bookings if b.booking_status == 'CONFIRMED' and b.schedule.journey_date >= today]
    upcoming_journey = upcoming_journeys[0] if upcoming_journeys else None

    return render_template('passenger/dashboard.html',
                           user=user,
                           total_bookings=total_bookings,
                           confirmed_bookings=confirmed_bookings,
                           cancelled_bookings=cancelled_bookings,
                           upcoming_journey=upcoming_journey,
                           recent_bookings=bookings[:5])


@passenger_bp.route('/my-bookings')
@login_required
@roles_accepted('passenger', 'admin')
def my_bookings():
    user_id = session['user_id']
    status_filter = request.args.get('status', 'ALL')

    query = Booking.query.filter_by(user_id=user_id)
    if status_filter in ('CONFIRMED', 'CANCELLED'):
        query = query.filter_by(booking_status=status_filter)

    bookings = query.order_by(Booking.created_at.desc()).all()
    return render_template('passenger/bookings.html', bookings=bookings, current_status=status_filter)


@passenger_bp.route('/booking/<booking_id>/cancel', methods=['POST'])
@login_required
@roles_accepted('passenger', 'admin')
def cancel_ticket(booking_id):
    user = User.query.get_or_404(session['user_id'])
    reason = request.form.get('reason', 'Cancelled by passenger')

    try:
        booking, refund_amount = BookingService.cancel_booking(booking_id, user, reason=reason)
        flash(f"Booking {booking_id} cancelled successfully. Refund of ₹{refund_amount:.2f} has been initiated.", "success")
    except BookingException as e:
        flash(str(e), "danger")

    return redirect(url_for('passenger.my_bookings'))


# -------------------------------------------------------------------
# 7. Profile Management
# -------------------------------------------------------------------
@passenger_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    user = User.query.get_or_404(session['user_id'])

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'update_info':
            name = request.form.get('name', '').strip()
            phone = request.form.get('phone', '').strip()

            if not name or len(name) < 2:
                flash("Name must be at least 2 characters long.", "danger")
            elif not validate_phone(phone):
                flash("Please enter a valid 10-digit phone number.", "danger")
            else:
                user.name = name
                user.phone = phone
                session['user_name'] = name
                db.session.commit()
                flash("Profile details updated successfully!", "success")

        elif action == 'change_password':
            current_pwd = request.form.get('current_password', '')
            new_pwd = request.form.get('new_password', '')
            confirm_pwd = request.form.get('confirm_password', '')

            if not user.check_password(current_pwd):
                flash("Current password entered is incorrect.", "danger")
            elif not validate_password(new_pwd):
                flash("New password must be at least 6 characters long.", "danger")
            elif new_pwd != confirm_pwd:
                flash("New passwords do not match.", "danger")
            else:
                user.set_password(new_pwd)
                db.session.commit()
                flash("Password updated successfully!", "success")

        return redirect(url_for('passenger.profile'))

    return render_template('passenger/profile.html', user=user)
