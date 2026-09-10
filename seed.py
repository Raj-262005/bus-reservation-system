import os
import math
from datetime import datetime, date, time, timedelta, timezone
from app import create_app
from app.models import db, User, Bus, Route, Schedule, Seat, Booking, BookingPassenger, Payment, ActivityLog
from app.utils.helpers import generate_booking_id, generate_transaction_id

app = create_app()

# 27 Major Indian Demo Cities with geographic coordinates for realistic distance/duration calculation
CITIES_COORDS = {
    'Mumbai': (18.9220, 72.8347),
    'Pune': (18.5204, 73.8567),
    'Nashik': (19.9975, 73.7898),
    'Nagpur': (21.1458, 79.0882),
    'Thane': (19.2183, 72.9781),
    'Aurangabad': (19.8762, 75.3433),
    'Ahmednagar': (19.0952, 74.7496),
    'Ahmedabad': (23.0225, 72.5714),
    'Vadodara': (22.3072, 73.1812),
    'Surat': (21.1702, 72.8311),
    'Rajkot': (22.3039, 70.8022),
    'Indore': (22.7196, 75.8577),
    'Bhopal': (23.2599, 77.4126),
    'Jaipur': (26.9124, 75.7873),
    'Udaipur': (24.5854, 73.7125),
    'Delhi': (28.6139, 77.2090),
    'Gurugram': (28.4595, 77.0266),
    'Chandigarh': (30.7333, 76.7794),
    'Lucknow': (26.8467, 80.9462),
    'Kanpur': (26.4499, 80.3319),
    'Varanasi': (25.3176, 82.9739),
    'Patna': (25.5941, 85.1376),
    'Kolkata': (22.5726, 88.3639),
    'Bengaluru': (12.9716, 77.5946),
    'Bangalore': (12.9716, 77.5946),
    'Hyderabad': (17.3850, 78.4867),
    'Chennai': (13.0827, 80.2707),
    'Goa': (15.2993, 74.1240),
}


def calculate_route_metrics(src, dst):
    """Calculates realistic road distance (km) and travel duration string."""
    if src not in CITIES_COORDS or dst not in CITIES_COORDS:
        return 350.0, "6h 00m", 6, 0

    lat1, lon1 = CITIES_COORDS[src]
    lat2, lon2 = CITIES_COORDS[dst]
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    great_circle_km = 6371.0 * c
    road_km = max(35.0, round(great_circle_km * 1.25, 0))

    hours = max(1, int(road_km / 55))
    mins = int(round((road_km % 55) / 55 * 4)) * 15
    if mins == 60:
        hours += 1
        mins = 0
    return road_km, f"{hours}h {mins:02d}m", hours, mins


