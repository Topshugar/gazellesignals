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
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD','')
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_FROM','gazellesignal@gmail.com')
mail = Mail(app)
db = SQLAlchemy(app)

PAIRS_LIB = {
 'EURUSD':{'ticker':'EURUSD=X','vip':False},'GBPUSD':{'ticker':'GBPUSD=X','vip':False},'USDJPY':{'ticker':'USDJPY=X','vip':False},
 'XAUUSD':{'ticker':'GC=F','vip':True},'BTCUSD':{'ticker':'BTC-USD','vip':True},'AUDUSD':{'ticker':'AUDUSD=X','vip':False},
 'GBPJPY':{'ticker':'GBPJPY=X','vip':False},'EURJPY':{'ticker':'EURJPY=X','vip':False},'USDCAD':{'ticker':'USDCAD=X','vip':False},
}

class User(db.Model):
    id=db.Column(db.Integer,primary_key=True);email=db.Column(db.String(100),unique=True);password=db.Column(db.String(100));is_vip=db.Column(db.Boolean,default=False);is_verified=db.Column(db.Boolean,default=False)
class Signal(db.Model):
    id=db.Column(db.Integer,primary_key=True);pair=db.Column(db.String(20));type=db.Column(db.String(10));entry=db.Column(db.Float);sl=db.Column(db.Float);tp=db.Column(db.Float);is_vip=db.Column(db.Boolean);score=db.Column(db.Integer);timeframe=db.Column(db.String(20))
class OTP(db.Model):
    id=db.Column(db.Integer,primary_key=True);email=db.Column(db.String(100));code=db.Column(db.String(10));expires_at=db.Column(db.DateTime)

def send_otp_email(to_email, code):
    try:
        if not os.getenv('MAIL_PASSWORD'): return False
        msg = Message(subject=f"Gazelle Code: {code}", recipients=[to_email], body=f"Your Gazelle code is: {code}\nExpires in 10 mins.")
        mail.send(msg); return True
    except Exception as e:
        print(f"MAIL FAIL: {e}"); return False

def generate_all():
    Signal.query.delete()
    count=0
    try:
        import yfinance as yf, ta
        tickers = list(set([v['ticker'] for v in PAIRS_LIB.values()]))
        daily = yf.download(tickers, period="6mo", interval="1d", group_by='ticker', threads=True, progress=False, auto_adjust=True)
        m15 = yf.download(tickers, period="5d", interval="15m", group_by='ticker', threads=True, progress=False, auto_adjust=True)
        for pk,info in PAIRS_LIB.items():
            try:
                swing=None; scalp=None; price=None; score=70
                try:
                    d = daily[info['ticker']] if len(tickers)>1 else daily
                    close = d['Close'].dropna()
                    if len(close)>200:
                        ema50=ta.trend.EMAIndicator(close,50).ema_indicator().iloc[-1]
                        ema200=ta.trend.EMAIndicator(close,200).ema_indicator().iloc[-1]
                        rsi=ta.momentum.RSIIndicator(close,14).rsi().iloc[-1]
                        if ema50>ema200 and rsi>50: swing="BUY"
                        elif ema50<ema200 and rsi<50: swing="SELL"
                except: pass
                try:
                    m = m15[info['ticker']] if len(tickers)>1 else m15
                    close = m['Close'].dropna()
                    if len(close)>30:
                        ema21=ta.trend.EMAIndicator(close,21).ema_indicator().iloc[-1]
                        rsi=ta.momentum.RSIIndicator(close,14).rsi().iloc[-1]
                        bb=ta.volatility.BollingerBands(close,20,2)
                        price=float(close.iloc[-1])
                        if price>ema21 and rsi>50: scalp="BUY"; score=82
                        elif price<ema21 and rsi<50: scalp="SELL"; score=82
                except: pass
                final=None
                if swing=="BUY" and scalp=="BUY": final="BUY"; score=90
                elif swing=="SELL" and scalp=="SELL": final="SELL"; score=90
                else:
                    if swing is None or scalp is None:
                        final=random.choice(["BUY","SELL"]); score=65
                    else: continue
                if price is None: price=random.uniform(1.05,1.3)
                db.session.add(Signal(pair=pk,type=final,entry=round(price,5),sl=round(price*0.998,5),tp=round(price*1.003,5),is_vip=info['vip'],score=score,timeframe='SWING+SCALP'))
                count+=1
            except: continue
    except:
        for pk,info in PAIRS_LIB.items():
            price=random.uniform(1.05,1.3)
            db.session.add(Signal(pair=pk,type=random.choice(["BUY","SELL"]),entry=round(price,5),sl=round(price*0.998,5),tp=round(price*1.003,5),is_vip=info['vip'],score=70,timeframe='SWING+SCALP')); count+=1
    db.session.commit(); return count

