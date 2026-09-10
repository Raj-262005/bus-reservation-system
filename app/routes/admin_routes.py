from datetime import datetime, date, time
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from sqlalchemy import func
from app.models import db, User, Bus, Route, Schedule, Seat, Booking, BookingPassenger, Payment, Cancellation, ActivityLog
from app.utils.decorators import login_required, roles_accepted, get_current_user
from app.services.booking_service import BookingService

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


# -------------------------------------------------------------------
# 1. Admin Dashboard
# -------------------------------------------------------------------
@admin_bp.route('/dashboard')
@login_required
@roles_accepted('admin')
def dashboard():
    total_buses = Bus.query.filter_by(is_active=True).count()
    total_routes = Route.query.filter_by(is_active=True).count()
    total_passengers = User.query.filter_by(role='passenger').count()
    total_bookings = Booking.query.count()

    today = date.today()
    today_start = datetime.combine(today, time.min)
    today_bookings = Booking.query.filter(Booking.created_at >= today_start).count()

    # Calculate total revenue from confirmed bookings
    revenue_res = db.session.query(func.sum(Booking.total_amount))\
        .filter(Booking.booking_status == 'CONFIRMED').scalar()
    total_revenue = float(revenue_res or 0.0)

    # Calculate currently available seats across upcoming schedules
    total_capacity = db.session.query(func.sum(Bus.total_seats))\
        .join(Schedule, Schedule.bus_id == Bus.id)\
        .filter(Schedule.journey_date >= today, Schedule.status == 'SCHEDULED').scalar() or 0
    total_booked = db.session.query(func.count(BookingPassenger.id))\
        .join(Booking, BookingPassenger.booking_id == Booking.id)\
        .join(Schedule, Booking.schedule_id == Schedule.id)\
        .filter(Schedule.journey_date >= today, Schedule.status == 'SCHEDULED', Booking.booking_status == 'CONFIRMED').scalar() or 0
    available_seats_total = max(0, total_capacity - total_booked)

    recent_bookings = Booking.query.order_by(Booking.created_at.desc()).limit(8).all()

    return render_template('admin/dashboard.html',
                           total_buses=total_buses,
                           total_routes=total_routes,
                           total_passengers=total_passengers,
                           total_bookings=total_bookings,
                           today_bookings=today_bookings,
                           total_revenue=total_revenue,
                           available_seats_total=available_seats_total,
                           recent_bookings=recent_bookings)


# -------------------------------------------------------------------
# 2. Bus Management (CRUD)
# -------------------------------------------------------------------
@admin_bp.route('/buses')
@login_required
@roles_accepted('admin')
def buses():
    buses_list = Bus.query.order_by(Bus.created_at.desc()).all()
    return render_template('admin/buses.html', buses=buses_list)


@admin_bp.route('/buses/add', methods=['GET', 'POST'])
@login_required
@roles_accepted('admin')
def add_bus():
    operators = User.query.filter_by(role='operator', is_active=True).all()

    if request.method == 'POST':
        bus_number = request.form.get('bus_number', '').strip().upper()
        bus_name = request.form.get('bus_name', '').strip()
        bus_type = request.form.get('bus_type', 'AC Seater')
        total_seats = int(request.form.get('total_seats', 40))
        operator_id = request.form.get('operator_id') or None
        amenities = request.form.get('amenities', '').strip()

        if not bus_number or not bus_name:
            flash("Bus Number and Bus Name are required.", "danger")
            return render_template('admin/bus_form.html', bus=None, operators=operators)

        existing = Bus.query.filter_by(bus_number=bus_number).first()
        if existing:
            flash(f"A bus with number {bus_number} already exists.", "danger")
            return render_template('admin/bus_form.html', bus=None, operators=operators)

        bus = Bus(
            bus_number=bus_number,
            bus_name=bus_name,
            bus_type=bus_type,
            total_seats=total_seats,
            operator_id=int(operator_id) if operator_id else None,
            amenities=amenities or 'Air Conditioning, Charging Point, Reading Light, Water Bottle',
            is_active=True
        )
        db.session.add(bus)
        db.session.commit()

        # Automatically generate physical seat records for this bus
        bus.initialize_seats(total_seats)
        db.session.commit()

        flash(f"Bus '{bus.bus_name}' ({bus.bus_number}) and {total_seats} seats created successfully!", "success")
        return redirect(url_for('admin.buses'))

    return render_template('admin/bus_form.html', bus=None, operators=operators)


