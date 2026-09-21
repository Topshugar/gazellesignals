import os
import urllib.parse
from datetime import datetime

import pandas as pd
import requests
from flask import Flask, jsonify, redirect, request, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

from signal_lifecycle import as_dict, configure, refresh_signal, signal_history

app = Flask(__name__)
production = os.getenv("RENDER") == "true" or os.getenv("FLASK_ENV") == "production"
secret_key = os.getenv("SECRET_KEY")
if production and not secret_key:
    raise RuntimeError("SECRET_KEY is missing. Set it in Render environment variables.")
app.secret_key = secret_key or "dev-secret-key-change-me"
app.config.update(
    SESSION_COOKIE_SECURE=production,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
)

db_url = os.getenv("DATABASE_URL") or ("sqlite:///gazelle.db" if not production else None)
if not db_url:
    raise RuntimeError("DATABASE_URL is missing. Set it in Render environment variables.")
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = db_url

db = SQLAlchemy(app)
configure(db)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    is_vip = db.Column(db.Boolean, default=False)


with app.app_context():
    db.create_all()


PAIRS_LIBRARY = {
    "FOREX (FREE)": ["EUR/USD", "GBP/USD", "USD/JPY", "USD/CHF", "AUD/USD", "NZD/USD", "USD/CAD", "EUR/GBP", "EUR/JPY", "GBP/JPY"],
    "METALS (VIP)": ["XAU/USD - GOLD", "XAG/USD - SILVER"],
    "CRYPTO (VIP)": ["BTC/USD", "ETH/USD", "SOL/USD", "XRP/USD", "BNB/USD", "DOGE/USD"],
    "INDICES (VIP)": ["US30", "NAS100", "SPX500", "GER40"],
}
CRYPTO_BASES = {"BTC", "ETH", "SOL", "XRP", "BNB", "ADA", "DOGE", "SHIB", "AVAX", "DOT"}
FLW_PAY_LINK = "https://flutterwave.com/pay/3sjsabbo3lqx"
FLW_SECRET_HASH = os.getenv("FLW_SECRET_HASH")


def hash_password(password):
    return generate_password_hash(password)


def verify_password(password, stored):
    return bool(stored) and check_password_hash(stored, password)


def current_user():
    uid = session.get("user_id")
    return db.session.get(User, uid) if uid else None


def get_live_price(symbol):
    clean = symbol.split(" - ")[0].strip()
    try:
        if "/" in clean and clean.split("/")[0] in CRYPTO_BASES:
            base, quote = clean.split("/", 1)
            pair = base + ("USDT" if quote == "USD" else quote)
            data = requests.get("https://api.binance.com/api/v3/ticker/price", params={"symbol": pair}, timeout=5).json()
            return float(data["price"])
        if "XAU" in clean or "GOLD" in clean:
            data = requests.get("https://api.binance.com/api/v3/ticker/price", params={"symbol": "PAXGUSDT"}, timeout=5).json()
            return float(data["price"])
        if "XAG" in clean or "SILVER" in clean:
            data = requests.get("https://api.binance.com/api/v3/ticker/price", params={"symbol": "PAXGUSDT"}, timeout=5).json()
            return float(data["price"]) * 0.025
        if "/" in clean and len(clean) == 7:
            base, quote = clean.split("/", 1)
            for url in (f"https://api.frankfurter.app/latest?from={base}&to={quote}", f"https://open.er-api.com/v6/latest/{base}"):
                try:
                    rates = requests.get(url, timeout=4).json().get("rates", {})
                    if quote in rates:
                        return float(rates[quote])
                except (requests.RequestException, ValueError, TypeError):
                    continue
    except (requests.RequestException, KeyError, ValueError, TypeError):
        pass
    return None


