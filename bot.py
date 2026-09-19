import os
import requests
from datetime import datetime

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
CHANNEL_ID = os.getenv("CHANNEL_ID", "@gazellesignals")

def send_signal(pair, type_, entry, sl, tp, category, tier="FREE"):
    if tier == "VIP" and category == "forex":
        tier = "FREE"
    msg = f"""
🦌 GAZELLE SIGNALS
{pair} | {type_} | {category.upper()}
Entry: {entry}
SL: {sl}
TP: {tp}
Tier: {tier}
Time: {datetime.utcnow().strftime('%H:%M UTC')}
"""
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print(msg)
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": CHANNEL_ID, "text": msg})

if __name__ == "__main__":
    send_signal("EURUSD", "BUY", "1.0845", "1.0820", "1.0890", "forex")
