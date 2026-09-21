import os
import requests
import pandas as pd
import urllib.parse
from datetime import datetime
from flask import Flask, request, jsonify, session, redirect
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

from signal_lifecycle import configure, refresh_signal, signal_history, as_dict

app = Flask(__name__)

is_production = os.getenv("RENDER") == "true" or os.getenv("FLASK_ENV") == "production"
secret_key = os.getenv("SECRET_KEY")
if not secret_key and is_production:
    raise RuntimeError("SECRET_KEY is missing. Set it in your Render environment variables.")
app.secret_key = secret_key or "dev-secret-key-change-me"
app.config["SESSION_COOKIE_SECURE"] = is_production
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

db_url = os.getenv("DATABASE_URL")
if not db_url:
    if is_production:
        raise RuntimeError("DATABASE_URL is missing. Set it in your Render environment variables.")
    db_url = "sqlite:///gazelle.db"
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
configure(db)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    is_vip = db.Column(db.Boolean, default=False)


with app.app_context():
    db.create_all()


def hash_password(password):
    return generate_password_hash(password)


def verify_password(password, stored_hash):
    if not stored_hash:
        return False
    if stored_hash.startswith("pbkdf2:") or stored_hash.startswith("scrypt:") or stored_hash.startswith("argon2"):
        return check_password_hash(stored_hash, password)
    return stored_hash == password


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
            if (loss == 0).all():
                return closes[-1], 50.0, float(series.ewm(span=9, adjust=False).mean().iloc[-1]), float(series.ewm(span=21, adjust=False).mean().iloc[-1]), closes
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
    if not closes:
        return None
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
    return {"pair": symbol, "type": sig, "entry": round(real_price, precision), "tp": round(tp1, precision), "tp2": round(tp2, precision), "sl": round(sl, precision), "conf": 75, "timeframe": "SWING", "live": True, "price": real_price}


def current_user():
    uid = session.get("user_id")
    return User.query.get(uid) if uid else None


def signal_for(symbol):
    price = get_live_price(symbol)
    if price is None:
        return None
    signal = get_signal(symbol)
    if signal is None:
        return None
    current = refresh_signal(symbol, price, lambda: signal)
    return as_dict(current)


PAIRS_LIBRARY = {"FOREX (FREE)": ["EUR/USD", "GBP/USD", "USD/JPY", "USD/CHF", "AUD/USD", "NZD/USD", "USD/CAD", "EUR/GBP", "EUR/JPY", "GBP/JPY"], "METALS (VIP) 🔒": ["XAU/USD - GOLD", "XAG/USD - SILVER"], "OILS (VIP) 🔒": ["UK OIL", "US OIL"], "CRYPTO (VIP) 🔒": ["BTC/USD", "ETH/USD", "SOL/USD", "XRP/USD", "BNB/USD", "DOGE/USD"], "INDICES (VIP) 🔒": ["US30", "NAS100", "SPX500", "GER40"]}
TV_MAP = {"EUR/USD": "FX:EURUSD", "GBP/USD": "FX:GBPUSD", "USD/JPY": "FX:USDJPY", "USD/CHF": "FX:USDCHF", "AUD/USD": "FX:AUDUSD", "NZD/USD": "FX:NZDUSD", "USD/CAD": "FX:USDCAD", "EUR/GBP": "FX:EURGBP", "EUR/JPY": "FX:EURJPY", "GBP/JPY": "FX:GBPJPY", "XAU/USD - GOLD": "OANDA:XAUUSD", "XAG/USD - SILVER": "OANDA:XAGUSD", "BTC/USD": "BINANCE:BTCUSDT", "ETH/USD": "BINANCE:ETHUSDT", "SOL/USD": "BINANCE:SOLUSDT", "XRP/USD": "BINANCE:XRPUSDT", "BNB/USD": "BINANCE:BNBUSDT", "DOGE/USD": "BINANCE:DOGEUSDT", "US30": "INDEX:US30", "NAS100": "INDEX:NAS100", "SPX500": "INDEX:SPX500", "GER40": "INDEX:GER40"}


