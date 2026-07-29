"""
PSX Volume+Price Alert Backend
--------------------------------
Ye service asal PSX data (psxdata library ke through) fetch karta hai aur
un stocks ko flag karta hai jinka:
  1. volume aaj ke din apne 20-din average se kai guna zyada hai, AUR
  2. price already upar move kar raha hai

Ye sirf ek "unusual activity" detector hai — future prediction nahi.
"""

from flask import Flask, jsonify
from flask_cors import CORS
import psxdata
from datetime import datetime, timedelta
import traceback

app = Flask(__name__)
CORS(app)  # taake website (Blogger/HTML file) is API ko browser se call kar sake

# Apni watchlist yahan set karein — jitne symbols chahein utne add kar sakte hain
WATCHLIST = ["HASCOL", "PIBTL", "BOP", "KEL", "TELE", "FFL", "AGL", "SNGP"]

VOLUME_RATIO_THRESHOLD = 3.0   # aaj ka volume >= 3x average
PRICE_CHANGE_THRESHOLD = 2.0   # kam se kam +2% up


def get_alert_for_symbol(symbol):
    try:
        q = psxdata.quote(symbol)

        end = datetime.now()
        start = end - timedelta(days=30)
        hist = psxdata.stocks(symbol, start=start.strftime("%Y-%m-%d"), end=end.strftime("%Y-%m-%d"))

        if hist is None or len(hist) < 5:
            return None

        avg_volume = hist["Volume"].mean()
        current_volume = q.get("Volume") or q.get("volume")
        current_price = q.get("Price") or q.get("price") or q.get("Close")
        pct_change = q.get("ChangePercent") or q.get("change_percent") or 0

        if not current_volume or not current_price or avg_volume == 0:
            return None

        volume_ratio = current_volume / avg_volume

        qualifies = volume_ratio >= VOLUME_RATIO_THRESHOLD and pct_change >= PRICE_CHANGE_THRESHOLD

        return {
            "symbol": symbol,
            "price": round(float(current_price), 2),
            "change_percent": round(float(pct_change), 2),
            "volume_ratio": round(float(volume_ratio), 2),
            "ceiling_price": round(float(current_price) * 1.075, 2),
            "qualifies": bool(qualifies),
            "checked_at": datetime.now().isoformat(),
        }
    except Exception as e:
        return {"symbol": symbol, "error": str(e)}


@app.route("/api/alerts")
def alerts():
    results = []
    for symbol in WATCHLIST:
        r = get_alert_for_symbol(symbol)
        if r:
            results.append(r)

    qualifying = [r for r in results if r.get("qualifies")]
    return jsonify({
        "generated_at": datetime.now().isoformat(),
        "alerts": qualifying,
        "all_checked": results,
    })


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
