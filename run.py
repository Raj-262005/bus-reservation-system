import os
from app import create_app
from app.models import db, User
from seed import seed_database

app = create_app()

with app.app_context():
    # Ensure database schema is created
    db.create_all()
    # If the database is brand new with 0 users, auto-seed with initial data
    try:
        if User.query.count() == 0:
            print("Auto-seeding demo data on first start...")
            seed_database()
    except Exception as e:
        print(f"Note: Seed check encountered {e}")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', '1') == '1'
    print("\n=======================================================")
    print(" Bus Reservation System is running!")
    print(f" Access the website at: http://127.0.0.1:{port}")
    print(" Demo Logins:")
    print("  - Admin:     admin@busreservation.com     / Admin@123")
    print("  - Operator:  operator@busreservation.com  / Operator@123")
    print("  - Passenger: passenger@busreservation.com / Passenger@123")
    print("=======================================================\n")
    app.run(host='127.0.0.1', port=port, debug=debug)
