import os
from flask import Flask, render_template, session
from config import Config
from app.models import db, User


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize extensions
    db.init_app(app)

    # Ensure required directories exist
    tickets_dir = os.path.join(app.root_path, 'static', 'generated_tickets')
    try:
        os.makedirs(tickets_dir, exist_ok=True)
    except OSError:
        pass

    # Automatic schema migration for GST columns
    with app.app_context():
        try:
            from sqlalchemy import inspect, text
            inspector = inspect(db.engine)
            if 'bookings' in inspector.get_table_names():
                existing_cols = {c['name'] for c in inspector.get_columns('bookings')}
                with db.engine.connect() as conn:
                    if 'base_amount' not in existing_cols:
                        conn.execute(text("ALTER TABLE bookings ADD COLUMN base_amount FLOAT DEFAULT 0.0;"))
                    if 'gst_rate' not in existing_cols:
                        conn.execute(text("ALTER TABLE bookings ADD COLUMN gst_rate FLOAT DEFAULT 5.0;"))
                    if 'gst_amount' not in existing_cols:
                        conn.execute(text("ALTER TABLE bookings ADD COLUMN gst_amount FLOAT DEFAULT 0.0;"))
                    conn.execute(text("""
                        UPDATE bookings 
                        SET gst_rate = 5.0, 
                            base_amount = ROUND(total_amount / 1.05, 2), 
                            gst_amount = ROUND(total_amount - (total_amount / 1.05), 2)
                        WHERE (base_amount = 0.0 OR base_amount IS NULL) AND total_amount > 0;
                    """))
                    conn.commit()
        except Exception:
            pass

    # Register Blueprints
    from app.routes.auth_routes import auth_bp
    from app.routes.passenger_routes import passenger_bp
    from app.routes.admin_routes import admin_bp
    from app.routes.operator_routes import operator_bp
    from app.routes.ticket_routes import ticket_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(passenger_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(operator_bp)
    app.register_blueprint(ticket_bp)

    # Multi-language translation setup
    from app.translations import get_translation, TRANSLATIONS
    from flask import request, redirect, url_for, make_response, g

    @app.before_request
    def determine_language():
        lang = request.args.get('lang')
        if lang in ['en', 'hi', 'mr']:
            session['lang'] = lang
            g.lang = lang
        elif 'lang' in session and session['lang'] in ['en', 'hi', 'mr']:
            g.lang = session['lang']
        elif request.cookies.get('user_lang') in ['en', 'hi', 'mr']:
            g.lang = request.cookies.get('user_lang')
            session['lang'] = g.lang
        else:
            g.lang = 'en'

        if 'user_id' in session:
            user = db.session.get(User, session['user_id'])
            if not user or not user.is_active or user.role != session.get('role'):
                session.clear()

    @app.after_request
    def set_security_headers(response):
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
        return response

    @app.route('/set-language/<lang>')
    def set_language(lang):
        valid_langs = ['en', 'hi', 'mr']
        selected_lang = lang if lang in valid_langs else 'en'
        session['lang'] = selected_lang

        target = request.referrer
        if not target or target.startswith('javascript:'):
            target = url_for('passenger.home')

        resp = make_response(redirect(target))
        resp.set_cookie('user_lang', selected_lang, max_age=30 * 86400, samesite='Lax')
        return resp

    # Context processors for templates
    @app.context_processor
    def inject_global_vars():
        current_user = None
        if 'user_id' in session:
            current_user = db.session.get(User, session['user_id'])
        
        lang = getattr(g, 'lang', 'en')
        lang_names = {
            'en': 'English',
            'hi': 'हिन्दी',
            'mr': 'मराठी'
        }
        return {
            'current_user': current_user,
            'session_role': session.get('role'),
            'session_user_name': session.get('user_name'),
            '_': lambda key_or_phrase, **kwargs: get_translation(key_or_phrase, lang=getattr(g, 'lang', 'en'), **kwargs),
            't': lambda key_or_phrase, **kwargs: get_translation(key_or_phrase, lang=getattr(g, 'lang', 'en'), **kwargs),
            'current_lang': lang,
            'current_lang_name': lang_names.get(lang, 'English'),
            'supported_languages': [
                ('en', 'English'),
                ('hi', 'हिन्दी'),
                ('mr', 'मराठी')
            ],
            'T': TRANSLATIONS.get(lang, TRANSLATIONS['en'])
        }

    # Custom Jinja filters
    @app.template_filter('currency')
    def format_currency_filter(amount):
        try:
            return f"₹{float(amount):,.2f}"
        except (ValueError, TypeError):
            return f"₹{amount}"

    @app.template_filter('format_time')
    def format_time_filter(t):
        if hasattr(t, 'strftime'):
            return t.strftime('%I:%M %p')
        return str(t)

    @app.template_filter('format_date')
    def format_date_filter(d):
        if hasattr(d, 'strftime'):
            return d.strftime('%d %b %Y')
        return str(d)

    # Error handlers
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        return render_template('errors/500.html'), 500

    @app.errorhandler(403)
    def forbidden(e):
        return render_template('errors/404.html', message="403 Forbidden - Access Denied"), 403

    return app
