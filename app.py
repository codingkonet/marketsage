import io
import csv
import json

import pandas as pd
import yfinance as yf
from flask import Flask, render_template, request, jsonify, Response

from forex_agent.agent import ForexAgent
from forex_agent.options_analyzer import analyze_options
from forex_agent.data_loader import load_close_prices

app = Flask(__name__)

MODEL_TYPES = ["random_forest", "xgboost", "neural_net"]
DEFAULT_PAIRS = "EURUSD=X,GBPUSD=X,USDJPY=X,AUDUSD=X,USDCAD=X,USDCHF=X"


# ── Pages ────────────────────────────────────────────────────────────────────

@app.route("/")
def home():
    return render_template("home.html")


@app.route("/forex", methods=["GET", "POST"])
def forex():
    result = None
    error = None
    form_data = {"pair": "EURUSD=X", "period": "1y", "interval": "1d", "model_type": "random_forest"}

    if request.method == "POST":
        form_data.update({
            "pair": request.form.get("pair", "EURUSD=X"),
            "period": request.form.get("period", "1y"),
            "interval": request.form.get("interval", "1d"),
            "model_type": request.form.get("model_type", "random_forest"),
        })
        try:
            agent = ForexAgent(
                pair=form_data["pair"],
                period=form_data["period"],
                interval=form_data["interval"],
                model_type=form_data["model_type"],
            )
            result = agent.analyze()
        except Exception as exc:
            error = str(exc)

    return render_template("forex.html", form_data=form_data, result=result, error=error, model_types=MODEL_TYPES)


@app.route("/options", methods=["GET", "POST"])
def options():
    result = None
    error = None
    form_data = {"symbol": "SPY", "expiry": ""}

    if request.method == "POST":
        form_data["symbol"] = request.form.get("symbol", "SPY").strip().upper()
        form_data["expiry"] = request.form.get("expiry", "").strip()
        try:
            result = analyze_options(form_data["symbol"], form_data["expiry"] or None)
        except Exception as exc:
            error = str(exc)

    return render_template("options.html", form_data=form_data, result=result, error=error)


@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    results = []
    corr_data = None
    error = None
    form_data = {"pairs": DEFAULT_PAIRS, "period": "3mo", "interval": "1d"}

    if request.method == "POST":
        form_data["pairs"] = request.form.get("pairs", DEFAULT_PAIRS)
        form_data["period"] = request.form.get("period", "3mo")
        form_data["interval"] = request.form.get("interval", "1d")
        pairs = [p.strip() for p in form_data["pairs"].split(",") if p.strip()][:8]

        for pair in pairs:
            try:
                agent = ForexAgent(pair=pair, period=form_data["period"], interval=form_data["interval"])
                r = agent.analyze(run_backtest=False)
                results.append({"ok": True, "result": r})
            except Exception as e:
                results.append({"ok": False, "symbol": pair, "error": str(e)})

        # Correlation matrix
        if len(pairs) > 1:
            closes = load_close_prices(pairs, period=form_data["period"])
            if len(closes.columns) > 1:
                corr = closes.pct_change().dropna().corr().round(3)
                corr_data = {
                    "labels": list(corr.columns),
                    "values": corr.values.tolist(),
                }

    return render_template("dashboard.html", form_data=form_data, results=results, corr_data=corr_data, error=error)


@app.route("/watchlist")
def watchlist():
    return render_template("watchlist.html")


# ── JSON API ─────────────────────────────────────────────────────────────────

@app.route("/api/forex")
def api_forex():
    pair = request.args.get("pair", "EURUSD=X")
    period = request.args.get("period", "1y")
    interval = request.args.get("interval", "1d")
    model_type = request.args.get("model_type", "random_forest")
    try:
        agent = ForexAgent(pair=pair, period=period, interval=interval, model_type=model_type)
        r = agent.analyze(run_backtest=False)
        return jsonify({
            "symbol": r.symbol, "direction": r.direction,
            "last_close": r.last_close, "next_prediction": r.next_prediction,
            "predicted_change": r.predicted_change, "confidence": r.confidence,
            "model_type": r.model_type, "metrics": r.metrics,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/options")
def api_options():
    symbol = request.args.get("symbol", "SPY")
    expiry = request.args.get("expiry", None)
    try:
        r = analyze_options(symbol, expiry)
        return jsonify({
            "symbol": r.symbol, "name": r.name, "current_price": r.current_price,
            "expiry": r.expiry, "days_to_expiry": r.days_to_expiry,
            "put_call_ratio": r.put_call_ratio, "max_pain": r.max_pain,
            "calls": r.calls[:10], "puts": r.puts[:10],
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/price/<symbol>")
def api_price(symbol):
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.fast_info
        price = float(info.last_price)
        prev = float(info.previous_close) if hasattr(info, "previous_close") else price
        change_pct = round((price - prev) / prev * 100, 3) if prev else 0
        return jsonify({"symbol": symbol, "price": price, "change_pct": change_pct})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


# ── CSV Export ───────────────────────────────────────────────────────────────

@app.route("/api/export/forex")
def export_forex():
    pair = request.args.get("pair", "EURUSD=X")
    period = request.args.get("period", "1y")
    interval = request.args.get("interval", "1d")
    try:
        from forex_agent.data_loader import load_forex_data
        from forex_agent.features import build_features
        data = build_features(load_forex_data(pair, period, interval))
        buf = io.StringIO()
        data.reset_index().to_csv(buf, index=False)
        return Response(
            buf.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment; filename={pair}_{period}.csv"},
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/export/options")
def export_options():
    symbol = request.args.get("symbol", "SPY")
    expiry = request.args.get("expiry", None)
    try:
        r = analyze_options(symbol, expiry)
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=["type"] + list(r.calls[0].keys()) if r.calls else [])
        writer.writeheader()
        for row in r.calls:
            writer.writerow({"type": "call", **row})
        for row in r.puts:
            writer.writerow({"type": "put", **row})
        return Response(
            buf.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment; filename={symbol}_{r.expiry}_options.csv"},
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 400


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
