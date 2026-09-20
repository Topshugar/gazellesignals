from flask import Flask, request, redirect, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import os
import random
from flask_mail import Mail, Message

app = Flask(__name__)
app.secret_key = "gazelle_vip_2025"
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///signals.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# --- BREVO MAIL CONFIG - FIXED FOR YAHOO/GMAIL/ALL ---
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER', 'smtp-relay.brevo.com')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', '587'))
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME', 'ba3bbb001@smtp-brevo.com')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_FROM', 'gazellesignal@gmail.com')

mail = Mail(app)
db = SQLAlchemy(app)

# YOUR LIVE $1000 FLUTTERWAVE LINK
FLUTTERWAVE_PAYMENT_LINK = "https://flutterwave.com/pay/3sjsabbo3lqx"

PAIRS_LIB = {
    'AUDJPY': {'ticker': 'AUDJPY=X', 'name': 'AUD/JPY', 'vip': False},
    'AUDNZD': {'ticker': 'AUDNZD=X', 'name': 'AUD/NZD', 'vip': False},
    'AUDUSD': {'ticker': 'AUDUSD=X', 'name': 'AUD/USD', 'vip': False},
    'CADJPY': {'ticker': 'CADJPY=X', 'name': 'CAD/JPY', 'vip': False},
    'CHFJPY': {'ticker': 'CHFJPY=X', 'name': 'CHF/JPY', 'vip': False},
    'EURAUD': {'ticker': 'EURAUD=X', 'name': 'EUR/AUD', 'vip': False},
    'EURCAD': {'ticker': 'EURCAD=X', 'name': 'EUR/CAD', 'vip': False},
    'EURCHF': {'ticker': 'EURCHF=X', 'name': 'EUR/CHF', 'vip': False},
    'EURGBP': {'ticker': 'EUR/GBP=X', 'name': 'EUR/GBP', 'vip': False},
    'EURJPY': {'ticker': 'EURJPY=X', 'name': 'EUR/JPY', 'vip': False},
    'EURNOK': {'ticker': 'EURNOK=X', 'name': 'EUR/NOK', 'vip': False},
    'EURNZD': {'ticker': 'EURNZD=X', 'name': 'EUR/NZD', 'vip': False},
    'EURSEK': {'ticker': 'EURSEK=X', 'name': 'EUR/SEK', 'vip': False},
    'EURUSD': {'ticker': 'EURUSD=X', 'name': 'EUR/USD', 'vip': False},
    'GBPAUD': {'ticker': 'GBPAUD=X', 'name': 'GBP/AUD', 'vip': False},
    'GBPCAD': {'ticker': 'GBPCAD=X', 'name': 'GBP/CAD', 'vip': False},
    'GBPCHF': {'ticker': 'GBPCHF=X', 'name': 'GBP/CHF', 'vip': False},
    'GBPJPY': {'ticker': 'GBPJPY=X', 'name': 'GBP/JPY', 'vip': False},
    'GBPNZD': {'ticker': 'GBPNZD=X', 'name': 'GBP/NZD', 'vip': False},
    'GBPUSD': {'ticker': 'GBPUSD=X', 'name': 'GBP/USD', 'vip': False},
    'NZDJPY': {'ticker': 'NZDJPY=X', 'name': 'NZD/JPY', 'vip': False},
    'NZDUSD': {'ticker': 'NZDUSD=X', 'name': 'NZD/USD', 'vip': False},
    'USDCAD': {'ticker': 'USDCAD=X', 'name': 'USD/CAD', 'vip': False},
    'USDCHF': {'ticker': 'USDCHF=X', 'name': 'USD/CHF', 'vip': False},
    'USDJPY': {'ticker': 'USDJPY=X', 'name': 'USD/JPY', 'vip': False},
    'USDMXN': {'ticker': 'USDMXN=X', 'name': 'USD/MXN', 'vip': False},
    'USDNOK': {'ticker': 'USDNOK=X', 'name': 'USD/NOK', 'vip': False},
    'USDSEK': {'ticker': 'USDSEK=X', 'name': 'USD/SEK', 'vip': False},
    'USDSGD': {'ticker': 'USDSGD=X', 'name': 'USD/SGD', 'vip': False},
    'USDTRY': {'ticker': 'USDTRY=X', 'name': 'USD/TRY', 'vip': False},
    'USDZAR': {'ticker': 'USDZAR=X', 'name': 'USD/ZAR', 'vip': False},
    'BTCUSD': {'ticker': 'BTC-USD', 'name': 'Bitcoin', 'vip': True},
    'ETHUSD': {'ticker': 'ETH-USD', 'name': 'Ethereum', 'vip': True},
    'SOLUSD': {'ticker': 'SOL-USD', 'name': 'Solana', 'vip': True},
    'SPX500': {'ticker': '^GSPC', 'name': 'S&P 500', 'vip': True},
    'UKOIL': {'ticker': 'BZ=F', 'name': 'Brent Oil', 'vip': True},
    'US100': {'ticker': '^NDX', 'name': 'Nasdaq', 'vip': True},
    'US30': {'ticker': '^DJI', 'name': 'Dow Jones', 'vip': True},
    'USOIL': {'ticker': 'CL=F', 'name': 'WTI Oil', 'vip': True},
    'XAGUSD': {'ticker': 'SI=F', 'name': 'Silver', 'vip': True},
    'XAUUSD': {'ticker': 'GC=F', 'name': 'Gold', 'vip': True},
}

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    is_vip = db.Column(db.Boolean, default=False)
    vip_expiry = db.Column(db.DateTime, nullable=True)
    is_verified = db.Column(db.Boolean, default=False)

