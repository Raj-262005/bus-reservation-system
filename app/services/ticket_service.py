import io
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT


class TicketService:

    @staticmethod
    def generate_pdf(booking):
        """
        Generates a professional E-Ticket PDF for a confirmed or cancelled booking.
        Returns a BytesIO stream containing the PDF binary.
        """
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=36,
            leftMargin=36,
            topMargin=36,
            bottomMargin=36
        )

        styles = getSampleStyleSheet()

        # Custom styles
        title_style = ParagraphStyle(
            'TicketTitle',
            parent=styles['Heading1'],
            fontName='Helvetica-Bold',
            fontSize=22,
            textColor=colors.HexColor('#0f172a'),
            alignment=TA_CENTER,
            spaceAfter=4
        )
        subtitle_style = ParagraphStyle(
            'TicketSubtitle',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=11,
            textColor=colors.HexColor('#64748b'),
            alignment=TA_CENTER,
            spaceAfter=15
        )
        badge_style = ParagraphStyle(
            'StatusBadge',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=12,
            textColor=colors.HexColor('#166534') if booking.booking_status == 'CONFIRMED' else colors.HexColor('#991b1b'),
            alignment=TA_RIGHT
        )
        label_style = ParagraphStyle(
            'FieldLabel',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=9,
            textColor=colors.HexColor('#475569')
        )
        value_style = ParagraphStyle(
            'FieldValue',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=10,
            textColor=colors.HexColor('#0f172a')
        )
        section_heading = ParagraphStyle(
            'SectionHead',
            parent=styles['Heading3'],
            fontName='Helvetica-Bold',
            fontSize=12,
            textColor=colors.HexColor('#1e40af'),
            spaceBefore=10,
            spaceAfter=6
        )
        terms_style = ParagraphStyle(
            'Terms',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=8,
            textColor=colors.HexColor('#64748b'),
            leading=11
        )

        elements = []

        # 1. Header Banner
        elements.append(Paragraph("BUS RESERVATION SYSTEM", title_style))
        elements.append(Paragraph("Official Electronic Journey Ticket & Boarding Pass", subtitle_style))
        elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#2563eb'), spaceAfter=15))

        # 2. Key Booking Metadata Bar
        status_text = f"STATUS: {booking.booking_status}"
        meta_table_data = [
            [
                Paragraph(f"<b>Booking ID:</b> {booking.booking_id}", value_style),
                Paragraph(f"<b>Booking Date:</b> {booking.created_at.strftime('%d %b %Y, %I:%M %p')}", value_style),
                Paragraph(status_text, badge_style)
            ]
        ]
        meta_table = Table(meta_table_data, colWidths=[200, 200, 140])
        meta_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f1f5f9')),
            ('PADDING', (0, 0), (-1, -1), 8),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ROUNDEDCORNERS', [4, 4, 4, 4]),
        ]))
        elements.append(meta_table)
        elements.append(Spacer(1, 12))

        # 3. Trip & Bus Details Table
        elements.append(Paragraph("Trip & Schedule Details", section_heading))
        schedule = booking.schedule
        bus = schedule.bus
        route = schedule.route

        dep_time_str = schedule.departure_time.strftime('%I:%M %p') if hasattr(schedule.departure_time, 'strftime') else str(schedule.departure_time)
        arr_time_str = schedule.arrival_time.strftime('%I:%M %p') if hasattr(schedule.arrival_time, 'strftime') else str(schedule.arrival_time)
        journey_date_str = schedule.journey_date.strftime('%A, %d %B %Y') if hasattr(schedule.journey_date, 'strftime') else str(schedule.journey_date)

        trip_data = [
            [
                Paragraph("<b>From (Source)</b>", label_style),
                Paragraph(route.source_city, value_style),
                Paragraph("<b>To (Destination)</b>", label_style),
                Paragraph(route.destination_city, value_style)
            ],
            [
                Paragraph("<b>Journey Date</b>", label_style),
                Paragraph(journey_date_str, value_style),
                Paragraph("<b>Departure Time</b>", label_style),
                Paragraph(dep_time_str, value_style)
            ],
            [
                Paragraph("<b>Bus Name</b>", label_style),
                Paragraph(bus.bus_name, value_style),
                Paragraph("<b>Arrival Time</b>", label_style),
                Paragraph(arr_time_str, value_style)
            ],
            [
                Paragraph("<b>Bus Number</b>", label_style),
                Paragraph(bus.bus_number, value_style),
                Paragraph("<b>Bus Type</b>", label_style),
                Paragraph(bus.bus_type, value_style)
            ],
            [
                Paragraph("<b>Distance / Duration</b>", label_style),
                Paragraph(f"{route.distance_km} km / {route.estimated_duration}", value_style),
                Paragraph("<b>Amenities</b>", label_style),
                Paragraph(bus.amenities or "Standard", value_style)
            ]
        ]
        trip_table = Table(trip_data, colWidths=[120, 150, 120, 150])
        trip_table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f8fafc')),
            ('BACKGROUND', (2, 0), (2, -1), colors.HexColor('#f8fafc')),
            ('PADDING', (0, 0), (-1, -1), 6),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        elements.append(trip_table)
        elements.append(Spacer(1, 12))

        # 4. Passenger Details Table
        elements.append(Paragraph("Passenger Manifest & Allocated Seats", section_heading))
        passenger_rows = [
            [
                Paragraph("<b>#</b>", label_style),
                Paragraph("<b>Passenger Name</b>", label_style),
                Paragraph("<b>Age</b>", label_style),
                Paragraph("<b>Gender</b>", label_style),
                Paragraph("<b>Allocated Seat</b>", label_style),
            ]
        ]
        for idx, p in enumerate(booking.passengers, 1):
            passenger_rows.append([
                Paragraph(str(idx), value_style),
                Paragraph(p.passenger_name, value_style),
                Paragraph(str(p.age), value_style),
                Paragraph(p.gender, value_style),
                Paragraph(f"<b>{p.seat_number}</b>", value_style),
            ])

        pass_table = Table(passenger_rows, colWidths=[30, 220, 60, 90, 140])
        pass_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e2e8f0')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
            ('PADDING', (0, 0), (-1, -1), 6),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        elements.append(pass_table)
        elements.append(Spacer(1, 12))

        # 5. Payment & Fare Breakdown
        elements.append(Paragraph("Payment & Fare Summary", section_heading))
        payment = booking.latest_payment
        pay_method = payment.payment_method if payment else "N/A"
        pay_txn = payment.transaction_id if payment else "N/A"
        pay_status = payment.payment_status if payment else "N/A"

        fare_per_seat = schedule.fare
        seat_count = len(booking.passengers)
        total_fare = booking.total_amount

        pay_data = [
            [
                Paragraph("<b>Base Fare per Seat:</b>", label_style),
                Paragraph(f"INR {fare_per_seat:.2f}", value_style),
                Paragraph("<b>Payment Method:</b>", label_style),
                Paragraph(pay_method, value_style),
            ],
            [
                Paragraph("<b>Total Seats Booked:</b>", label_style),
                Paragraph(str(seat_count), value_style),
                Paragraph("<b>Transaction ID:</b>", label_style),
                Paragraph(pay_txn, value_style),
            ],
            [
                Paragraph("<b>Ticket Base Fare:</b>", label_style),
                Paragraph(f"INR {booking.computed_base_amount:.2f}", value_style),
                Paragraph("<b>Payment Status:</b>", label_style),
                Paragraph(f"<b>{pay_status}</b>", value_style),
            ],
            [
                Paragraph(f"<b>GST ({int(booking.gst_rate) if booking.gst_rate else 5}%):</b>", label_style),
                Paragraph(f"INR {booking.computed_gst_amount:.2f}", value_style),
                Paragraph("<b>Tax Specification:</b>", label_style),
                Paragraph("Passenger Transport GST", value_style),
            ],
            [
                Paragraph("<b>Grand Total Paid:</b>", ParagraphStyle('TotalBold', parent=label_style, fontSize=11, textColor=colors.HexColor('#0f172a'))),
                Paragraph(f"<b>INR {total_fare:.2f}</b>", ParagraphStyle('TotalAmt', parent=value_style, fontSize=11, textColor=colors.HexColor('#166534'))),
                Paragraph("<b>Ticket Status:</b>", label_style),
                Paragraph(f"<b>{booking.booking_status}</b>", value_style),
            ]
        ]
        pay_table = Table(pay_data, colWidths=[140, 130, 120, 150])
        pay_table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f8fafc')),
            ('BACKGROUND', (2, 0), (2, -1), colors.HexColor('#f8fafc')),
            ('PADDING', (0, 0), (-1, -1), 6),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        elements.append(pay_table)
        elements.append(Spacer(1, 15))

        # 6. Important Instructions & Terms
        elements.append(Paragraph("Important Travel Instructions", section_heading))
        terms_text = """
        1. Please arrive at the boarding point at least 20 minutes prior to scheduled departure.<br/>
        2. Valid government-issued photo identification (Aadhaar/Passport/Driving License) is required for each passenger.<br/>
        3. This E-ticket on mobile or printed copy is valid for boarding.<br/>
        4. In case of cancellation, eligible refund will be credited per the cancellation policy.<br/>
        5. For 24/7 passenger assistance, please contact support@busreservation.com or call our toll-free helpline.
        """
        elements.append(Paragraph(terms_text, terms_style))
        elements.append(Spacer(1, 10))
        elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#94a3b8'), spaceAfter=8))
        elements.append(Paragraph("Thank you for choosing Bus Reservation System. We wish you a safe and pleasant journey!", subtitle_style))

        doc.build(elements)
        buffer.seek(0)
        return buffer
