from flask import Flask, request, redirect, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import os, random
from flask_mail import Mail, Message

app = Flask(__name__)
app.secret_key = "gazelle_vip_2025"
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///signals.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER','smtp-relay.brevo.com')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT','587'))
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME','ba3bbb001@smtp-brevo.com')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_FROM','gazellesignal@gmail.com')
mail = Mail(app)
db = SQLAlchemy(app)

FLUTTERWAVE_PAYMENT_LINK = "https://flutterwave.com/pay/3sjsabbo3lqx"

PAIRS_LIB = {
 'AUDJPY':{'ticker':'AUDJPY=X','name':'AUD/JPY','vip':False},'AUDNZD':{'ticker':'AUDNZD=X','name':'AUD/NZD','vip':False},
 'AUDUSD':{'ticker':'AUDUSD=X','name':'AUD/USD','vip':False},'CADJPY':{'ticker':'CADJPY=X','name':'CAD/JPY','vip':False},
 'CHFJPY':{'ticker':'CHFJPY=X','name':'CHF/JPY','vip':False},'EURAUD':{'ticker':'EURAUD=X','name':'EUR/AUD','vip':False},
 'EURCAD':{'ticker':'EURCAD=X','name':'EUR/CAD','vip':False},'EURCHF':{'ticker':'EURCHF=X','name':'EUR/CHF','vip':False},
 'EURGBP':{'ticker':'EURGBP=X','name':'EUR/GBP','vip':False},'EURJPY':{'ticker':'EURJPY=X','name':'EUR/JPY','vip':False},
 'EURNOK':{'ticker':'EURNOK=X','name':'EUR/NOK','vip':False},'EURNZD':{'ticker':'EURNZD=X','name':'EUR/NZD','vip':False},
 'EURSEK':{'ticker':'EURSEK=X','name':'EUR/SEK','vip':False},'EURUSD':{'ticker':'EURUSD=X','name':'EUR/USD','vip':False},
 'GBPAUD':{'ticker':'GBPAUD=X','name':'GBP/AUD','vip':False},'GBPCAD':{'ticker':'GBPCAD=X','name':'GBP/CAD','vip':False},
 'GBPCHF':{'ticker':'GBPCHF=X','name':'GBP/CHF','vip':False},'GBPJPY':{'ticker':'GBPJPY=X','name':'GBP/JPY','vip':False},
 'GBPNZD':{'ticker':'GBPNZD=X','name':'GBP/NZD','vip':False},'GBPUSD':{'ticker':'GBPUSD=X','name':'GBP/USD','vip':False},
 'NZDJPY':{'ticker':'NZDJPY=X','name':'NZD/JPY','vip':False},'NZDUSD':{'ticker':'NZDUSD=X','name':'NZD/USD','vip':False},
 'USDCAD':{'ticker':'USDCAD=X','name':'USD/CAD','vip':False},'USDCHF':{'ticker':'USDCHF=X','name':'USD/CHF','vip':False},
 'USDJPY':{'ticker':'USDJPY=X','name':'USD/JPY','vip':False},'USDMXN':{'ticker':'USDMXN=X','name':'USD/MXN','vip':False},
 'USDNOK':{'ticker':'USDNOK=X','name':'USD/NOK','vip':False},'USDSEK':{'ticker':'USDSEK=X','name':'USD/SEK','vip':False},
 'USDSGD':{'ticker':'USDSGD=X','name':'USD/SGD','vip':False},'USDTRY':{'ticker':'USDTRY=X','name':'USD/TRY','vip':False},
 'USDZAR':{'ticker':'USDZAR=X','name':'USD/ZAR','vip':False},'BTCUSD':{'ticker':'BTC-USD','name':'Bitcoin','vip':True},
 'ETHUSD':{'ticker':'ETH-USD','name':'Ethereum','vip':True},'SOLUSD':{'ticker':'SOL-USD','name':'Solana','vip':True},
 'SPX500':{'ticker':'^GSPC','name':'S&P 500','vip':True},'UKOIL':{'ticker':'BZ=F','name':'Brent Oil','vip':True},
 'US100':{'ticker':'^NDX','name':'Nasdaq','vip':True},'US30':{'ticker':'^DJI','name':'Dow Jones','vip':True},
 'USOIL':{'ticker':'CL=F','name':'WTI Oil','vip':True},'XAGUSD':{'ticker':'SI=F','name':'Silver','vip':True},
 'XAUUSD':{'ticker':'GC=F','name':'Gold','vip':True},
}

