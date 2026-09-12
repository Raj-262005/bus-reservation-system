# Bus Reservation System - End-to-End Web Application

A full-stack, production-grade **Bus Reservation System** engineered for an academic Software Engineering project. Built with Python, Flask, SQLAlchemy, MySQL / SQLite dual-mode database engine, and a responsive Bootstrap 5 frontend.

---

## Key Features & Highlights

- **Visual Interactive Bus Seat Layout**: Real-time 2D deck and row seating layout (Available, Selected, Booked states) with dynamic fare calculation.
- **Double Booking Prevention Engine**: Strict server-side transaction locking and atomic conflict detection ensuring two users can never book the same seat.
- **Role-Based Access Control (RBAC)**:
  - **Passenger**: Search schedules, interactive seat picking, multi-passenger detail entry, demo/gateway payment, downloadable PDF tickets, dashboard, cancellation with automatic seat release and refund status tracking.
  - **Admin**: Executive metrics dashboard, complete CRUD for Bus Fleets (with automatic physical seat generator), Routes, Schedules, Users, Master Bookings, and filterable Revenue & Passenger Analytics Reports.
  - **Bus Operator**: Restricted portal to monitor assigned buses, operational schedules, and live passenger boarding manifests.
- **Payment Gateway Architecture**: Dual-mode payment support:
  - **Demo Payment Mode (Default)**: Test UPI, Debit/Credit Card, and Net Banking simulations with 1-click Success or Failure testing out of the box (zero external API keys needed).
  - **Razorpay Sandbox Integration**: Seamless live testing when API keys are configured in `.env`.
- **E-Ticket PDF Engine**: Generates professional, downloadable, printable journey boarding passes using ReportLab with passenger details, seat numbers, journey dates, and fare summaries.

---

## Secure Admin Access

Administrative access is configured privately through environment variables and is never exposed in the public UI or source control.

Set the following in your local `.env` file or deployment environment before starting the app:

```env
ADMIN_EMAIL=admin@yourdomain.com
ADMIN_PASSWORD=your-private-admin-password
```

Passenger and operator demo accounts may still be seeded for non-admin testing, but the admin credential is intentionally private and must not be committed to GitHub or embedded in frontend code.

---

## Beginner-Friendly Quick Start Guide (Windows)

You do **not** need advanced programming knowledge to run this project. Follow these simple steps:

### Option A: 1-Click Launch (Recommended for Beginners)

1. Open the project folder:
   ```
   C:\Users\rajth\.gemini\antigravity\scratch\bus-reservation-system
   ```
2. Double-click **`setup.bat`**:
   - This automatically installs dependencies and seeds the database with initial routes, buses, and schedules.
3. Double-click **`run.bat`**:
   - This starts the Flask web server.
4. Open your web browser (Chrome, Edge, Firefox) and navigate to:
   ```
   http://127.0.0.1:5000
   ```

---

### Option B: Command-Line Execution (PowerShell or Command Prompt)

1. Open PowerShell and change directory into the project:
   ```powershell
   cd C:\Users\rajth\.gemini\antigravity\scratch\bus-reservation-system
   ```

2. Install the required libraries:
   ```powershell
   python -m pip install -r requirements.txt
   ```

3. Seed the database with demo records:
   ```powershell
   python seed.py
   ```

4. Start the application:
   ```powershell
   python run.py
   ```

5. Open your browser and visit: **`http://127.0.0.1:5000`**

---

## Configuring MySQL Database (Optional)

The application includes an automatic **SQLite engine out-of-the-box**, allowing you to run and grade the project instantly without any database setup.

To connect to your local **MySQL Server** (e.g., MySQL Community Server 8.0 running on port 3306):

1. Open MySQL Command Line or MySQL Workbench and run:
   ```sql
   CREATE DATABASE bus_reservation_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   ```
   *(Or import the provided `database.sql` script into MySQL).*

2. Open the `.env` file in the project root and update the database settings:
   ```ini
   USE_MYSQL=True
   MYSQL_HOST=localhost
   MYSQL_PORT=3306
   MYSQL_USER=root
   MYSQL_PASSWORD=your_mysql_password
   MYSQL_DB=bus_reservation_db
   ```

3. Re-run `python seed.py` to populate MySQL with tables and seed data.

---

## Step-by-Step Testing & Verification Guide

### 1. Test Passenger Journey Booking Flow
1. Open `http://127.0.0.1:5000`.
2. In the search box, enter:
   - **From:** `Mumbai`
   - **To:** `Pune`
   - **Date:** Select today's date or tomorrow
   - Click **Search Buses**.
3. In the search results, click **View Seats** on any bus (e.g. *Volvo 9600 Multi-Axle*).
4. Notice how previously booked seats (e.g. `1A`, `1B`) appear greyed out and locked!
5. Click on available seats (e.g. `2A`, `2B`). Notice the live selected badges and auto-calculated price.
6. Click **Proceed to Passenger Details**.
7. Enter passenger names, ages, and genders for each seat.
8. Click **Continue to Payment**.
9. Select payment method (**UPI**, **Card**, or **Net Banking**) and click **Pay**.
10. You will arrive at the **Booking Confirmed** page with a unique Booking ID (e.g. `BRS-20260909-XXXXXX`).
11. Click **Download E-Ticket (PDF)** to verify the generated PDF boarding pass.