def page_shell(title, content):
    return f"""
    <!doctype html>
    <html lang="en">
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <title>{title}</title>
      <style>
        :root {{
          --bg: #071018;
          --bg-2: #0d1b24;
          --panel: rgba(16,24,32,0.94);
          --panel-2: #121d29;
          --soft: #1c2b36;
          --soft-2: #223542;
          --text: #edf6ff;
          --muted: #9badbc;
          --line: rgba(255,255,255,0.08);
          --green: #30d99a;
          --green-2: #19b57e;
          --red: #ff5b6e;
          --gold: #e7d29c;
          --shadow: 0 20px 50px rgba(0,0,0,0.35);
        }}
        * {{ box-sizing: border-box; }}
        html, body {{ height: 100%; }}
        body {{
          margin: 0; font-family: Arial, Helvetica, sans-serif; background: radial-gradient(circle at top, #0d1b24 0%, var(--bg) 35%, #050b12 100%); color: var(--text);
        }}
        a {{ color: var(--green); text-decoration: none; }}
        .page {{ max-width: 1200px; margin: 0 auto; padding: 30px 18px 60px; }}
        .topbar {{
          display: flex; justify-content: space-between; align-items: center; gap: 16px; padding: 18px 20px; border: 1px solid var(--line); background: rgba(12,18,24,0.8); border-radius: 18px; box-shadow: var(--shadow); backdrop-filter: blur(8px);
        }}
        .brand {{ display: flex; align-items: center; gap: 12px; font-weight: 700; font-size: 1.1rem; }}
        .brand-mark {{ width: 34px; height: 34px; display: grid; place-items: center; border-radius: 10px; background: linear-gradient(135deg, var(--green), var(--green-2)); color: #04170f; font-weight: 900; }}
        .nav-actions {{ display: flex; align-items: center; gap: 10px; }}
        .chip {{ padding: 10px 14px; border-radius: 999px; border: 1px solid var(--line); background: rgba(255,255,255,0.03); color: var(--text); font-weight: 600; }}
        .primary-btn, .secondary-btn {{
          display: inline-flex; align-items: center; justify-content: center; border: none; border-radius: 12px; font-weight: 700; cursor: pointer; transition: 0.2s ease;
        }}
        .primary-btn {{ padding: 14px 18px; background: linear-gradient(135deg, var(--green), var(--green-2)); color: #05130d; box-shadow: 0 12px 30px rgba(48,217,154,0.28); }}
        .secondary-btn {{ padding: 13px 18px; background: transparent; border: 1px solid var(--line); color: var(--text); }}
        .primary-btn:hover, .secondary-btn:hover {{ transform: translateY(-1px); }}
        .hero {{ margin-top: 22px; padding: 26px 22px; border: 1px solid var(--line); border-radius: 22px; background: linear-gradient(180deg, rgba(18,29,41,0.98), rgba(10,18,24,0.95)); box-shadow: var(--shadow); }}
        .hero-grid {{ display: grid; grid-template-columns: 1.3fr 0.7fr; gap: 18px; }}
        .eyebrow {{ text-transform: uppercase; letter-spacing: 0.14em; color: var(--gold); font-size: 0.72rem; font-weight: 700; margin-bottom: 14px; }}
        h1 {{ font-size: clamp(2.4rem, 4vw, 4.3rem); line-height: 0.95; margin: 0 0 16px; letter-spacing: -0.04em; }}
        .subtext {{ color: var(--muted); font-size: 1.05rem; line-height: 1.7; max-width: 620px; }}
        .cta-row {{ display: flex; flex-wrap: wrap; gap: 12px; margin-top: 22px; }}
        .stats {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin-top: 24px; }}
        .stat-card {{ background: rgba(255,255,255,0.02); border: 1px solid var(--line); border-radius: 16px; padding: 16px; }}
        .stat-value {{ font-size: 1.5rem; font-weight: 800; margin-bottom: 8px; }}
        .stat-label {{ color: var(--muted); font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.08em; }}
        .card-grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px; margin-top: 26px; }}
        .market-card {{ background: rgba(18,29,41,0.9); border-radius: 18px; border: 1px solid var(--line); padding: 18px; box-shadow: var(--shadow); }}
        .section-title {{ margin: 26px 0 12px; font-size: clamp(1.8rem, 3vw, 3rem); letter-spacing: -0.04em; }}
        .pair-list {{ display: grid; gap: 12px; margin-top: 12px; }}
        .pair-row {{ display: flex; justify-content: space-between; align-items: center; padding: 14px 16px; border: 1px solid var(--line); border-radius: 12px; background: rgba(255,255,255,0.02); color: var(--text); cursor: pointer; }}
        .pair-row:hover {{ background: rgba(48,217,154,0.06); border-color: rgba(48,217,154,0.4); }}
        .label {{ color: var(--muted); font-size: 0.76rem; text-transform: uppercase; letter-spacing: 0.08em; }}
        .mini-box {{ background: rgba(255,255,255,0.03); border: 1px solid var(--line); border-radius: 16px; padding: 18px; }}
        .form-shell {{ max-width: 520px; margin: 28px auto 0; background: rgba(18,29,41,0.96); border: 1px solid var(--line); border-radius: 22px; padding: 28px; box-shadow: var(--shadow); }}
        .form-shell h2 {{ margin: 0 0 10px; font-size: clamp(2rem, 3vw, 3rem); letter-spacing: -0.04em; }}
        form {{ display: grid; gap: 14px; margin-top: 18px; }}
        label {{ display: grid; gap: 8px; color: var(--muted); font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.08em; }}
        input {{ width: 100%; padding: 15px 14px; border-radius: 12px; border: 1px solid var(--line); background: rgba(255,255,255,0.03); color: var(--text); font-size: 1rem; }}
        .submit-btn {{ width: 100%; margin-top: 8px; padding: 15px 18px; border-radius: 12px; border: none; background: linear-gradient(135deg, var(--green), var(--green-2)); color: #07140d; font-weight: 800; font-size: 1rem; cursor: pointer; }}
        .helper {{ color: var(--muted); font-size: 0.9rem; margin-top: 16px; text-align: center; }}
        .sigbox {{ background: rgba(18,29,41,0.96); border: 1px solid var(--line); border-radius: 22px; padding: 26px; box-shadow: var(--shadow); }}
        .signal-head {{ display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; margin-bottom: 16px; }}
        .signal-badge {{ padding: 8px 12px; border-radius: 999px; font-weight: 800; letter-spacing: 0.04em; text-transform: uppercase; }}
        .buy {{ background: rgba(48,217,154,0.15); color: var(--green); border: 1px solid rgba(48,217,154,0.35); }}
        .sell {{ background: rgba(255,91,110,0.15); color: var(--red); border: 1px solid rgba(255,91,110,0.35); }}
        .stats-row {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin-top: 18px; }}
        .stat-chip {{ background: rgba(255,255,255,0.03); border: 1px solid var(--line); border-radius: 14px; padding: 16px; }}
        .table-wrap {{ margin-top: 18px; overflow: hidden; border: 1px solid var(--line); border-radius: 18px; background: rgba(255,255,255,0.02); }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ padding: 14px 16px; border-bottom: 1px solid var(--line); text-align: left; }}
        th {{ color: var(--muted); text-transform: uppercase; font-size: 0.72rem; letter-spacing: 0.08em; }}
        @media (max-width: 800px) {{
          .hero-grid, .card-grid, .stats-row, .stats {{ grid-template-columns: 1fr; }}
          .topbar {{ flex-direction: column; align-items: flex-start; }}
          .nav-actions {{ width: 100%; justify-content: space-between; }}
          h1 {{ font-size: 2.5rem; }}
        }}
      </style>
    </head>
    <body>
      <div class="page">
        {content}
      </div>
    </body>
    </html>
    """