def get_signal(symbol):
    price = get_live_price(symbol)
    if price is None:
        return None
    try:
        rows = requests.get("https://api.binance.com/api/v3/klines", params={"symbol": "BTCUSDT", "interval": "5m", "limit": 100}, timeout=5).json()
        closes = [float(row[4]) for row in rows] if isinstance(rows, list) else []
        if len(closes) < 2:
            return None
        series = pd.Series(closes)
        delta = series.diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = -delta.where(delta < 0, 0).rolling(14).mean()
        rsi = float((100 - (100 / (1 + gain / loss))).iloc[-1])
        ema9 = float(series.ewm(span=9, adjust=False).mean().iloc[-1])
        ema21 = float(series.ewm(span=21, adjust=False).mean().iloc[-1])
    except (requests.RequestException, ValueError, TypeError, IndexError):
        return None
    direction = "BUY" if (rsi < 40 and ema9 > ema21) or (rsi <= 60 and closes[-1] >= closes[-2]) else "SELL"
    precision = 5 if price < 10 else 2
    distance = 0.002 if price < 10 else price * 0.015
    tp = price + distance if direction == "BUY" else price - distance
    tp2 = price + distance * 2.5 if direction == "BUY" else price - distance * 2.5
    sl = price - distance * 0.7 if direction == "BUY" else price + distance * 0.7
    return {"pair": symbol, "type": direction, "entry": round(price, precision), "tp": round(tp, precision), "tp2": round(tp2, precision), "sl": round(sl, precision), "conf": 75, "timeframe": "SWING"}


def signal_for(symbol):
    price = get_live_price(symbol)
    if price is None:
        return None
    values = get_signal(symbol)
    if values is None:
        return None
    signal = refresh_signal(symbol, price, lambda: values)
    return as_dict(signal) if signal else None


def shell(title, body):
    css = """
    <style>
    :root{color-scheme:dark}*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at top,#142b36,#071018 45%,#05090d);color:#edf6ff;font:16px Arial,sans-serif}.page{max-width:1100px;margin:auto;padding:24px 16px 60px}a{color:#30d99a;text-decoration:none}.top{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:16px 18px;border:1px solid #ffffff16;border-radius:16px;background:#101b24}.brand{font-weight:bold}.actions{display:flex;gap:10px;align-items:center;flex-wrap:wrap}.btn{display:inline-block;padding:12px 16px;border-radius:11px;border:1px solid #ffffff18}.primary{background:#30d99a;color:#06140e;font-weight:bold;border:0}.hero,.card,.form,.signal{margin-top:20px;padding:24px;border:1px solid #ffffff14;border-radius:20px;background:#101d28e8;box-shadow:0 18px 40px #0005}.hero h1{font-size:clamp(2.3rem,6vw,4.5rem);margin:10px 0}.muted{color:#9badbc;line-height:1.6}.grid{display:grid;grid-template-columns:repeat(2,1fr);gap:16px;margin-top:20px}.pairs{display:grid;gap:10px;margin-top:14px}.pair{display:flex;justify-content:space-between;padding:14px;border:1px solid #ffffff12;border-radius:11px;background:#ffffff05;cursor:pointer}.pair:hover{border-color:#30d99a}.form{max-width:480px;margin:30px auto}.form h2{font-size:2rem;margin-top:0}.form form{display:grid;gap:14px}.form label{display:grid;gap:7px;color:#9badbc}.form input{padding:14px;border-radius:10px;border:1px solid #ffffff18;background:#ffffff08;color:#fff}.form button{padding:14px;border:0;border-radius:10px;background:#30d99a;font-weight:bold}.metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-top:18px}.metric{padding:14px;border:1px solid #ffffff12;border-radius:12px;background:#ffffff05}.label{color:#9badbc;font-size:.75rem;text-transform:uppercase;letter-spacing:.08em}.value{font-weight:bold;font-size:1.2rem;margin-top:7px}table{width:100%;border-collapse:collapse;margin-top:20px}th,td{text-align:left;padding:12px;border-bottom:1px solid #ffffff12}.buy{color:#30d99a}.sell{color:#ff5b6e}@media(max-width:700px){.grid,.metrics{grid-template-columns:1fr}.top{align-items:flex-start;flex-direction:column}}
    </style>
    """
    return f"<!doctype html><html><head><meta name='viewport' content='width=device-width,initial-scale=1'><title>{title}</title>{css}</head><body><main class='page'>{body}</main></body></html>"


