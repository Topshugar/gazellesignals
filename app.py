import os
from dotenv import load_dotenv
load_dotenv()
from flask import Flask, render_template, request, redirect, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'gazelle-secret-2024'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///gazelle.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Flutterwave Public Key from env
FLW_PUBK = os.getenv("FLW_PUBLIC_KEY")

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    tier = db.Column(db.String(10), default='FREE')
    telegram_id = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Signal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    pair = db.Column(db.String(20), nullable=False)
    type = db.Column(db.String(10), nullable=False)
    entry = db.Column(db.Float, nullable=False)
    sl = db.Column(db.Float, nullable=False)
    tp = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(10), default='forex')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

with app.app_context():
    db.create_all()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        if User.query.filter_by(email=email).first():
            return 'Email exists <a href="/login">Login</a>'
        new_user = User(
            email=email,
            password_hash=generate_password_hash(password),
            tier='FREE'
        )
        db.session.add(new_user)
        db.session.commit()
        session['user_id'] = new_user.id
        return redirect('/dashboard')
    return render_template('index.html', mode='register')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            return redirect('/dashboard')
        return 'Invalid login'
    return render_template('index.html', mode='login')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

@app.route('/dashboard')
def dashboard():
    user_id = session.get('user_id')
    if not user_id:
        return redirect('/login')
    user = User.query.get(user_id)
    signals = Signal.query.order_by(Signal.created_at.desc()).limit(20).all()
    free_signals = [s for s in signals if s.category == 'forex']
    vip_signals = signals
    show_signals = vip_signals if user.tier == 'VIP' else free_signals
    return render_template('dashboard.html',
                           user=user,
                           signals=show_signals,
                           all_signals=signals,
                           flw_pubk=FLW_PUBK)

@app.route('/upgrade')
def upgrade_page():
    user_id = session.get('user_id')
    if not user_id:
        return redirect('/login')
    user = User.query.get(user_id)
    return render_template('dashboard.html', user=user, upgrade_mode=True, flw_pubk=FLW_PUBK)

@app.route('/verify-payment', methods=['POST'])
def verify_payment():
    user_id = session.get('user_id')
    if not user_id:
        return {'status': 'error'}
    user = User.query.get(user_id)
    user.tier = 'VIP'
    db.session.commit()
    return {'status': 'success', 'tier': 'VIP'}
