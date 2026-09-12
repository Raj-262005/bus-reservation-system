from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app.models import db, User, ActivityLog
from app.utils.helpers import validate_email, validate_phone, validate_password

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('passenger.dashboard'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        phone = request.form.get('phone', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        submitted_role = (request.form.get('role') or '').strip().lower()

        if submitted_role and submitted_role != 'passenger':
            flash("Role assignment is not permitted during registration.", "danger")
            return render_template('auth/register.html', name=name, email=email, phone=phone)

        # Validations
        errors = []
        if not name or len(name) < 2:
            errors.append("Please enter your full name.")
        if not validate_email(email):
            errors.append("Please enter a valid email address.")
        if not validate_phone(phone):
            errors.append("Please enter a valid 10-digit mobile number.")
        if not validate_password(password):
            errors.append("Password must be at least 6 characters long.")
        if password != confirm_password:
            errors.append("Passwords do not match.")

        # Check existing user
        if not errors:
            existing_user = User.query.filter_by(email=email).first()
            if existing_user:
                errors.append("An account with this email address already exists. Please log in.")

        if errors:
            for err in errors:
                flash(err, 'danger')
            return render_template('auth/register.html', name=name, email=email, phone=phone)

        # Create new passenger user
        user = User(
            name=name,
            email=email,
            phone=phone,
            role='passenger',
            is_active=True
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        ActivityLog.log('USER_REGISTERED', f"New passenger registered: {email}", user_id=user.id)

        flash("Registration successful! You can now log in with your credentials.", "success")
        return redirect(url_for('auth.login'))

    return render_template('auth/register.html')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        role = session.get('role')
        if role == 'admin':
            return redirect(url_for('admin.dashboard'))
        elif role == 'operator':
            return redirect(url_for('operator.dashboard'))
        return redirect(url_for('passenger.dashboard'))

    next_url = request.args.get('next')

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        remember = request.form.get('remember') == 'on'

        if not email or not password:
            flash("Please enter both email and password.", "danger")
            return render_template('auth/login.html', email=email)

        user = User.query.filter_by(email=email).first()

        if not user or not user.check_password(password):
            flash("Invalid email or password. Please check your credentials.", "danger")
            return render_template('auth/login.html', email=email)

        if not user.is_active:
            flash("Your account is deactivated. Please contact customer support.", "danger")
            return render_template('auth/login.html', email=email)

        # Populate session
        session.permanent = remember
        session['user_id'] = user.id
        session['role'] = user.role
        session['user_name'] = user.name
        session['user_email'] = user.email

        ActivityLog.log('USER_LOGIN', f"User logged in: {user.email}", user_id=user.id)

        flash(f"Welcome back, {user.name}!", "success")

        # Redirect based on next parameter or role
        if next_url and next_url.startswith('/'):
            return redirect(next_url)

        if user.role == 'admin':
            return redirect(url_for('admin.dashboard'))
        elif user.role == 'operator':
            return redirect(url_for('operator.dashboard'))
        else:
            return redirect(url_for('passenger.dashboard'))

    return render_template('auth/login.html', next=next_url)


@auth_bp.route('/logout')
def logout():
    user_id = session.get('user_id')
    if user_id:
        ActivityLog.log('USER_LOGOUT', "User logged out", user_id=user_id)
    session.clear()
    flash("You have been logged out successfully.", "info")
    return redirect(url_for('auth.login'))