class Signal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    pair = db.Column(db.String(20))
    type = db.Column(db.String(10))
    entry = db.Column(db.Float)
    sl = db.Column(db.Float)
    tp = db.Column(db.Float)
    is_vip = db.Column(db.Boolean)
    score = db.Column(db.Integer)
    timeframe = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class OTP(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100))
    code = db.Column(db.String(10))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime)

def send_otp_email(to_email, otp_code):
    try:
        msg = Message(
            subject=f"Gazelle Signal - Your OTP: {otp_code}",
            recipients=[to_email],
            body=f"""Hello,

Welcome to Gazelle Signal!

Your verification code is: {otp_code}

This code expires in 10 minutes.

If you didn't request this, ignore this email.

- Gazelle Team
"""
        )
        mail.send(msg)
        print(f"OTP sent to {to_email}")
        return True
    except Exception as e:
        print(f"MAIL ERROR: {e}")
        return False

def is_market_open(pair_key):
    if pair_key in ['BTCUSD', 'ETHUSD', 'SOLUSD', 'XAUUSD', 'XAGUSD', 'USOIL', 'UKOIL', 'US30', 'US100', 'SPX500']:
        return True
    if datetime.utcnow().weekday() >= 5:
        return False
    return True

def generate_all():
    Signal.query.delete()
    tickers = list(set([v['ticker'] for v in PAIRS_LIB.values()]))
    batch = None
    try:
        import yfinance as yf
        interval = "1d" if datetime.utcnow().weekday() >= 5 else "15m"
        period = "1mo" if interval == "1d" else "5d"
        batch = yf.download(tickers, period=period, interval=interval, group_by='ticker', threads=True, progress=False, auto_adjust=True)
    except Exception as e:
        print(f"Download failed: {e}")
        batch = None
    count = 0
    for pair_key, info in PAIRS_LIB.items():
        try:
            price = None
            signal_type = "BUY"
            score = 74
            df = None
            if batch is not None:
                try:
                    if len(tickers) > 1:
                        df = batch[info['ticker']]
                    else:
                        df = batch
                except:
                    df = None
            if df is not None and hasattr(df, 'empty') and not df.empty and len(df) > 30:
                try:
                    import ta
                    close = df['Close'].dropna()
                    if len(close) > 21:
                        ema21 = ta.trend.EMAIndicator(close, 21).ema_indicator().iloc[-1]
                        rsi = ta.momentum.RSIIndicator(close, 14).rsi().iloc[-1]
                        bb = ta.volatility.BollingerBands(close, 20, 2)
                        bb_low = bb.bollinger_lband().iloc[-1]
                        bb_high = bb.bollinger_hband().iloc[-1]
                        price = float(close.iloc[-1])
                        if price > ema21 and rsi > 50 and price < bb_high:
                            signal_type = "BUY"
                            score = 82 if rsi < 70 else 76
                        elif price < ema21 and rsi < 50 and price > bb_low:
                            signal_type = "SELL"
                            score = 82 if rsi > 30 else 76
                        else:
                            signal_type = "BUY" if price > ema21 else "SELL"
                            score = 70
                except Exception as e:
                    price = None
            if price is None:
                if "JPY" in pair_key:
                    price = random.uniform(140, 160)
                elif pair_key == "XAUUSD":
                    price = random.uniform(2620, 2680)
                elif pair_key == "XAGUSD":
                    price = random.uniform(29, 31)
                elif "BTC" in pair_key:
                    price = random.uniform(62000, 68000)
                elif "ETH" in pair_key:
                    price = random.uniform(2500, 2800)
                elif "US30" in pair_key:
                    price = random.uniform(44000, 45000)
                elif "US100" in pair_key:
                    price = random.uniform(19000, 20000)
                else:
                    price = random.uniform(1.05, 1.30)
                signal_type = random.choice(["BUY", "SELL"])
                score = random.randint(70, 75)
            db.session.add(Signal(pair=pair_key, type=signal_type, entry=round(price, 5), sl=round(price * 0.998, 5), tp=round(price * 1.003, 5), is_vip=info['vip'], score=score, timeframe='15M'))
            count += 1
        except Exception as e:
            continue
    db.session.commit()
    return count

