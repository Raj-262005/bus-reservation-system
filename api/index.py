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


class VercelPathFixMiddleware:
    """
    WSGI middleware ensuring requests rewritten by Vercel to /api/index,
    /api/index.py, or /api are properly mapped to internal Flask routes.
    """
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        path_info = environ.get('PATH_INFO', '')
        if path_info.startswith('/api/index.py'):
            environ['PATH_INFO'] = path_info[len('/api/index.py'):] or '/'
        elif path_info.startswith('/api/index'):
            environ['PATH_INFO'] = path_info[len('/api/index'):] or '/'
        elif path_info.startswith('/api'):
            environ['PATH_INFO'] = path_info[len('/api'):] or '/'
        return self.wsgi_app(environ, start_response)


app.wsgi_app = VercelPathFixMiddleware(app.wsgi_app)

# Initialize schema and seed demo data on first startup / cold start
with app.app_context():
    try:
        db.create_all()
        if User.query.count() == 0:
            from seed import seed_database
            seed_database(app)
    except Exception as e:
        app.logger.warning(f"Vercel startup database check notice: {e}")
