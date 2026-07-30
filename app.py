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
from concurrent.futures import ThreadPoolExecutor, as_completed
import traceback

app = Flask(__name__)
CORS(app)  # taake website (Blogger/HTML file) is API ko browser se call kar sake

VOLUME_RATIO_THRESHOLD = 3.0   # aaj ka volume >= 3x average
PRICE_CHANGE_THRESHOLD = 2.0   # kam se kam +2% up
MAX_WORKERS = 20               # kitne symbols ek saath parallel check hon


def get_all_symbols():
    try:
        return list(psxdata.tickers())
    except Exception:
        # Agar tickers() fail ho, purani chhoti list par wapis gir jayein
        return ["HASCOL", "PIBTL", "BOP", "KEL", "TELE", "FFL", "AGL", "SNGP"]


def get_alert_for_symbol(symbol):
    try:
        end = datetime.now()
        start = end - timedelta(days=30)
        hist = psxdata.stocks(symbol, start=start.strftime("%Y-%m-%d"), end=end.strftime("%Y-%m-%d"))

        if hist is None or len(hist) < 5:
            return {"symbol": symbol, "error": "not enough history"}

        # Rows come back newest-first (index 0 = latest trading day)
        current_volume = float(hist["volume"].iloc[0])
        current_close = float(hist["close"].iloc[0])
        prev_close = float(hist["close"].iloc[1])
        avg_volume = float(hist["volume"].iloc[1:].mean())

        if avg_volume == 0 or prev_close == 0:
            return {"symbol": symbol, "error": "bad averages"}

        volume_ratio = current_volume / avg_volume
        pct_change = ((current_close - prev_close) / prev_close) * 100

        qualifies = volume_ratio >= VOLUME_RATIO_THRESHOLD and pct_change >= PRICE_CHANGE_THRESHOLD

        return {
            "symbol": symbol,
            "price": round(current_close, 2),
            "change_percent": round(pct_change, 2),
            "volume_ratio": round(volume_ratio, 2),
            "ceiling_price": round(current_close * 1.075, 2),
            "qualifies": bool(qualifies),
            "checked_at": datetime.now().isoformat(),
        }
    except Exception as e:
        return {"symbol": symbol, "error": str(e)}


@app.route("/api/alerts")
def alerts():
    symbols = get_all_symbols()
    results = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(get_alert_for_symbol, s): s for s in symbols}
        for future in as_completed(futures):
            try:
                r = future.result()
                if r:
                    results.append(r)
            except Exception as e:
                results.append({"symbol": futures[future], "error": str(e)})

    qualifying = [r for r in results if r.get("qualifies")]
    return jsonify({
        "generated_at": datetime.now().isoformat(),
        "total_checked": len(results),
        "alerts": qualifying,
        "all_checked": results,
    })


@app.route("/api/test-hist/<symbol>")
def test_hist(symbol):
    try:
        end = datetime.now()
        start = end - timedelta(days=30)
        hist = psxdata.stocks(symbol, start=start.strftime("%Y-%m-%d"), end=end.strftime("%Y-%m-%d"))
        return jsonify({
            "symbol": symbol,
            "columns": list(hist.columns) if hasattr(hist, "columns") else None,
            "sample": hist.head(2).to_dict() if hasattr(hist, "head") else str(hist)[:500],
        })
    except Exception as e:
        return jsonify({"symbol": symbol, "error": str(e), "type": str(type(e))}), 500


@app.route("/api/test/<symbol>")
def test_symbol(symbol):
    try:
        q = psxdata.quote(symbol)
        return jsonify({"symbol": symbol, "quote": q})
    except Exception as e:
        return jsonify({"symbol": symbol, "error": str(e), "type": str(type(e))}), 500


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
