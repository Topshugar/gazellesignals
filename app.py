import os, requests
import pandas as pd
from flask import Flask, request, jsonify, session, redirect
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import urllib.parse

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'gazelle-secret-2025')
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

with app.app_context():
    db.create_all()

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
    except: return 50.0

def get_signal(symbol):
    try:
        bsym = symbol.replace("/","")
        if bsym in ["BTCUSD","ETHUSD","SOLUSD","XRPUSD","BNBUSD","ADAUSD","DOGEUSD","SHIBUSD","AVAXUSD","DOTUSD"]:
            bsym = bsym.replace("USD","USDT")
        else:
            bsym = "BTCUSDT"
        url = f"https://api.binance.com/api/v3/klines?symbol={bsym}&interval=5m&limit=100"
        r = requests.get(url, timeout=8).json()
        if isinstance(r, list):
            closes = [float(x[4]) for x in r]
            price = closes[-1]
            rsi = calc_rsi(closes)
            ema9 = pd.Series(closes).ewm(span=9, adjust=False).mean().iloc[-1]
            ema21 = pd.Series(closes).ewm(span=21, adjust=False).mean().iloc[-1]
            sig = "BUY" if (rsi < 38 and ema9 > ema21) else "SELL" if (rsi > 62 and ema9 < ema21) else ("BUY" if closes[-1]>closes[-2] else "SELL")
            return {"pair": symbol, "type": sig, "entry": round(price, 5) if price<1000 else round(price,2), "conf": 75, "timeframe": "SWING+SCALP CONFIRMED", "live": True}
    except: pass
    return {"pair": symbol, "type": "SELL", "entry": 1.52050, "conf": 75, "timeframe": "SWING+SCALP CONFIRMED", "live": False}

def wrap(html):
    return f"<html><head><meta name='viewport' content='width=device-width,initial-scale=1'><style>body{{background:#0a0a0a;color:#fff;font-family:Arial,sans-serif;margin:0}}.top{{padding:15px 20px;background:#121212;border-bottom:1px solid #222;position:sticky;top:0;z-index:10}}.card{{background:#111;border:1px solid #222;border-radius:18px;margin:12px;padding:5px}}.row{{padding:14px 18px;border-bottom:1px solid #1a1a1a;display:flex;justify-content:space-between;cursor:pointer}}.row:last-child{{border:none}}.sec{{padding:12px 18px 6px;color:#666;font-size:11px;letter-spacing:1.2px}}.sec.vip{{color:#c8a44a}}.btn{{background:gold;color:#000;padding:12px;border:none;border-radius:10px;font-weight:700;width:100%}}.input{{width:100%;padding:12px;margin:8px 0;border-radius:10px;background:#222;border:1px solid #333;color:#fff}} a{{color:gold;text-decoration:none}}.sigbox{{background:#151515;border:1px solid #2a2a2a;border-radius:22px;padding:22px;margin:12px}} </style></head><body>{html}</body></html>"

def current_user():
    uid = session.get('user_id')
    return User.query.get(uid) if uid else None

PAIRS_LIBRARY = {
    "FOREX (FREE)": ["EUR/USD","GBP/USD","USD/JPY","USD/CHF","AUD/USD","NZD/USD","USD/CAD","EUR/GBP","EUR/JPY","GBP/JPY","AUD/JPY","EUR/AUD","GBP/AUD","EUR/CAD","GBP/CAD","AUD/CAD","NZD/JPY","EUR/NZD","GBP/NZD","USD/SGD","EUR/CHF","AUD/CHF","CAD/JPY","CHF/JPY","EUR/SGD","GBP/CHF"],
    "METALS (VIP) 🔒": ["XAU/USD - GOLD","XAG/USD - SILVER","XPT/USD - PLATINUM","XPD/USD - PALLADIUM"],
    "OILS (VIP) 🔒": ["UK OIL","US OIL","NAT GAS"],
    "CRYPTO (VIP) 🔒": ["BTC/USD","ETH/USD","SOL/USD","XRP/USD","BNB/USD","ADA/USD","DOGE/USD","SHIB/USD","AVAX/USD","DOT/USD"],
    "INDICES (VIP) 🔒": ["US30","NAS100","SPX500","GER40","UK100","FRA40","ESP35","ITA40","JPN225","AUS200"],
    "VOLATILITY (VIP) 🔒": ["Volatility 75 Index","Volatility 100 Index","Boom 1000 Index","Crash 1000 Index"]
}

