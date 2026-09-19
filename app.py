import os
from dotenv import load_dotenv
load_dotenv()
from flask import Flask, render_template, request, redirect, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import yfinance as yf
import pandas as pd
from apscheduler.schedulers.background import BackgroundScheduler

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
    is_vip = db.Column(db.Boolean, default=False)
    status = db.Column(db.String(20), default='active')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

with app.app_context():
    db.create_all()

# ===== YOUR STRATEGY ENGINE: RSI + BB + EMA + Alligator + MACD + Stoch =====
PAIRS = {
    'EURUSD': 'EURUSD=X',
    'GBPUSD': 'GBPUSD=X',
    'USDJPY': 'JPY=X',
    'XAUUSD': 'GC=F',
    'BTCUSD': 'BTC-USD'
}

def calc_indicators(df):
    close = df['Close']
    df['EMA50'] = close.ewm(span=50).mean()
    df['EMA200'] = close.ewm(span=200).mean()
    delta = close.diff()
    gain = delta.where(delta>0,0).rolling(14).mean()
    loss = -delta.where(delta<0,0).rolling(14).mean()
    rs = gain/loss
    df['RSI'] = 100 - (100/(1+rs))
    df['BB_MA'] = close.rolling(20).mean()
    df['BB_STD'] = close.rolling(20).std()
    df['BB_UP'] = df['BB_MA'] + 2*df['BB_STD']
    df['BB_LOW'] = df['BB_MA'] - 2*df['BB_STD']
    ema12 = close.ewm(span=12).mean()
    ema26 = close.ewm(span=26).mean()
    df['MACD'] = ema12 - ema26
    df['MACD_SIG'] = df['MACD'].ewm(span=9).mean()
    low14 = df['Low'].rolling(14).min()
    high14 = df['High'].rolling(14).max()
    df['%K'] = (close - low14)/(high14-low14)*100
    df['%D'] = df['%K'].rolling(3).mean()
    df['JAW'] = close.ewm(span=13).mean().shift(8)
    df['TEETH'] = close.ewm(span=8).mean().shift(5)
    df['LIPS'] = close.ewm(span=5).mean().shift(3)
    return df

def generate_signal():
    signals = []
    for pair, yf_symbol in PAIRS.items():
        try:
            df = yf.download(yf_symbol, period='2mo', interval='1h', progress=False)
            if df.empty or len(df) < 200: continue
            df = calc_indicators(df)
            last = df.iloc[-1]
            score = 0
            if last['EMA50'] > last['EMA200']: score += 1
            else: score -= 1
            if last['RSI'] > 55: score += 1
            elif last['RSI'] < 45: score -= 1
            if last['MACD'] > last['MACD_SIG']: score += 1
            else: score -= 1
            if last['%K'] > last['%D']: score += 1
            else: score -= 1
            if last['LIPS'] > last['TEETH'] > last['JAW']: score += 1
            elif last['LIPS'] < last['TEETH'] < last['JAW']: score -= 1

            if abs(score) < 2: continue
            direction = 'BUY' if score > 0 else 'SELL'
            entry = float(last['Close'].iloc[0] if hasattr(last['Close'], 'iloc') else last['Close'])
            sl = float(last['BB_LOW'])
            tp = float(last['BB_UP'])

            signals.append({
                'pair': pair,
                'type': direction,
                'entry': round(entry, 5),
                'tp': round(tp, 5) if pair!= 'XAUUSD' else round(tp, 2),
                'sl': round(sl, 5) if pair!= 'XAUUSD' else round(sl, 2),
                'is_vip': True if abs(score) >= 3 else False,
            })
        except Exception as e:
            print(f"Error {pair}: {e}")
            continue
    return signals

def auto_create_signals():
    with app.app_context():
        new_signals = generate_signal()
        count = 0
        for s in new_signals:
            exists = Signal.query.filter_by(pair=s['pair'], status='active').first()
            if not exists:
                sig = Signal(pair=s['pair'], type=s['type'], entry=s['entry'], sl=s['sl'], tp=s['tp'], category='forex', is_vip=s['is_vip'], status='active')
                db.session.add(sig)
                count += 1
        if count > 0:
            db.session.commit()
        print(f"[{datetime.utcnow()}] Generated {count} new signals")

# Scheduler - runs every 5 mins
scheduler = BackgroundScheduler()
scheduler.add_job(func=auto_create_signals, trigger="interval", minutes=5)
scheduler.start()

# Run once on startup
try:
    auto_create_signals()
except:
    pass

# ===== ROUTES =====
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
        new_user = User(email=email, password_hash=generate_password_hash(password), tier='FREE')
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
    signals = Signal.query.filter_by(status='active').order_by(Signal.created_at.desc()).limit(20).all()
    # FREE users see only is_vip=False, VIP sees all
    if user.tier == 'VIP':
        show_signals = signals
    else:
        show_signals = [s for s in signals if not s.is_vip]
        if not show_signals: # if no free, show at least 1 as demo
            show_signals = signals[:3]
    return render_template('dashboard.html', user=user, signals=show_signals, all_signals=signals, flw_pubk=FLW_PUBK)

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
        return jsonify({'status': 'error'})
    user = User.query.get(user_id)
    user.tier = 'VIP'
    db.session.commit()
    return jsonify({'status': 'success', 'tier': 'VIP'})

@app.route('/seed-free')
def seed_free():
    # Manual trigger to force signals now
    auto_create_signals()
    return redirect('/dashboard')

if __name__ == '__main__':
    app.run(debug=True)
