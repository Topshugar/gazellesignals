import yfinance as yf
import pandas_ta as ta
import time
import random
from datetime import datetime
from app import app, db, Signal

# --- YOUR GAZELLE STRATEGY CONFIG ---
# Swing = direction bias, Day = entry

SWING_CONFIG = {
    "rsi": 14,
    "bb": 20,
    "ema_fast": 50,
    "ema_slow": 200,
    "macd_fast": 12, "macd_slow": 26, "macd_signal": 9,
    "stoch_k": 14, "stoch_d": 3,
    "alligator_jaw": 13, "alligator_teeth": 8, "alligator_lips": 5
}

DAY_CONFIG = {
    "rsi": 7,
    "bb": 20,
    "ema_fast": 9,
    "ema_slow": 21,
    "macd_fast": 8, "macd_slow": 21, "macd_signal": 5,
    "stoch_k": 5, "stoch_d": 3,
    "alligator_jaw": 13, "alligator_teeth": 8, "alligator_lips": 5
}

PAIRS_MAP = {
    'EURUSD': 'EURUSD=X',
    'GBPUSD': 'GBPUSD=X',
    'XAUUSD': 'GC=F',
    'BTCUSD': 'BTC-USD',
    'ETHUSD': 'ETH-USD'
}

def get_analysis(ticker, config, interval):
    try:
        df = yf.download(ticker, period="5d", interval=interval, progress=False)
        if len(df) < 50: return None

        # EMA Crossover
        df['ema_fast'] = ta.ema(df['Close'], length=config['ema_fast'])
        df['ema_slow'] = ta.ema(df['Close'], length=config['ema_slow'])

        # RSI
        df['rsi'] = ta.rsi(df['Close'], length=config['rsi'])

        # Bollinger Bands for SL/TP/BE
        bb = ta.bbands(df['Close'], length=config['bb'], std=2)
        df = df.join(bb)

        # MACD
        macd = ta.macd(df['Close'], fast=config['macd_fast'], slow=config['macd_slow'], signal=config['macd_signal'])
        df = df.join(macd)

        # Stochastic
        stoch = ta.stoch(df['High'], df['Low'], df['Close'], k=config['stoch_k'], d=config['stoch_d'])
        df = df.join(stoch)

        # Alligator
        df['jaw'] = ta.sma(df['Close'], length=config['alligator_jaw'])
        df['teeth'] = ta.sma(df['Close'], length=config['alligator_teeth'])
        df['lips'] = ta.sma(df['Close'], length=config['alligator_lips'])

        last = df.iloc[-1]
        prev = df.iloc[-2]

        # Scoring system
        score = 0
        if last['ema_fast'] > last['ema_slow']: score += 1
        else: score -= 1

        if last['rsi'] > 50: score += 1
        else: score -= 1

        if last['lips'] > last['teeth'] > last['jaw']: score += 1
        elif last['lips'] < last['teeth'] < last['jaw']: score -= 1

        # MACD
        macd_col = [c for c in df.columns if 'MACD_' in c and '_h' not in c and '_s' not in c][0]
        macds_col = [c for c in df.columns if 'MACDs_' in c][0]
        if last[macd_col] > last[macds_col]: score += 1
        else: score -= 1

        # Stochastic
        stoch_k = [c for c in df.columns if 'STOCHk_' in c][0]
        stoch_d = [c for c in df.columns if 'STOCHd_' in c][0]
        if last[stoch_k] > last[stoch_d] and last[stoch_k] < 80: score += 0.5
        if last[stoch_k] < last[stoch_d] and last[stoch_k] > 20: score -= 0.5

        direction = "BUY" if score >= 2 else "SELL" if score <= -2 else "NEUTRAL"

        return {
            "direction": direction,
            "score": score,
            "entry": float(last['Close']),
            "sl": float(last[bb.columns[0]]), # Lower BB for SL if BUY
            "tp": float(last[bb.columns[2]]), # Upper BB for TP if BUY
            "df": df
        }
    except Exception as e:
        print(f"Error {ticker}: {e}")
        return None

def generate_gazelle_signal():
    with app.app_context():
        for pair_name, ticker in PAIRS_MAP.items():
            print(f"Analyzing {pair_name}...")

            # 1. SWING DIRECTION (4h)
            swing = get_analysis(ticker, SWING_CONFIG, "4h")
            if not swing or swing['direction'] == "NEUTRAL": continue

            # 2. DAY TRADING ENTRY (15m) - must align with swing
            day = get_analysis(ticker, DAY_CONFIG, "15m")
            if not day or day['direction']!= swing['direction']: continue

            # 3. CONFIRMED SIGNAL
            entry = day['entry']
            category = 'forex' if 'USD' in pair_name and 'XAU' not in pair_name and 'BTC' not in pair_name else 'gold' if 'XAU' in pair_name else 'crypto'

            # SL/TP from Bollinger logic
            if day['direction'] == 'BUY':
                sl = min(swing['sl'], day['sl'])
                tp = max(swing['tp'], day['tp'])
            else:
                sl = max(swing['sl'], day['sl'])
                tp = min(swing['tp'], day['tp'])

            # Avoid duplicate
            exists = Signal.query.filter_by(pair=pair_name, entry=entry).first()
            if exists: continue

            sig = Signal(
                pair=pair_name,
                type=day['direction'],
                entry=round(entry, 5),
                sl=round(sl, 5),
                tp=round(tp, 5),
                category=category
            )
            db.session.add(sig)
            db.session.commit()
            print(f"✅ SIGNAL: {pair_name} {day['direction']} @ {entry}")

if __name__ == '__main__':
    while True:
        generate_gazelle_signal()
        print("Sleeping 15 mins...")
        time.sleep(900)