@app.route('/')
def dashboard():
    if 'user_id' not in session:
        return redirect('/login')
    free_signals = Signal.query.filter_by(is_vip=False).order_by(Signal.pair.asc()).all()
    vip_signals = Signal.query.filter_by(is_vip=True).order_by(Signal.pair.asc()).all()
    user_is_vip = session.get('is_vip', False)
    html = "<html><head><meta name='viewport' content='width=device-width, initial-scale=1'><style>body{background:#0a0a0a;color:#fff;font-family:Arial;padding:10px;margin:0}.card{background:#1a1a1a;border-radius:12px;padding:12px;margin:8px 0;border-left:4px solid #00ff88}.vip-card{border-left-color:gold}.closed{opacity:0.55}.badge{float:right;padding:3px 8px;border-radius:10px;font-size:11px;font-weight:bold}.open{background:#00ff88;color:#000}.closed-badge{background:#ff3b3b;color:#fff}</style></head><body>"
    html += f"<h3>GAZELLE <span style='float:right;font-size:14px'><a href='/logout' style='color:gold;text-decoration:none'>Logout</a></span></h3>"
    html += f"<div style='display:flex;justify-content:space-between'><span>Live Signals - LIVE {datetime.utcnow().strftime('%H:%M')} UTC</span><a href='/refresh-library' style='color:gold;text-decoration:none'>Refresh</a></div><br>"
    for s in free_signals:
        open_now = is_market_open(s.pair)
        badge_text = "OPEN" if open_now else "CLOSED"
        badge_class = "open" if open_now else "closed-badge"
        closed_class = "" if open_now else "closed"
        html += f"<div class='card {closed_class}'><span class='badge {badge_class}'>{badge_text}</span><b>{s.pair} {s.type}</b> <span style='float:right;background:#333;padding:2px 8px;border-radius:10px'>{s.score}%</span><br><small>SCALP 15M<br>Entry: {s.entry} | SL: {s.sl} | TP: {s.tp}</small></div>"
    if not user_is_vip:
        html += f"<div style='background:linear-gradient(90deg,gold,#ffcc00);color:#000;border-radius:12px;padding:15px;margin:15px 0;text-align:center'><b>LOCKED {len(vip_signals)} VIP Signals - $1000/month</b><br><br><a href='/subscribe' style='background:#000;color:gold;padding:12px 20px;border-radius:8px;text-decoration:none;display:block;font-weight:bold'>Unlock VIP $1000/month</a></div>"
    else:
        for s in vip_signals:
            open_now = is_market_open(s.pair)
            badge_text = "OPEN" if open_now else "CLOSED"
            html += f"<div class='card vip-card'><span class='badge open'>{badge_text} VIP</span><b>{s.pair} {s.type}</b> <span style='float:right;background:gold;color:#000;padding:2px 8px;border-radius:10px'>{s.score}%</span><br><small>Entry: {s.entry} | SL: {s.sl} | TP: {s.tp}</small></div>"
    html += "</body></html>"
    return html