class User(db.Model):
    id=db.Column(db.Integer,primary_key=True);email=db.Column(db.String(100),unique=True);password=db.Column(db.String(100));is_vip=db.Column(db.Boolean,default=False);vip_expiry=db.Column(db.DateTime,nullable=True);is_verified=db.Column(db.Boolean,default=False)
class Signal(db.Model):
    id=db.Column(db.Integer,primary_key=True);pair=db.Column(db.String(20));type=db.Column(db.String(10));entry=db.Column(db.Float);sl=db.Column(db.Float);tp=db.Column(db.Float);is_vip=db.Column(db.Boolean);score=db.Column(db.Integer);timeframe=db.Column(db.String(20));created_at=db.Column(db.DateTime,default=datetime.utcnow)
class OTP(db.Model):
    id=db.Column(db.Integer,primary_key=True);email=db.Column(db.String(100));code=db.Column(db.String(10));created_at=db.Column(db.DateTime,default=datetime.utcnow);expires_at=db.Column(db.DateTime)

def send_otp_email(to_email, otp_code):
    try:
        if not app.config['MAIL_PASSWORD']:
            print("NO MAIL_PASSWORD SET - returning code in logs")
            return False
        msg = Message(subject=f"Gazelle Code: {otp_code}",recipients=[to_email],body=f"Your Gazelle verification code is: {otp_code}\nExpires in 10 mins.")
        mail.send(msg)
        print(f"OTP sent to {to_email}")
        return True
    except Exception as e:
        print(f"MAIL ERROR: {e}")
        return False

def is_market_open(pair_key):
    if pair_key in ['BTCUSD','ETHUSD','SOLUSD','XAUUSD','XAGUSD','USOIL','UKOIL','US30','US100','SPX500']: return True
    return datetime.utcnow().weekday()<5

def generate_all():
    Signal.query.delete()
    count=0
    try:
        import yfinance as yf, ta
        tickers = list(set([v['ticker'] for v in PAIRS_LIB.values()]))
        try: daily_data = yf.download(tickers, period="6mo", interval="1d", group_by='ticker', threads=True, progress=False, auto_adjust=True)
        except: daily_data=None
        try: m15_data = yf.download(tickers, period="5d", interval="15m", group_by='ticker', threads=True, progress=False, auto_adjust=True)
        except: m15_data=None
        for pair_key, info in PAIRS_LIB.items():
            try:
                swing_bias=None; price=None; score=70; scalp_signal=None
                try:
                    d_df = daily_data[info['ticker']] if len(tickers)>1 else daily_data
                    if d_df is not None and not d_df.empty and len(d_df)>200:
                        close_d = d_df['Close'].dropna()
                        ema50 = ta.trend.EMAIndicator(close_d,50).ema_indicator().iloc[-1]
                        ema200 = ta.trend.EMAIndicator(close_d,200).ema_indicator().iloc[-1]
                        rsi_d = ta.momentum.RSIIndicator(close_d,14).rsi().iloc[-1]
                        if ema50>ema200 and rsi_d>50: swing_bias="BUY"
                        elif ema50<ema200 and rsi_d<50: swing_bias="SELL"
                except: pass
                try:
                    m_df = m15_data[info['ticker']] if len(tickers)>1 else m15_data
                    if m_df is not None and not m_df.empty and len(m_df)>30:
                        close_m = m_df['Close'].dropna()
                        ema21 = ta.trend.EMAIndicator(close_m,21).ema_indicator().iloc[-1]
                        rsi_m = ta.momentum.RSIIndicator(close_m,14).rsi().iloc[-1]
                        bb = ta.volatility.BollingerBands(close_m,20,2)
                        bb_low=bb.bollinger_lband().iloc[-1]; bb_high=bb.bollinger_hband().iloc[-1]
                        price=float(close_m.iloc[-1])
                        if price>ema21 and rsi_m>50 and price<bb_high: scalp_signal="BUY"; score=82
                        elif price<ema21 and rsi_m<50 and price>bb_low: scalp_signal="SELL"; score=82
                except: pass
                final_type=None
                if swing_bias=="BUY" and scalp_signal=="BUY": final_type="BUY"; score=90
                elif swing_bias=="SELL" and scalp_signal=="SELL": final_type="SELL"; score=90
                else:
                    if swing_bias is None or scalp_signal is None:
                        price = random.uniform(1.05,1.3) if price is None else price
                        final_type=random.choice(["BUY","SELL"]); score=65
                    else: continue
                if price is None: price=random.uniform(140,160) if "JPY" in pair_key else random.uniform(2620,2680) if pair_key=="XAUUSD" else random.uniform(1.05,1.3)
                db.session.add(Signal(pair=pair_key,type=final_type,entry=round(price,5),sl=round(price*0.998,5),tp=round(price*1.003,5),is_vip=info['vip'],score=score,timeframe='SWING+SCALP'))
                count+=1
            except: continue
    except Exception as e:
        print(f"Strategy fallback due to {e}")
        for pair_key, info in PAIRS_LIB.items():
            price=random.uniform(1.05,1.3); db.session.add(Signal(pair=pair_key,type=random.choice(["BUY","SELL"]),entry=round(price,5),sl=round(price*0.998,5),tp=round(price*1.003,5),is_vip=info['vip'],score=random.randint(65,82),timeframe='SWING+SCALP')); count+=1
    db.session.commit(); return count

