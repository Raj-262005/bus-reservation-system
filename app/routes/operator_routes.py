from datetime import date
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, abort
from app.models import db, User, Bus, Schedule, Booking, BookingPassenger
from app.utils.decorators import login_required, roles_accepted
from app.services.booking_service import BookingService

operator_bp = Blueprint('operator', __name__, url_prefix='/operator')


@operator_bp.route('/dashboard')
@login_required
@roles_accepted('operator')
def dashboard():
    operator_id = session['user_id']
    assigned_buses = Bus.query.filter_by(operator_id=operator_id, is_active=True).all()
    bus_ids = [b.id for b in assigned_buses]

    today = date.today()
    upcoming_schedules = (
        Schedule.query.filter(Schedule.bus_id.in_(bus_ids), Schedule.journey_date >= today)
        .order_by(Schedule.journey_date, Schedule.departure_time)
        .limit(60)
        .all()
    ) if bus_ids else []

    total_passengers_today = 0
    if bus_ids:
        from sqlalchemy import func
        from app.models import BookingPassenger
        total_passengers_today = (
            db.session.query(func.count(BookingPassenger.id))
            .join(Booking, BookingPassenger.booking_id == Booking.id)
            .join(Schedule, Booking.schedule_id == Schedule.id)
            .filter(
                Schedule.bus_id.in_(bus_ids),
                Schedule.journey_date == today,
                Booking.booking_status == 'CONFIRMED'
            )
            .scalar() or 0
        )

    return render_template('operator/dashboard.html',
                           buses=assigned_buses,
                           schedules=upcoming_schedules,
                           total_passengers_today=total_passengers_today)


@operator_bp.route('/buses')
@login_required
@roles_accepted('operator')
def buses():
    operator_id = session['user_id']
    assigned_buses = Bus.query.filter_by(operator_id=operator_id).all()
    return render_template('operator/buses.html', buses=assigned_buses)


@operator_bp.route('/schedules/<int:schedule_id>/manifest')
@login_required
@roles_accepted('operator', 'admin')
def schedule_manifest(schedule_id):
    schedule = Schedule.query.get_or_404(schedule_id)
    operator_id = session['user_id']
    role = session.get('role')

    # Ensure operator is assigned to this bus (or user is admin)
    if role != 'admin' and schedule.bus.operator_id != operator_id:
        flash("Unauthorized: You do not operate this bus.", "danger")
        return redirect(url_for('operator.dashboard'))

    # Retrieve all confirmed passengers and their seats
    passengers = (
        BookingPassenger.query.join(Booking, BookingPassenger.booking_id == Booking.id)
        .filter(Booking.schedule_id == schedule.id, Booking.booking_status == 'CONFIRMED')
        .order_by(BookingPassenger.seat_number)
        .all()
    )

    seat_status = BookingService.get_schedule_seat_status(schedule.id)

    return render_template('operator/manifest.html',
                           schedule=schedule,
                           passengers=passengers,
                           seat_status=seat_status)
