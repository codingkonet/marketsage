from .data_loader import load_forex_data
from .features import build_features
from .model import ForexModel, ForecastResult


class ForexAgent:
    def __init__(self, pair: str = "EURUSD=X", period: str = "1y", interval: str = "1d"):
        self.pair = pair
        self.period = period
        self.interval = interval
        self.model = ForexModel()

    def analyze(self) -> ForecastResult:
        raw_data = load_forex_data(self.pair, period=self.period, interval=self.interval)
        feature_data = build_features(raw_data)
        metrics = self.model.train(feature_data)
        next_close, confidence = self.model.predict_next(feature_data)
        last_close = float(feature_data["Close"].iloc[-1])
        direction, predicted_change = self.model.predict_direction(last_close, next_close)

        chart_window = feature_data.tail(120)
        chart_dates = [d.strftime("%Y-%m-%d") for d in chart_window.index]
        chart_prices = [round(float(p), 6) for p in chart_window["Close"]]

        bb_upper = float(feature_data["bb_upper"].iloc[-1])
        bb_lower = float(feature_data["bb_lower"].iloc[-1])

        return ForecastResult(
            symbol=self.pair,
            direction=direction,
            predicted_change=predicted_change,
            last_close=last_close,
            next_prediction=next_close,
            confidence=confidence,
            metrics=metrics,
            chart_dates=chart_dates,
            chart_prices=chart_prices,
            bb_upper=bb_upper,
            bb_lower=bb_lower,
        )

    def summary(self) -> str:
        result = self.analyze()
        lines = [
            f"Forex Agent Analysis for {result.symbol}",
            f"Last Close:          {result.last_close:.6f}",
            f"Predicted Next Close:{result.next_prediction:.6f} ± {result.confidence:.6f}",
            f"Forecast Direction:  {result.direction}",
            f"Predicted Change:    {result.predicted_change:.6f}",
            "",
            "Model metrics:",
            f"  MAE:  {result.metrics['mae']:.6f}",
            f"  RMSE: {result.metrics['rmse']:.6f}",
        ]
        return "\n".join(lines)
