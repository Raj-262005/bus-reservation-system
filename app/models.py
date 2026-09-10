from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    phone = db.Column(db.String(20), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='passenger', index=True)  # passenger, admin, operator
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    assigned_buses = db.relationship('Bus', backref='operator', lazy=True, foreign_keys='Bus.operator_id')
    bookings = db.relationship('Booking', backref='user', lazy=True)
    activity_logs = db.relationship('ActivityLog', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self):
        return self.role == 'admin'

    @property
    def is_operator(self):
        return self.role == 'operator'

    @property
    def is_passenger(self):
        return self.role == 'passenger'

    def __repr__(self):
        return f"<User {self.email} ({self.role})>"


class Route(db.Model):
    __tablename__ = 'routes'

    id = db.Column(db.Integer, primary_key=True)
    source_city = db.Column(db.String(100), nullable=False, index=True)
    destination_city = db.Column(db.String(100), nullable=False, index=True)
    distance_km = db.Column(db.Float, nullable=False, default=0.0)
    estimated_duration = db.Column(db.String(50), nullable=False)  # e.g., '4h 30m'
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    schedules = db.relationship('Schedule', backref='route', lazy=True, cascade='all, delete-orphan')

    @property
    def route_name(self):
        return f"{self.source_city} -> {self.destination_city}"

    def __repr__(self):
        return f"<Route {self.source_city} - {self.destination_city}>"