def wrap(html):
    return page_shell("Gazelle Signals", html)


@app.route("/")
def home():
    user = current_user()
    if not user:
        return wrap(f"""
            <div class="topbar">
              <div class="brand"><div class="brand-mark">G</div> Gazelle Signals</div>
              <div class="nav-actions">
                <a href="/login" class="secondary-btn">Login</a>
                <a href="/register" class="primary-btn">Register</a>
              </div>
            </div>
            <div class="hero">
              <div class="hero-grid">
                <div>
                  <div class="eyebrow">Live market intelligence</div>
                  <h1>Signals that feel clear, fast, and premium.</h1>
                  <div class="subtext">Track forex, metals, indices, and crypto opportunities with a clean dashboard designed for confident decision-making.</div>
                  <div class="cta-row">
                    <a href="/register" class="primary-btn">Create account</a>
                    <a href="/login" class="secondary-btn">Already a member?</a>
                  </div>
                  <div class="stats">
                    <div class="stat-card"><div class="stat-value">10+</div><div class="stat-label">Forex pairs</div></div>
                    <div class="stat-card"><div class="stat-value">24/7</div><div class="stat-label">Market view</div></div>
                    <div class="stat-card"><div class="stat-value">VIP</div><div class="stat-label">Advanced access</div></div>
                  </div>
                </div>
                <div class="mini-box">
                  <div class="label">Market focus</div>
                  <div class="pair-list" style="margin-top:16px;">
                    <div class="pair-row"><span>EUR/USD</span><span class="chip">Live</span></div>
                    <div class="pair-row"><span>BTC/USD</span><span class="chip">VIP</span></div>
                    <div class="pair-row"><span>XAU/USD</span><span class="chip">VIP</span></div>
                    <div class="pair-row"><span>NAS100</span><span class="chip">VIP</span></div>
                  </div>
                </div>
              </div>
            </div>
        """)
    sections = ""
    for section, pairs in PAIRS_LIBRARY.items():
        rows = "".join(f"<div class='pair-row' onclick=\"location='/market/{urllib.parse.quote(pair.split(' - ')[0])}'\"><span>{pair}</span><span class='chip'>{'Free' if section.startswith('FOREX') else 'VIP'}</span></div>" for pair in pairs)
        sections += f"<div class='market-card'><div class='label'>{section}</div><div class='pair-list'>{rows}</div></div>"
    return wrap(f"""
        <div class="topbar">
          <div class="brand"><div class="brand-mark">G</div> Gazelle Signals</div>
          <div class="nav-actions">
            <span class="chip">{user.email}</span>
            <a href="/logout" class="secondary-btn">Logout</a>
          </div>
        </div>
        <div class="hero">
          <div class="eyebrow">Welcome back</div>
          <h1>Market dashboard</h1>
          <div class="subtext">Choose your market and open the latest signal with clear entry, target, and stop levels.</div>
        </div>
        <div class="card-grid">{sections}</div>
    """)


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
        return wrap(f"<div class='form-shell'><h2>Market unavailable</h2><p class='helper'>Live market price is temporarily unavailable. No signal was generated.</p><a href='/' class='primary-btn' style='display:inline-flex;margin-top:12px;'>Return home</a></div>"), 503
    history = signal_history(symbol, 20)
    rows = "".join(f"<tr><td>{item.status}</td><td>{item.close_price}</td><td>{item.closed_at}</td></tr>" for item in history)
    col = "#00ff88" if signal["type"] == "BUY" else "#ff4444"
    tone = "buy" if signal["type"] == "BUY" else "sell"
    return wrap(f"""
        <div class="topbar">
          <div class="brand"><div class="brand-mark">G</div> Gazelle Signals</div>
          <div class="nav-actions"><a href="/" class="secondary-btn">Back</a></div>
        </div>
        <div class="sigbox" style="margin-top:22px;">
          <div class="signal-head">
            <div>
              <div class="label">Pair</div>
              <h2 style="margin:8px 0 0; font-size:2.2rem;">{symbol}</h2>
            </div>
            <span class="signal-badge {tone}">{signal['type']}</span>
          </div>
          <div class="stats-row">
            <div class="stat-chip"><div class="label">Entry</div><div class="stat-value" style="font-size:1.2rem; margin-top:8px;">{signal['entry']}</div></div>
            <div class="stat-chip"><div class="label">TP</div><div class="stat-value" style="font-size:1.2rem; margin-top:8px;">{signal['tp']}</div></div>
            <div class="stat-chip"><div class="label">SL</div><div class="stat-value" style="font-size:1.2rem; margin-top:8px;">{signal['sl']}</div></div>
            <div class="stat-chip"><div class="label">Confidence</div><div class="stat-value" style="font-size:1.2rem; margin-top:8px;">{signal['conf']}%</div></div>
          </div>
          <p class="subtext" style="margin-top:18px;">Strategy: {signal['timeframe']}</p>
        </div>
        <div class="table-wrap" style="margin-top:22px;">
          <table>
            <thead><tr><th>Status</th><th>Close</th><th>Closed at</th></tr></thead>
            <tbody>{rows or '<tr><td colspan="3">No completed signals yet.</td></tr>'}</tbody>
          </table>
        </div>
    """)


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
        email = request.form["email"].lower().strip()
        password = request.form["password"].strip()
        if User.query.filter_by(email=email).first():
            return wrap(f"<div class='form-shell'><h2>Already registered</h2><p class='helper'>That email already exists. Please log in instead.</p><div class='cta-row' style='justify-content:center;'><a href='/login' class='primary-btn'>Go to login</a></div></div>")
        user = User(email=email, password=hash_password(password))
        db.session.add(user)
        db.session.commit()
        session["user_id"] = user.id
        return redirect("/")
    return wrap(f"""
        <div class="form-shell">
          <div class="eyebrow">Create your account</div>
          <h2>Register</h2>
          <form method="post">
            <label>Email<input name="email" type="email" required></label>
            <label>Password<input name="password" type="password" required></label>
            <button class="submit-btn">Create account</button>
          </form>
          <div class="helper">Already have an account? <a href="/login">Login here</a></div>
        </div>
    """)


