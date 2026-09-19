import os
from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'gazelle-signals-2026-secret'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///gazelle.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# FLUTTERWAVE PUBK - safe for frontend
FLW_PUBK = "FLWPUBK-680c2f65a0795c23ac1ad8f6aabe4e4c-X"
VIP_PRICE = 10

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    tier = db.Column(db.String(10), default='FREE')
    telegram_id = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Signal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    pair = db.Column(db.String(20), nullable=False)
    type = db.Column(db.String(10), nullable=False)
    entry = db.Column(db.String(20))
    sl = db.Column(db.String(20))
    tp = db.Column(db.String(20))
    category = db.Column(db.String(20), default='forex')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    amount = db.Column(db.Float, default=10.0)
    status = db.Column(db.String(20), default='PENDING')
    reference = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

with app.app_context():
    db.create_all()

@app.route('/')
def index():
    return render_template('index.html', pubk=FLW_PUBK)

if __name__ == '__main__':
    app.run(debug=True)
import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from functools import wraps

app = Flask(__name__)
app.config['SECRET_KEY'] = 'gazelle-signals-2026-secret'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///gazelle.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

FLW_PUBK = "FLWPUBK-680c2f65a0795c23ac1ad8f6aabe4e4c-X"
VIP_PRICE = 10
ADMIN_EMAIL = "admin@gazelle.com"

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    tier = db.Column(db.String(10), default='FREE')
    telegram_id = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Signal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    pair = db.Column(db.String(20), nullable=False)
    type = db.Column(db.String(10), nullable=False)
    entry = db.Column(db.String(20))
    sl = db.Column(db.String(20))
    tp = db.Column(db.String(20))
    category = db.Column(db.String(20), default='forex')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    amount = db.Column(db.Float, default=10.0)
    status = db.Column(db.String(20), default='PENDING')
    reference = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

with app.app_context():
    db.create_all()

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html', pubk=FLW_PUBK)

@app.route('/register', methods=['POST'])
def register():
    email = request.form.get('email')
    password = request.form.get('password')
    if User.query.filter_by(email=email).first():
        flash('Email exists')
        return redirect(url_for('index'))
    hashed = generate_password_hash(password)
    user = User(email=email, password_hash=hashed)
    db.session.add(user)
    db.session.commit()
    session['user_id'] = user.id
    session['email'] = user.email
    session['tier'] = user.tier
    return redirect(url_for('dashboard'))

@app.route('/login', methods=['POST'])
def login():
    email = request.form.get('email')
    password = request.form.get('password')
    user = User.query.filter_by(email=email).first()
    if user and check_password_hash(user.password_hash, password):
        session['user_id'] = user.id
        session['email'] = user.email
        session['tier'] = user.tier
        return redirect(url_for('dashboard'))
    flash('Invalid login')
    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    signals = Signal.query.order_by(Signal.created_at.desc()).limit(20).all()
    user = User.query.get(session['user_id'])
    return render_template('dashboard.html', signals=signals, user=user, pubk=FLW_PUBK)

if __name__ == '__main__':
    app.run(debug=True) 
import os
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from functools import wraps
import secrets

app = Flask(__name__)
app.config['SECRET_KEY'] = 'gazelle-signals-2026-secret'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///gazelle.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

FLW_PUBK = "FLWPUBK-680c2f65a0795c23ac1ad8f6aabe4e4c-X"
VIP_PRICE = 10
ADMIN_EMAIL = "admin@gazelle.com"

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    tier = db.Column(db.String(10), default='FREE')
    telegram_id = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Signal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    pair = db.Column(db.String(20), nullable=False)
    type = db.Column(db.String(10), nullable=False)
    entry = db.Column(db.String(20))
    sl = db.Column(db.String(20))
    tp = db.Column(db.String(20))
    category = db.Column(db.String(20), default='forex')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    amount = db.Column(db.Float, default=10.0)
    status = db.Column(db.String(20), default='PENDING')
    reference = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

with app.app_context():
    db.create_all()

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html', pubk=FLW_PUBK)

@app.route('/register', methods=['POST'])
def register():
    email = request.form.get('email')
    password = request.form.get('password')
    if User.query.filter_by(email=email).first():
        flash('Email exists')
        return redirect(url_for('index'))
    hashed = generate_password_hash(password)
    user = User(email=email, password_hash=hashed)
    db.session.add(user)
    db.session.commit()
    session['user_id'] = user.id
    session['email'] = user.email
    session['tier'] = user.tier
    return redirect(url_for('dashboard'))

@app.route('/login', methods=['POST'])
def login():
    email = request.form.get('email')
    password = request.form.get('password')
    user = User.query.filter_by(email=email).first()
    if user and check_password_hash(user.password_hash, password):
        session['user_id'] = user.id
        session['email'] = user.email
        session['tier'] = user.tier
        return redirect(url_for('dashboard'))
    flash('Invalid login')
    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    signals = Signal.query.order_by(Signal.created_at.desc()).limit(20).all()
    user = User.query.get(session['user_id'])
    return render_template('dashboard.html', signals=signals, user=user, pubk=FLW_PUBK)

@app.route('/pay')
@login_required
def pay():
    user = User.query.get(session['user_id'])
    return render_template('index.html', pubk=FLW_PUBK, show_pay=True, user=user)

@app.route('/verify_payment', methods=['POST'])
@login_required
def verify_payment():
    reference = request.form.get('reference')
    user_id = session['user_id']
    existing = Payment.query.filter_by(reference=reference).first()
    if existing:
        flash('Reference already used')
        return redirect(url_for('dashboard'))
    payment = Payment(user_id=user_id, reference=reference, status='PENDING', amount=VIP_PRICE)
    db.session.add(payment)
    db.session.commit()
    flash('Payment submitted - admin will verify')
    return redirect(url_for('dashboard'))

@app.route('/telegram', methods=['POST'])
@login_required
def telegram():
    tid = request.form.get('telegram_id')
    user = User.query.get(session['user_id'])
    user.telegram_id = tid
    db.session.commit()
    flash('Telegram saved')
    return redirect(url_for('dashboard'))

@app.route('/admin')
@login_required
def admin():
    user = User.query.get(session['user_id'])
    if user.email != ADMIN_EMAIL:
        return redirect(url_for('dashboard'))
    payments = Payment.query.filter_by(status='PENDING').all()
    users = User.query.all()
    return render_template('dashboard.html', signals=[], user=user, payments=payments, users=users, is_admin=True, pubk=FLW_PUBK)

@app.route('/admin/approve/<int:pid>')
@login_required
def approve(pid):
    user = User.query.get(session['user_id'])
    if user.email != ADMIN_EMAIL:
        return redirect(url_for('dashboard'))
    payment = Payment.query.get(pid)
    if payment:
        payment.status = 'APPROVED'
        u = User.query.get(payment.user_id)
        u.tier = 'VIP'
        db.session.commit()
    return redirect(url_for('admin'))

@app.route('/api/signals')
@login_required
def api_signals():
    signals = Signal.query.order_by(Signal.created_at.desc()).limit(30).all()
    data = []
    for s in signals:
        data.append({
            'pair': s.pair,
            'type': s.type,
            'entry': s.entry,
            'sl': s.sl,
            'tp': s.tp,
            'category': s.category,
            'time': s.created_at.strftime('%H:%M')
        })
    return jsonify(data)

if __name__ == '__main__':
    app.run(debug=True)