class Bus(db.Model):
    __tablename__ = 'buses'

    id = db.Column(db.Integer, primary_key=True)
    bus_number = db.Column(db.String(30), unique=True, nullable=False, index=True)
    bus_name = db.Column(db.String(100), nullable=False)
    bus_type = db.Column(db.String(50), nullable=False, default='AC Seater')  # AC Sleeper, AC Seater, Non-AC Seater, Luxury Multi-Axle
    total_seats = db.Column(db.Integer, nullable=False, default=40)
    operator_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    amenities = db.Column(db.String(255), default='Air Conditioning, Charging Point, Reading Light, Water Bottle')
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    seats = db.relationship('Seat', backref='bus', lazy=True, cascade='all, delete-orphan')
    schedules = db.relationship('Schedule', backref='bus', lazy=True, cascade='all, delete-orphan')

    def initialize_seats(self, total=None):
        """Automatically generates numbered seats with aisle layout for this bus."""
        count = total or self.total_seats
        # Standard bus has 4 seats per row (2 + 2) e.g., 1A, 1B, 1C, 1D
        Seat.query.filter_by(bus_id=self.id).delete()
        letters = ['A', 'B', 'C', 'D']
        seats_created = []
        seat_counter = 1
        row = 1

        is_sleeper = 'sleeper' in self.bus_type.lower()

        while seat_counter <= count:
            for letter in letters:
                if seat_counter > count:
                    break
                seat_num = f"{row}{letter}"
                seat_type = 'SLEEPER' if is_sleeper else 'SEATER'
                deck = 'UPPER' if (row > (count // 8) and is_sleeper) else 'LOWER'
                seat = Seat(
                    bus_id=self.id,
                    seat_number=seat_num,
                    seat_type=seat_type,
                    deck=deck,
                    is_active=True
                )
                db.session.add(seat)
                seats_created.append(seat)
                seat_counter += 1
            row += 1
        return seats_created

    def __repr__(self):
        return f"<Bus {self.bus_number} - {self.bus_name}>"


class Seat(db.Model):
    __tablename__ = 'seats'

    id = db.Column(db.Integer, primary_key=True)
    bus_id = db.Column(db.Integer, db.ForeignKey('buses.id', ondelete='CASCADE'), nullable=False, index=True)
    seat_number = db.Column(db.String(10), nullable=False)
    seat_type = db.Column(db.String(20), nullable=False, default='SEATER')  # SEATER, SLEEPER, WINDOW, AISLE
    deck = db.Column(db.String(20), nullable=False, default='LOWER')  # LOWER, UPPER
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    # Relationships
    booking_passengers = db.relationship('BookingPassenger', backref='seat', lazy=True)

    __table_args__ = (
        db.UniqueConstraint('bus_id', 'seat_number', name='uq_bus_seat'),
    )

    def __repr__(self):
        return f"<Seat {self.seat_number} on Bus {self.bus_id}>"


class Schedule(db.Model):
    __tablename__ = 'schedules'

    id = db.Column(db.Integer, primary_key=True)
    bus_id = db.Column(db.Integer, db.ForeignKey('buses.id', ondelete='CASCADE'), nullable=False, index=True)
    route_id = db.Column(db.Integer, db.ForeignKey('routes.id', ondelete='RESTRICT'), nullable=False, index=True)
    journey_date = db.Column(db.Date, nullable=False, index=True)
    departure_time = db.Column(db.Time, nullable=False)
    arrival_time = db.Column(db.Time, nullable=False)
    fare = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='SCHEDULED')  # SCHEDULED, COMPLETED, CANCELLED
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    bookings = db.relationship('Booking', backref='schedule', lazy=True)

    def get_booked_seat_ids(self):
        """Returns set of seat_ids already booked for this schedule."""
        from app.models import Booking, BookingPassenger
        booked = (
            db.session.query(BookingPassenger.seat_id)
            .join(Booking, BookingPassenger.booking_id == Booking.id)
            .filter(
                Booking.schedule_id == self.id,
                Booking.booking_status == 'CONFIRMED'
            )
            .all()
        )
        return {item[0] for item in booked}

    @property
    def available_seats_count(self):
        total = self.bus.total_seats if self.bus else 0
        booked = len(self.get_booked_seat_ids())
        return max(0, total - booked)

    @property
    def is_past(self):
        from datetime import date
        return self.journey_date < date.today()

    def __repr__(self):
        return f"<Schedule #{self.id} Bus {self.bus_id} on {self.journey_date}>"


class Booking(db.Model):
    __tablename__ = 'bookings'

    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.String(30), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False, index=True)
    schedule_id = db.Column(db.Integer, db.ForeignKey('schedules.id', ondelete='RESTRICT'), nullable=False, index=True)
    total_passengers = db.Column(db.Integer, nullable=False, default=1)
    base_amount = db.Column(db.Float, nullable=False, default=0.0)
    gst_rate = db.Column(db.Float, nullable=False, default=5.0)
    gst_amount = db.Column(db.Float, nullable=False, default=0.0)
    total_amount = db.Column(db.Float, nullable=False)
    booking_status = db.Column(db.String(20), nullable=False, default='CONFIRMED', index=True)  # CONFIRMED, CANCELLED, PENDING
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    cancellation_reason = db.Column(db.String(255), nullable=True)
    cancelled_at = db.Column(db.DateTime, nullable=True)

    # Computed helpers for fallback / legacy bookings
    @property
    def computed_base_amount(self):
        if self.base_amount is not None and self.base_amount > 0:
            return round(self.base_amount, 2)
        rate = self.gst_rate if self.gst_rate is not None else 5.0
        return round(self.total_amount / (1.0 + (rate / 100.0)), 2)

    @property
    def computed_gst_amount(self):
        if self.gst_amount is not None and self.gst_amount > 0:
            return round(self.gst_amount, 2)
        return round(self.total_amount - self.computed_base_amount, 2)

    # Relationships
    passengers = db.relationship('BookingPassenger', backref='booking', lazy=True, cascade='all, delete-orphan')
    payments = db.relationship('Payment', backref='booking', lazy=True, cascade='all, delete-orphan')
    cancellation = db.relationship('Cancellation', backref='booking', uselist=False, cascade='all, delete-orphan')
    ticket = db.relationship('Ticket', backref='booking', uselist=False, cascade='all, delete-orphan')

    @property
    def seat_numbers_list(self):
        return ", ".join([p.seat_number for p in self.passengers])

    @property
    def primary_passenger(self):
        return self.passengers[0].passenger_name if self.passengers else "Passenger"

    @property
    def latest_payment(self):
        return self.payments[-1] if self.payments else None

    @property
    def is_cancellable(self):
        from datetime import date
        return self.booking_status == 'CONFIRMED' and self.schedule.journey_date >= date.today()

    def __repr__(self):
        return f"<Booking {self.booking_id} ({self.booking_status})>"