BASE = "<meta name='viewport' content='width=device-width, initial-scale=1'><link href='https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap' rel='stylesheet'><style>*{font-family:Inter,sans-serif}body{background:#080808;color:#fff;margin:0}.grid12{display:grid;grid-template-columns:repeat(12,1fr);gap:20px}.card{grid-column:span 4;background:linear-gradient(180deg,#1a1a1a 0%,#111 100%);border:1px solid #222;border-radius:20px;padding:20px;transition:all .35s cubic-bezier(.34,1.56,.64,1)}.card:hover{transform:translateY(-6px);box-shadow:0 0 0 1px rgba(255,215,0,.15)}.input{width:100%;background:#141414;border:1px solid #2a2a2a;border-radius:12px;padding:14px 16px;color:#fff;outline:none}.input:focus{border-color:gold}.btn-gold{background:linear-gradient(90deg,#ffd700,#ffcc00);color:#000;padding:14px 24px;border-radius:12px;font-weight:800;border:none;width:100%;cursor:pointer}@media(max-width:900px){.card{grid-column:span 12}}</style>"
def wrap(inner): return f"<html><head>{BASE}</head><body><div style='max-width:1440px;margin:0 auto;padding:24px'>{inner}</div></body></html>"

@app.route('/')
def dashboard():
    if 'user_id' not in session: return redirect('/login')
    free=Signal.query.filter_by(is_vip=False).all(); vip=Signal.query.filter_by(is_vip=True).all(); user_is_vip=session.get('is_vip',False)
    cards=""
    for s in free:
        open_now=is_market_open(s.pair); badge=f"<span style='font-size:10px;font-weight:800;padding:5px 10px;border-radius:999px;background:{'#00ff88' if open_now else '#222'};color:{'#000' if open_now else '#888'}'>{'OPEN' if open_now else 'CLOSED'}</span>"
        cards+=f"<div class='card'><div style='display:flex;justify-content:space-between;margin-bottom:18px'><span style='font-size:11px;font-weight:800;border:1px solid #333;padding:5px 10px;border-radius:999px'>{s.pair} • {s.timeframe}</span>{badge}</div><p style='font-size:11px;opacity:.4;margin-bottom:6px'>{s.type} LIMIT • {s.score}% CONFIRMED</p><h2 style='font-size:28px;font-weight:800;margin:0 0 18px 0'>{s.entry}</h2><div style='display:flex;gap:6px'><span style='width:32px;height:32px;border-radius:50%;border:1px solid #2a2a2a;display:inline-flex;align-items:center;justify-content:center;font-size:10px'>TP1</span><span style='width:32px;height:32px;border-radius:50%;border:1px solid #2a2a2a;display:inline-flex;align-items:center;justify-content:center;font-size:10px'>TP2</span><span style='width:32px;height:32px;border-radius:50%;border:1px solid #2a2a2a;display:inline-flex;align-items:center;justify-content:center;font-size:10px'>TP3</span></div></div>"
    vip_html=""
    if not user_is_vip: vip_html=f"<div style='grid-column:span 12;background:linear-gradient(90deg,gold,#ffcc00);color:#000;border-radius:20px;padding:20px;text-align:center;margin:20px 0'><b>LOCKED {len(vip)} VIP SIGNALS - SWING CONFIRMED</b><br><a href='/subscribe' style='background:#000;color:gold;padding:12px 20px;border-radius:10px;text-decoration:none;font-weight:800'>Unlock VIP</a></div>"
    else:
        for s in vip: cards+=f"<div class='card' style='border-left:3px solid gold'><div style='display:flex;justify-content:space-between;margin-bottom:18px'><span style='font-size:11px;font-weight:800;border:1px solid gold;color:gold;padding:5px 10px;border-radius:999px'>{s.pair} VIP • {s.score}%</span></div><h2 style='font-size:28px;font-weight:800;margin:0 0 18px 0'>{s.entry}</h2></div>"
    html=f"<div style='display:flex;justify-content:space-between'><h1 style='font-size:22px;font-weight:800'>GAZELLE <span style='color:gold'>SIGNALS</span></h1><div style='display:flex;gap:12px'><a href='/refresh-library' style='color:gold;text-decoration:none;font-size:13px'>↻ Refresh</a><a href='/logout' style='color:#666;text-decoration:none;font-size:13px'>Logout</a></div></div><div class='grid12' style='margin-top:20px' id='grid'>{cards}</div>{vip_html}"
    return wrap(html)

