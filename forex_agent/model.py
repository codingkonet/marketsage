from dataclasses import dataclass, field
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.model_selection import train_test_split

FEATURES = [
    "Close", "return", "sma_14", "ema_14", "volatility_14", "momentum_7", "rsi_14",
    "macd", "macd_signal", "macd_hist", "bb_width", "bb_pct",
]


@dataclass
class ForecastResult:
    symbol: str
    direction: str
    predicted_change: float
    last_close: float
    next_prediction: float
    confidence: float
    metrics: dict
    chart_dates: list = field(default_factory=list)
    chart_prices: list = field(default_factory=list)
    bb_upper: float = 0.0
    bb_lower: float = 0.0


class ForexModel:
    def __init__(self):
        self.model = RandomForestRegressor(n_estimators=200, random_state=42, n_jobs=-1)

    def _prepare_training_data(self, data: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
        target = data["Close"].shift(-1)
        features = data[FEATURES].copy()
        combined = features.copy()
        combined["__target__"] = target
        combined = combined.dropna()
        target = combined.pop("__target__")
        return combined, target

    def train(self, data: pd.DataFrame) -> dict:
        X, y = self._prepare_training_data(data)
        split_index = int(len(X) * 0.8)
        X_train, X_test = X.iloc[:split_index], X.iloc[split_index:]
        y_train, y_test = y.iloc[:split_index], y.iloc[split_index:]
        self.model.fit(X_train, y_train)
        predictions = self.model.predict(X_test)
        metrics = {
            "mae": float(mean_absolute_error(y_test, predictions)),
            "rmse": float(np.sqrt(mean_squared_error(y_test, predictions))),
        }
        return metrics

    def predict_next(self, data: pd.DataFrame) -> tuple[float, float]:
        X, _ = self._prepare_training_data(data)
        last_features = X.iloc[[-1]]
        arr = last_features.to_numpy()
        tree_preds = np.array([t.predict(arr)[0] for t in self.model.estimators_])
        return float(tree_preds.mean()), float(tree_preds.std())

    def predict_direction(self, last_close: float, next_close: float) -> tuple[str, float]:
        change = next_close - last_close
        direction = "UP" if change > 0 else "DOWN" if change < 0 else "NEUTRAL"
        return direction, float(change)