def seed_database():
    with app.app_context():
        print("Initializing database tables...")
        db.create_all()

        # Optimize database if running on SQLite or PostgreSQL
        with db.engine.connect() as con:
            if db.engine.name == 'sqlite':
                try:
                    con.execute(db.text("PRAGMA synchronous = NORMAL;"))
                except Exception:
                    pass
            try:
                con.execute(db.text("CREATE INDEX IF NOT EXISTS idx_schedules_search ON schedules(route_id, journey_date, status);"))
                con.commit()
            except Exception as e:
                print(f"Note on index creation: {e}")

        print("Checking / Seeding Users...")
        # 1. Admin User
        admin = User.query.filter_by(email='admin@busreservation.com').first()
        if not admin:
            admin = User(
                name="System Administrator",
                email="admin@busreservation.com",
                phone="9876543210",
                role="admin",
                is_active=True
            )
            admin.set_password("Admin@123")
            db.session.add(admin)

        # 2. Operator User
        operator = User.query.filter_by(email='operator@busreservation.com').first()
        if not operator:
            operator = User(
                name="National Express Travels",
                email="operator@busreservation.com",
                phone="9876543211",
                role="operator",
                is_active=True
            )
            operator.set_password("Operator@123")
            db.session.add(operator)

        # 3. Passenger Users
        passenger = User.query.filter_by(email='passenger@busreservation.com').first()
        if not passenger:
            passenger = User(
                name="Amit Verma",
                email="passenger@busreservation.com",
                phone="9876543212",
                role="passenger",
                is_active=True
            )
            passenger.set_password("Passenger@123")
            db.session.add(passenger)

        passenger2 = User.query.filter_by(email='priya@example.com').first()
        if not passenger2:
            passenger2 = User(
                name="Priya Sharma",
                email="priya@example.com",
                phone="9876543213",
                role="passenger",
                is_active=True
            )
            passenger2.set_password("Passenger@123")
            db.session.add(passenger2)

        db.session.commit()
        print("Users verified: Admin, Operator, Passengers.")

        # 4. Comprehensive Fleet of Buses across all 4 Bus Types
        print("Checking / Seeding Diverse Bus Fleet...")
        buses_seed = [
            # --- AC Sleeper Fleet (30 buses) ---
            {"num": "MH-01-AB-1001", "name": "Volvo 9600 Multi-Axle", "type": "AC Sleeper", "seats": 32, "amenities": "WiFi, Charging Point, Blanket, Water Bottle, Reading Lamp, Live GPS"},
            {"num": "MH-15-KL-6006", "name": "MSRTC Shivshahi AC Sleeper", "type": "AC Sleeper", "seats": 32, "amenities": "Air Conditioning, USB Ports, Reading Lamp, Blanket, Water Bottle"},
            {"num": "TS-07-OP-8008", "name": "Deccan Express Sleeper", "type": "AC Sleeper", "seats": 32, "amenities": "WiFi, Charging Point, Mineral Water, Blanket"},
            {"num": "BR-01-PT-1100", "name": "Patliputra Super Luxury Sleeper", "type": "AC Sleeper", "seats": 32, "amenities": "WiFi, Charging Point, Blanket, Water Bottle, Reading Lamp, Live GPS"},
            {"num": "MH-20-VW-5151", "name": "Khurana Express AC Sleeper", "type": "AC Sleeper", "seats": 36, "amenities": "Central AC, Individual Air Vents, Charging Sockets, Clean Bedding"},
            {"num": "GA-01-ZA-7171", "name": "Kadamba Transport AC Sleeper", "type": "AC Sleeper", "seats": 36, "amenities": "AC Berths, Fresh Linen, Live Tracking, USB Charging"},
            {"num": "GJ-05-DE-9191", "name": "Patel Tours & Travels AC Sleeper", "type": "AC Sleeper", "seats": 32, "amenities": "WiFi, AC, Charging Point, Pillow & Blanket, Emergency Exit"},
            {"num": "DL-01-LM-4040", "name": "IntrCity SmartBus AC Sleeper", "type": "AC Sleeper", "seats": 32, "amenities": "Smart Lounge Access, WiFi, Air Purifier, Warm Blanket, Live GPS"},
            {"num": "UP-32-TU-8080", "name": "Raj Ratan Tours AC Sleeper", "type": "AC Sleeper", "seats": 36, "amenities": "AC Sleepers, Individual Screen, Bedroll, Water Bottle"},
            {"num": "UP-65-XY-1234", "name": "Kashi Vishwanath Travels AC Sleeper", "type": "AC Sleeper", "seats": 32, "amenities": "AC Multi-Axle, Charging Point, Mineral Water, Blanket"},
            {"num": "KA-05-BC-3456", "name": "VRL Travels Multi-Axle AC Sleeper", "type": "AC Sleeper", "seats": 36, "amenities": "Individual TV, WiFi, AC, Fresh Bedroll, Emergency Call Button"},
            {"num": "TS-08-HI-6789", "name": "Orange Tours and Travels AC Sleeper", "type": "AC Sleeper", "seats": 36, "amenities": "AC Sleeper, Clean Blankets, Live GPS Tracking, Water Bottle"},
            {"num": "TN-09-LM-8901", "name": "Parveen Travels AC Sleeper", "type": "AC Sleeper", "seats": 32, "amenities": "AC Berths, Personal USB, Clean Linen, Night Reading Lamp"},
            {"num": "RJ-27-RS-1234", "name": "Shrinath Travel Agency AC Sleeper", "type": "AC Sleeper", "seats": 32, "amenities": "AC Sleeper, Clean Blanket, Pillow, Mineral Water"},
            {"num": "WB-02-VW-3456", "name": "Shyamoli Paribahan AC Sleeper", "type": "AC Sleeper", "seats": 36, "amenities": "Luxury AC Sleeper, Charging Sockets, Blanket, Water"},
            {"num": "MH-01-SL-1101", "name": "National Express Starline Sleeper", "type": "AC Sleeper", "seats": 32, "amenities": "WiFi, USB Port, Pillow, Blanket, Water Bottle"},
            {"num": "MH-04-SL-1102", "name": "Thane Royal AC Sleeper", "type": "AC Sleeper", "seats": 32, "amenities": "AC Berths, Charging Sockets, Blanket"},
            {"num": "GJ-01-SL-1103", "name": "Gujarat Queen AC Sleeper", "type": "AC Sleeper", "seats": 36, "amenities": "Central AC, Blanket, Personal Reading Light"},
            {"num": "RJ-14-SL-1104", "name": "Pink City Deluxe AC Sleeper", "type": "AC Sleeper", "seats": 32, "amenities": "WiFi, Individual AC Vents, Linen"},
            {"num": "DL-01-SL-1105", "name": "Capital Connect AC Sleeper", "type": "AC Sleeper", "seats": 36, "amenities": "Air Suspension, GPS, Clean Bedding, Water Bottle"},
            {"num": "UP-32-SL-1106", "name": "Awadh Luxury AC Sleeper", "type": "AC Sleeper", "seats": 32, "amenities": "AC Sleeper, USB Port, Reading Light"},
            {"num": "KA-01-SL-1107", "name": "Silicon Express AC Sleeper", "type": "AC Sleeper", "seats": 36, "amenities": "Live GPS, WiFi, Mineral Water, Blanket"},
            {"num": "TS-09-SL-1108", "name": "Nizam Express AC Sleeper", "type": "AC Sleeper", "seats": 32, "amenities": "AC Berths, Clean Blanket, Pillow"},
            {"num": "TN-01-SL-1109", "name": "Coromandel Club AC Sleeper", "type": "AC Sleeper", "seats": 36, "amenities": "AC Berths, USB Charger, Water Bottle"},
            {"num": "WB-01-SL-1110", "name": "Howrah Superfast AC Sleeper", "type": "AC Sleeper", "seats": 32, "amenities": "Air Conditioned, Charging Socket, Linen"},
            {"num": "MP-09-SL-1111", "name": "Malwa Platinum AC Sleeper", "type": "AC Sleeper", "seats": 32, "amenities": "AC Berths, Clean Bedroll, Reading Light"},
            {"num": "GA-02-SL-1112", "name": "Goa Beachline AC Sleeper", "type": "AC Sleeper", "seats": 36, "amenities": "WiFi, AC, Blanket, Charging Points"},
            {"num": "CH-01-SL-1113", "name": "City Beautiful AC Sleeper", "type": "AC Sleeper", "seats": 32, "amenities": "HVAC Climate Control, USB, Blanket"},
            {"num": "BR-02-SL-1114", "name": "Magadh Express AC Sleeper", "type": "AC Sleeper", "seats": 32, "amenities": "AC Berths, Clean Bedroll, Water Bottle"},
            {"num": "HR-26-SL-1115", "name": "Cyber City Express AC Sleeper", "type": "AC Sleeper", "seats": 36, "amenities": "WiFi, GPS, Warm Blanket, USB"},

            # --- AC Seater Fleet (30 buses) ---
            {"num": "MH-02-CD-2002", "name": "Scania Metrolink HD", "type": "AC Seater", "seats": 40, "amenities": "Air Conditioning, USB Ports, Push-Back Seats, Emergency Hammer"},
            {"num": "KA-01-EF-3003", "name": "Mercedes Super Luxury", "type": "AC Seater", "seats": 36, "amenities": "Air Conditioning, Snacks, Reclining Seats, Live GPS, Personal Screen"},
            {"num": "DL-01-GH-4004", "name": "BharatBenz Glider AC", "type": "AC Seater", "seats": 40, "amenities": "Air Conditioning, Reading Lamp, First Aid Box, USB Charging"},
            {"num": "GJ-06-MN-7007", "name": "Gujarat Travels Intercity Express", "type": "AC Seater", "seats": 40, "amenities": "Air Conditioning, Push-Back Seats, USB Ports, Live GPS"},
            {"num": "GJ-01-QR-9009", "name": "Gujarat Rajdhani Superfast", "type": "AC Seater", "seats": 40, "amenities": "Air Conditioning, Reclining Seats, Reading Light, USB Charging"},
            {"num": "MH-04-TU-4141", "name": "Purple Travels Starline", "type": "AC Seater", "seats": 40, "amenities": "Air Conditioning, Ergonomic Seats, USB Ports, CCTV"},
            {"num": "GJ-03-FG-1010", "name": "Eagle Falcon Travels AC Seater", "type": "AC Seater", "seats": 40, "amenities": "Air Conditioning, Push-Back Seats, Footrest, Reading Lamps"},
            {"num": "UP-32-RS-7070", "name": "UPSRTC Janrath AC Seater", "type": "AC Seater", "seats": 40, "amenities": "2x2 Air Conditioned, Push-Back Seats, Reading Light"},
            {"num": "KA-01-ZA-2345", "name": "KSRTC Airavat Club Class AC Seater", "type": "AC Seater", "seats": 45, "amenities": "Volvo Multi-Axle AC, Reclining Calf Support, USB, Blanket"},
            {"num": "TS-09-FG-5678", "name": "TSRTC Rajdhani AC Seater", "type": "AC Seater", "seats": 40, "amenities": "AC Push-Back, LED TV, Charging Ports"},
            {"num": "MP-04-PQ-0123", "name": "Verma Travels AC Seater", "type": "AC Seater", "seats": 40, "amenities": "AC Push-Back, Charging Point, Mineral Water"},
            {"num": "WB-01-TU-2345", "name": "Royal Cruiser Volvo AC Seater", "type": "AC Seater", "seats": 40, "amenities": "Volvo B11R AC, Reclining Seats, USB, Entertainment"},
            {"num": "CH-01-XY-4567", "name": "Chandigarh Transport CTU AC Seater", "type": "AC Seater", "seats": 40, "amenities": "HVAC Climate Control, High Comfort Push-Back Seats"},
            {"num": "MH-12-ST-2101", "name": "Deccan Queen AC Seater", "type": "AC Seater", "seats": 40, "amenities": "Air Conditioned, Push-Back Seats, USB"},
            {"num": "MH-15-ST-2102", "name": "Godavari Express AC Seater", "type": "AC Seater", "seats": 40, "amenities": "Push-Back Reclining Seats, AC, Reading Lamp"},
            {"num": "GJ-06-ST-2103", "name": "Sayaji Express AC Seater", "type": "AC Seater", "seats": 40, "amenities": "AC, Push-Back 2x2, Charging Sockets"},
            {"num": "RJ-14-ST-2104", "name": "Thar Intercity AC Seater", "type": "AC Seater", "seats": 45, "amenities": "Reclining Seats, AC, USB Ports"},
            {"num": "DL-02-ST-2105", "name": "NCR Metro Shuttle AC Seater", "type": "AC Seater", "seats": 40, "amenities": "Comfortable 2x2 Seating, AC, CCTV"},
            {"num": "UP-78-ST-2106", "name": "Ganga Jamuna AC Seater", "type": "AC Seater", "seats": 40, "amenities": "Air Conditioning, Reading Lamp, First Aid"},
            {"num": "KA-04-ST-2107", "name": "Kaveri Intercity AC Seater", "type": "AC Seater", "seats": 45, "amenities": "Push-Back Ergonomic Seats, AC, Music"},
            {"num": "TS-10-ST-2108", "name": "Charminar Express AC Seater", "type": "AC Seater", "seats": 40, "amenities": "AC, Reclining Seats, USB Charging"},
            {"num": "TN-02-ST-2109", "name": "Marina Breeze AC Seater", "type": "AC Seater", "seats": 45, "amenities": "Air Conditioned, Clean Cabin, Push-Back"},
            {"num": "WB-03-ST-2110", "name": "Victoria Line AC Seater", "type": "AC Seater", "seats": 40, "amenities": "Volvo AC Seater, USB Ports, Reading Light"},
            {"num": "MP-01-ST-2111", "name": "Narmada Superfast AC Seater", "type": "AC Seater", "seats": 40, "amenities": "Push-Back Seats, AC, Overhead Storage"},
            {"num": "GA-01-ST-2112", "name": "Mandovi Coastline AC Seater", "type": "AC Seater", "seats": 36, "amenities": "Reclining Seats, AC, Panoramic Windows"},
            {"num": "HR-03-ST-2113", "name": "Haryana Shakti AC Seater", "type": "AC Seater", "seats": 40, "amenities": "AC 2x2 Seater, High-Back Seats, USB"},
            {"num": "BR-01-ST-2114", "name": "Vaishali Intercity AC Seater", "type": "AC Seater", "seats": 40, "amenities": "Air Conditioned, Push-Back, Clean Cabin"},
            {"num": "MH-20-ST-2115", "name": "Ajanta Caves AC Seater", "type": "AC Seater", "seats": 40, "amenities": "Comfortable Seats, AC, Mineral Water"},
            {"num": "RJ-27-ST-2116", "name": "Mewar Super Deluxe AC Seater", "type": "AC Seater", "seats": 40, "amenities": "Reclining Seats, AC, Charging Point"},
            {"num": "UP-65-ST-2117", "name": "Banaras Express AC Seater", "type": "AC Seater", "seats": 40, "amenities": "Push-Back Seats, AC, Reading Light"},

            # --- Non-AC Sleeper Fleet (30 buses) ---
            {"num": "MH-14-RS-3131", "name": "Neeta Tours & Travels Executive Sleeper", "type": "Non-AC Sleeper", "seats": 30, "amenities": "Spacious Berths, Reading Lights, Curtains, Mineral Water"},
            {"num": "MH-09-XY-6161", "name": "Konduskar Travels Non-AC Sleeper", "type": "Non-AC Sleeper", "seats": 32, "amenities": "Wide Sleepers, Reading Lamps, Luggage Storage, Fan Ventilation"},
            {"num": "GA-03-BC-8181", "name": "Paulo Travels Non-AC Sleeper", "type": "Non-AC Sleeper", "seats": 30, "amenities": "Individual Berths, Fan Cooled, Pillow, Water Bottle"},
            {"num": "GJ-01-HI-2020", "name": "Shree Sahjanand Travels Non-AC Sleeper", "type": "Non-AC Sleeper", "seats": 30, "amenities": "Individual Sleepers, Reading Light, Clean Bedding, Window Curtains"},
            {"num": "RJ-14-PQ-6060", "name": "Mahaveer Travels Non-AC Sleeper", "type": "Non-AC Sleeper", "seats": 30, "amenities": "Comfortable Sleepers, Charging Points, Fan Cooled"},
            {"num": "KA-01-DE-4567", "name": "SRS Travels Non-AC Sleeper", "type": "Non-AC Sleeper", "seats": 32, "amenities": "Double & Single Berths, Reading Light, Fan Ventilation"},
            {"num": "MP-09-NO-9012", "name": "Hans Travels Non-AC Sleeper", "type": "Non-AC Sleeper", "seats": 30, "amenities": "Spacious Sleepers, Luggage Space, Fan Cooled"},
            {"num": "MH-01-NS-3101", "name": "Sahyadri Non-AC Sleeper", "type": "Non-AC Sleeper", "seats": 32, "amenities": "Fan Cooled Berths, Reading Lights, Pillow"},
            {"num": "MH-12-NS-3102", "name": "Shivaji Travels Non-AC Sleeper", "type": "Non-AC Sleeper", "seats": 30, "amenities": "Clean Berths, Window Curtains, Water Bottle"},
            {"num": "GJ-06-NS-3103", "name": "Somnath Deluxe Non-AC Sleeper", "type": "Non-AC Sleeper", "seats": 32, "amenities": "Individual Fan, Luggage Space, Bedroll"},
            {"num": "RJ-01-NS-3104", "name": "Ranthambore Non-AC Sleeper", "type": "Non-AC Sleeper", "seats": 30, "amenities": "Spacious Sleepers, Fan Ventilation, Charging Points"},
            {"num": "DL-03-NS-3105", "name": "Northern Star Non-AC Sleeper", "type": "Non-AC Sleeper", "seats": 32, "amenities": "Wide Berths, Reading Lamp, Overhead Rack"},
            {"num": "UP-32-NS-3106", "name": "Gomti Express Non-AC Sleeper", "type": "Non-AC Sleeper", "seats": 30, "amenities": "Single & Double Berths, Fan Cooled"},
            {"num": "KA-02-NS-3107", "name": "Dharwad Non-AC Sleeper", "type": "Non-AC Sleeper", "seats": 32, "amenities": "Fan Cooled Berths, Curtains, Mineral Water"},
            {"num": "TS-07-NS-3108", "name": "Kakatiya Non-AC Sleeper", "type": "Non-AC Sleeper", "seats": 30, "amenities": "Comfortable Sleepers, Clean Linen, Fan"},
            {"num": "TN-09-NS-3109", "name": "Chola Heritage Non-AC Sleeper", "type": "Non-AC Sleeper", "seats": 32, "amenities": "Individual Fans, Reading Lights, Pillows"},
            {"num": "WB-02-NS-3110", "name": "Bengal Night Non-AC Sleeper", "type": "Non-AC Sleeper", "seats": 30, "amenities": "Clean Sleepers, Luggage Space, Fan"},
            {"num": "MP-04-NS-3111", "name": "Satpura Non-AC Sleeper", "type": "Non-AC Sleeper", "seats": 32, "amenities": "Wide Berths, Curtains, Water Bottle"},
            {"num": "GA-01-NS-3112", "name": "Konkan Night Non-AC Sleeper", "type": "Non-AC Sleeper", "seats": 30, "amenities": "Fan Cooled, Reading Light, Bedding"},
            {"num": "CH-02-NS-3113", "name": "Shivalik Non-AC Sleeper", "type": "Non-AC Sleeper", "seats": 32, "amenities": "Spacious Berths, Curtains, Overhead Storage"},
            {"num": "BR-03-NS-3114", "name": "Pataliputra Deluxe Non-AC Sleeper", "type": "Non-AC Sleeper", "seats": 30, "amenities": "Individual Sleepers, Fan, Pillow"},
            {"num": "HR-01-NS-3115", "name": "Murthal Non-AC Sleeper", "type": "Non-AC Sleeper", "seats": 32, "amenities": "Comfortable Berths, Charging Points, Fan"},
            {"num": "MH-15-NS-3116", "name": "Panchavati Non-AC Sleeper", "type": "Non-AC Sleeper", "seats": 30, "amenities": "Clean Sleepers, Window Curtains, Reading Lamp"},
            {"num": "GJ-05-NS-3117", "name": "Diamond City Non-AC Sleeper", "type": "Non-AC Sleeper", "seats": 32, "amenities": "Wide Berths, Fan Cooled, Mineral Water"},
            {"num": "UP-65-NS-3118", "name": "Ghats Express Non-AC Sleeper", "type": "Non-AC Sleeper", "seats": 30, "amenities": "Single and Double Berths, Fan Cooled"},
            {"num": "KA-05-NS-3119", "name": "Hampi Heritage Non-AC Sleeper", "type": "Non-AC Sleeper", "seats": 32, "amenities": "Fan Cooled Berths, Reading Light, Bedding"},
            {"num": "TS-08-NS-3120", "name": "Golconda Non-AC Sleeper", "type": "Non-AC Sleeper", "seats": 30, "amenities": "Clean Sleepers, Curtains, Water Bottle"},
            {"num": "RJ-27-NS-3121", "name": "Lake City Non-AC Sleeper", "type": "Non-AC Sleeper", "seats": 32, "amenities": "Spacious Sleepers, Fan Cooled, Pillow"},
            {"num": "MH-20-NS-3122", "name": "Ellora Deluxe Non-AC Sleeper", "type": "Non-AC Sleeper", "seats": 30, "amenities": "Fan Cooled Berths, Luggage Carrier"},
            {"num": "WB-04-NS-3123", "name": "Sundarbans Non-AC Sleeper", "type": "Non-AC Sleeper", "seats": 32, "amenities": "Wide Sleepers, Reading Light, Fan"},

            # --- Non-AC Seater Fleet (30 buses) ---
            {"num": "TS-09-IJ-5005", "name": "Ashok Leyland Starline", "type": "Non-AC Seater", "seats": 40, "amenities": "Comfortable Seating, Luggage Space, Water Bottle, Emergency Window"},
            {"num": "MH-12-PQ-2121", "name": "MSRTC Hirkani Semi-Luxury", "type": "Non-AC Seater", "seats": 45, "amenities": "Comfortable High-Back Seats, Overhead Luggage Rack, First Aid Box"},
            {"num": "GJ-06-JK-3030", "name": "GSRTC Gurjarnagri Express", "type": "Non-AC Seater", "seats": 50, "amenities": "Standard Seating, Luggage Space, Window Guards"},
            {"num": "RJ-14-NO-5050", "name": "RSRTC Super Express Non-AC Seater", "type": "Non-AC Seater", "seats": 50, "amenities": "Push-Back Seats, Wide Windows, Overhead Racks"},
            {"num": "UP-78-VW-9090", "name": "Shatabdi Travels Non-AC Seater", "type": "Non-AC Seater", "seats": 45, "amenities": "High-Back Seats, Clean Interior, First Aid"},
            {"num": "TN-01-JK-7890", "name": "SETC Ultra Deluxe Non-AC Seater", "type": "Non-AC Seater", "seats": 45, "amenities": "Air Suspension, Reclining Seats, Overhead Rack"},
            {"num": "BR-01-ZA-5678", "name": "Bihar State Road Transport Non-AC Seater", "type": "Non-AC Seater", "seats": 50, "amenities": "Semi-Deluxe Seater, Luggage Carrier, Clean Cabin"},
            {"num": "MH-01-SE-4101", "name": "Maharashtra Parivahan Super", "type": "Non-AC Seater", "seats": 45, "amenities": "High-Back Comfortable Seats, Overhead Rack"},
            {"num": "MH-15-SE-4102", "name": "Nashik Citylink Non-AC Seater", "type": "Non-AC Seater", "seats": 40, "amenities": "2x2 Seating, Wide Windows, First Aid Box"},
            {"num": "GJ-01-SE-4103", "name": "Gujarat Parivahan Non-AC Seater", "type": "Non-AC Seater", "seats": 50, "amenities": "Standard High-Back Seats, Luggage Space"},
            {"num": "RJ-14-SE-4104", "name": "Marwar Express Non-AC Seater", "type": "Non-AC Seater", "seats": 45, "amenities": "Push-Back Seats, Overhead Carrier"},
            {"num": "DL-01-SE-4105", "name": "Yamuna Express Non-AC Seater", "type": "Non-AC Seater", "seats": 50, "amenities": "Wide 2x2 Seating, Overhead Luggage"},
            {"num": "UP-32-SE-4106", "name": "Pradeshik Parivahan Non-AC Seater", "type": "Non-AC Seater", "seats": 45, "amenities": "High-Back Seats, First Aid, Luggage Space"},
            {"num": "KA-01-SE-4107", "name": "Karnataka Sarige Non-AC Seater", "type": "Non-AC Seater", "seats": 50, "amenities": "Ergonomic Seating, Clean Interior"},
            {"num": "TS-09-SE-4108", "name": "Palle Velugu Deluxe Non-AC Seater", "type": "Non-AC Seater", "seats": 45, "amenities": "High-Back Seats, Wide Windows"},
            {"num": "TN-01-SE-4109", "name": "Pallavan Express Non-AC Seater", "type": "Non-AC Seater", "seats": 45, "amenities": "Reclining 2x2 Seats, Overhead Storage"},
            {"num": "WB-01-SE-4110", "name": "SBSTC Intercity Non-AC Seater", "type": "Non-AC Seater", "seats": 50, "amenities": "Standard 2x2 Seating, Luggage Space"},
            {"num": "MP-09-SE-4111", "name": "Madhya Parivahan Non-AC Seater", "type": "Non-AC Seater", "seats": 45, "amenities": "High-Back Seats, Wide Windows"},
            {"num": "GA-01-SE-4112", "name": "Goa Sarige Non-AC Seater", "type": "Non-AC Seater", "seats": 40, "amenities": "Comfortable 2x2 Seating, Clean Cabin"},
            {"num": "CH-01-SE-4113", "name": "Chandigarh Star Non-AC Seater", "type": "Non-AC Seater", "seats": 45, "amenities": "High-Back Push-Back Seats, Overhead Rack"},
            {"num": "BR-02-SE-4114", "name": "Bhojpur Superfast Non-AC Seater", "type": "Non-AC Seater", "seats": 50, "amenities": "Semi-Deluxe 2x2 Seats, Luggage Carrier"},
            {"num": "HR-02-SE-4115", "name": "Haryana Roadways Express", "type": "Non-AC Seater", "seats": 50, "amenities": "High-Back Ergonomic Seats, Overhead Racks"},
            {"num": "MH-20-SE-4116", "name": "Marathwada King Non-AC Seater", "type": "Non-AC Seater", "seats": 45, "amenities": "Clean Cabin, High-Back Seats"},
            {"num": "GJ-06-SE-4117", "name": "Karnavati Intercity Non-AC Seater", "type": "Non-AC Seater", "seats": 45, "amenities": "Comfortable 2x2 Seating, Wide Windows"},
            {"num": "UP-65-SE-4118", "name": "Sarnath Express Non-AC Seater", "type": "Non-AC Seater", "seats": 45, "amenities": "High-Back Seats, Overhead Storage"},
            {"num": "KA-04-SE-4119", "name": "Mysuru Sarige Non-AC Seater", "type": "Non-AC Seater", "seats": 50, "amenities": "Ergonomic Seating, Wide Windows"},
            {"num": "TS-07-SE-4120", "name": "Telangana Star Non-AC Seater", "type": "Non-AC Seater", "seats": 45, "amenities": "High-Back Seats, Luggage Space"},
            {"num": "RJ-27-SE-4121", "name": "Chetak Express Non-AC Seater", "type": "Non-AC Seater", "seats": 45, "amenities": "Standard High-Back Seats, Overhead Rack"},
            {"num": "MH-04-SE-4122", "name": "Kalyan Shuttle Non-AC Seater", "type": "Non-AC Seater", "seats": 40, "amenities": "2x2 Seating, Wide Windows"},
            {"num": "WB-02-SE-4123", "name": "Rupasi Bangla Non-AC Seater", "type": "Non-AC Seater", "seats": 50, "amenities": "High-Back Seats, Clean Interior"},
        ]

        # Insert missing fleet buses and initialize their seats
        fleet_buses = {}
        for b_data in buses_seed:
            bus = Bus.query.filter_by(bus_number=b_data["num"]).first()
            if not bus:
                bus = Bus(
                    bus_number=b_data["num"],
                    bus_name=b_data["name"],
                    bus_type=b_data["type"],
                    total_seats=b_data["seats"],
                    operator_id=operator.id,
                    amenities=b_data["amenities"],
                    is_active=True
                )
                db.session.add(bus)
                db.session.flush()
                bus.initialize_seats(b_data["seats"])
            else:
                seat_cnt = Seat.query.filter_by(bus_id=bus.id).count()
                if seat_cnt == 0:
                    bus.initialize_seats(b_data["seats"])
            fleet_buses[b_data["num"]] = bus

        db.session.commit()
        print(f"Bus fleet ready ({len(fleet_buses)} buses verified/initialized).")

        # Categorize fleet buses by standard type for assignment
        ac_sleepers = [b for b in fleet_buses.values() if b.bus_type == 'AC Sleeper']
        ac_seaters = [b for b in fleet_buses.values() if b.bus_type == 'AC Seater']
        non_ac_sleepers = [b for b in fleet_buses.values() if b.bus_type == 'Non-AC Sleeper']
        non_ac_seaters = [b for b in fleet_buses.values() if b.bus_type == 'Non-AC Seater']

        print(f"Fleet categorized: {len(ac_sleepers)} AC Sleeper, {len(ac_seaters)} AC Seater, "
              f"{len(non_ac_sleepers)} Non-AC Sleeper, {len(non_ac_seaters)} Non-AC Seater.")

        # 5. Generate Routes for EVERY directed pair between all 27 demo cities
        print("Checking / Generating Routes for ALL demo city pairs...")
        demo_cities = sorted(list(CITIES_COORDS.keys()))
        existing_routes = {(r.source_city, r.destination_city): r for r in Route.query.all()}
        new_routes_count = 0

        for src in demo_cities:
            for dst in demo_cities:
                if src == dst or (src in ('Bangalore', 'Bengaluru') and dst in ('Bangalore', 'Bengaluru')):
                    continue
                pair = (src, dst)
                if pair not in existing_routes:
                    dist_km, dur_str, _, _ = calculate_route_metrics(src, dst)
                    route = Route(
                        source_city=src,
                        destination_city=dst,
                        distance_km=dist_km,
                        estimated_duration=dur_str,
                        is_active=True
                    )
                    db.session.add(route)
                    existing_routes[pair] = route
                    new_routes_count += 1

        db.session.commit()
        # Refresh routes map with assigned IDs
        all_routes_map = {(r.source_city, r.destination_city): r for r in Route.query.all()}
        print(f"Routes ready: {len(all_routes_map)} total directed routes (added {new_routes_count} new routes).")

        # 6. Generate 4 Schedules per route across the next 30 days
        print("Generating schedules across 30-day window for all routes...")
        existing_schedules = set(
            (s.bus_id, s.route_id, s.journey_date, s.departure_time)
            for s in Schedule.query.with_entities(
                Schedule.bus_id, Schedule.route_id, Schedule.journey_date, Schedule.departure_time
            ).all()
        )

        today = date.today()
        schedules_batch = []
        new_schedules_count = 0

        sorted_route_pairs = sorted(all_routes_map.keys())

        for idx, pair in enumerate(sorted_route_pairs):
            route = all_routes_map[pair]
            src, dst = pair
            dist_km = route.distance_km or 350.0
            _, _, dur_h, dur_m = calculate_route_metrics(src, dst)

            # Assign 4 distinct buses covering all 4 types for this route
            b_ac_seater = ac_seaters[idx % len(ac_seaters)]
            b_non_ac_seater = non_ac_seaters[idx % len(non_ac_seaters)]
            b_ac_sleeper = ac_sleepers[idx % len(ac_sleepers)]
            b_non_ac_sleeper = non_ac_sleepers[idx % len(non_ac_sleepers)]

            # 4 distinct departure times across Morning, Afternoon, Evening, Night
            m_dep_min = ((idx * 15) % 4) * 15
            dep_morning = time(6 + (idx % 3), m_dep_min)

            a_dep_min = ((idx * 7) % 4) * 15
            dep_afternoon = time(12 + (idx % 3), a_dep_min)

            e_dep_min = ((idx * 11) % 4) * 15
            dep_evening = time(18 + (idx % 2), e_dep_min)

            n_dep_min = ((idx * 17) % 4) * 15
            dep_night = time(21 + (idx % 3), n_dep_min)

            # Fares calculated realistically from road distance
            fare_ac_sleeper = float(max(450.0, round(250.0 + dist_km * 1.65, -1)))
            fare_ac_seater = float(max(350.0, round(200.0 + dist_km * 1.35, -1)))
            fare_non_ac_sleeper = float(max(320.0, round(180.0 + dist_km * 1.20, -1)))
            fare_non_ac_seater = float(max(200.0, round(120.0 + dist_km * 0.85, -1)))

            # Arrival time calculation helper
            def calc_arr(dep_t):
                arr_hour = (dep_t.hour + dur_h + (dep_t.minute + dur_m) // 60) % 24
                arr_min = (dep_t.minute + dur_m) % 60
                return time(arr_hour, arr_min)

            four_runs = [
                {"bus": b_ac_seater, "dep": dep_morning, "arr": calc_arr(dep_morning), "fare": fare_ac_seater},
                {"bus": b_non_ac_seater, "dep": dep_afternoon, "arr": calc_arr(dep_afternoon), "fare": fare_non_ac_seater},
                {"bus": b_ac_sleeper, "dep": dep_evening, "arr": calc_arr(dep_evening), "fare": fare_ac_sleeper},
                {"bus": b_non_ac_sleeper, "dep": dep_night, "arr": calc_arr(dep_night), "fare": fare_non_ac_sleeper},
            ]

            # Generate runs for each date in the 30-day window
            for day_offset in range(0, 31):
                journey_d = today + timedelta(days=day_offset)
                for run in four_runs:
                    b_id = run["bus"].id
                    dep_t = run["dep"]
                    key = (b_id, route.id, journey_d, dep_t)
                    if key in existing_schedules:
                        continue

                    s = Schedule(
                        bus_id=b_id,
                        route_id=route.id,
                        journey_date=journey_d,
                        departure_time=dep_t,
                        arrival_time=run["arr"],
                        fare=run["fare"],
                        status='SCHEDULED'
                    )
                    schedules_batch.append(s)
                    existing_schedules.add(key)
                    new_schedules_count += 1

                    if len(schedules_batch) >= 10000:
                        db.session.bulk_save_objects(schedules_batch)
                        db.session.commit()
                        schedules_batch.clear()

        if schedules_batch:
            db.session.bulk_save_objects(schedules_batch)
            db.session.commit()
            schedules_batch.clear()

        print(f"Schedules check complete. Added {new_schedules_count} new schedules across the 30-day window.")

        # 7. Sample Bookings (Preserve existing bookings if present)
        if Booking.query.count() == 0:
            print("Seeding Initial Sample Bookings...")
            today_schedules = Schedule.query.filter_by(journey_date=today).all()
            if today_schedules:
                target_schedule = today_schedules[0]
                bus_seats = Seat.query.filter_by(bus_id=target_schedule.bus_id).order_by(Seat.seat_number).all()

                if len(bus_seats) >= 2:
                    booking_code = generate_booking_id()
                    sample_booking = Booking(
                        booking_id=booking_code,
                        user_id=passenger2.id,
                        schedule_id=target_schedule.id,
                        total_passengers=2,
                        total_amount=target_schedule.fare * 2,
                        booking_status='CONFIRMED',
                        created_at=datetime.now(timezone.utc) - timedelta(hours=2)
                    )
                    db.session.add(sample_booking)
                    db.session.flush()

                    bp1 = BookingPassenger(
                        booking_id=sample_booking.id,
                        seat_id=bus_seats[0].id,
                        passenger_name="Priya Sharma",
                        age=26,
                        gender="Female",
                        seat_number=bus_seats[0].seat_number
                    )
                    bp2 = BookingPassenger(
                        booking_id=sample_booking.id,
                        seat_id=bus_seats[1].id,
                        passenger_name="Rohan Sharma",
                        age=29,
                        gender="Male",
                        seat_number=bus_seats[1].seat_number
                    )
                    db.session.add_all([bp1, bp2])

                    pay = Payment(
                        booking_id=sample_booking.id,
                        transaction_id=generate_transaction_id(),
                        payment_method="UPI",
                        amount=target_schedule.fare * 2,
                        payment_status="SUCCESS",
                        paid_at=datetime.now(timezone.utc) - timedelta(hours=2)
                    )
                    db.session.add(pay)

                    from app.models import Ticket
                    tkt1 = Ticket(
                        ticket_number=f"TKT-{sample_booking.booking_id[4:]}",
                        booking_id=sample_booking.id,
                        passenger_name="Priya Sharma, Rohan Sharma",
                        seat_numbers=f"{bus_seats[0].seat_number}, {bus_seats[1].seat_number}",
                        journey_date=target_schedule.journey_date,
                        departure_time=target_schedule.departure_time,
                        source_city=target_schedule.route.source_city,
                        destination_city=target_schedule.route.destination_city,
                        bus_name=target_schedule.bus.bus_name,
                        total_fare=sample_booking.total_amount,
                        ticket_status="ISSUED"
                    )
                    db.session.add(tkt1)
                    db.session.commit()
                    print("Sample bookings created.")
        else:
            print(f"Existing bookings detected ({Booking.query.count()} bookings). Preserving existing bookings intact.")

        print("\n=======================================================")
        print("DEMO CREDENTIALS FOR TESTING:")
        print("Admin:     admin@busreservation.com     / Admin@123")
        print("Operator:  operator@busreservation.com  / Operator@123")
        print("Passenger: passenger@busreservation.com / Passenger@123")
        print("=======================================================\n")


if __name__ == '__main__':
    seed_database()
