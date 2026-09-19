import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime

PAIRS = {
    'EURUSD': 'EURUSD=X',
    'GBPUSD': 'GBPUSD=X', 
    'USDJPY': 'JPY=X',
    'XAUUSD': 'GC=F',
    'BTCUSD': 'BTC-USD'
}

def get_data(symbol, period='1mo', interval='1h'): # swing = 1h
    try:
        df = yf.download(symbol, period=period, interval=interval, progress=False)
        if df.empty: return None
        return df
    except:
        return None

def calc_indicators(df):
    close = df['Close']
    
    # EMA 50 & 200 crossover
    df['EMA50'] = close.ewm(span=50).mean()
    df['EMA200'] = close.ewm(span=200).mean()
    
    # RSI 14
    delta = close.diff()
    gain = delta.where(delta>0,0).rolling(14).mean()
    loss = -delta.where(delta<0,0).rolling(14).mean()
    rs = gain/loss
    df['RSI'] = 100 - (100/(1+rs))
    
    # Bollinger 20,2
    df['BB_MA'] = close.rolling(20).mean()
    df['BB_STD'] = close.rolling(20).std()
    df['BB_UP'] = df['BB_MA'] + 2*df['BB_STD']
    df['BB_LOW'] = df['BB_MA'] - 2*df['BB_STD']
    
    # MACD 12,26,9
    ema12 = close.ewm(span=12).mean()
    ema26 = close.ewm(span=26).mean()
    df['MACD'] = ema12 - ema26
    df['MACD_SIG'] = df['MACD'].ewm(span=9).mean()
    
    # Stochastic 14,3,3
    low14 = df['Low'].rolling(14).min()
    high14 = df['High'].rolling(14).max()
    df['%K'] = (close - low14)/(high14-low14)*100
    df['%D'] = df['%K'].rolling(3).mean()
    
    # Alligator - Jaw 13, Teeth 8, Lips 5
    df['JAW'] = close.ewm(span=13).mean().shift(8)
    df['TEETH'] = close.ewm(span=8).mean().shift(5)
    df['LIPS'] = close.ewm(span=5).mean().shift(3)
    
    return df

def get_direction_score(df):
    if df is None or len(df) < 200: return 0, None
    last = df.iloc[-1]
    
    score = 0
    # EMA
    if last['EMA50'] > last['EMA200']: score += 1
    else: score -= 1
    # RSI
    if last['RSI'] > 55: score += 1
    elif last['RSI'] < 45: score -= 1
    # MACD
    if last['MACD'] > last['MACD_SIG']: score += 1
    else: score -= 1
    # Stochastic
    if last['%K'] > last['%D'] and last['%K'] < 80: score += 1
    elif last['%K'] < last['%D'] and last['%K'] > 20: score -= 1
    # Alligator
    if last['LIPS'] > last['TEETH'] > last['JAW']: score += 1
    elif last['LIPS'] < last['TEETH'] < last['JAW']: score -= 1
    
    return score, last

def generate_signal():
    signals = []
    for pair, yf_symbol in PAIRS.items():
        # SWING - 1h chart determines direction
        df_swing = get_data(yf_symbol, period='2mo', interval='1h')
        if df_swing is None: continue
        df_swing = calc_indicators(df_swing)
        score, last = get_direction_score(df_swing)
        
        if abs(score) < 2: # no strong direction
            continue
            
        direction = 'BUY' if score > 0 else 'SELL'
        
        # TP/SL/BE from Bollinger
        entry = float(last['Close'])
        if direction == 'BUY':
            sl = float(last['BB_LOW'])
            tp = float(last['BB_UP'])
        else:
            sl = float(last['BB_UP'])
            tp = float(last['BB_LOW'])
        
        # BE = BB middle
        be = float(last['BB_MA'])
        
        signals.append({
            'pair': pair,
            'type': direction,
            'entry': round(entry, 5),
            'tp': round(tp, 5),
            'sl': round(sl, 5),
            'be': round(be, 5),
            'score': score,
            'is_vip': False if abs(score) < 3 else True, # strong confluence = VIP
            'timeframe': 'Swing→Day→Scalp'
        })
    return signals