@admin_bp.route('/buses/<int:bus_id>/edit', methods=['GET', 'POST'])
@login_required
@roles_accepted('admin')
def edit_bus(bus_id):
    bus = Bus.query.get_or_404(bus_id)
    operators = User.query.filter_by(role='operator', is_active=True).all()

    if request.method == 'POST':
        bus.bus_name = request.form.get('bus_name', '').strip()
        bus.bus_type = request.form.get('bus_type', bus.bus_type)
        operator_id = request.form.get('operator_id') or None
        bus.operator_id = int(operator_id) if operator_id else None
        bus.amenities = request.form.get('amenities', '').strip()
        bus.is_active = request.form.get('is_active') == 'on'

        db.session.commit()
        flash(f"Bus '{bus.bus_name}' details updated.", "success")
        return redirect(url_for('admin.buses'))

    return render_template('admin/bus_form.html', bus=bus, operators=operators)


@admin_bp.route('/buses/<int:bus_id>/delete', methods=['POST'])
@login_required
@roles_accepted('admin')
def delete_bus(bus_id):
    bus = Bus.query.get_or_404(bus_id)

    # Check for active bookings on any schedule of this bus
    active_bookings = (
        db.session.query(Booking)
        .join(Schedule, Booking.schedule_id == Schedule.id)
        .filter(Schedule.bus_id == bus.id, Booking.booking_status == 'CONFIRMED')
        .count()
    )
    if active_bookings > 0:
        flash(f"Cannot delete bus {bus.bus_number} because it has {active_bookings} active confirmed bookings. You can deactivate it instead.", "danger")
        return redirect(url_for('admin.buses'))

    db.session.delete(bus)
    db.session.commit()
    flash(f"Bus {bus.bus_number} was deleted successfully.", "success")
    return redirect(url_for('admin.buses'))


# -------------------------------------------------------------------
# 3. Route Management (CRUD)
# -------------------------------------------------------------------
@admin_bp.route('/routes')
@login_required
@roles_accepted('admin')
def routes():
    routes_list = Route.query.order_by(Route.source_city).all()
    return render_template('admin/routes.html', routes=routes_list)


@admin_bp.route('/routes/add', methods=['GET', 'POST'])
@login_required
@roles_accepted('admin')
def add_route():
    if request.method == 'POST':
        source = request.form.get('source_city', '').strip()
        destination = request.form.get('destination_city', '').strip()
        distance = float(request.form.get('distance_km', 0.0))
        duration = request.form.get('estimated_duration', '').strip()

        if not source or not destination:
            flash("Source and Destination are required.", "danger")
            return render_template('admin/route_form.html', route=None)

        if source.lower() == destination.lower():
            flash("Source and Destination cannot be the same.", "danger")
            return render_template('admin/route_form.html', route=None)

        route = Route(
            source_city=source,
            destination_city=destination,
            distance_km=distance,
            estimated_duration=duration or "4h 00m",
            is_active=True
        )
        db.session.add(route)
        db.session.commit()
        flash(f"Route '{route.route_name}' added successfully!", "success")
        return redirect(url_for('admin.routes'))

    return render_template('admin/route_form.html', route=None)


@admin_bp.route('/routes/<int:route_id>/edit', methods=['GET', 'POST'])
@login_required
@roles_accepted('admin')
def edit_route(route_id):
    route = Route.query.get_or_404(route_id)

    if request.method == 'POST':
        route.source_city = request.form.get('source_city', '').strip()
        route.destination_city = request.form.get('destination_city', '').strip()
        route.distance_km = float(request.form.get('distance_km', route.distance_km))
        route.estimated_duration = request.form.get('estimated_duration', route.estimated_duration).strip()
        route.is_active = request.form.get('is_active') == 'on'

        db.session.commit()
        flash(f"Route '{route.route_name}' updated successfully.", "success")
        return redirect(url_for('admin.routes'))

    return render_template('admin/route_form.html', route=route)


@admin_bp.route('/routes/<int:route_id>/delete', methods=['POST'])
@login_required
@roles_accepted('admin')
def delete_route(route_id):
    route = Route.query.get_or_404(route_id)
    if route.schedules:
        flash(f"Cannot delete route '{route.route_name}' because active schedules are linked to it.", "danger")
        return redirect(url_for('admin.routes'))

    db.session.delete(route)
    db.session.commit()
    flash(f"Route '{route.route_name}' deleted.", "success")
    return redirect(url_for('admin.routes'))