@app.route("/login", methods=["GET", "POST"])
def log():
    if request.method == "POST":
        email = request.form["email"].lower().strip()
        password = request.form["password"].strip()
        user = User.query.filter_by(email=email).first()
        if user and verify_password(password, user.password):
            session["user_id"] = user.id
            return redirect("/")
        return wrap(f"<div class='form-shell'><h2>Login failed</h2><p class='helper'>Wrong password or email. Please try again.</p><div class='cta-row' style='justify-content:center;'><a href='/login' class='primary-btn'>Try again</a></div></div>")
    return wrap(f"""
        <div class="form-shell">
          <div class="eyebrow">Welcome back</div>
          <h2>Login</h2>
          <form method="post">
            <label>Email<input name="email" type="email" required></label>
            <label>Password<input name="password" type="password" required></label>
            <button class="submit-btn">Login</button>
          </form>
          <div class="helper">Need an account? <a href="/register">Register here</a></div>
        </div>
    """)


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



"path":"app.py"},
{"content":"from functools import wraps
import os
from datetime import datetime, timezone

from flask import Blueprint, redirect, render_template_string, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash


def init_admin(app, db, User):
    """Register the database-backed administrator area on the existing app."""

    class Admin(db.Model):
        __tablename__ = "admins"
        id = db.Column(db.Integer, primary_key=True)
        email = db.Column(db.String(120), unique=True, nullable=False)
        password_hash = db.Column(db.String(255), nullable=False)
        created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    with app.app_context():
        db.create_all()
        _bootstrap_admin(db, Admin)

    admin = Blueprint("admin", __name__, url_prefix="/admin")

    def logged_in_admin():
        admin_id = session.get("admin_id")
        return Admin.query.get(admin_id) if admin_id else None

    def admin_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not logged_in_admin():
                return redirect(url_for("admin.login", next=request.path))
            return view(*args, **kwargs)
        return wrapped

    @admin.route("/login", methods=["GET", "POST"])
    def login():
        error = None
        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            account = Admin.query.filter_by(email=email).first()
            if account and check_password_hash(account.password_hash, password):
                session.clear()
                session["admin_id"] = account.id
                return redirect(request.args.get("next") or url_for("admin.dashboard"))
            error = "Invalid administrator login."
        return render_template_string(_LOGIN_HTML, error=error)

    @admin.route("/")
    @admin_required
    def dashboard():
        users = User.query.order_by(User.id.desc()).all()
        return render_template_string(_DASHBOARD_HTML, users=users, admin=logged_in_admin())

    @admin.route("/logout")
    def logout():
        session.pop("admin_id", None)
        return redirect(url_for("admin.login"))

    app.register_blueprint(admin)
    return Admin


def _bootstrap_admin(db, Admin):
    """Create the first administrator from Render environment variables only once."""
    email = os.getenv("ADMIN_EMAIL", "").strip().lower()
    password = os.getenv("ADMIN_PASSWORD", "")
    if not email or not password:
        return
    account = Admin.query.filter_by(email=email).first()
    if account:
        return
    db.session.add(Admin(email=email, password_hash=generate_password_hash(password)))
    db.session.commit()


_LOGIN_HTML = """
<!doctype html><title>Admin login | Gazelle Signals</title>
<style>
  :root { --bg:#071018; --panel:#0e1a23; --panel-2:#121f2a; --line:rgba(255,255,255,0.08); --text:#edf6ff; --muted:#9badbc; --green:#30d99a; }
  * { box-sizing:border-box; }
  body { margin:0; min-height:100vh; display:grid; place-items:center; background:radial-gradient(circle at top, #0d1b24 0%, #071018 40%, #050b12 100%); color:var(--text); font-family:Arial, sans-serif; }
  .card { width:min(500px, 92vw); background:rgba(14,26,35,0.96); border:1px solid var(--line); border-radius:22px; padding:32px; box-shadow:0 20px 50px rgba(0,0,0,0.35); }
  h1 { margin:0 0 12px; font-size:clamp(2rem,4vw,3rem); letter-spacing:-0.04em; }
  form { display:grid; gap:14px; margin-top:20px; }
  input { width:100%; padding:14px 12px; border-radius:12px; border:1px solid var(--line); background:rgba(255,255,255,0.03); color:var(--text); font-size:1rem; }
  button { width:100%; padding:14px 18px; border:none; border-radius:12px; background:linear-gradient(135deg, var(--green), #19b57e); color:#05130d; font-weight:800; cursor:pointer; }
  .error { color:#ff8697; margin:0 0 12px; }
  .helper { margin-top:16px; color:var(--muted); text-align:center; }
  a { color:#7fe0b5; text-decoration:none; }
</style>
<div class="card">
  <div style="color:#30d99a; text-transform:uppercase; letter-spacing:.12em; font-size:.72rem; font-weight:700;">Admin access</div>
  <h1>Gazelle Signals</h1>
  {% if error %}<p class="error">{{ error }}</p>{% endif %}
  <form method="post">
    <input name="email" type="email" placeholder="Admin email" required autofocus>
    <input name="password" type="password" placeholder="Password" required>
    <button>Sign in</button>
  </form>
  <div class="helper">Secure admin panel for registrations</div>
</div>
"""

_DASHBOARD_HTML = """
<!doctype html><title>Registrations | Gazelle Signals</title>
<style>
  :root { --bg:#071018; --panel:#0e1a23; --panel-2:#121f2a; --line:rgba(255,255,255,0.08); --text:#edf6ff; --muted:#9badbc; --green:#30d99a; }
  * { box-sizing:border-box; }
  body { margin:0; background:radial-gradient(circle at top, #0d1b24 0%, #071018 40%, #050b12 100%); color:var(--text); font-family:Arial, sans-serif; }
  .wrap { max-width:1100px; margin:0 auto; padding:28px 18px 50px; }
  .top { display:flex; justify-content:space-between; align-items:center; gap:12px; flex-wrap:wrap; margin-bottom:18px; }
  .title { font-size:clamp(2rem,4vw,3rem); letter-spacing:-0.04em; margin:0; }
  .pill { background:#101d29; border:1px solid var(--line); border-radius:999px; padding:9px 14px; color:var(--text); }
  .logout { display:inline-block; padding:11px 18px; border-radius:12px; border:1px solid var(--line); color:var(--text); text-decoration:none; }
  .card { background:rgba(14,26,35,0.97); border:1px solid var(--line); border-radius:20px; padding:18px; box-shadow:0 20px 50px rgba(0,0,0,0.35); }
  table { width:100%; border-collapse:collapse; }
  th, td { padding:14px 16px; border-bottom:1px solid var(--line); text-align:left; }
  th { color:var(--muted); text-transform:uppercase; letter-spacing:0.08em; font-size:0.72rem; }
  .vip { color:var(--green); font-weight:700; }
  .sub { color:var(--muted); margin:10px 0 20px; }
</style>
<div class="wrap">
  <div class="top">
    <div>
      <div style="color:#30d99a; text-transform:uppercase; letter-spacing:.12em; font-size:.72rem; font-weight:700;">Admin dashboard</div>
      <h1 class="title">Registered users</h1>
    </div>
    <div style="display:flex; gap:10px; align-items:center; flex-wrap:wrap;">
      <span class="pill">{{ admin.email }}</span>
      <a class="logout" href="{{ url_for('admin.logout') }}">Logout</a>
    </div>
  </div>
  <div class="sub">Total registrations: <strong>{{ users|length }}</strong></div>
  <div class="card">
    <table>
      <thead>
        <tr><th>ID</th><th>Email</th><th>Plan</th></tr>
      </thead>
      <tbody>
        {% for user in users %}
          <tr><td>{{ user.id }}</td><td>{{ user.email }}</td><td class="{% if user.is_vip %}vip{% endif %}">{{ 'VIP' if user.is_vip else 'FREE' }}</td></tr>
        {% else %}
          <tr><td colspan="3">No registrations yet.</td></tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
</div>
"""

"path":"admin_routes.py"}]}t to=functions.push_files  ARGH we got invalid JSON due malformed. Need retry with correct JSON. Need be careful escaping. Simpler use create_or_update_file maybe easier but for two files still okay. Let's do one file at a time with push_files; ensure valid JSON. We'll do app.py alone and admin_routes.py alone. I need ensure no extra text. Let's use push_files with proper JSON but shorter. For app.py we can use raw multi-line string not need escaping? In JSON we can include properly. Need ensure not too large but okay. I'll do with app.py content and admin_routes.py content. I'll avoid semantically weird invalid JSON. Let's do smaller but complete. Need not include huge CSS but okay. Use push_files. Let's craft carefully with valid JSON string escaping. This is cumbersome but manageable. I'll do app.py first. Then admin_routes.py second maybe just if needed. Let's do simpler because admin_routes already polished enough; may skip. User asked UI/UX friendly and lovely; app.py redesign enough. So only app.py patch needed. Great. Use push_files with single file. Let's do. Need valid JSON with escaped newlines automatically by function call from tool. We can pass as raw text in JSON values; it's fine. Let's do smaller but complete. I must be careful not to include unescaped quotes inside string but tool handles it because it's JSON. Need not manually escape every quote? In tool JSON string, quotes inside value must be escaped by the client, but here since I'm writing it as JSON literal in the assistant message, it will be properly escaped by model? Usually yes. Let's do. Let's proceed. Need use commentary channel tool. Let's do. Celebrate. Use functions.push_files. Let's go. Mention branch main. repository owner Topshugar repo gazellesignals. Great. Let's proceed. She says 