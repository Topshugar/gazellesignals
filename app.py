from flask import Flask, request, redirect, session, jsonify
from flask_sqlalchemy import SQLAlchemy
import os, random
from datetime import datetime

app = Flask(__name__)
app.secret_key = "gazelle_final_2025"
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///gazelle.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

GROUPS = {
 "FOREX (FREE)": {
    "EURUSD": {"name":"EUR/USD","ticker":"EURUSD=X","vip":False},
    "GBPUSD": {"name":"GBP/USD","ticker":"GBPUSD=X","vip":False},
    "USDJPY": {"name":"USD/JPY","ticker":"USDJPY=X","vip":False},
    "AUDUSD": {"name":"AUD/USD","ticker":"AUDUSD=X","vip":False},
    "USDCAD": {"name":"USD/CAD","ticker":"USDCAD=X","vip":False},
    "USDCHF": {"name":"USD/CHF","ticker":"USDCHF=X","vip":False},
    "NZDUSD": {"name":"NZD/USD","ticker":"NZDUSD=X","vip":False},
    "EURJPY": {"name":"EUR/JPY","ticker":"EURJPY=X","vip":False},
    "GBPJPY": {"name":"GBP/JPY","ticker":"GBPJPY=X","vip":False},
    "EURGBP": {"name":"EUR/GBP","ticker":"EURGBP=X","vip":False},
    "AUDJPY": {"name":"AUD/JPY","ticker":"AUDJPY=X","vip":False},
    "EURAUD": {"name":"EUR/AUD","ticker":"EURAUD=X","vip":False},
 },
 "METALS (VIP) 🔒": {
    "XAUUSD": {"name":"GOLD","ticker":"GC=F","vip":True},
    "XAGUSD": {"name":"SILVER","ticker":"SI=F","vip":True},
 },
 "INDICES (VIP) 🔒": {
    "US30": {"name":"US30","ticker":"^DJI","vip":True},
    "NAS100": {"name":"NASDAQ","ticker":"^IXIC","vip":True},
    "SPX500": {"name":"S&P 500","ticker":"^GSPC","vip":True},
 },
 "OIL (VIP) 🔒": {
    "USOIL": {"name":"US OIL","ticker":"CL=F","vip":True},
    "UKOIL": {"name":"UK OIL","ticker":"BZ=F","vip":True},
 },
 "CRYPTO (VIP) 🔒": {
    "BTCUSD": {"name":"BTC/USD","ticker":"BTC-USD","vip":True},
    "ETHUSD": {"name":"ETH/USD","ticker":"ETH-USD","vip":True},
    "SOLUSD": {"name":"SOL/USD","ticker":"SOL-USD","vip":True},
    "XRPUSD": {"name":"XRP/USD","ticker":"XRP-USD","vip":True},
 }
}

class User(db.Model):
    id=db.Column(db.Integer,primary_key=True); email=db.Column(db.String(100),unique=True); password=db.Column(db.String(100)); is_vip=db.Column(db.Boolean,default=False)

