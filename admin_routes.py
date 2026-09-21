from functools import wraps
import os
from datetime import datetime, timezone

from flask import Blueprint, redirect, render_template_string, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash


def init_admin(app, db, User):
    """Register the database-backed administrator area on the existing app."""

    class Admin(db.Model):
        __tablename__ = "admins"
        id = db.Column(db.Integer, primary_key=True)
        email = db.Column(db.String(120), unique=True, nullable=False)
        password_hash = db.Column(db.String(255), nullable=False)
        created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    with app.app_context():
        db.create_all()
        _bootstrap_admin(db, Admin)

    admin = Blueprint("admin", __name__, url_prefix="/admin")

    def logged_in_admin():
        admin_id = session.get("admin_id")
        return Admin.query.get(admin_id) if admin_id else None

    def admin_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not logged_in_admin():
                return redirect(url_for("admin.login", next=request.path))
            return view(*args, **kwargs)
        return wrapped

    @admin.route("/login", methods=["GET", "POST"])
    def login():
        error = None
        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            account = Admin.query.filter_by(email=email).first()
            if account and check_password_hash(account.password_hash, password):
                session.clear()
                session["admin_id"] = account.id
                return redirect(request.args.get("next") or url_for("admin.dashboard"))
            error = "Invalid administrator login."
        return render_template_string(_LOGIN_HTML, error=error)

    @admin.route("/")
    @admin_required
    def dashboard():
        users = User.query.order_by(User.id.desc()).all()
        return render_template_string(_DASHBOARD_HTML, users=users, admin=logged_in_admin())

    @admin.route("/logout")
    def logout():
        session.pop("admin_id", None)
        return redirect(url_for("admin.login"))

    app.register_blueprint(admin)
    return Admin


def _bootstrap_admin(db, Admin):
    """Create the first administrator from Render environment variables only once."""
    email = os.getenv("ADMIN_EMAIL", "").strip().lower()
    password = os.getenv("ADMIN_PASSWORD", "")
    if not email or not password:
        return
    account = Admin.query.filter_by(email=email).first()
    if account:
        return
    db.session.add(Admin(email=email, password_hash=generate_password_hash(password)))
    db.session.commit()


_LOGIN_HTML = """
<!doctype html><title>Admin login | Gazelle Signals</title>
<style>body{background:#0a0a0a;color:#fff;font:16px Arial;max-width:440px;margin:60px auto;padding:20px}input,button{box-sizing:border-box;width:100%;padding:12px;margin:8px 0;border:0;border-radius:8px}input{background:#1b1b1b;color:#fff}button{background:#00ff88;font-weight:bold}.error{color:#ff7777}</style>
<h1>Administrator login</h1>{% if error %}<p class=error>{{ error }}</p>{% endif %}
<form method=post><input name=email type=email placeholder="Admin email" required autofocus><input name=password type=password placeholder="Password" required><button>Sign in</button></form>
"""

_DASHBOARD_HTML = """
<!doctype html><title>Registrations | Gazelle Signals</title>
<style>body{background:#0a0a0a;color:#fff;font:16px Arial;margin:30px auto;max-width:900px;padding:20px}a{color:#00ff88}table{width:100%;border-collapse:collapse;background:#151515}th,td{text-align:left;padding:12px;border-bottom:1px solid #333}th{color:#00ff88}.vip{color:#00ff88}</style>
<h1>Registered users</h1><p>Signed in as {{ admin.email }} · <a href="{{ url_for('admin.logout') }}">Log out</a></p>
<p>Total registrations: <b>{{ users|length }}</b></p>
<table><tr><th>ID</th><th>Email</th><th>Plan</th></tr>{% for user in users %}<tr><td>{{ user.id }}</td><td>{{ user.email }}</td><td class="{% if user.is_vip %}vip{% endif %}">{{ 'VIP' if user.is_vip else 'FREE' }}</td></tr>{% else %}<tr><td colspan=3>No registrations yet.</td></tr>{% endfor %}</table>
"""
