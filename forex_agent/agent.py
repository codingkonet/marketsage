from .data_loader import load_forex_data
from .features import build_features
from .model import ForexModel, ForecastResult


class ForexAgent:
    def __init__(self, pair: str = "EURUSD=X", period: str = "1y", interval: str = "1d", model_type: str = "random_forest"):
        self.pair = pair
        self.period = period
        self.interval = interval
        self.model = ForexModel(model_type=model_type)

    def analyze(self, run_backtest: bool = True) -> ForecastResult:
        raw_data = load_forex_data(self.pair, period=self.period, interval=self.interval)
        feature_data = build_features(raw_data)
        metrics = self.model.train(feature_data)
        next_close, confidence = self.model.predict_next(feature_data)
        last_close = float(feature_data["Close"].iloc[-1])
        direction, predicted_change = self.model.predict_direction(last_close, next_close)

        chart_window = feature_data.tail(120)
        chart_dates = [d.strftime("%Y-%m-%d") for d in chart_window.index]
        chart_prices = [round(float(p), 6) for p in chart_window["Close"]]

        backtest = self.model.run_backtest(feature_data) if run_backtest else {}
        fi = self.model.get_feature_importance()

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
        )
