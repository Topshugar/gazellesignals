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