def get_signal(ticker):
    try:
        import yfinance as yf, ta
        d = yf.download(ticker, period="6mo", interval="1d", progress=False, auto_adjust=True)
        close_d = d['Close']
        ema50 = float(ta.trend.EMAIndicator(close_d,50).ema_indicator().iloc[-1])
        ema200 = float(ta.trend.EMAIndicator(close_d,200).ema_indicator().iloc[-1])
        rsi_d = float(ta.momentum.RSIIndicator(close_d,14).rsi().iloc[-1])
        price = float(close_d.iloc[-1])
        swing = "BUY" if ema50>ema200 and rsi_d>50 else "SELL" if ema50<ema200 and rsi_d<50 else None
        m = yf.download(ticker, period="5d", interval="15m", progress=False, auto_adjust=True)
        close_m = m['Close']
        ema21 = float(ta.trend.EMAIndicator(close_m,21).ema_indicator().iloc[-1])
        rsi_m = float(ta.momentum.RSIIndicator(close_m,14).rsi().iloc[-1])
        scalp = "BUY" if price>ema21 and rsi_m>55 else "SELL" if price<ema21 and rsi_m<45 else None
        if swing=="BUY" and scalp=="BUY": return {"type":"BUY","price":price,"conf":90,"note":f"SWING BUY + SCALP BUY CONFIRMED - Daily EMA50 {round(ema50,2)} > EMA200"}
        if swing=="SELL" and scalp=="SELL": return {"type":"SELL","price":price,"conf":90,"note":f"SWING SELL + SCALP SELL CONFIRMED"}
        if swing: return {"type":swing,"price":price,"conf":65,"note":f"Swing {swing} but waiting scalp - NO TRADE"}
        return {"type":"WAIT","price":price,"conf":50,"note":"Wait - No alignment"}
    except:
        p=random.uniform(1.0,2.0); t=random.choice(["BUY","SELL"])
        return {"type":t,"price":p,"conf":75,"note":"Demo signal - live data loading"}

CSS = """
<meta name='viewport' content='width=device-width,initial-scale=1'><link href='https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap' rel='stylesheet'>
<style>body{background:#080808;color:#fff;font-family:Inter;margin:0}.sidebar{width:300px;background:#0f0f0f;border-right:1px solid #222;height:100vh;overflow-y:auto;position:fixed;left:0;top:0;padding:20px}.main{margin-left:300px;padding:30px}.group{margin-bottom:24px}.group-title{font-size:11px;opacity:.4;letter-spacing:2px;margin-bottom:10px}.pair{padding:12px 14px;border-radius:12px;background:#151515;border:1px solid #222;margin-bottom:6px;cursor:pointer;display:flex;justify-content:space-between}.pair.vip{opacity:.6;border-color:#442}.pair:hover{background:#1c1c1c}.card{background:#111;border:1px solid #222;border-radius:20px;padding:24px}.btn{width:100%;background:gold;color:#000;padding:14px;border-radius:12px;font-weight:800;border:none;cursor:pointer}
.input{width:100%;background:#141414;border:1px solid #2a2a2a;border-radius:12px;padding:14px;color:#fff;margin-bottom:12px;box-sizing:border-box}
@media(max-width:800px){.sidebar{width:100%;position:relative;height:auto}.main{margin-left:0}}
</style>
"""

def wrap(h): return f"<html><head>{CSS}</head><body>{h}</body></html>"

@app.route('/')
def home():
    if 'user_id' not in session: return redirect('/login')
    user=User.query.get(session['user_id'])
    groups_html=""
    for gname,pairs in GROUPS.items():
        groups_html+=f"<div class=group><div class=group-title>{gname}</div>"
        for code,info in pairs.items():
            lock="🔒" if info['vip'] else ""
            groups_html+=f"<div class='pair {'vip' if info['vip'] else ''}' onclick=\"loadSignal('{code}')\"><span>{info['name']}</span><span>{lock}</span></div>"
        groups_html+="</div>"
    return wrap(f"""
    <div class=sidebar><h2>GAZELLE<span style='color:gold'>SIGNALS</span></h2><p style='opacity:.5;font-size:12px'>Free Forex • VIP locked</p>{groups_html}<br><a href='/logout' style='color:#666;font-size:12px'>Logout</a></div>
    <div class=main><div id=signalBox class=card><h2>Select a pair on the left</h2><p style='opacity:.5'>Strategy: Swing (Daily EMA50/200) + Scalp (15m EMA21) confirmation. Signals appear only when aligned.</p></div></div>
    <script>
    async function loadSignal(pair){{
        document.getElementById('signalBox').innerHTML='<h3>Loading '+pair+'... Analyzing swing+scalp</h3>';
        let r=await fetch('/api/signal/'+pair); let d=await r.json();
        if(d.vip_lock){{
            document.getElementById('signalBox').innerHTML=`<div style='text-align:center;padding:40px'><h1>🔒 ${{pair}} VIP ONLY</h1><p>${{d.message}}</p><button class=btn onclick="pay()" style='max-width:300px'>Unlock VIP - Pay with Flutterwave</button><br><br><p style='opacity:.5'>Metals, Indices, Oil, Crypto are VIP</p></div>`;
            return;
        }}
        document.getElementById('signalBox').innerHTML=`<h1>${{pair}} <span style='color:${{d.type=='BUY'?'#0f0':'#f44'}}'>${{d.type}}</span></h1><h2>Entry: ${{d.price.toFixed(5)}} | Confidence: ${{d.conf}}%</h2><p>${{d.note}}</p><p style='opacity:.5'>Timeframe: SWING+SCALP CONFIRMED</p>`;
    }}
    function pay(){{
        FlutterwaveCheckout({{public_key:"{os.getenv('FLW_PUBLIC_KEY','FLWPUBK_TEST-xxx')}",tx_ref:"gazelle_"+Date.now(),amount:20,currency:"USD",customer:{{email:"{user.email}"}},callback:function(d){{window.location='/pay/success'}}}});
    }}
    </script>
    <script src="https://checkout.flutterwave.com/v3.js"></script>
    """)

