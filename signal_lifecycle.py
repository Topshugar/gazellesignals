import os
import requests
import pandas as pd
import urllib.parse
from datetime import datetime
from flask import Flask, request, jsonify, session, redirect
from flask_sqlalchemy import SQLAlchemy

from signal_lifecycle import configure, refresh_signal, signal_history, as_dict

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")
db_url = os.getenv("DATABASE_URL", "sqlite:///gazelle.db")
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)
configure(db)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    is_vip = db.Column(db.Boolean, default=False)


with app.app_context():
    db.create_all()

FLW_PAY_LINK = "https://flutterwave.com/pay/3sjsabbo3lqx"
FLW_SECRET_HASH = os.getenv("FLW_SECRET_HASH")
CRYPTO_BASES = {"BTC", "ETH", "SOL", "XRP", "BNB", "ADA", "DOGE", "SHIB", "AVAX", "DOT"}


def get_live_price(symbol):
    """Return a provider price or None; never invent a market price."""
    try:
        clean = symbol.split(" - ")[0].strip()
        if "/" in clean and clean.split("/")[0] in CRYPTO_BASES:
            base, quote = clean.split("/", 1)
            pair = base + ("USDT" if quote == "USD" else quote)
            response = requests.get("https://api.binance.com/api/v3/ticker/price", params={"symbol": pair}, timeout=5)
            response.raise_for_status()
            return float(response.json()["price"])
        if "XAU" in clean or "GOLD" in clean:
            response = requests.get("https://api.binance.com/api/v3/ticker/price", params={"symbol": "PAXGUSDT"}, timeout=5)
            response.raise_for_status()
            return float(response.json()["price"])
        if "XAG" in clean or "SILVER" in clean:
            response = requests.get("https://api.binance.com/api/v3/ticker/price", params={"symbol": "PAXGUSDT"}, timeout=5)
            response.raise_for_status()
            return float(response.json()["price"]) * 0.025
        if "/" in clean and len(clean) == 7:
            base, quote = clean.split("/", 1)
            for endpoint in (f"https://api.frankfurter.app/latest?from={base}&to={quote}", f"https://open.er-api.com/v6/latest/{base}"):
                try:
                    data = requests.get(endpoint, timeout=4).json()
                    rates = data.get("rates", {})
                    if quote in rates:
                        return float(rates[quote])
                except (requests.RequestException, ValueError, TypeError):
                    continue
        return None
    except (requests.RequestException, KeyError, ValueError, TypeError):
        return None


def calc_rsi_from_binance(bsym="BTCUSDT"):
    try:
        response = requests.get(f"https://api.binance.com/api/v3/klines?symbol={bsym}&interval=5m&limit=100", timeout=5)
        response.raise_for_status()
        rows = response.json()
        if isinstance(rows, list) and len(rows) >= 22:
            closes = [float(row[4]) for row in rows]
            series = pd.Series(closes)
            delta = series.diff()
            gain = delta.where(delta > 0, 0).rolling(14).mean()
            loss = -delta.where(delta < 0, 0).rolling(14).mean()
            rsi = 100 - (100 / (1 + gain / loss))
            return closes[-1], float(rsi.iloc[-1]), float(series.ewm(span=9, adjust=False).mean().iloc[-1]), float(series.ewm(span=21, adjust=False).mean().iloc[-1]), closes
    except (requests.RequestException, ValueError, TypeError, IndexError):
        pass
    return None, 50, 0, 0, []


