from functools import wraps
from flask import session, flash, redirect, url_for, request, abort
from app.models import User


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function


def roles_accepted(*roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash('Please log in to continue.', 'warning')
                return redirect(url_for('auth.login', next=request.url))

            user_role = session.get('role')
            if user_role not in roles:
                flash('You do not have permission to access that page.', 'danger')
                if user_role == 'admin':
                    return redirect(url_for('admin.dashboard'))
                elif user_role == 'operator':
                    return redirect(url_for('operator.dashboard'))
                else:
                    return redirect(url_for('passenger.dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def get_current_user():
    """Retrieves the currently logged-in User instance from the database."""
    user_id = session.get('user_id')
    if user_id:
        from app.models import db, User
        return db.session.get(User, user_id)
    return None