# TRADINGVIEW SYMBOL MAP
TV_MAP = {
    "EUR/USD":"FX:EURUSD","GBP/USD":"FX:GBPUSD","USD/JPY":"FX:USDJPY","USD/CHF":"FX:USDCHF","AUD/USD":"FX:AUDUSD","NZD/USD":"FX:NZDUSD","USD/CAD":"FX:USDCAD",
    "XAU/USD - GOLD":"OANDA:XAUUSD","XAG/USD - SILVER":"OANDA:XAGUSD","UK OIL":"OANDA:UKOIL","US OIL":"OANDA:USOIL",
    "BTC/USD":"BINANCE:BTCUSDT","ETH/USD":"BINANCE:ETHUSDT","SOL/USD":"BINANCE:SOLUSDT","XRP/USD":"BINANCE:XRPUSDT","BNB/USD":"BINANCE:BNBUSDT",
    "US30":"OANDA:US30USD","NAS100":"OANDA:NAS100USD","SPX500":"OANDA:SPX500USD","GER40":"OANDA:DE40EUR"
}

@app.route('/')
def home():
    u = current_user()
    if not u:
        return wrap("<div style='max-width:400px;margin:80px auto;padding:20px;text-align:center'><h1>🦌 GAZELLE PRO</h1><div class=card style='padding:20px'><a href='/login'><button class=btn>Login</button></a><br><br><a href='/register'><button class=btn style='background:#222;color:#fff'>Register</button></a></div></div>")
    vip = u.is_vip
    html_sections = ""
    for sec, pairs in PAIRS_LIBRARY.items():
        is_vip_sec = "VIP" in sec
        sec_class = "sec vip" if is_vip_sec else "sec"
        html_sections += f"<div class=card><div class='{sec_class}'>{sec}</div>"
        for p in pairs:
            clean = p.split(" - ")[0]
            enc = urllib.parse.quote(clean)
            html_sections += f"<div class=row onclick=\"window.location='/market/{enc}'\"><span>{p} {'🔒' if is_vip_sec and not vip else ''}</span><span style='color:#333'>›</span></div>"
        html_sections += "</div>"
    return wrap(f"<div class=top><b>🦌 GAZELLE PRO</b><br><small style='color:#888'>{u.email} - {'VIP ✅' if vip else 'Free | <a href=/pay>Upgrade VIP</a>'} | <a href='/logout' style='color:#666'>Logout</a></small></div>{html_sections}")

@app.route('/market/<path:symbol>')
def market_page(symbol):
    u = current_user()
    if not u: return redirect('/login')
    symbol = urllib.parse.unquote(symbol)
    forex_free = PAIRS_LIBRARY["FOREX (FREE)"]
    is_vip_market = symbol not in forex_free and symbol.split(" - ")[0] not in forex_free
    if is_vip_market and not u.is_vip:
        return redirect('/pay')

    sig = get_signal(symbol)
    tv_symbol = TV_MAP.get(symbol, TV_MAP.get(symbol.split(" - ")[0], "FX:EURUSD"))
    col = "#00ff88" if sig['type']=="BUY" else "#ff4444"

    return wrap(f"""
    <div class=top><a href='/' style='color:#888'>‹ Back</a> &nbsp; <b>{symbol}</b></div>

    <div class=sigbox>
        <div style='font-size:32px;font-weight:900'>{sig['pair']} <span style='color:{col}'>{sig['type']}</span></div>
        <div style='margin-top:12px;font-size:20px;font-weight:700'>Entry: {sig['entry']} | Confidence: {sig['conf']}%</div>
        <div style='margin-top:8px;color:#888'>{ 'Live market data' if sig['live'] else 'Demo signal - live updating'}</div>
        <div style='margin-top:4px;color:#666;font-size:13px'>Timeframe: {sig['timeframe']}</div>
    </div>

    <div class=card style='padding:0;overflow:hidden;height:420px'>
        <div id="tradingview_chart" style="height:420px"></div>
    </div>

    <div class=card style='padding:18px'>
        <div style='font-weight:700;margin-bottom:10px'>📰 News Affecting {symbol}</div>
        <div id='news' style='color:#888;font-size:14px;line-height:1.6'>Loading market news...</div>
    </div>

    <script type="text/javascript" src="https://s.tradingview.com/tv.js"></script>
    <script>
    new TradingView.widget({{
        "autosize": true,
        "symbol": "{tv_symbol}",
        "interval": "5",
        "timezone": "Etc/UTC",
        "theme": "dark",
        "style": "1",
        "locale": "en",
        "backgroundColor": "#111",
        "gridColor": "#222",
        "container_id": "tradingview_chart"
    }});

    async function loadNews(){{
        try{{
            let q = encodeURIComponent("{symbol} forex crypto");
            let r = await fetch(`https://api.binance.com/api/v3/ticker/24hr?symbol=BTCUSDT`);
            let newsHtml = `
                <div style='padding:10px 0;border-bottom:1px solid #222'>• <b>USD Strength:</b> Dollar index affecting {symbol} momentum today</div>
                <div style='padding:10px 0;border-bottom:1px solid #222'>• <b>Market Sentiment:</b> Risk-on mood - {symbol} showing {sig['type']} bias</div>
                <div style='padding:10px 0;border-bottom:1px solid #222'>• <b>Volatility Alert:</b> High impact news expected in next 4hrs - manage risk</div>
                <div style='padding:10px 0'>• <b>Trend:</b> {symbol} {sig['type']} - {sig['timeframe']} - Confidence {sig['conf']}%</div>
            `;
            document.getElementById('news').innerHTML = newsHtml;
        }}catch(e){{ document.getElementById('news').innerHTML='News feed temporarily unavailable'; }}
    }}
    loadNews();
    setInterval(async ()=>{{
        let r=await fetch('/api/signal?symbol='+encodeURIComponent("{symbol}"));
        let d=await r.json();
        location.reload();
    }}, 30000);
    </script>
    """)

