import os, math
from flask import Flask, request, redirect, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta

# Safe imports - won't crash if not installed yet
try:
    import yfinance as yf
    import pandas as pd
    import numpy as np
    HAS_YF = True
except:
    HAS_YF = False

app = Flask(__name__)
app.secret_key = 'gazelle-real-2024'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///gazelle.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True)
    password_hash = db.Column(db.String(200))
    tier = db.Column(db.String(10), default='FREE')

class Signal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    pair = db.Column(db.String(20))
    type = db.Column(db.String(10))
    entry = db.Column(db.Float)
    sl = db.Column(db.Float)
    tp = db.Column(db.Float)
    is_vip = db.Column(db.Boolean, default=False)
    score = db.Column(db.Integer, default=70)
    timeframe = db.Column(db.String(20), default='SCALP 15M')
    status = db.Column(db.String(20), default='active')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

with app.app_context():
    db.create_all()

# ===== REAL STRATEGY =====
def rsi(series, period=14):
    delta = series.diff()
    gain = delta.where(delta>0,0).rolling(period).mean()
    loss = -delta.where(delta<0,0).rolling(period).mean()
    rs = gain / loss
    return 100 - (100/(1+rs))

def calculate_signals(df):
    try:
        df['EMA9'] = df['Close'].ewm(span=9).mean()
        df['EMA21'] = df['Close'].ewm(span=21).mean()
        df['EMA50'] = df['Close'].ewm(span=50).mean()
        df['EMA200'] = df['Close'].ewm(span=200).mean()
        df['RSI'] = rsi(df['Close'])
        # BB
        df['BB_MA'] = df['Close'].rolling(20).mean()
        df['BB_STD'] = df['Close'].rolling(20).std()
        df['BB_UP'] = df['BB_MA'] + 2*df['BB_STD']
        df['BB_LOW'] = df['BB_MA'] - 2*df['BB_STD']
        # Alligator simplified (SMMA)
        df['JAW'] = df['Close'].rolling(13).mean().shift(8)
        df['TEETH'] = df['Close'].rolling(8).mean().shift(5)
        df['LIPS'] = df['Close'].rolling(5).mean().shift(3)
        return df
    except:
        return df

def get_live_signal(ticker, pair_name):
    if not HAS_YF: return None
    try:
        df = yf.download(ticker, period='5d', interval='15m', progress=False)
        if len(df) < 210: return None
        df = calculate_signals(df)
        last = df.iloc[-1]
        prev = df.iloc[-2]
        price = float(last['Close'])

        # SWING FILTER
        swing_bull = price > last['EMA200']
        swing_bear = price < last['EMA200']
        
        # DAY FILTER
        day_bull = last['EMA21'] > last['EMA50']
        day_bear = last['EMA21'] < last['EMA50']

        # SCALP TRIGGER
        rsi_val = float(last['RSI'])
        score = 50
        
        buy_cond = 0
        sell_cond = 0

        if last['EMA9'] > last['EMA21']: buy_cond+=1; score+=10
        if last['Close'] > last['BB_MA']: buy_cond+=1
        if rsi_val > 45 and rsi_val < 68: buy_cond+=1; score+=15
        if last['LIPS'] > last['TEETH']: buy_cond+=1; score+=10

        if last['EMA9'] < last['EMA21']: sell_cond+=1; score+=10
        if last['Close'] < last['BB_MA']: sell_cond+=1
        if rsi_val < 55 and rsi_val > 32: sell_cond+=1; score+=15
        if last['LIPS'] < last['TEETH']: sell_cond+=1; score+=10

        if swing_bull and day_bull and buy_cond >=3:
            sl = price * 0.997 if 'JPY' not in pair_name else price * 0.998
            tp = price * 1.004
            return {'pair':pair_name, 'type':'BUY', 'entry':round(price,5), 'sl':round(sl,5), 'tp':round(tp,5), 'score':min(score+10,92), 'tf':'SCALP 15M BUY'}
        
        if swing_bear and day_bear and sell_cond >=3:
            sl = price * 1.003 if 'JPY' not in pair_name else price * 1.002
            tp = price * 0.996
            return {'pair':pair_name, 'type':'SELL', 'entry':round(price,5), 'sl':round(sl,5), 'tp':round(tp,5), 'score':min(score+10,92), 'tf':'SCALP 15M SELL'}

        return None
    except Exception as e:
        print(f"Error {pair_name}: {e}")
        return None

