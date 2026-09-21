"""Persistent signal lifecycle helpers for Gazelle Signals.

Prototype-only service layer. The Flask app should call ``refresh_signal`` before
rendering a market page and expose ``signal_history`` for completed trades.
"""
from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Signal(db.Model):
    """One persisted signal, including its terminal outcome."""

    __tablename__ = "signals"
    id = db.Column(db.Integer, primary_key=True)
    symbol = db.Column(db.String(40), nullable=False, index=True)
    direction = db.Column(db.String(4), nullable=False)  # BUY or SELL
    entry = db.Column(db.Float, nullable=False)
    tp1 = db.Column(db.Float, nullable=False)
    tp2 = db.Column(db.Float, nullable=False)
    stop_loss = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="ACTIVE", index=True)
    opened_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    closed_at = db.Column(db.DateTime, nullable=True)
    close_price = db.Column(db.Float, nullable=True)


def active_signal(symbol):
    return Signal.query.filter_by(symbol=symbol, status="ACTIVE").order_by(Signal.opened_at.desc()).first()


def create_signal(symbol, values):
    signal = Signal(
        symbol=symbol,
        direction=values["type"],
        entry=values["entry"],
        tp1=values["tp"],
        tp2=values["tp2"],
        stop_loss=values["sl"],
        status="ACTIVE",
    )
    db.session.add(signal)
    db.session.commit()
    return signal


def _outcome(signal, price):
    if signal.direction == "BUY":
        if price <= signal.stop_loss:
            return "SL_HIT"
        if price >= signal.tp2:
            return "TP2_HIT"
        if price >= signal.tp1:
            return "TP1_HIT"
    else:
        if price >= signal.stop_loss:
            return "SL_HIT"
        if price <= signal.tp2:
            return "TP2_HIT"
        if price <= signal.tp1:
            return "TP1_HIT"
    return None


def refresh_signal(symbol, price, generator):
    """Close an active signal when TP/SL is reached, then create its replacement.

    ``generator`` must return the current signal dictionary. A replacement is
    created only after the previous record has been closed, preventing duplicate
    active signals during repeated browser/API refreshes.
    """
    signal = active_signal(symbol)
    outcome = _outcome(signal, price) if signal else None
    if outcome:
        signal.status = outcome
        signal.close_price = price
        signal.closed_at = utcnow()
        db.session.commit()
        signal = None
    if signal is None:
        signal = create_signal(symbol, generator())
    return signal


def signal_history(symbol=None, limit=100):
    query = Signal.query.filter(Signal.status != "ACTIVE")
    if symbol:
        query = query.filter_by(symbol=symbol)
    return query.order_by(Signal.closed_at.desc()).limit(limit).all()
