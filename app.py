import os
from flask import Flask, render_template, request, redirect, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'gazelle-secret-real-2024-production')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///gazelle.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

FLW_PUBK = os.getenv("FLW_PUBLIC_KEY", "FLWPUBK_TEST-123")

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    tier = db.Column(db.String(10), default='FREE')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Signal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    pair = db.Column(db.String(20), nullable=False)
    type = db.Column(db.String(10), nullable=False)
    entry = db.Column(db.Float, nullable=False)
    sl = db.Column(db.Float, nullable=False)
    tp = db.Column(db.Float, nullable=False)
    is_vip = db.Column(db.Boolean, default=False)
    status = db.Column(db.String(20), default='active')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

with app.app_context():
    db.create_all()
    if Signal.query.count() == 0:
        demo = [
            ('EURUSD', 'BUY', 1.0845, 1.0820, 1.0890, False),
            ('GBPUSD', 'SELL', 1.2720, 1.2750, 1.2670, False),
            ('USDJPY', 'BUY', 149.80, 149.30, 150.60, False),
            ('XAUUSD', 'BUY', 2025.50, 2015.00, 2045.00, True),
            ('BTCUSD', 'SELL', 43200, 43800, 42100, True),
        ]
        for p,t,e,sl,tp,vip in demo:
            db.session.add(Signal(pair=p, type=t, entry=e, sl=sl, tp=tp, is_vip=vip, status='active'))
        db.session.commit()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        try:
            email = request.form.get('email','').strip().lower()
            password = request.form.get('password','')
            if not email or not password:
                return 'Email and password required <a href="/register">Back</a>'
            if User.query.filter_by(email=email).first():
                return 'Email exists <a href="/login">Login</a>'
            u = User(email=email, password_hash=generate_password_hash(password), tier='FREE')
            db.session.add(u)
            db.session.commit()
            session['user_id'] = u.id
            return redirect('/dashboard')
        except Exception as e:
            return f"Register Error: {str(e)} - <a href='/register'>Try again</a>"
    return render_template('index.html', mode='register')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        try:
            email = request.form.get('email','').strip().lower()
            password = request.form.get('password','')
            u = User.query.filter_by(email=email).first()
            if u and check_password_hash(u.password_hash, password):
                session['user_id'] = u.id
                return redirect('/dashboard')
            return 'Invalid login <a href="/login">Back</a>'
        except Exception as e:
            return f"Login Error: {str(e)}"
    return render_template('index.html', mode='login')

@app.route('/dashboard')
def dashboard():
    uid = session.get('user_id')
    if not uid:
        return redirect('/login')
    user = User.query.get(uid)
    if not user:
        session.clear()
        return redirect('/login')
    signals = Signal.query.filter_by(status='active').all()
    show = signals if user.tier=='VIP' else [s for s in signals if not s.is_vip]
    return render_template('dashboard.html', user=user, signals=show, all_signals=signals, flw_pubk=FLW_PUBK, upgrade_mode=False)

@app.route('/upgrade')
def upgrade_page():
    uid = session.get('user_id')
    if not uid: return redirect('/login')
    user = User.query.get(uid)
    return render_template('dashboard.html', user=user, signals=[], all_signals=Signal.query.all(), flw_pubk=FLW_PUBK, upgrade_mode=True)

@app.route('/verify-payment', methods=['POST'])
def verify_payment():
    uid = session.get('user_id')
    if not uid: return jsonify({'status':'error'})
    u = User.query.get(uid)
    u.tier = 'VIP'
    db.session.commit()
    return jsonify({'status':'success'})

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

if __name__ == '__main__':
    app.run(debug=True)