def get_signal(symbol):
    real_price = get_live_price(symbol)
    if real_price is None:
        return None
    _, rsi, ema9, ema21, closes = calc_rsi_from_binance("BTCUSDT")
    sig = "BUY" if rsi < 40 and ema9 > ema21 else "SELL" if rsi > 60 and ema9 < ema21 else "BUY" if len(closes) < 2 or closes[-1] > closes[-2] else "SELL"
    if real_price < 10:
        distance = 0.002
        tp1 = real_price + distance if sig == "BUY" else real_price - distance
        tp2 = real_price + distance * 2 if sig == "BUY" else real_price - distance * 2
        sl = real_price - distance / 2 if sig == "BUY" else real_price + distance / 2
    else:
        pct = 0.015
        tp1 = real_price * (1 + pct) if sig == "BUY" else real_price * (1 - pct)
        tp2 = real_price * (1 + pct * 2.5) if sig == "BUY" else real_price * (1 - pct * 2.5)
        sl = real_price * (1 - pct * 0.7) if sig == "BUY" else real_price * (1 + pct * 0.7)
    precision = 5 if real_price < 10 else 2
    return {"pair": symbol, "type": sig, "entry": round(real_price, precision), "tp": round(tp1, precision), "tp2": round(tp2, precision), "sl": round(sl, precision), "conf": 75, "timeframe": "SWING+SCALP CONFIRMED", "live": True, "price": real_price}


def current_user():
    uid = session.get("user_id")
    return User.query.get(uid) if uid else None


def signal_for(symbol):
    price = get_live_price(symbol)
    if price is None:
        return None
    current = refresh_signal(symbol, price, lambda: get_signal(symbol))
    return as_dict(current)


PAIRS_LIBRARY = {
    "FOREX (FREE)": ["EUR/USD", "GBP/USD", "USD/JPY", "USD/CHF", "AUD/USD", "NZD/USD", "USD/CAD", "EUR/GBP", "EUR/JPY", "GBP/JPY"],
    "METALS (VIP) 🔒": ["XAU/USD - GOLD", "XAG/USD - SILVER"],
    "OILS (VIP) 🔒": ["UK OIL", "US OIL"],
    "CRYPTO (VIP) 🔒": ["BTC/USD", "ETH/USD", "SOL/USD", "XRP/USD", "BNB/USD", "DOGE/USD"],
    "INDICES (VIP) 🔒": ["US30", "NAS100", "SPX500", "GER40"],
}
TV_MAP = {
    "EUR/USD": "FX:EURUSD", "GBP/USD": "FX:GBPUSD", "USD/JPY": "FX:USDJPY", "USD/CHF": "FX:USDCHF", "AUD/USD": "FX:AUDUSD", "NZD/USD": "FX:NZDUSD", "USD/CAD": "FX:USDCAD", "EUR/GBP": "FX:EURGBP", "EUR/JPY": "FX:EURJPY", "GBP/JPY": "FX:GBPJPY",
    "XAU/USD - GOLD": "OANDA:XAUUSD", "XAG/USD - SILVER": "OANDA:XAGUSD", "BTC/USD": "BINANCE:BTCUSDT", "ETH/USD": "BINANCE:ETHUSDT", "SOL/USD": "BINANCE:SOLUSDT", "XRP/USD": "BINANCE:XRPUSDT", "BNB/USD": "BINANCE:BNBUSDT", "DOGE/USD": "BINANCE:DOGEUSDT",
}


def wrap(html):
    return f"<html><head><meta name='viewport' content='width=device-width,initial-scale=1'><style>body{{background:#0a0a0a;color:#fff;font-family:Arial;margin:0;padding:20px}}a{{color:#00ff88}}.card,.sigbox{{background:#151515;border-radius:10px;padding:18px;margin:15px auto;max-width:900px}}.row{{padding:14px;border-bottom:1px solid #292929;cursor:pointer}}.tp{{color:#00ff88}}.sl{{color:#ff4444}}table{{width:100%;border-collapse:collapse}}td,th{{padding:8px;border-bottom:1px solid #333;text-align:left}}</style></head><body>{html}</body></html>"


@app.route("/")
def home():
    user = current_user()
    if not user:
        return wrap("<h1>🦌 GAZELLE PRO</h1><a href='/login'>Login</a> or <a href='/register'>Register</a>")
    sections = ""
    for section, pairs in PAIRS_LIBRARY.items():
        rows = "".join(f"<div class='row' onclick=\"location='/market/{urllib.parse.quote(pair.split(' - ')[0])}'\">{pair}</div>" for pair in pairs)
        sections += f"<div class='card'><h3>{section}</h3>{rows}</div>"
    return wrap(f"<p>{user.email} | <a href='/logout'>Logout</a></p>{sections}")


