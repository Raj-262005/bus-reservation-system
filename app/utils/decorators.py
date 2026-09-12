from functools import wraps
from flask import session, flash, redirect, url_for, request, abort
from app.models import User


def get_current_user():
    """Retrieves the currently logged-in User instance from the database and validates the session."""
    user_id = session.get('user_id')
    if not user_id:
        return None

    from app.models import db
    user = db.session.get(User, user_id)
    if not user or not user.is_active:
        session.clear()
        return None

    session_role = session.get('role')
    if user.role != session_role:
        session['role'] = user.role
        session['user_name'] = user.name
        session['user_email'] = user.email

    return user


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        if not user:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function


def roles_accepted(*roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user = get_current_user()
            if not user:
                flash('Please log in to continue.', 'warning')
                return redirect(url_for('auth.login', next=request.url))

            if user.role not in roles:
                flash('You do not have permission to access that page.', 'danger')
                abort(403)

            return f(*args, **kwargs)
        return decorated_function
    return decorator