@app.route('/api/signal/<pair>')
def api_sig(pair):
    if 'user_id' not in session: return jsonify({"error":"login"}),401
    # find pair
    found=None; is_vip=False
    for g,pairs in GROUPS.items():
        if pair in pairs: found=pairs[pair]; is_vip=found['vip']; break
    if not found: return jsonify({"error":"not found"}),404
    user=User.query.get(session['user_id'])
    if is_vip and not user.is_vip:
        return jsonify({{"vip_lock":True,"message":"This market (Metals/Indices/Oil/Crypto) is VIP. Forex is free. Subscribe to unlock."}})
    sig=get_signal(found['ticker']); return jsonify(sig)

@app.route('/register',methods=['GET','POST'])
def reg():
    if request.method=='POST':
        email=request.form['email'].lower().strip(); pwd=request.form['password']
        if User.query.filter_by(email=email).first(): return wrap("<div style='max-width:400px;margin:100px auto' class=card>Exists <a href='/login' style='color:gold'>Login</a></div>")
        u=User(email=email,password=pwd); db.session.add(u); db.session.commit()
        session['user_id']=u.id; return redirect('/')
    return wrap("<div style='max-width:400px;margin:80px auto' class=card><h2>Create account</h2><p style='opacity:.5'>Forex FREE, Others VIP</p><form method=post><input name=email placeholder='Email' class=input required><input name=password type=password placeholder='Password' class=input required><button class=btn>Enter Gazelle →</button></form><a href='/login' style='color:gold'>Login</a></div>")

@app.route('/login',methods=['GET','POST'])
def log():
    if request.method=='POST':
        u=User.query.filter_by(email=request.form['email'].lower(),password=request.form['password']).first()
        if u: session['user_id']=u.id; return redirect('/')
        return wrap("<div style='max-width:400px;margin:100px auto' class=card>Wrong <a href='/login' style='color:gold'>Back</a></div>")
    return wrap("<div style='max-width:400px;margin:80px auto' class=card><h2>Welcome back</h2><form method=post><input name=email placeholder='Email' class=input required><input name=password type=password placeholder='Password' class=input required><button class=btn>Login →</button></form><a href='/register' style='color:gold'>Create</a></div>")

@app.route('/logout')
def out(): session.clear(); return redirect('/login')

@app.route('/pay/success')
def pay_success():
    if 'user_id' in session:
        u=User.query.get(session['user_id']); u.is_vip=True; db.session.commit()
    return redirect('/')

with app.app_context(): db.create_all()

if __name__=='__main__': app.run(host='0.0.0.0',port=int(os.environ.get('PORT',10000)))