# -------------------------------------------------------------------
# 4. Schedule Management (CRUD)
# -------------------------------------------------------------------
@admin_bp.route('/schedules')
@login_required
@roles_accepted('admin')
def schedules():
    schedules_list = Schedule.query.order_by(Schedule.journey_date.desc(), Schedule.departure_time).limit(100).all()
    return render_template('admin/schedules.html', schedules=schedules_list)


@admin_bp.route('/schedules/add', methods=['GET', 'POST'])
@login_required
@roles_accepted('admin')
def add_schedule():
    buses = Bus.query.filter_by(is_active=True).all()
    routes = Route.query.filter_by(is_active=True).all()

    if request.method == 'POST':
        bus_id = request.form.get('bus_id')
        route_id = request.form.get('route_id')
        journey_date_str = request.form.get('journey_date')
        departure_time_str = request.form.get('departure_time')
        arrival_time_str = request.form.get('arrival_time')
        fare = float(request.form.get('fare', 500.0))

        if not bus_id or not route_id or not journey_date_str or not departure_time_str or not arrival_time_str:
            flash("All schedule fields are required.", "danger")
            return render_template('admin/schedule_form.html', schedule=None, buses=buses, routes=routes)

        j_date = datetime.strptime(journey_date_str, '%Y-%m-%d').date()
        dep_time = datetime.strptime(departure_time_str, '%H:%M').time()
        arr_time = datetime.strptime(arrival_time_str, '%H:%M').time()

        schedule = Schedule(
            bus_id=int(bus_id),
            route_id=int(route_id),
            journey_date=j_date,
            departure_time=dep_time,
            arrival_time=arr_time,
            fare=fare,
            status='SCHEDULED'
        )
        db.session.add(schedule)
        db.session.commit()
        flash("New journey schedule created successfully!", "success")
        return redirect(url_for('admin.schedules'))

    today_str = date.today().strftime('%Y-%m-%d')
    return render_template('admin/schedule_form.html', schedule=None, buses=buses, routes=routes, today_str=today_str)


@admin_bp.route('/schedules/<int:schedule_id>/edit', methods=['GET', 'POST'])
@login_required
@roles_accepted('admin')
def edit_schedule(schedule_id):
    schedule = Schedule.query.get_or_404(schedule_id)
    buses = Bus.query.filter_by(is_active=True).all()
    routes = Route.query.filter_by(is_active=True).all()

    if request.method == 'POST':
        schedule.bus_id = int(request.form.get('bus_id', schedule.bus_id))
        schedule.route_id = int(request.form.get('route_id', schedule.route_id))
        schedule.journey_date = datetime.strptime(request.form.get('journey_date'), '%Y-%m-%d').date()
        schedule.departure_time = datetime.strptime(request.form.get('departure_time'), '%H:%M').time()
        schedule.arrival_time = datetime.strptime(request.form.get('arrival_time'), '%H:%M').time()
        schedule.fare = float(request.form.get('fare', schedule.fare))
        schedule.status = request.form.get('status', schedule.status)

        db.session.commit()
        flash("Schedule updated successfully.", "success")
        return redirect(url_for('admin.schedules'))

    return render_template('admin/schedule_form.html', schedule=schedule, buses=buses, routes=routes)


@admin_bp.route('/schedules/<int:schedule_id>/delete', methods=['POST'])
@login_required
@roles_accepted('admin')
def delete_schedule(schedule_id):
    schedule = Schedule.query.get_or_404(schedule_id)
    confirmed_bookings = Booking.query.filter_by(schedule_id=schedule.id, booking_status='CONFIRMED').count()
    if confirmed_bookings > 0:
        flash(f"Cannot delete schedule #{schedule.id} because it has {confirmed_bookings} confirmed bookings. You can cancel the schedule instead.", "danger")
        return redirect(url_for('admin.schedules'))

    db.session.delete(schedule)
    db.session.commit()
    flash(f"Schedule #{schedule.id} deleted successfully.", "success")
    return redirect(url_for('admin.schedules'))


