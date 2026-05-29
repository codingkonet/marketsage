from dataclasses import dataclass, field
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.neural_network import MLPRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error

try:
    from xgboost import XGBRegressor
    HAS_XGBOOST = True
except ImportError:
    HAS_XGBOOST = False

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
    model_type: str = "random_forest"
    chart_dates: list = field(default_factory=list)
    chart_prices: list = field(default_factory=list)
    bb_upper: float = 0.0
    bb_lower: float = 0.0
    feature_importance: dict = field(default_factory=dict)
    backtest: dict = field(default_factory=dict)


class ForexModel:
    def __init__(self, model_type: str = "random_forest"):
        self.model_type = model_type
        if model_type == "xgboost" and HAS_XGBOOST:
            self.model = XGBRegressor(n_estimators=200, random_state=42, n_jobs=-1, verbosity=0)
        elif model_type == "neural_net":
            self.model = MLPRegressor(hidden_layer_sizes=(128, 64), max_iter=500, random_state=42)
        else:
            self.model = RandomForestRegressor(n_estimators=200, random_state=42, n_jobs=-1)

    def _prepare_training_data(self, data: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
        target = data["Close"].shift(-1)
        combined = data[FEATURES].copy()
        combined["__target__"] = target
        combined = combined.dropna()
        target = combined.pop("__target__")
        return combined, target

    def train(self, data: pd.DataFrame) -> dict:
        X, y = self._prepare_training_data(data)
        split = int(len(X) * 0.8)
        X_train, X_test = X.iloc[:split], X.iloc[split:]
        y_train, y_test = y.iloc[:split], y.iloc[split:]
        self.model.fit(X_train, y_train)
        preds = self.model.predict(X_test)
        return {
            "mae": float(mean_absolute_error(y_test, preds)),
            "rmse": float(np.sqrt(mean_squared_error(y_test, preds))),
        }

    def predict_next(self, data: pd.DataFrame) -> tuple[float, float]:
        X, _ = self._prepare_training_data(data)
        last = X.iloc[[-1]]
        pred = float(self.model.predict(last)[0])
        # confidence via tree variance (RF only)
        if self.model_type == "random_forest" and hasattr(self.model, "estimators_"):
            arr = last.to_numpy()
            tree_preds = np.array([t.predict(arr)[0] for t in self.model.estimators_])
            conf = float(tree_preds.std())
        else:
            conf = 0.0
        return pred, conf

    def predict_direction(self, last_close: float, next_close: float) -> tuple[str, float]:
        change = next_close - last_close
        return ("UP" if change > 0 else "DOWN" if change < 0 else "NEUTRAL"), float(change)

    def get_feature_importance(self) -> dict:
        if hasattr(self.model, "feature_importances_"):
            raw = self.model.feature_importances_
            total = raw.sum() or 1
            return {f: round(float(v / total), 4) for f, v in zip(FEATURES, raw)}
        return {}

    def run_backtest(self, data: pd.DataFrame) -> dict:
        X, _ = self._prepare_training_data(data)
        split = int(len(X) * 0.8)
        X_test = X.iloc[split:]
        if len(X_test) < 5:
            return {}
        closes = X_test["Close"].values
        preds = self.model.predict(X_test)
        returns, wins = [], 0
        for i in range(len(preds) - 1):
            actual = (closes[i + 1] - closes[i]) / closes[i]
            direction = 1 if preds[i] > closes[i] else -1
            r = direction * actual
            returns.append(r)
            if r > 0:
                wins += 1
        if not returns:
            return {}
        returns = np.array(returns)
        equity = np.cumprod(1 + returns)
        peak = np.maximum.accumulate(equity)
        drawdown = (equity - peak) / peak
        sharpe = float((returns.mean() / returns.std()) * np.sqrt(252)) if returns.std() > 0 else 0.0
        dates = [d.strftime("%Y-%m-%d") for d in X_test.index[:-1]]
        return {
            "dates": dates,
            "equity": [round(float(e), 6) for e in equity],
            "win_rate": round(wins / len(returns), 4),
            "total_return": round(float(equity[-1] - 1), 6),
            "sharpe": round(sharpe, 3),
            "max_drawdown": round(float(drawdown.min()), 4),
            "n_trades": len(returns),
        }
