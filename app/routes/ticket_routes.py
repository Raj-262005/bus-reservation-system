from flask import Blueprint, send_file, flash, redirect, url_for, session, abort
from app.models import Booking, User
from app.utils.decorators import login_required
from app.services.ticket_service import TicketService

ticket_bp = Blueprint('ticket', __name__)


@ticket_bp.route('/ticket/<booking_id>/download')
@login_required
def download_ticket(booking_id):
    booking = Booking.query.filter_by(booking_id=booking_id).first_or_404()
    user_id = session.get('user_id')
    user_role = session.get('role')

    # Security check: only the passenger who booked, an admin, or the bus operator can download
    if user_role != 'admin' and booking.user_id != user_id:
        if user_role == 'operator':
            if booking.schedule.bus.operator_id != user_id:
                abort(403)
        else:
            abort(403)

    pdf_buffer = TicketService.generate_pdf(booking)
    filename = f"E-Ticket_{booking.booking_id}.pdf"

    return send_file(
        pdf_buffer,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=filename
    )


@ticket_bp.route('/ticket/<booking_id>/view')
@login_required
def view_ticket(booking_id):
    booking = Booking.query.filter_by(booking_id=booking_id).first_or_404()
    user_id = session.get('user_id')
    user_role = session.get('role')

    if user_role != 'admin' and booking.user_id != user_id:
        if user_role == 'operator':
            if booking.schedule.bus.operator_id != user_id:
                abort(403)
        else:
            abort(403)

    pdf_buffer = TicketService.generate_pdf(booking)
    filename = f"E-Ticket_{booking.booking_id}.pdf"

    return send_file(
        pdf_buffer,
        mimetype='application/pdf',
        as_attachment=False,
        download_name=filename
    )