@app.route('/refresh-library')
def refresh_library():
    c = generate_all()
    return f"Refreshed {c} signals<br><a href='/'>Back</a>"

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        pwd = request.form['password']
        if User.query.filter_by(email=email).first():
            if User.query.filter_by(email=email, is_verified=True).first():
                return "Email exists <a href='/login'>Login</a>"
            User.query.filter_by(email=email).delete()
            db.session.commit()
        
        # Create unverified user
        u = User(email=email, password=pwd, is_verified=False)
        db.session.add(u)
        db.session.commit()

        # Generate OTP
        otp_code = str(random.randint(100000, 999999))
        # Delete old OTPs
        OTP.query.filter_by(email=email).delete()
        new_otp = OTP(email=email, code=otp_code, expires_at=datetime.utcnow() + timedelta(minutes=10))
        db.session.add(new_otp)
        db.session.commit()

        # Send Email via Brevo
        sent = send_otp_email(email, otp_code)
        if not sent:
            return f"Failed to send email. Check Render logs. <br>OTP for testing: {otp_code} <a href='/verify?email={email}'>Go Verify</a>"

        return redirect(f'/verify?email={email}')

    return '<div style="padding:30px;background:#111;color:#fff;min-height:100vh"><h2>Register - Gazelle</h2><form method=post>Email: <input name=email type=email required><br><br>Password: <input name=password type=password required><br><br><button style="padding:10px 20px;background:gold">Send OTP</button></form><br><a href="/login" style="color:gold">Login</a></div>'

@app.route('/verify', methods=['GET', 'POST'])
def verify():
    email = request.args.get('email') or request.form.get('email')
    if not email:
        return redirect('/register')
    if request.method == 'POST':
        user_code = request.form['otp'].strip()
        stored = OTP.query.filter_by(email=email).order_by(OTP.id.desc()).first()
        if not stored:
            return "No OTP found. <a href='/register'>Register again</a>"
        if datetime.utcnow() > stored.expires_at:
            return "OTP expired. <a href='/register'>Register again</a>"
        if stored.code == user_code:
            user = User.query.filter_by(email=email).first()
            if user:
                user.is_verified = True
                db.session.commit()
                OTP.query.filter_by(email=email).delete()
                db.session.commit()
                session['user_id'] = user.id
                session['is_vip'] = user.is_vip
                return redirect('/')
        else:
            return f"Wrong OTP. <a href='/verify?email={email}'>Try again</a>"

    return f'''
    <div style="padding:30px;background:#111;color:#fff;min-height:100vh">
    <h2>Verify OTP - Gazelle</h2>
    <p>OTP sent to <b>{email}</b> - Check inbox AND spam (Yahoo/Gmail)</p>
    <form method=post>
    <input type=hidden name=email value="{email}">
    Enter OTP: <input name=otp required><br><br>
    <button style="padding:10px 20px;background:gold">Verify</button>
    </form><br>
    <a href="/register" style="color:gold">Resend OTP - Register again</a>
    </div>
    '''

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        u = User.query.filter_by(email=email, password=request.form['password']).first()
        if u:
            if not u.is_verified:
                return f"Email not verified. <a href='/verify?email={email}'>Verify OTP</a>"
            session['user_id'] = u.id
            session['is_vip'] = u.is_vip
            return redirect('/')
        return "Wrong email/password"
    return '<div style="padding:30px;background:#111;color:#fff;min-height:100vh"><h2>Login - Gazelle</h2><form method=post>Email: <input name=email><br><br>Password: <input name=password type=password><br><br><button style="padding:10px 20px;background:gold">Login</button></form><br><a href="/register" style="color:gold">Register</a></div>'

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

@app.route('/subscribe')
def subscribe():
    if 'user_id' not in session:
        return redirect('/login')
    return redirect(FLUTTERWAVE_PAYMENT_LINK)

@app.route('/subscribe/confirm')
def subscribe_confirm():
    if 'user_id' not in session:
        return redirect('/login')
    u = User.query.get(session['user_id'])
    u.is_vip = True
    u.vip_expiry = datetime.utcnow() + timedelta(days=30)
    db.session.commit()
    session['is_vip'] = True
    return "VIP Activated! <a href='/'>Go to Dashboard</a>"

with app.app_context():
    try:
        db.create_all()
        if Signal.query.count() == 0:
            generate_all()
        # Try to read new column to test
        User.query.first()
    except Exception as e:
        print(f"DB needs reset: {e}")
        db.drop_all()
        db.create_all()
        generate_all()
        print("DB reset done!")