# -------------------------------------------------------------------
# 5. User Management
# -------------------------------------------------------------------
@admin_bp.route('/users')
@login_required
@roles_accepted('admin')
def users():
    role_filter = request.args.get('role', 'ALL')
    query = User.query
    if role_filter in ('passenger', 'operator', 'admin'):
        query = query.filter_by(role=role_filter)
    users_list = query.order_by(User.created_at.desc()).all()
    return render_template('admin/users.html', users=users_list, role_filter=role_filter)


@admin_bp.route('/users/<int:user_id>/toggle-status', methods=['POST'])
@login_required
@roles_accepted('admin')
def toggle_user_status(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == session.get('user_id'):
        flash("You cannot deactivate your own admin account.", "danger")
        return redirect(url_for('admin.users'))

    user.is_active = not user.is_active
    db.session.commit()
    status_label = "activated" if user.is_active else "deactivated"
    flash(f"User account for '{user.email}' has been {status_label}.", "success")
    return redirect(url_for('admin.users'))


# -------------------------------------------------------------------
# 6. Booking Management
# -------------------------------------------------------------------
@admin_bp.route('/bookings')
@login_required
@roles_accepted('admin')
def bookings():
    search_query = request.args.get('q', '').strip()
    status_filter = request.args.get('status', 'ALL')

    query = Booking.query.join(User, Booking.user_id == User.id)

    if status_filter in ('CONFIRMED', 'CANCELLED'):
        query = query.filter(Booking.booking_status == status_filter)

    if search_query:
        query = query.filter(
            (Booking.booking_id.ilike(f"%{search_query}%")) |
            (User.email.ilike(f"%{search_query}%")) |
            (User.name.ilike(f"%{search_query}%"))
        )

    bookings_list = query.order_by(Booking.created_at.desc()).all()
    return render_template('admin/bookings.html', bookings=bookings_list, current_status=status_filter, query=search_query)


@admin_bp.route('/bookings/<booking_id>/cancel', methods=['POST'])
@login_required
@roles_accepted('admin')
def cancel_booking_admin(booking_id):
    admin_user = User.query.get_or_404(session['user_id'])
    reason = request.form.get('reason', 'Cancelled by system administrator')

    try:
        booking, refund = BookingService.cancel_booking(booking_id, admin_user, reason=reason)
        flash(f"Booking {booking_id} cancelled by Admin. Refund of ₹{refund:.2f} processed.", "success")
    except Exception as e:
        flash(f"Error cancelling booking: {str(e)}", "danger")

    return redirect(url_for('admin.bookings'))


# -------------------------------------------------------------------
# 7. Reports & Analytics
# -------------------------------------------------------------------
@admin_bp.route('/reports')
@login_required
@roles_accepted('admin')
def reports():
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    bus_id = request.args.get('bus_id')
    route_id = request.args.get('route_id')

    # Base query for confirmed bookings
    query = Booking.query.filter(Booking.booking_status == 'CONFIRMED')

    if start_date_str:
        try:
            s_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            query = query.filter(Booking.created_at >= s_date)
        except ValueError:
            pass

    if end_date_str:
        try:
            e_date = datetime.strptime(end_date_str, '%Y-%m-%d')
            e_date_end = datetime.combine(e_date.date(), time.max)
            query = query.filter(Booking.created_at <= e_date_end)
        except ValueError:
            pass

    if bus_id and bus_id != 'ALL':
        query = query.join(Schedule, Booking.schedule_id == Schedule.id).filter(Schedule.bus_id == int(bus_id))

    if route_id and route_id != 'ALL':
        if not bus_id or bus_id == 'ALL':
            query = query.join(Schedule, Booking.schedule_id == Schedule.id)
        query = query.filter(Schedule.route_id == int(route_id))

    filtered_bookings = query.order_by(Booking.created_at.desc()).all()

    total_tickets = sum(b.total_passengers for b in filtered_bookings)
    total_rev = sum(b.total_amount for b in filtered_bookings)

    buses = Bus.query.filter_by(is_active=True).all()
    routes = Route.query.filter_by(is_active=True).all()

    return render_template('admin/reports.html',
                           bookings=filtered_bookings,
                           total_tickets=total_tickets,
                           total_rev=total_rev,
                           buses=buses,
                           routes=routes,
                           start_date=start_date_str,
                           end_date=end_date_str,
                           selected_bus=bus_id,
                           selected_route=route_id)
