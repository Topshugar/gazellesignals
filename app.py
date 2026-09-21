import os, requests
import pandas as pd
from flask import Flask, request, jsonify, session, redirect
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'gazelle-secret-2025')

# === DATABASE - FIXES YOUR LOGOUT BUG ===
db_url = os.getenv('DATABASE_URL', 'sqlite:///gazelle.db')
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    is_vip = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    tx_ref = db.Column(db.String(200))

with app.app_context():
    db.create_all()

# === CONFIG ===
FLW_PAY_LINK = "https://flutterwave.com/pay/3sjsabbo3lqx"
FLW_SECRET_HASH = os.getenv('FLW_SECRET_HASH', 'gazelle123')

def calc_rsi(prices, period=14):
    try:
        s = pd.Series(prices)
        delta = s.diff()
        gain = delta.where(delta > 0, 0).rolling(window=period).mean()
        loss = -delta.where(delta < 0, 0).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return float(rsi.iloc[-1])
    except:
        return 50.0

def get_signal(symbol):
    try:
        url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=5m&limit=100"
        r = requests.get(url, timeout=10).json()
        closes = [float(x[4]) for x in r]
        price = closes[-1]
        rsi = calc_rsi(closes, 14)
        ema9 = pd.Series(closes).ewm(span=9, adjust=False).mean().iloc[-1]
        ema21 = pd.Series(closes).ewm(span=21, adjust=False).mean().iloc[-1]

        buy = rsi < 35 and ema9 > ema21
        sell = rsi > 65 and ema9 < ema21

        if buy:
            return {"type": "BUY", "price": price, "conf": 88}
        if sell:
            return {"type": "SELL", "price": price, "conf": 88}
        return {"type": "WAIT", "price": price, "conf": 60}
    except Exception as e:
        return {"type": "WAIT", "price": 0, "conf": 0}

def wrap(html):
    return f"<html><head><meta name='viewport' content='width=device-width,initial-scale=1'><style>body{{background:#0a0a0a;color:#fff;font-family:sans-serif;margin:0}}.card{{background:#151515;border:1px solid #222;border-radius:16px;padding:20px;margin:10px}}.btn{{background:gold;color:#000;padding:12px;border:none;border-radius:10px;font-weight:700;width:100%;cursor:pointer}}.input{{width:100%;padding:12px;margin:8px 0;border-radius:10px;background:#222;border:1px solid #333;color:#fff}}a{{text-decoration:none}}</style></head><body>{html}</body></html>"

def current_user():
    uid = session.get('user_id')
    return User.query.get(uid) if uid else None

@app.route('/')
def home():
    u = current_user()
    vip = u.is_vip if u else False
    status = f"VIP ✅ {u.email}" if vip else f"Free - <a href='/pay' style='color:gold'>Upgrade VIP</a> | {u.email}" if u else "<a href='/login' style='color:gold'>Login / Register</a>"
    return wrap(f"""
    <div style='padding:20px;max-width:500px;margin:0 auto'>
        <h1>🦌 GAZELLE PRO</h1><div class=card>{status} | <a href='/logout' style='color:#888'>Logout</a></div>
        <div id='pairs' class=card>Loading...</div><div id='signal' class=card>Select pair</div>
        <script>
        let cur='BTCUSDT';
        async function loadPairs(){{
            let r=await fetch('/api/pairs'); let data=await r.json();
            let h=''; data.forEach(p=>{{
                let lock = {str(vip).lower()}? '' : (p.vip? '🔒' : '');
                h+=`<div onclick="pick('${{p.symbol}}',${{p.vip}})" style='padding:12px;border-bottom:1px solid #222;cursor:pointer;display:flex;justify-content:space-between'><span>${{p.name}} ${{lock}}</span><span style='color:#888'>${{p.symbol}}</span></div>`
            }});
            document.getElementById('pairs').innerHTML=h;
        }}
        async function pick(sym,isVip){{ if(isVip &&!{str(vip).lower()}){{ window.location='/pay'; return; }} cur=sym; getSig(); }}
        async function getSig(){{
            let r=await fetch('/api/signal?symbol='+cur); let d=await r.json();
            if(d.type=='LOCKED'){{ document.getElementById('signal').innerHTML="<h3>🔒 VIP Only</h3><a href='/pay'><button class=btn>Unlock VIP</button></a>"; return; }}
            let col = d.type=='BUY'? '#00ff88' : d.type=='SELL'? '#ff4444' : '#888';
            document.getElementById('signal').innerHTML=`<h2 style='color:${{col}}'>${{d.type}} - ${{cur}}</h2><p>Price: ${{d.price}}</p><p>Conf: ${{d.conf}}%</p>`;
        }}
        loadPairs(); setInterval(getSig, 10000);
        </script>
    </div>""")

