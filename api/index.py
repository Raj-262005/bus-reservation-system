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
    /api/index/<path>, /api/index.py, or via HTTP_X_MATCHED_PATH
    are properly mapped to internal Flask routes with full query strings.
    """
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        path_info = environ.get('PATH_INFO', '')

        # 1. Prefer original matched path if forwarded by Vercel edge
        matched_path = environ.get('HTTP_X_MATCHED_PATH', '')
        if matched_path and not matched_path.startswith('/api'):
            environ['PATH_INFO'] = matched_path.split('?')[0] or '/'
        elif path_info.startswith('/api/index.py'):
            remainder = path_info[len('/api/index.py'):]
            environ['PATH_INFO'] = remainder if remainder else '/'
        elif path_info.startswith('/api/index'):
            remainder = path_info[len('/api/index'):]
            environ['PATH_INFO'] = remainder if remainder else '/'
        elif path_info.startswith('/api'):
            remainder = path_info[len('/api'):]
            environ['PATH_INFO'] = remainder if remainder else '/'

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