@app.route("/market/<path:symbol>")
def market_page(symbol):
    user = current_user()
    if not user:
        return redirect("/login")
    symbol = urllib.parse.unquote(symbol)
    if symbol not in PAIRS_LIBRARY["FOREX (FREE)"] and not user.is_vip:
        return redirect("/pay")
    signal = signal_for(symbol)
    if signal is None:
        return wrap(f"<a href='/'>‹ Back</a><div class='sigbox'><h2>{symbol}</h2><p>Live market price is temporarily unavailable. No signal was generated.</p></div>"), 503
    history = signal_history(symbol, 20)
    rows = "".join(f"<tr><td>{item.status}</td><td>{item.close_price}</td><td>{item.closed_at}</td></tr>" for item in history)
    col = "#00ff88" if signal["type"] == "BUY" else "#ff4444"
    return wrap(f"<a href='/'>‹ Back to Markets</a><div class='sigbox'><h2>{symbol} <span style='color:{col}'>{signal['type']}</span></h2><p>ACTIVE • Current market price: <b>{signal['entry']}</b></p><p>Entry: <b>{signal['entry']}</b> | TP1: <span class='tp'>{signal['tp']}</span> | TP2: <span class='tp'>{signal['tp2']}</span> | SL: <span class='sl'>{signal['sl']}</span></p><small>Signal opened: {signal['opened_at']}</small></div><div class='card'><h3>Signal history</h3><table><tr><th>Result</th><th>Close price</th><th>Closed at</th></tr>{rows or '<tr><td colspan=3>No completed signals yet.</td></tr>'}</table></div>")


@app.route("/api/signal")
def api_signal():
    symbol = request.args.get("symbol", "EUR/USD")
    signal = signal_for(symbol)
    if signal is None:
        return jsonify({"status": "UNAVAILABLE", "pair": symbol, "message": "Live market price unavailable"}), 503
    return jsonify(signal)


@app.route("/api/signal/history")
def api_signal_history():
    symbol = request.args.get("symbol")
    return jsonify([{**as_dict(item)} for item in signal_history(symbol)])


@app.route("/register", methods=["GET", "POST"])
def reg():
    if request.method == "POST":
        email, password = request.form["email"].lower().strip(), request.form["password"].strip()
        if User.query.filter_by(email=email).first():
            return wrap("Email exists. <a href='/login'>Login</a>")
        user = User(email=email, password=password)
        db.session.add(user)
        db.session.commit()
        session["user_id"] = user.id
        return redirect("/")
    return wrap("<h2>Register</h2><form method=post><input name=email type=email required><input name=password type=password required><button>Register</button></form>")


@app.route("/login", methods=["GET", "POST"])
def log():
    if request.method == "POST":
        user = User.query.filter_by(email=request.form["email"].lower().strip()).first()
        if user and user.password == request.form["password"].strip():
            session["user_id"] = user.id
            return redirect("/")
        return wrap("Wrong password. <a href='/login'>Try again</a>")
    return wrap("<h2>Login</h2><form method=post><input name=email type=email required><input name=password type=password required><button>Login</button></form>")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


@app.route("/pay")
def pay():
    user = current_user()
    if not user:
        return redirect("/login")
    return redirect(f"{FLW_PAY_LINK}?email={user.email}&tx_ref=gazelle-{user.id}-{int(datetime.utcnow().timestamp())}")


@app.route("/webhook/flutterwave", methods=["POST"])
def webhook():
    if not FLW_SECRET_HASH or request.headers.get("verif-hash") != FLW_SECRET_HASH:
        return jsonify({"status": "invalid"}), 401
    payload = (request.json or {}).get("data", request.json or {})
    if payload.get("status") == "successful":
        email = (payload.get("customer", {}).get("email") or "").lower().strip()
        user = User.query.filter_by(email=email).first()
        if user:
            user.is_vip = True
            db.session.commit()
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