@app.route('/api/pairs')
def api_pairs():
    return jsonify([
        {"symbol":"BTCUSDT","name":"BTC/USD","vip":False},{"symbol":"ETHUSDT","name":"ETH/USD","vip":False},
        {"symbol":"BNBUSDT","name":"BNB/USD","vip":False},{"symbol":"SOLUSDT","name":"SOL/USD","vip":False},
        {"symbol":"XRPUSDT","name":"XRP/USD","vip":False},{"symbol":"ADAUSDT","name":"ADA/USD","vip":False},
        {"symbol":"DOGEUSDT","name":"DOGE/USD","vip":True},{"symbol":"SHIBUSDT","name":"SHIB/USD","vip":True},
        {"symbol":"AVAXUSDT","name":"AVAX/USD","vip":True},{"symbol":"DOTUSDT","name":"DOT/USD","vip":True},
    ])

@app.route('/api/signal')
def api_signal():
    sym = request.args.get('symbol','BTCUSDT')
    u = current_user()
    if sym in ["DOGEUSDT","SHIBUSDT","AVAXUSDT","DOTUSDT"] and (not u or not u.is_vip):
        return jsonify({"type":"LOCKED"})
    return jsonify(get_signal(sym))

@app.route('/register',methods=['GET','POST'])
def reg():
    if request.method=='POST':
        email=request.form['email'].lower().strip(); pwd=request.form['password'].strip()
        if User.query.filter_by(email=email).first():
            return wrap("<div class=card style='max-width:400px;margin:100px auto'>Email exists <a href='/login' style='color:gold'>Login</a></div>")
        u=User(email=email,password=pwd); db.session.add(u); db.session.commit()
        session['user_id']=u.id; return redirect('/')
    return wrap("<div class=card style='max-width:400px;margin:100px auto'><h2>Register</h2><form method=post><input name=email placeholder='Email' class=input required><input name=password type=password placeholder='Password' class=input required><button class=btn>Register</button></form></div>")

@app.route('/login',methods=['GET','POST'])
def log():
    if request.method=='POST':
        email=request.form['email'].lower().strip(); pwd=request.form['password'].strip()
        u=User.query.filter_by(email=email).first()
        if u and u.password==pwd: session['user_id']=u.id; return redirect('/')
        return wrap("<div class=card style='max-width:400px;margin:100px auto'>Wrong email/password <a href='/login' style='color:gold'>Try again</a></div>")
    return wrap("<div class=card style='max-width:400px;margin:100px auto'><h2>Login</h2><form method=post><input name=email placeholder='Email' class=input required><input name=password type=password placeholder='Password' class=input required><button class=btn>Login</button></form></div>")

@app.route('/logout')
def logout(): session.clear(); return redirect('/login')

@app.route('/pay')
def pay():
    u=current_user()
    if not u: return redirect('/login')
    return redirect(f"{FLW_PAY_LINK}?email={u.email}&tx_ref=gazelle-{u.id}-{int(datetime.utcnow().timestamp())}")

@app.route('/pay/success')
def pay_success():
    u=current_user()
    if not u: return redirect('/login')
    return wrap(f"<div class=card style='max-width:400px;margin:100px auto;text-align:center'><h2>⏳ Verifying payment...</h2><p>{u.email}</p><p>Confirming with Flutterwave. VIP unlocks automatically.</p><a href='/'><button class=btn>Check Status →</button></a></div>")

@app.route('/webhook/flutterwave', methods=['POST'])
def flw_webhook():
    signature = request.headers.get('verif-hash')
    if signature!= FLW_SECRET_HASH:
        return jsonify({"status":"invalid hash"}), 401
    data = request.json
    try:
        payload = data.get('data', data)
        status_ok = payload.get('status') == 'successful' or data.get('status') == 'successful'
        if status_ok:
            email = payload.get('customer', {}).get('email') or payload.get('customer_email') or data.get('customer', {}).get('email')
            if email:
                email = email.lower().strip()
                user = User.query.filter_by(email=email).first()
                if user:
                    user.is_vip = True
                    user.tx_ref = str(payload.get('id') or payload.get('tx_ref') or '')
                    db.session.commit()
                    return jsonify({"status":"VIP activated"}), 200
        return jsonify({"status":"ignored"}), 200
    except Exception as e:
        return jsonify({"error":str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)))