PAIRS_LIB = {
    # ===== FREE FOREX - MAJORS (7) =====
    'EURUSD': {'ticker':'EURUSD=X', 'name':'Euro / US Dollar', 'cat':'Forex Major', 'vip':False, 'icon':'€$'},
    'GBPUSD': {'ticker':'GBPUSD=X', 'name':'British Pound / Dollar', 'cat':'Forex Major', 'vip':False, 'icon':'£$'},
    'USDJPY': {'ticker':'USDJPY=X', 'name':'Dollar / Japanese Yen', 'cat':'Forex Major', 'vip':False, 'icon':'$¥'},
    'AUDUSD': {'ticker':'AUDUSD=X', 'name':'Aussie / Dollar', 'cat':'Forex Major', 'vip':False, 'icon':'A$'},
    'USDCAD': {'ticker':'USDCAD=X', 'name':'Dollar / Canadian', 'cat':'Forex Major', 'vip':False, 'icon':'$C'},
    'NZDUSD': {'ticker':'NZDUSD=X', 'name':'NZD / Dollar', 'cat':'Forex Major', 'vip':False, 'icon':'N$'},
    'USDCHF': {'ticker':'USDCHF=X', 'name':'Dollar / Swiss Franc', 'cat':'Forex Major', 'vip':False, 'icon':'$F'},

    # ===== FREE FOREX - MINORS / CROSSES (10) =====
    'EURGBP': {'ticker':'EURGBP=X', 'name':'Euro / Pound', 'cat':'Forex Cross', 'vip':False, 'icon':'€£'},
    'EURJPY': {'ticker':'EURJPY=X', 'name':'Euro / Yen', 'cat':'Forex Cross', 'vip':False, 'icon':'€¥'},
    'GBPJPY': {'ticker':'GBPJPY=X', 'name':'Pound / Yen', 'cat':'Forex Cross', 'vip':False, 'icon':'£¥'},
    'AUDJPY': {'ticker':'AUDJPY=X', 'name':'Aussie / Yen', 'cat':'Forex Cross', 'vip':False, 'icon':'A¥'},
    'EURCAD': {'ticker':'EURCAD=X', 'name':'Euro / Canadian', 'cat':'Forex Cross', 'vip':False, 'icon':'€C'},
    'GBPCAD': {'ticker':'GBPCAD=X', 'name':'Pound / Canadian', 'cat':'Forex Cross', 'vip':False, 'icon':'£C'},
    'AUDCAD': {'ticker':'AUDCAD=X', 'name':'Aussie / Canadian', 'cat':'Forex Cross', 'vip':False, 'icon':'AC'},
    'EURAUD': {'ticker':'EURAUD=X', 'name':'Euro / Aussie', 'cat':'Forex Cross', 'vip':False, 'icon':'€A'},
    'GBPAUD': {'ticker':'GBPAUD=X', 'name':'Pound / Aussie', 'cat':'Forex Cross', 'vip':False, 'icon':'£A'},
    'CADJPY': {'ticker':'CADJPY=X', 'name':'Canadian / Yen', 'cat':'Forex Cross', 'vip':False, 'icon':'C¥'},

    # ===== VIP - NON FOREX ($1000) =====
    'XAUUSD': {'ticker':'GC=F', 'name':'Gold / Dollar', 'cat':'Metals', 'vip':True, 'icon':'🥇'},
    'XAGUSD': {'ticker':'SI=F', 'name':'Silver / Dollar', 'cat':'Metals', 'vip':True, 'icon':'🥈'},
    'BTCUSD': {'ticker':'BTC-USD', 'name':'Bitcoin / Dollar', 'cat':'Crypto', 'vip':True, 'icon':'₿'},
    'ETHUSD': {'ticker':'ETH-USD', 'name':'Ethereum / Dollar', 'cat':'Crypto', 'vip':True, 'icon':'Ξ'},
    'SOLUSD': {'ticker':'SOL-USD', 'name':'Solana / Dollar', 'cat':'Crypto', 'vip':True, 'icon':'◎'},
    'US30': {'ticker':'^DJI', 'name':'Dow Jones 30', 'cat':'Indices', 'vip':True, 'icon':'🇺🇸'},
    'NAS100': {'ticker':'^IXIC', 'name':'NASDAQ 100', 'cat':'Indices', 'vip':True, 'icon':'💻'},
    'SPX500': {'ticker':'^GSPC', 'name':'S&P 500', 'cat':'Indices', 'vip':True, 'icon':'📊'},
    'USOIL': {'ticker':'CL=F', 'name':'Crude Oil', 'cat':'Energy', 'vip':True, 'icon':'🛢️'},
}

