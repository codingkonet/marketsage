from .data_loader import load_forex_data
from .features import build_features
from .model import ForexModel, ForecastResult, HAS_XGBOOST


def _compare_models(feature_data):
    """Quick comparison of all model types on the same data."""
    types = ["random_forest", "neural_net"]
    if HAS_XGBOOST:
        types.append("xgboost")
    types.append("ensemble")
    rows = []
    for mt in types:
        try:
            m = ForexModel(mt)
            metrics = m.train(feature_data)
            pred, conf = m.predict_next(feature_data)
            rows.append({
                "model": mt.replace("_", " ").title(),
                "prediction": round(pred, 6),
                "confidence": round(conf, 6),
                "mae": round(metrics["mae"], 6),
                "rmse": round(metrics["rmse"], 6),
            })
        except Exception:
            pass
    return rows


class ForexAgent:
    def __init__(self, pair="EURUSD=X", period="1y", interval="1d", model_type="random_forest"):
        self.pair = pair
        self.period = period
        self.interval = interval
        self.model = ForexModel(model_type=model_type)

    def analyze(self, run_backtest=True, run_walk_forward=False, run_sentiment=True, run_comparison=False) -> ForecastResult:
        raw_data = load_forex_data(self.pair, period=self.period, interval=self.interval)
        feature_data = build_features(raw_data)
        metrics = self.model.train(feature_data)
        next_close, confidence = self.model.predict_next(feature_data)
        last_close = float(feature_data["Close"].iloc[-1])
        direction, predicted_change = self.model.predict_direction(last_close, next_close)

        chart_window = feature_data.tail(120)
        chart_dates  = [d.strftime("%Y-%m-%d") for d in chart_window.index]
        chart_prices = [round(float(p), 6) for p in chart_window["Close"]]

        backtest      = self.model.run_backtest(feature_data) if run_backtest else {}
        walk_forward  = self.model.walk_forward_validate(feature_data) if run_walk_forward else {}
        fi            = self.model.get_feature_importance()

        sentiment = {}
        if run_sentiment:
            try:
                from .sentiment import analyze_sentiment
                sentiment = analyze_sentiment(self.pair)
            except Exception:
                pass

        comparison = _compare_models(feature_data) if run_comparison else []

        return ForecastResult(
            symbol=self.pair,
            direction=direction,
            predicted_change=predicted_change,
            last_close=last_close,
            next_prediction=next_close,
            confidence=confidence,
            metrics=metrics,
            model_type=self.model.model_type,
            chart_dates=chart_dates,
            chart_prices=chart_prices,
            bb_upper=float(feature_data["bb_upper"].iloc[-1]),
            bb_lower=float(feature_data["bb_lower"].iloc[-1]),
            feature_importance=fi,
            backtest=backtest,
            walk_forward=walk_forward,
            sentiment=sentiment,
            model_comparison=comparison,
        )
