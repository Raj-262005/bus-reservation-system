from datetime import datetime, timezone, date
from app.models import db, Booking, BookingPassenger, Schedule, Seat, Payment, Cancellation, ActivityLog
from app.utils.helpers import generate_booking_id, generate_transaction_id


class BookingException(Exception):
    pass


class SeatAlreadyBookedException(BookingException):
    pass


class BookingService:

    @staticmethod
    def get_schedule_seat_status(schedule_id):
        """
        Retrieves all seats for a given schedule with their current availability status.
        Status values: 'available', 'booked'
        """
        schedule = Schedule.query.get_or_404(schedule_id)
        bus = schedule.bus
        if not bus:
            return []

        booked_seat_ids = schedule.get_booked_seat_ids()
        seats = Seat.query.filter_by(bus_id=bus.id, is_active=True).order_by(Seat.seat_number).all()

        # Sort logically by row number then letter e.g., 1A, 1B, 2A...
        def sort_key(s):
            num = ''.join(c for c in s.seat_number if c.isdigit())
            letter = ''.join(c for c in s.seat_number if not c.isdigit())
            return (int(num) if num else 0, letter)

        sorted_seats = sorted(seats, key=sort_key)

        result = []
        for seat in sorted_seats:
            result.append({
                'id': seat.id,
                'seat_number': seat.seat_number,
                'seat_type': seat.seat_type,
                'deck': seat.deck,
                'status': 'booked' if seat.id in booked_seat_ids else 'available'
            })
        return result

    @staticmethod
    def create_booking_atomic(schedule_id, user_id, passengers_data, payment_method='UPI',
                              gateway_payment_id=None, gateway_order_id=None, payment_status='SUCCESS'):
        """
        Atomic transaction to create a booking and prevent double booking.
        passengers_data is a list of dicts: [{'seat_id': int, 'passenger_name': str, 'age': int, 'gender': str}]
        """
        if not passengers_data:
            raise BookingException("At least one passenger and seat must be selected.")

        requested_seat_ids = [p['seat_id'] for p in passengers_data]
        if len(requested_seat_ids) != len(set(requested_seat_ids)):
            raise BookingException("Duplicate seat selections are not permitted.")

        schedule = db.session.get(Schedule, schedule_id)
        if not schedule or schedule.status != 'SCHEDULED':
            raise BookingException("Selected bus schedule is no longer active.")

        if schedule.journey_date < date.today():
            raise BookingException("Cannot book seats for past journey dates.")

        # Ensure all requested seats belong to this bus
        valid_seats = Seat.query.filter(
            Seat.bus_id == schedule.bus_id,
            Seat.id.in_(requested_seat_ids),
            Seat.is_active == True
        ).all()
        if len(valid_seats) != len(requested_seat_ids):
            raise BookingException("One or more selected seats are invalid for this bus.")

        seat_map = {s.id: s for s in valid_seats}

        try:
            # DOUBLE BOOKING PREVENTION:
            # Check if ANY of the requested seats are already in a CONFIRMED booking for this schedule
            conflicting_bookings = (
                db.session.query(BookingPassenger.seat_id, BookingPassenger.seat_number)
                .join(Booking, BookingPassenger.booking_id == Booking.id)
                .filter(
                    Booking.schedule_id == schedule_id,
                    Booking.booking_status == 'CONFIRMED',
                    BookingPassenger.seat_id.in_(requested_seat_ids)
                )
                .all()
            )

            if conflicting_bookings:
                conflict_seat_numbers = [c.seat_number for c in conflicting_bookings]
                raise SeatAlreadyBookedException(
                    f"Seat(s) {', '.join(conflict_seat_numbers)} have already been booked by another passenger. Please choose different seats."
                )

            # Calculate total amount
            total_passengers = len(passengers_data)
            total_amount = round(schedule.fare * total_passengers, 2)
            booking_code = generate_booking_id()

            # Create Master Booking
            booking = Booking(
                booking_id=booking_code,
                user_id=user_id,
                schedule_id=schedule_id,
                total_passengers=total_passengers,
                total_amount=total_amount,
                booking_status='CONFIRMED' if payment_status == 'SUCCESS' else 'PENDING'
            )
            db.session.add(booking)
            db.session.flush()  # Populates booking.id

            # Create Passenger records
            for p_info in passengers_data:
                seat_obj = seat_map[p_info['seat_id']]
                passenger = BookingPassenger(
                    booking_id=booking.id,
                    seat_id=seat_obj.id,
                    passenger_name=p_info['passenger_name'].strip(),
                    age=int(p_info['age']),
                    gender=p_info['gender'],
                    seat_number=seat_obj.seat_number
                )
                db.session.add(passenger)

            # Create Payment record
            payment = Payment(
                booking_id=booking.id,
                transaction_id=generate_transaction_id(),
                payment_method=payment_method,
                amount=total_amount,
                payment_status=payment_status,
                gateway_payment_id=gateway_payment_id,
                gateway_order_id=gateway_order_id,
                paid_at=datetime.now(timezone.utc) if payment_status == 'SUCCESS' else None
            )
            db.session.add(payment)

            # Create Official E-Ticket Record
            from app.models import Ticket
            all_seat_nums = ", ".join(seat_map[p['seat_id']].seat_number for p in passengers_data)
            all_pass_names = ", ".join(p['passenger_name'] for p in passengers_data)
            ticket = Ticket(
                ticket_number=f"TKT-{booking_code[4:]}",
                booking_id=booking.id,
                passenger_name=all_pass_names,
                seat_numbers=all_seat_nums,
                journey_date=schedule.journey_date,
                departure_time=schedule.departure_time,
                source_city=schedule.route.source_city,
                destination_city=schedule.route.destination_city,
                bus_name=schedule.bus.bus_name,
                total_fare=total_amount,
                ticket_status='ISSUED'
            )
            db.session.add(ticket)

            db.session.commit()

            ActivityLog.log(
                action='BOOKING_CONFIRMED',
                details=f"Booking {booking_code} created for {total_passengers} passenger(s). Amount: {total_amount}",
                user_id=user_id
            )

            return booking

        except SeatAlreadyBookedException:
            db.session.rollback()
            raise
        except Exception as e:
            db.session.rollback()
            raise BookingException(f"Booking transaction failed: {str(e)}")

    @staticmethod
    def cancel_booking(booking_id_str, user, reason="Cancelled by passenger"):
        """
        Cancels a booking, issues refund status, and releases the seats automatically.
        Enforces user ownership or admin privileges.
        """
        booking = Booking.query.filter_by(booking_id=booking_id_str).first_or_404()

        # Authorization check
        if not user.is_admin and booking.user_id != user.id:
            raise BookingException("Unauthorized: You do not have permission to cancel this booking.")

        if booking.booking_status == 'CANCELLED':
            raise BookingException("This booking has already been cancelled.")

        if booking.schedule.journey_date < date.today():
            raise BookingException("Cannot cancel tickets for past journeys.")

        try:
            # Update booking status
            booking.booking_status = 'CANCELLED'
            booking.cancellation_reason = reason
            booking.cancelled_at = datetime.now(timezone.utc)

            # Update ticket status if exists
            if booking.ticket:
                booking.ticket.ticket_status = 'CANCELLED'

            # Update payment refund status
            refund_amount = round(booking.total_amount * 0.90, 2)  # 90% refund after nominal cancellation fee
            for p in booking.payments:
                if p.payment_status == 'SUCCESS':
                    p.payment_status = 'REFUNDED'

            # Record cancellation record
            cancellation = Cancellation(
                booking_id=booking.id,
                cancelled_by_id=user.id,
                refund_amount=refund_amount,
                refund_status='PROCESSED',
                reason=reason,
                cancellation_date=datetime.now(timezone.utc)
            )
            db.session.add(cancellation)
            db.session.commit()

            ActivityLog.log(
                action='BOOKING_CANCELLED',
                details=f"Booking {booking.booking_id} cancelled by User #{user.id}. Refund: {refund_amount}",
                user_id=user.id
            )

            return booking, refund_amount

        except Exception as e:
            db.session.rollback()
            raise BookingException(f"Cancellation failed: {str(e)}")
