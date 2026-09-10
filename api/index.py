import os
import sys

# Ensure root directory is on sys.path so 'app', 'config', and 'seed' can be imported
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from app import create_app
from app.models import db, User

# WSGI application callable required by Vercel's Python runtime
app = create_app()

# Initialize schema and seed demo data on first startup / cold start
with app.app_context():
    try:
        db.create_all()
        if User.query.count() == 0:
            from seed import seed_database
            seed_database(app)
    except Exception as e:
        app.logger.warning(f"Vercel startup database check notice: {e}")