@app.route("/")
def home():
    user = current_user()
    if not user:
        return shell("Gazelle Signals", "<div class='top'><div class='brand'>🦌 Gazelle Signals</div><div class='actions'><a class='btn' href='/login'>Login</a><a class='btn primary' href='/register'>Register</a></div></div><section class='hero'><div class='label'>Live market intelligence</div><h1>Clear signals. Better decisions.</h1><p class='muted'>A friendly, premium dashboard for forex and digital market signals.</p><div class='actions'><a class='btn primary' href='/register'>Create your account</a></div></section>")
    sections = ""
    for name, pairs in PAIRS_LIBRARY.items():
        rows = "".join(f"<div class='pair' onclick=\"location='/market/{urllib.parse.quote(pair.split(' - ')[0])}'\"><span>{pair}</span><span class='label'>{'FREE' if 'FREE' in name else 'VIP'}</span></div>" for pair in pairs)
        sections += f"<section class='card'><div class='label'>{name}</div><div class='pairs'>{rows}</div></section>"
    return shell("Market dashboard", f"<div class='top'><div class='brand'>🦌 Gazelle Signals</div><div class='actions'><span>{user.email}</span><a class='btn' href='/logout'>Logout</a></div></div><section class='hero'><div class='label'>Welcome back</div><h1>Market dashboard</h1><p class='muted'>Choose a pair to view the latest signal.</p></section><div class='grid'>{sections}</div>")


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
        return shell("Market unavailable", "<div class='form'><h2>Market temporarily unavailable</h2><p class='muted'>No reliable live data was returned. Please try again shortly.</p><a class='btn primary' href='/'>Return home</a></div>"), 503
    tone = "buy" if signal["type"] == "BUY" else "sell"
    history = signal_history(symbol, 20)
    rows = "".join(f"<tr><td>{item.status}</td><td>{item.close_price}</td><td>{item.closed_at}</td></tr>" for item in history)
    body = f"<div class='top'><div class='brand'>🦌 Gazelle Signals</div><a class='btn' href='/'>Back</a></div><section class='signal'><div class='label'>Pair</div><h2>{symbol} <span class='{tone}'>{signal['type']}</span></h2><div class='metrics'><div class='metric'><div class='label'>Entry</div><div class='value'>{signal['entry']}</div></div><div class='metric'><div class='label'>TP</div><div class='value'>{signal['tp']}</div></div><div class='metric'><div class='label'>SL</div><div class='value'>{signal['sl']}</div></div><div class='metric'><div class='label'>Confidence</div><div class='value'>{signal.get('conf', 75)}%</div></div></div></section><section class='card'><div class='label'>Signal history</div><table><tr><th>Status</th><th>Close</th><th>Closed at</th></tr>{rows or '<tr><td colspan=3>No completed signals yet.</td></tr>'}</table></section>"
    return shell(symbol, body)


@app.route("/api/signal")
def api_signal():
    symbol = request.args.get("symbol", "EUR/USD")
    signal = signal_for(symbol)
    if signal is None:
        return jsonify({"status": "UNAVAILABLE", "pair": symbol, "message": "Live market price unavailable"}), 503
    return jsonify(signal)


@app.route("/api/signal/history")
def api_signal_history():
    return jsonify([as_dict(item) for item in signal_history(request.args.get("symbol"))])


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email", "").lower().strip()
        password = request.form.get("password", "")
        if User.query.filter_by(email=email).first():
            return shell("Register", "<div class='form'><h2>Already registered</h2><p class='muted'>Please use the login page.</p><a class='btn primary' href='/login'>Login</a></div>")
        user = User(email=email, password=hash_password(password))
        db.session.add(user)
        db.session.commit()
        session["user_id"] = user.id
        return redirect("/")
    return shell("Register", "<div class='form'><div class='label'>Create your account</div><h2>Register</h2><form method='post'><label>Email<input name='email' type='email' required></label><label>Password<input name='password' type='password' required></label><button>Create account</button></form><p class='muted'>Already registered? <a href='/login'>Log in</a></p></div>")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = User.query.filter_by(email=request.form.get("email", "").lower().strip()).first()
        if user and verify_password(request.form.get("password", ""), user.password):
            session["user_id"] = user.id
            return redirect("/")
        return shell("Login", "<div class='form'><h2>Login failed</h2><p class='muted'>Incorrect email or password.</p><a class='btn primary' href='/login'>Try again</a></div>")
    return shell("Login", "<div class='form'><div class='label'>Welcome back</div><h2>Login</h2><form method='post'><label>Email<input name='email' type='email' required></label><label>Password<input name='password' type='password' required></label><button>Login</button></form><p class='muted'>Need an account? <a href='/register'>Register</a></p></div>")


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
        email = payload.get("customer", {}).get("email", "").lower().strip()
        user = User.query.filter_by(email=email).first()
        if user:
            user.is_vip = True
            db.session.commit()
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