VIP_PRICE = 1000

def generate_all():
    with app.app_context():
        # clear old active
        Signal.query.filter_by(status='active').delete()
        count=0
        for name,ticker in PAIRS.items():
            sig = get_live_signal(ticker, name)
            if sig:
                is_vip = name in ['XAUUSD','BTCUSD']
                db.session.add(Signal(pair=sig['pair'], type=sig['type'], entry=sig['entry'], sl=sig['sl'], tp=sig['tp'], is_vip=is_vip, score=sig['score'], timeframe=sig['tf']))
                count+=1
        # fallback demo if yfinance fails
        if count==0:
    db.session.add(Signal(pair='EURUSD', type='BUY', entry=1.0845, sl=1.082, tp=1.089, is_vip=False, score=74, timeframe='SCALP 15M'))
    db.session.add(Signal(pair='BTCUSD', type='BUY', entry=65000, sl=64000, tp=67000, is_vip=True, score=88, timeframe='SCALP 15M'))
             db.session.commit()

def page(body):
    return f"<!DOCTYPE html><html><head><meta name='viewport' content='width=device-width, initial-scale=1'><style>body{{background:#0e0e0e;color:#fff;font-family:Arial;padding:20px;max-width:600px;margin:0 auto}}input{{width:100%;padding:14px;margin:8px 0;border-radius:10px;border:1px solid #333;background:#1c1c1e;color:#fff;box-sizing:border-box}}button{{width:100%;padding:14px;background:#FFD700;border:0;border-radius:10px;font-weight:800;cursor:pointer}} .card{{background:#1c1c1e;border:1px solid #333;border-radius:16px;padding:14px;margin:12px 0}} .vip{{border-color:#FFD700}} a{{color:#FFD700}} .badge{{background:#FFD700;color:#000;padding:3px 8px;border-radius:20px;font-size:11px;font-weight:800}}</style></head><body>{body}</body></html>"