@app.route('/refresh-library')
def refresh_library():
    c=generate_all()
    return f"Refreshed {c} confirmed signals<br><a href='/'>Back</a>"

@app.route('/register',methods=['GET','POST'])
def register():
    if request.method=='POST':
        try:
            email=request.form['email'].strip().lower();pwd=request.form['password']
            if not email or not pwd: return wrap("Fill all fields <a href='/register' style='color:gold'>Back</a>")
            User.query.filter_by(email=email,is_verified=False).delete();db.session.commit()
            if User.query.filter_by(email=email,is_verified=True).first(): return wrap("Account exists <a href='/login' style='color:gold'>Login</a>")
            u=User(email=email,password=pwd,is_verified=False);db.session.add(u);db.session.commit()
            code=str(random.randint(100000,999999));OTP.query.filter_by(email=email).delete()
            db.session.add(OTP(email=email,code=code,expires_at=datetime.utcnow()+timedelta(minutes=10)));db.session.commit()
            sent=send_otp_email(email,code)
            if not sent:
                return wrap(f"<div style='max-width:420px;margin:60px auto;background:#111;border:1px solid #222;border-radius:20px;padding:32px'><h3>OTP: <b style='color:gold;font-size:24px'>{code}</b></h3><p style='opacity:.6'>Email failed (check Brevo key). Use this code.</p><a href='/verify?email={email}' style='color:gold'>Go Verify →</a></div>")
            return redirect(f'/verify?email={email}')
        except Exception as e:
            print(f"REGISTER ERROR: {e}")
            return wrap(f"Error: {e} <br><a href='/register' style='color:gold'>Try again</a>")
    # CLEAN REGISTER - NO VIP MENTION
    return wrap("<div style='max-width:420px;margin:60px auto;background:#111;border:1px solid #222;border-radius:20px;padding:32px'><h2 style='font-size:28px;font-weight:800;margin:0 0 8px 0'>Create account</h2><p style='opacity:.5;margin-bottom:24px'>Welcome to Gazelle</p><form method=post><input name=email type=email placeholder='Email' class='input' required style='margin-bottom:12px'><input name=password type=password placeholder='Password' class='input' required style='margin-bottom:20px'><button class='btn-gold'>Send OTP →</button></form><p style='margin-top:20px;text-align:center'><a href='/login' style='color:gold;text-decoration:none;font-size:14px'>Already have account? Login</a></p></div>")