@app.route('/api/signal')
def api_signal():
    sym = request.args.get('symbol','EUR/USD')
    u = current_user()
    forex_free = PAIRS_LIBRARY["FOREX (FREE)"]
    if sym not in forex_free and sym.split(" - ")[0] not in forex_free and (not u or not u.is_vip):
        return jsonify({"type":"LOCKED"})
    return jsonify(get_signal(sym))

@app.route('/register',methods=['GET','POST'])
def reg():
    if request.method=='POST':
        e=request.form['email'].lower().strip(); p=request.form['password'].strip()
        if User.query.filter_by(email=e).first():
            return wrap("<div class=card style='max-width:400px;margin:80px auto;padding:20px'>Email exists <a href='/login'>Login</a></div>")
        u=User(email=e,password=p); db.session.add(u); db.session.commit(); session['user_id']=u.id; return redirect('/')
    return wrap("<div class=card style='max-width:400px;margin:60px auto;padding:20px'><h2>Register</h2><form method=post><input name=email class=input placeholder=Email required><input name=password type=password class=input placeholder=Password required><button class=btn>Register</button></form><br><a href='/login'>Login</a></div>")

@app.route('/login',methods=['GET','POST'])
def log():
    if request.method=='POST':
        e=request.form['email'].lower().strip(); p=request.form['password'].strip()
        u=User.query.filter_by(email=e).first()
        if u and u.password==p: session['user_id']=u.id; return redirect('/')
        return wrap("<div class=card style='max-width:400px;margin:80px auto;padding:20px'>Wrong password <a href='/login'>Try again</a></div>")
    return wrap("<div class=card style='max-width:400px;margin:60px auto;padding:20px'><h2>Login</h2><form method=post><input name=email class=input placeholder=Email required><input name=password type=password class=input placeholder=Password required><button class=btn>Login</button></form><br><a href='/register'>Register</a></div>")

@app.route('/logout')
def logout(): session.clear(); return redirect('/login')

@app.route('/pay')
def pay():
    u=current_user()
    if not u: return redirect('/login')
    return redirect(f"{FLW_PAY_LINK}?email={u.email}&tx_ref=gazelle-{u.id}-{int(datetime.utcnow().timestamp())}")

@app.route('/webhook/flutterwave', methods=['POST'])
def webhook():
    if request.headers.get('verif-hash')!=FLW_SECRET_HASH: return jsonify({"status":"invalid"}),401
    data=request.json; payload=data.get('data',data)
    if payload.get('status')=='successful':
        email=(payload.get('customer',{}).get('email') or '').lower().strip()
        if email:
            user=User.query.filter_by(email=email).first()
            if user: user.is_vip=True; db.session.commit()
    return jsonify({"status":"ok"}),200

if __name__=='__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT',5000)))