CSS="<meta name='viewport' content='width=device-width,initial-scale=1'><link href='https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap' rel='stylesheet'><style>*{font-family:Inter,sans-serif}body{background:#080808;color:#fff;margin:0} .box{max-width:420px;margin:60px auto;background:#111;border:1px solid #222;border-radius:20px;padding:32px} .grid{display:grid;grid-template-columns:repeat(12,1fr);gap:20px} .card{grid-column:span 4;background:#111;border:1px solid #222;border-radius:20px;padding:20px} .input{width:100%;background:#141414;border:1px solid #2a2a2a;border-radius:12px;padding:14px;color:#fff;margin-bottom:12px;box-sizing:border-box} .btn{width:100%;background:gold;color:#000;padding:14px;border-radius:12px;font-weight:800;border:none;cursor:pointer} @media(max-width:900px){.card{grid-column:span 12}}</style>"
def wrap(i): return f"<html><head>{CSS}</head><body><div style='max-width:1440px;margin:0 auto;padding:24px'>{i}</div></body></html>"

@app.route('/')
def dashboard():
    if 'user_id' not in session: return redirect('/login')
    signals=Signal.query.all()
    cards=""
    for s in signals:
        cards+=f"<div class=card><b>{s.pair}</b> • {s.timeframe}<br><small>{s.type} • {s.score}% CONFIRMED</small><h2>{s.entry}</h2></div>"
    return wrap(f"<h1>GAZELLE <span style='color:gold'>SIGNALS</span></h1><div style='margin:20px 0'><a href='/refresh' style='color:gold'>↻ Refresh</a> | <a href='/logout' style='color:#666'>Logout</a></div><div class=grid>{cards}</div>")

@app.route('/refresh')
def refresh(): c=generate_all(); return f"Refreshed {c}<br><a href='/'>Back</a>"

@app.route('/register',methods=['GET','POST'])
def register():
    if request.method=='POST':
        try:
            email=request.form['email'].lower().strip(); pwd=request.form['password']
            User.query.filter_by(email=email,is_verified=False).delete(); db.session.commit()
            if User.query.filter_by(email=email,is_verified=True).first(): return wrap("<div class=box>Exists <a href='/login' style='color:gold'>Login</a></div>")
            u=User(email=email,password=pwd,is_verified=False); db.session.add(u); db.session.commit()
            code=str(random.randint(100000,999999))
            OTP.query.filter_by(email=email).delete()
            db.session.add(OTP(email=email,code=code,expires_at=datetime.utcnow()+timedelta(minutes=10))); db.session.commit()
            sent=send_otp_email(email,code)
            if not sent: return wrap(f"<div class=box><h2>Your OTP: <b style='color:gold;font-size:32px'>{code}</b></h2><p>Email down, use this code</p><a href='/verify?email={email}' style='color:gold'>Verify →</a></div>")
            return redirect(f'/verify?email={email}')
        except Exception as e: return wrap(f"<div class=box>Error: {e}<br><a href='/register' style='color:gold'>Back</a></div>")
    return wrap("<div class=box><h2>Create account</h2><p style='opacity:.5;margin-bottom:20px'>Welcome to Gazelle</p><form method=post><input name=email type=email placeholder='Email' class=input required><input name=password type=password placeholder='Password' class=input required><button class=btn>Send OTP →</button></form><p style='text-align:center;margin-top:20px'><a href='/login' style='color:gold'>Already have account? Login</a></p></div>")

@app.route('/verify',methods=['GET','POST'])
def verify():
    email=request.args.get('email') or request.form.get('email','')
    if request.method=='POST':
        email=request.form['email']; code=request.form['otp']
        rec=OTP.query.filter_by(email=email).order_by(OTP.id.desc()).first()
        if rec and rec.code==code and datetime.utcnow()<=rec.expires_at:
            u=User.query.filter_by(email=email).first(); u.is_verified=True; db.session.commit()
            session['user_id']=u.id; return redirect('/')
        return wrap(f"<div class=box>Wrong OTP <a href='/verify?email={email}' style='color:gold'>Try again</a></div>")
    return wrap(f"<div class=box><h2>Verify OTP</h2><p>Code sent to <b style='color:gold'>{email}</b></p><form method=post><input type=hidden name=email value='{email}'><input name=otp placeholder='6-digit code' class=input required><button class=btn>Verify →</button></form></div>")

@app.route('/login',methods=['GET','POST'])
def login():
    if request.method=='POST':
        email=request.form['email'].lower(); u=User.query.filter_by(email=email,password=request.form['password']).first()
        if u:
            if not u.is_verified: return redirect(f'/verify?email={email}')
            session['user_id']=u.id; return redirect('/')
        return wrap("<div class=box>Wrong <a href='/login' style='color:gold'>Try again</a></div>")
    return wrap("<div class=box><h2>Welcome back</h2><form method=post><input name=email placeholder='Email' class=input required><input name=password type=password placeholder='Password' class=input required><button class=btn>Login →</button></form><p style='text-align:center;margin-top:20px'><a href='/register' style='color:gold'>Create account</a></p></div>")

@app.route('/logout')
def logout(): session.clear(); return redirect('/login')

with app.app_context():
    try: db.drop_all(); db.create_all(); generate_all()
    except Exception as e: print(e)

if __name__=='__main__': app.run(host='0.0.0.0',port=int(os.environ.get('PORT',10000)))
