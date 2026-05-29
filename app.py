from flask import Flask, render_template, request
from forex_agent.agent import ForexAgent
from forex_agent.options_analyzer import analyze_options

app = Flask(__name__)


@app.route("/")
def home():
    return render_template("home.html")


@app.route("/forex", methods=["GET", "POST"])
def forex():
    result = None
    error = None
    form_data = {"pair": "EURUSD=X", "period": "1y", "interval": "1d"}

    if request.method == "POST":
        form_data["pair"] = request.form.get("pair", "EURUSD=X")
        form_data["period"] = request.form.get("period", "1y")
        form_data["interval"] = request.form.get("interval", "1d")
        try:
            agent = ForexAgent(
                pair=form_data["pair"],
                period=form_data["period"],
                interval=form_data["interval"],
            )
            result = agent.analyze()
        except Exception as exc:
            error = str(exc)

    return render_template("forex.html", form_data=form_data, result=result, error=error)


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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