@app.route('/')
def home():
    return page("<h1>GAZELLE SIGNALS</h1><p>Real Strategy: Swing > Day > Scalp (EMA+RSI+BB+Alligator)</p><a href='/register'><button>Create Free Account</button></a><br><br><center><a href='/login'>Login</a> | <a href='/health'>Status</a></center>")

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method=='POST':
        email=request.form.get('email','').lower().strip()
        pw=request.form.get('password','')
        if not email or not pw: return page("Fill all <a href='/register'>Back</a>")
        if User.query.filter_by(email=email).first():
            return page("Email exists <a href='/login'>Login</a>")
        u=User(email=email,password_hash=generate_password_hash(pw))
        db.session.add(u); db.session.commit()
        session['user_id']=u.id
        return redirect('/dashboard')
    return page("<h2>Create Account</h2><form method='POST'><input name='email' placeholder='Email' required><input name='password' type='password' placeholder='Password' required><button>Create Account</button></form><p><a href='/login'>Login</a></p>")

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method=='POST':
        email=request.form.get('email','').lower().strip()
        u=User.query.filter_by(email=email).first()
        if u and check_password_hash(u.password_hash, request.form.get('password','')):
            session['user_id']=u.id
            return redirect('/dashboard')
        return page("Invalid login <a href='/login'>Try again</a>")
    return page("<h2>Login</h2><form method='POST'><input name='email' placeholder='Email'><input name='password' type='password' placeholder='Password'><button>Login</button></form>")

@app.route('/dashboard')
def dashboard():
    uid=session.get('user_id')
    if not uid: return redirect('/login')
    u=User.query.get(uid)
    # auto generate if older than 30 mins
    last_sig = Signal.query.order_by(Signal.created_at.desc()).first()
    if not last_sig or (datetime.utcnow() - last_sig.created_at) > timedelta(minutes=30):
        try:
            generate_all()
        except: pass

    sigs=Signal.query.filter_by(status='active').all()
    free=[s for s in sigs if not s.is_vip]
    html=f"<div style='display:flex;justify-content:space-between'><b>GAZELLE</b><span>{u.tier} | <a href='/logout'>Logout</a></span></div><h3>Live Signals ● LIVE {datetime.utcnow().strftime('%H:%M UTC')}</h3><p><a href='/refresh'>↻ Refresh Signals</a></p>"
    for s in free:
        html+=f"<div class='card'><div style='display:flex;justify-content:space-between'><b>{s.pair} {s.type}</b><span class='badge'>{s.score}%</span></div><small>{s.timeframe}</small><br>Entry: {s.entry} | SL: {s.sl} | TP: {s.tp}<br><small>Strategy: Swing {'>'} Day {'>'} Scalp</small></div>"
    if u.tier!='VIP':
        vip_locked = [s for s in sigs if s.is_vip]
        html+=f"<div style='background:gold;color:#000;padding:15px;border-radius:12px;text-align:center;margin-top:20px'><b>🔒 {len(vip_locked)} VIP Signals Locked (Gold & BTC)</b><br><small>Real RSI+BB+EMA strategy</small><br><a href='/upgrade'><button style='background:#000;color:gold;margin-top:10px'>Unlock VIP $29</button></a></div>"
    else:
        for s in [s for s in sigs if s.is_vip]:
            html+=f"<div class='card vip'><div style='display:flex;justify-content:space-between'><b>{s.pair} {s.type} VIP</b><span class='badge'>{s.score}%</span></div><small>{s.timeframe}</small><br>Entry: {s.entry} | SL: {s.sl} | TP: {s.tp}</div>"
    return page(html)

@app.route('/refresh')
def refresh():
    if not session.get('user_id'): return redirect('/login')
    generate_all()
    return redirect('/dashboard')

@app.route('/upgrade')
def upgrade():
    return page("<h2>VIP $29/mo</h2><p>Unlock XAUUSD + BTCUSD with REAL strategy</p><button onclick=\"fetch('/verify-payment',{method:'POST'}).then(()=>location='/dashboard')\">Pay with Flutterwave (Test)</button><p><small>Flutterwave will be added here</small></p>")

@app.route('/verify-payment', methods=['POST'])
def verify():
    u=User.query.get(session.get('user_id')); u.tier='VIP'; db.session.commit()
    return jsonify({"status":"success"})

@app.route('/health')
def health():
    return jsonify({"yfinance":HAS_YF, "signals":Signal.query.count(), "users":User.query.count()})

@app.route('/logout')
def logout():
    session.clear(); return redirect('/')

if __name__ == '__main__':
    app.run(debug=True)
