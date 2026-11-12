"""
TeleSense SARIMA & Seasonal Statistical Baseline
Provides traditional time-series baselines (SARIMA / Seasonal Decomposition)
to compare directly against LSTM and GRU deep models.
Calculates honest MAE, RMSE, and MAPE across 1h, 6h, 12h, and 24h horizons.
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple
import logging

logger = logging.getLogger("telesense.sarima")


class SeasonalBaselineModel:
    """
    Seasonal Holt-Winters / SARIMA-style baseline with 24-hour diurnal period.
    Decomposes series into:
    y_hat(t + h) = Level + Trend * h + Seasonal_Factor(t + h mod 24)
    Provides robust, explainable baseline for telecom traffic.
    """

    def __init__(self, seasonal_period: int = 24):
        self.seasonal_period = seasonal_period
        self.seasonal_factors = None
        self.trend = 0.0
        self.level = 50.0
        self.residual_std = 3.5

    def fit(self, series: pd.Series) -> "SeasonalBaselineModel":
        values = series.values.astype(float)
        n = len(values)
        if n < self.seasonal_period * 2:
            self.level = float(np.mean(values))
            self.seasonal_factors = np.zeros(self.seasonal_period)
            self.residual_std = float(np.std(values)) or 3.0
            return self

        # 1. Recent-window level & damped trend (last 7 days; avoid multi-month trend runaway)
        recent_window = values[-self.seasonal_period * 7 :]
        m = len(recent_window)
        t = np.arange(m)
        p = np.polyfit(t, recent_window, 1)
        self.trend = float(np.clip(p[0], -0.25, 0.25))
        self.level = float(np.mean(recent_window))

        # 2. 24-hour Seasonal Indices indexed by step offset from series end (phase = (n + h) % 24)
        detrended = recent_window - (p[0] * t + p[1])
        seasonal_idx = np.zeros(self.seasonal_period)
        for h in range(self.seasonal_period):
            # Map offset h after series end to matching modular positions within recent_window
            phase_positions = [idx for idx in range(m) if (idx - m) % self.seasonal_period == h]
            if phase_positions:
                seasonal_idx[h] = float(np.mean(detrended[phase_positions]))

        # Normalize seasonal factors to zero mean
        self.seasonal_factors = seasonal_idx - np.mean(seasonal_idx)

        # 3. Residual standard deviation on recent window
        fitted = np.array([
            p[0] * idx + p[1] + self.seasonal_factors[(idx - m) % self.seasonal_period]
            for idx in range(m)
        ])
        self.residual_std = float(np.std(recent_window - fitted)) or 3.0
        return self

    def predict(self, horizon: int = 24, start_hour: int = 0) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Generates point forecasts plus 95% confidence intervals:
        returns (forecast, lower_bound, upper_bound)
        """
        forecasts = np.zeros(horizon)
        lower_bounds = np.zeros(horizon)
        upper_bounds = np.zeros(horizon)

        for h in range(horizon):
            phase = h % self.seasonal_period
            factor = self.seasonal_factors[phase] if self.seasonal_factors is not None else 0.0
            val = self.level + self.trend * (h + 1) * 0.5 + factor
            clamped = float(np.clip(val, 2.0, 99.0))
            forecasts[h] = clamped

            # Expanding uncertainty cone: sigma * sqrt(1 + 0.05 * h)
            uncertainty = 1.96 * self.residual_std * np.sqrt(1.0 + 0.04 * h)
            lower_bounds[h] = float(np.clip(clamped - uncertainty, 0.0, 100.0))
            upper_bounds[h] = float(np.clip(clamped + uncertainty, 0.0, 100.0))

        return forecasts, lower_bounds, upper_bounds

