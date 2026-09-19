import os
from flask import Flask, request, redirect, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'gazelle-real-2024'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///gazelle.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True)
    password_hash = db.Column(db.String(200))
    tier = db.Column(db.String(10), default='FREE')

class Signal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    pair = db.Column(db.String(20))
    type = db.Column(db.String(10))
    entry = db.Column(db.Float)
    sl = db.Column(db.Float)
    tp = db.Column(db.Float)
    is_vip = db.Column(db.Boolean, default=False)

with app.app_context():
    db.create_all()
    if Signal.query.count()==0:
        for p,t,e,sl,tp,v in [('EURUSD','BUY',1.0845,1.082,1.089,False),('GBPUSD','SELL',1.272,1.275,1.267,False),('USDJPY','BUY',149.8,149.3,150.6,False),('XAUUSD','BUY',2025,2015,2045,True),('BTCUSD','SELL',43200,43800,42100,True)]:
            db.session.add(Signal(pair=p,type=t,entry=e,sl=sl,tp=tp,is_vip=v))
        db.session.commit()

def page(body):
    return f"<!DOCTYPE html><html><head><meta name='viewport' content='width=device-width, initial-scale=1'><style>body{{background:#0e0e0e;color:#fff;font-family:Arial;padding:20px;max-width:500px;margin:0 auto}}input{{width:100%;padding:14px;margin:8px 0;border-radius:10px;border:1px solid #333;background:#1c1c1e;color:#fff}}button{{width:100%;padding:14px;background:#FFD700;border:0;border-radius:10px;font-weight:800}} .card{{background:#1c1c1e;border:1px solid #333;border-radius:16px;padding:14px;margin:10px 0}} a{{color:#FFD700}}</style></head><body>{body}</body></html>"

@app.route('/')
def home():
    return page("<h1>GAZELLE SIGNALS</h1><p>Real Trading Strategy</p><a href='/register'><button>Create Free Account</button></a><br><br><a href='/login'>Login</a>")

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method=='POST':
        email=request.form.get('email','').lower().strip()
        pw=request.form.get('password','')
        if User.query.filter_by(email=email).first():
            return page("Email exists <a href='/login'>Login</a>")
        u=User(email=email,password_hash=generate_password_hash(pw))
        db.session.add(u); db.session.commit()
        session['user_id']=u.id
        return redirect('/dashboard')
    return page("<h2>Create Account</h2><form method='POST'><input name='email' placeholder='Email' required><input name='password' type='password' placeholder='Password' required><button>Create Account</button></form><p><a href='/login'>Already have account? Login</a></p>")

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method=='POST':
        email=request.form.get('email','').lower().strip()
        u=User.query.filter_by(email=email).first()
        if u and check_password_hash(u.password_hash, request.form.get('password','')):
            session['user_id']=u.id
            return redirect('/dashboard')
        return page("Invalid login <a href='/login'>Try again</a>")
    return page("<h2>Login</h2><form method='POST'><input name='email' placeholder='Email'><input name='password' type='password' placeholder='Password'><button>Login</button></form>")

@app.route('/dashboard')
def dashboard():
    uid=session.get('user_id')
    if not uid: return redirect('/login')
    u=User.query.get(uid)
    sigs=Signal.query.all()
    free=[s for s in sigs if not s.is_vip]
    html=f"<div style='display:flex;justify-content:space-between'><b>GAZELLE</b><span>{u.tier} | <a href='/logout'>Logout</a></span></div><h3>Live Signals ● LIVE</h3>"
    for s in free:
        html+=f"<div class='card'><b>{s.pair} {s.type}</b><br>Entry: {s.entry} | SL: {s.sl} | TP: {s.tp}<br><small>Score 87%</small></div>"
    if u.tier!='VIP':
        html+="<div style='background:gold;color:#000;padding:15px;border-radius:12px;text-align:center;margin-top:20px'><b>Unlock VIP Gold & Crypto</b><br><a href='/upgrade'><button style='background:#000;color:gold;margin-top:10px'>Upgrade $29</button></a></div>"
    else:
        for s in sigs:
            if s.is_vip:
                html+=f"<div class='card' style='border-color:gold'><b>{s.pair} {s.type} VIP</b><br>Entry: {s.entry} | SL: {s.sl} | TP: {s.tp}</div>"
    return page(html)

@app.route('/upgrade')
def upgrade():
    return page("<h2>VIP $29/mo</h2><p>Unlock all signals</p><button onclick=\"fetch('/verify-payment',{method:'POST'}).then(()=>location='/dashboard')\">Simulate Payment (Test)</button>")

@app.route('/verify-payment', methods=['POST'])
def verify():
    u=User.query.get(session.get('user_id')); u.tier='VIP'; db.session.commit()
    return jsonify({"status":"success"})

@app.route('/logout')
def logout():
    session.clear(); return redirect('/')