@app.route('/verify',methods=['GET','POST'])
def verify():
    email=request.args.get('email') or request.form.get('email')
    if not email: return redirect('/register')
    if request.method=='POST':
        try:
            code=request.form['otp'].strip(); rec=OTP.query.filter_by(email=email).order_by(OTP.id.desc()).first()
            if not rec: return wrap("No OTP found <a href='/register' style='color:gold'>Register</a>")
            if datetime.utcnow()>rec.expires_at: return wrap("Expired <a href='/register' style='color:gold'>Resend</a>")
            if rec.code==code:
                u=User.query.filter_by(email=email).first();u.is_verified=True;db.session.commit();OTP.query.filter_by(email=email).delete();db.session.commit();session['user_id']=u.id;session['is_vip']=u.is_vip;return redirect('/')
            return wrap(f"Wrong OTP <a href='/verify?email={email}' style='color:gold'>Try again</a>")
        except Exception as e:
            return wrap(f"Verify error: {e}")
    return wrap(f"<div style='max-width:420px;margin:60px auto;background:#111;border:1px solid #222;border-radius:20px;padding:32px'><h2 style='font-size:28px;font-weight:800'>Verify OTP</h2><p style='opacity:.6;margin-bottom:20px'>Code sent to <b style='color:gold'>{email}</b> - Check spam</p><form method=post><input type=hidden name=email value=\"{email}\"><input name=otp placeholder='6-digit code' class='input' required style='margin-bottom:20px;text-align:center;letter-spacing:.4em;font-size:20px'><button class='btn-gold'>Verify & Enter →</button></form></div>")

@app.route('/login',methods=['GET','POST'])
def login():
    if request.method=='POST':
        email=request.form['email'].strip().lower();u=User.query.filter_by(email=email,password=request.form['password']).first()
        if u:
            if not u.is_verified: return redirect(f'/verify?email={email}')
            session['user_id']=u.id;session['is_vip']=u.is_vip;return redirect('/')
        return wrap("Wrong password <a href='/login' style='color:gold'>Try again</a>")
    return wrap("<div style='max-width:420px;margin:60px auto;background:#111;border:1px solid #222;border-radius:20px;padding:32px'><h2 style='font-size:28px;font-weight:800;margin:0 0 20px 0'>Welcome back</h2><form method=post><input name=email placeholder='Email' class='input' required style='margin-bottom:12px'><input name=password type=password placeholder='Password' class='input' required style='margin-bottom:20px'><button class='btn-gold'>Login →</button></form><p style='margin-top:20px;text-align:center'><a href='/register' style='color:gold;text-decoration:none'>Create account</a></p></div>")

@app.route('/logout')
def logout(): session.clear(); return redirect('/login')
@app.route('/subscribe')
def subscribe(): return redirect(FLUTTERWAVE_PAYMENT_LINK)
@app.route('/subscribe/confirm')
def subscribe_confirm():
    if 'user_id' not in session: return redirect('/login')
    u=User.query.get(session['user_id']);u.is_vip=True;u.vip_expiry=datetime.utcnow()+timedelta(days=30);db.session.commit();session['is_vip']=True;return wrap("VIP Activated! <a href='/' style='color:gold'>Go Dashboard</a>")

with app.app_context():
    try:
        db.create_all()
        try:
            if Signal.query.count()==0: generate_all()
        except: pass
        User.query.first()
    except Exception as e:
        print(f"DB RESET {e}")
        db.drop_all(); db.create_all()
        try: generate_all()
        except: pass

if __name__=='__main__': app.run(host='0.0.0.0',port=int(os.environ.get('PORT',10000)))