### 2. Test Double-Booking Safeguard
- Open a second browser tab or incognito window.
- Try to select the exact same seat that was just booked. The system will display the seat as `Booked` and the server will reject any concurrent attempt with a controlled exception.

### 3. Test Ticket Cancellation & Seat Release
1. Navigate to **My Bookings** in the passenger navbar.
2. Click the red **Cancel** button on your booking.
3. Review the cancellation modal (showing the 90% refund credit).
4. Click **Confirm Cancellation**.
5. Re-check the bus seat map: the cancelled seat is **immediately released and available** for other passengers to book!

### 4. Test Admin Panel Functions
1. Set `ADMIN_EMAIL` and `ADMIN_PASSWORD` in your environment before starting the app.
2. Explore:
   - **Dashboard:** View revenue, total bookings, and live metrics.
   - **Manage Buses:** Add a new bus with 32 seats. Notice how the system automatically creates 32 physical seat records (`1A`, `1B`...).
   - **Manage Routes:** Add a new route (e.g. Delhi &rarr; Agra).
   - **Manage Schedules:** Schedule a bus for tomorrow with custom departure time and fare.
   - **Manage Users:** Toggle user account status (Activate / Deactivate).
   - **Reports & Analytics:** Filter revenue and ticket volumes by date range, bus, or route. Click **Print Report**.

### 5. Test Operator Panel Functions
1. Log in with the seeded operator account configured in your environment or the default local demo account.
2. View assigned buses and upcoming scheduled trips.
3. Click **Boarding Manifest** on any schedule to view the passenger roster, seat assignments, and check-in sheet.
4. Verify that the operator cannot access `/admin/*` management routes.

---

## Running Automated Backend Tests

To run the automated test suite verifying registration, login, search, atomic booking, double-booking prevention, cancellations, and PDF generation:

```powershell
python -m pytest tests/test_app.py -v
```

All tests run in an isolated in-memory test environment and will report 100% green status.

---

## Project Structure

```
bus-reservation-system/
│
├── app/
│   ├── __init__.py                # Flask application factory & filters
│   ├── models.py                  # SQLAlchemy normalized database models
│   ├── routes/
│   │   ├── auth_routes.py         # Login, Register, Logout
│   │   ├── passenger_routes.py    # Search, Seats, Details, Payment, Bookings
│   │   ├── admin_routes.py        # Dashboard, Buses, Routes, Schedules, Reports
│   │   ├── operator_routes.py     # Operator portal & passenger manifests
│   │   └── ticket_routes.py       # ReportLab PDF E-Ticket download & stream
│   ├── services/
│   │   ├── booking_service.py     # Atomic booking engine & double booking checks
│   │   ├── payment_service.py     # Demo simulator & Razorpay gateway logic
│   │   └── ticket_service.py      # ReportLab PDF generation service
│   ├── utils/
│   │   ├── decorators.py          # Session auth & role-based access decorators
│   │   └── helpers.py             # Booking ID generator, validators, formatters
│   ├── static/
│   │   ├── css/style.css          # Custom styling, seat map grid, responsive UI
│   │   ├── js/main.js             # Client utilities & 1-click credential fill
│   │   ├── js/seat_selection.js   # Interactive seat selection engine
│   │   └── generated_tickets/     # Output directory for tickets
│   └── templates/
│       ├── base.html              # Core Bootstrap 5 layout & navbar
│       ├── index.html             # Homepage, hero search, route cards
│       ├── auth/                  # Login & Register views
│       ├── passenger/             # Seat selection, details, payment, dashboard
│       ├── admin/                 # Admin dashboard, CRUD forms, audit reports
│       ├── operator/              # Operator dashboard & boarding manifest
│       └── errors/                # 404 & 500 error pages
│
├── tests/
│   ├── __init__.py
│   └── test_app.py                # Comprehensive pytest suite
│
├── config.py                      # Development, Testing, Production configs
├── run.py                         # Application entrypoint with auto-seeding
├── seed.py                        # Standalone database population script
├── database.sql                   # MySQL 8.0 DDL schema script
├── requirements.txt               # Dependencies specification
├── setup.bat                      # 1-click Windows setup batch file
├── run.bat                        # 1-click Windows launch batch file
├── .env.example                   # Environment configuration template
├── .env                           # Local environment configuration
├── .gitignore                     # Git ignore rules
└── README.md                      # Complete system documentation
```

---

## Academic Alignment & SDLC Notes

- **Primary SDLC Model:** Waterfall Model with Prototyping and Incremental refinements.
- **Architectural Pattern:** Model-View-Controller (MVC) with Service-Layer abstraction (`BookingService`, `TicketService`, `PaymentService`).
- **Data Integrity:** Fully normalized relational schema with foreign key constraints (`ON DELETE RESTRICT` / `ON DELETE CASCADE`), database indexes on search vectors, and atomic ACID transaction boundaries.
- **Security Engineering:** Werkzeug PBKDF2:SHA256 password hashing, session tampering protection, role-based route decorators, parameterized ORM queries preventing SQL injection, and strict user ownership checks on booking operations.
