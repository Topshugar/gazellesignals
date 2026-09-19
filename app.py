# File: app.py
import os
from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'gazelle-signals-2026-secret'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///gazelle.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# FLUTTERWAVE PUBK - safe for frontend
FLW_PUBK = "FLWPUBK-680c2f65a0795c23ac1ad8f6aabe4e4c-X"
VIP_PRICE = 10

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    tier = db.Column(db.String(10), default='FREE')
    telegram_id = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Signal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    pair = db.Column(db.String(20), nullable=False)
    type = db.Column(db.String(10), nullable=False)
    entry = db.Column(db.String(20))
    sl = db.Column(db.String(20))
    tp = db.Column(db.String(20))
    category = db.Column(db.String(20), default='forex')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    amount = db.Column(db.Float, default=10.0)
    status = db.Column(db.String(20), default='PENDING')
    reference = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

with app.app_context():
    db.create_all()

@app.route('/')
def index():
    return render_template('index.html', pubk=FLW_PUBK)

if __name__ == '__main__':
    app.run(debug=True)