class BookingPassenger(db.Model):
    __tablename__ = 'booking_passengers'

    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('bookings.id', ondelete='CASCADE'), nullable=False, index=True)
    seat_id = db.Column(db.Integer, db.ForeignKey('seats.id', ondelete='RESTRICT'), nullable=False, index=True)
    passenger_name = db.Column(db.String(100), nullable=False)
    age = db.Column(db.Integer, nullable=False)
    gender = db.Column(db.String(10), nullable=False)  # Male, Female, Other
    seat_number = db.Column(db.String(10), nullable=False)

    def __repr__(self):
        return f"<Passenger {self.passenger_name} Seat {self.seat_number}>"


class Payment(db.Model):
    __tablename__ = 'payments'

    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('bookings.id', ondelete='CASCADE'), nullable=False, index=True)
    transaction_id = db.Column(db.String(60), unique=True, nullable=False)
    payment_method = db.Column(db.String(30), nullable=False, default='UPI')  # UPI, CARD, NETBANKING, RAZORPAY_TEST, RAZORPAY_LIVE
    amount = db.Column(db.Float, nullable=False)
    payment_status = db.Column(db.String(20), nullable=False, default='PENDING', index=True)  # PENDING, SUCCESS, FAILED, REFUNDED
    gateway_payment_id = db.Column(db.String(100), nullable=True)
    gateway_order_id = db.Column(db.String(100), nullable=True)
    paid_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<Payment {self.transaction_id} - {self.payment_status}>"


class Cancellation(db.Model):
    __tablename__ = 'cancellations'

    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('bookings.id', ondelete='CASCADE'), unique=True, nullable=False)
    cancelled_by_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False)
    refund_amount = db.Column(db.Float, nullable=False, default=0.0)
    refund_status = db.Column(db.String(20), nullable=False, default='PROCESSED')  # PENDING, PROCESSED, FAILED, NO_REFUND
    reason = db.Column(db.String(255), nullable=True)
    cancellation_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationship
    cancelled_by_user = db.relationship('User', foreign_keys=[cancelled_by_id])

    def __repr__(self):
        return f"<Cancellation for Booking {self.booking_id}>"


class ActivityLog(db.Model):
    __tablename__ = 'activity_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    action = db.Column(db.String(100), nullable=False)
    details = db.Column(db.Text, nullable=True)
    ip_address = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    @classmethod
    def log(cls, action, details=None, user_id=None, ip_address=None):
        try:
            entry = cls(user_id=user_id, action=action, details=details, ip_address=ip_address)
            db.session.add(entry)
            db.session.commit()
        except Exception:
            db.session.rollback()

    def __repr__(self):
        return f"<ActivityLog {self.action} at {self.created_at}>"


class Ticket(db.Model):
    __tablename__ = 'tickets'

    id = db.Column(db.Integer, primary_key=True)
    ticket_number = db.Column(db.String(40), unique=True, nullable=False, index=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('bookings.id', ondelete='CASCADE'), unique=True, nullable=False, index=True)
    passenger_name = db.Column(db.String(100), nullable=False)
    seat_numbers = db.Column(db.String(100), nullable=False)
    journey_date = db.Column(db.Date, nullable=False)
    departure_time = db.Column(db.Time, nullable=False)
    source_city = db.Column(db.String(100), nullable=False)
    destination_city = db.Column(db.String(100), nullable=False)
    bus_name = db.Column(db.String(100), nullable=False)
    total_fare = db.Column(db.Float, nullable=False)
    ticket_status = db.Column(db.String(20), nullable=False, default='ISSUED')  # ISSUED, CANCELLED
    issued_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<Ticket {self.ticket_number} - {self.ticket_status}>"

