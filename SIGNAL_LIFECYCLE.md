# Live signal lifecycle integration

The `fix/live-signal-history` branch adds `signal_lifecycle.py`, which persists
signals and supports this lifecycle:

1. Create one ACTIVE signal per symbol.
2. On each refresh, compare the current market price with TP1, TP2, and SL.
3. Store the terminal result (`TP1_HIT`, `TP2_HIT`, or `SL_HIT`) in history.
4. Generate exactly one replacement after the prior signal closes.

The service expects the existing Flask-SQLAlchemy instance to be assigned before
use:

```python
from signal_lifecycle import db, refresh_signal, signal_history

# after creating the app's SQLAlchemy object:
# signal_lifecycle.db = db

current = refresh_signal(symbol, live_price, lambda: get_signal(symbol))
completed = signal_history(symbol)
```

Before deployment, wire `refresh_signal` into `/market/<symbol>` and `/api/signal`,
add a history route/template, and run it from a scheduler or worker for timely
updates. Never use hard-coded prices as a live-market fallback; return an explicit
unavailable state when the provider cannot be reached.
"""Persistent signal lifecycle for the Gazelle Signals Flask app."""
from datetime import datetime, timezone


db = None
Signal = None


def configure(database):
    """Bind this module to the application's existing SQLAlchemy instance."""
    global db, Signal
    db = database

    class _Signal(db.Model):
        __tablename__ = "signals"
        id = db.Column(db.Integer, primary_key=True)
        symbol = db.Column(db.String(40), nullable=False, index=True)
        direction = db.Column(db.String(4), nullable=False)
        entry = db.Column(db.Float, nullable=False)
        tp1 = db.Column(db.Float, nullable=False)
        tp2 = db.Column(db.Float, nullable=False)
        stop_loss = db.Column(db.Float, nullable=False)
        status = db.Column(db.String(20), nullable=False, default="ACTIVE", index=True)
        opened_at = db.Column(db.DateTime, nullable=False, default=utcnow)
        closed_at = db.Column(db.DateTime)
        close_price = db.Column(db.Float)

        __table_args__ = (db.UniqueConstraint("symbol", "status", name="uq_active_signal_symbol_status"),)

    Signal = _Signal
    return Signal


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def active_signal(symbol):
    return Signal.query.filter_by(symbol=symbol, status="ACTIVE").order_by(Signal.opened_at.desc()).first()


def create_signal(symbol, values):
    signal = Signal(symbol=symbol, direction=values["type"], entry=values["entry"], tp1=values["tp"], tp2=values["tp2"], stop_loss=values["sl"], status="ACTIVE")
    db.session.add(signal)
    db.session.commit()
    return signal


def outcome(signal, price):
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
    if Signal is None:
        raise RuntimeError("signal_lifecycle.configure(db) must be called first")
    signal = active_signal(symbol)
    result = outcome(signal, price) if signal else None
    if result:
        signal.status = result
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


def as_dict(signal):
    return {
        "id": signal.id,
        "pair": signal.symbol,
        "type": signal.direction,
        "entry": signal.entry,
        "tp": signal.tp1,
        "tp2": signal.tp2,
        "sl": signal.stop_loss,
        "status": signal.status,
        "opened_at": signal.opened_at.isoformat(),
        "closed_at": signal.closed_at.isoformat() if signal.closed_at else None,
        "close_price": signal.close_price,
    }
