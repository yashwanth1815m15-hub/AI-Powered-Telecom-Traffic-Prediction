"""
TeleSense ML Prediction Service
Serves live predictive forecasts:
- Loads the best trained PyTorch model (GRU / LSTM) with fallback to Seasonal Baseline
- Produces 24-hour ahead traffic forecast
- Computes 95% confidence interval uncertainty bounds
- Generates 5-second plain English summary & action recommendations
"""

import json
import os
from pathlib import Path
import torch
import numpy as np
import pandas as pd
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.models.telemetry import Tower, Reading
from app.config import settings
from ml.models.neural_sequence import load_model_checkpoint
from ml.models.sarima_baseline import SeasonalBaselineModel
import logging

logger = logging.getLogger("telesense.ml_service")

REPO_ROOT = Path(__file__).resolve().parents[2]
METRICS_ARTIFACT_PATH = REPO_ROOT / "artifacts" / "metrics.json"

# Global model cache
_cached_model = None
_cached_scaler = None
_cached_metrics = None


def get_serving_model_choice() -> str:
    """Returns selected_best_model from artifacts/metrics.json (chosen strictly by validation MAE)."""
    if METRICS_ARTIFACT_PATH.exists():
        try:
            data = json.loads(METRICS_ARTIFACT_PATH.read_text(encoding="utf-8"))
            sel = str(data.get("selected_best_model") or "").strip()
            if sel:
                return sel
        except Exception:
            pass
    return "SARIMA_Baseline"


def format_serving_model_label(choice: str) -> str:
    if choice == "SARIMA_Baseline":
        return "SARIMA Baseline (Shared Simulator Model)"
    if choice == "Seasonal_Naive_Baseline":
        return "Seasonal Naive Baseline (Shared Simulator Model)"
    if choice in ("LSTM", "GRU"):
        return f"PyTorch {choice} (Shared Simulator Model)"
    return f"{choice} (Shared Simulator Model)"


def get_inference_model(expected_arch: Optional[str] = None):
    """Loads cached PyTorch checkpoint only if it matches the selected serving architecture."""
    global _cached_model, _cached_scaler, _cached_metrics
    checkpoint_path = str(REPO_ROOT / "ml" / "saved_models" / "best_traffic_model.pt")
    if not os.path.exists(checkpoint_path):
        return None, None, None

    if _cached_model is not None:
        if expected_arch and getattr(_cached_model, "__class__", type(_cached_model)).__name__.lower().find(expected_arch.lower()) == -1:
            pass
        else:
            return _cached_model, _cached_scaler, _cached_metrics

    try:
        model, scaler, metrics = load_model_checkpoint(checkpoint_path, device="cpu")
        cls_name = model.__class__.__name__.upper()
        if expected_arch and expected_arch.upper() not in cls_name:
            return None, None, None
        _cached_model, _cached_scaler, _cached_metrics = model, scaler, metrics
        return _cached_model, _cached_scaler, _cached_metrics
    except Exception as e:
        logger.warning(f"Could not load checkpoint: {e}. Falling back to Seasonal Baseline.")
    return None, None, None


def _load_hourly_tower_history(db: Session, tower_id: str, max_hours: int = 168) -> pd.DataFrame:
    """Loads recent telemetry over [latest - max_hours, latest] and resamples to strict 1h buckets."""
    latest_row = (
        db.query(Reading.timestamp)
        .filter(Reading.tower_id == tower_id)
        .order_by(Reading.timestamp.desc())
        .first()
    )
    if not latest_row or latest_row[0] is None:
        return pd.DataFrame(columns=["timestamp", "load_pct", "active_users", "avg_throughput_mbps"])
    cutoff = latest_row[0] - timedelta(hours=max_hours + 2)
    rows = (
        db.query(
            Reading.timestamp,
            Reading.load_pct,
            Reading.active_users,
            Reading.avg_throughput_mbps,
        )
        .filter(Reading.tower_id == tower_id, Reading.timestamp >= cutoff)
        .order_by(Reading.timestamp.asc())
        .all()
    )
    if not rows:
        return pd.DataFrame(columns=["timestamp", "load_pct", "active_users", "avg_throughput_mbps"])
    raw = pd.DataFrame(
        [
            {
                "timestamp": pd.to_datetime(r[0]),
                "load_pct": float(r[1]),
                "active_users": float(r[2]),
                "avg_throughput_mbps": float(r[3]),
            }
            for r in rows
        ]
    )
    hourly = raw.set_index("timestamp").sort_index().resample("1h").mean().interpolate(method="linear").dropna().reset_index()
    return hourly.tail(max_hours).reset_index(drop=True)


def generate_tower_forecast(db: Session, tower: Tower) -> Dict[str, Any]:
    """
    Generates 24-hour predictive forecast curve for a cell tower using the serving model
    selected strictly by VALIDATION MAE in artifacts/metrics.json.
    """
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    serving_choice = get_serving_model_choice()
    serving_label = format_serving_model_label(serving_choice)

    hourly_df = _load_hourly_tower_history(db, tower.tower_id, max_hours=168)
    if not hourly_df.empty:
        current_load = float(hourly_df["load_pct"].iloc[-1])
        current_throughput = float(hourly_df["avg_throughput_mbps"].iloc[-1])
    else:
        latest = db.query(Reading).filter(Reading.tower_id == tower.tower_id).order_by(Reading.timestamp.desc()).first()
        current_load = float(latest.load_pct) if latest else 52.0
        current_throughput = float(latest.avg_throughput_mbps) if latest else 30.0

    forecast_values: List[float] = []
    lower_bounds: List[float] = []
    upper_bounds: List[float] = []
    model_used = serving_label

    if serving_choice in ("GRU", "LSTM"):
        model, scaler, _ = get_inference_model(expected_arch=serving_choice)
        if model is not None and len(hourly_df) >= 24:
            try:
                data = []
                for _, row in hourly_df.iterrows():
                    ts = pd.Timestamp(row["timestamp"])
                    h = int(ts.hour)
                    dow = int(ts.dayofweek)
                    data.append([
                        float(row["load_pct"]),
                        np.sin(2.0 * np.pi * h / 24.0),
                        np.cos(2.0 * np.pi * h / 24.0),
                        np.sin(2.0 * np.pi * dow / 7.0),
                        np.cos(2.0 * np.pi * dow / 7.0),
                        1.0 if dow in [5, 6] else 0.0,
                        float(row["active_users"]),
                    ])

                df_feats = pd.DataFrame(data, columns=scaler["feature_cols"])
                load_min, load_max = scaler["load_min"], scaler["load_max"]
                users_min, users_max = scaler["users_min"], scaler["users_max"]

                df_feats["load_pct"] = (df_feats["load_pct"] - load_min) / (load_max - load_min + 1e-6)
                df_feats["active_users"] = (df_feats["active_users"] - users_min) / (users_max - users_min + 1e-6)

                arr = df_feats.values
                if len(arr) < 72:
                    pad = np.repeat(arr[:1], 72 - len(arr), axis=0)
                    arr = np.vstack([pad, arr])
                else:
                    arr = arr[-72:]

                inp = torch.tensor(arr, dtype=torch.float32).unsqueeze(0)
                with torch.no_grad():
                    pred_norm = model(inp).squeeze(0).numpy()

                raw_preds = pred_norm * (load_max - load_min) + load_min
                smooth_preds = np.convolve(raw_preds, [0.15, 0.70, 0.15], mode="same")
                smooth_preds[0] = raw_preds[0]
                smooth_preds[-1] = raw_preds[-1]

                chronic_boost = 18.0 if tower.is_chronic_overloader else 0.0
                for h in range(24):
                    val = float(np.clip(smooth_preds[h] + chronic_boost, 5.0, 99.5))
                    forecast_values.append(round(val, 1))
                    sigma = 2.5 * np.sqrt(1.0 + 0.04 * h)
                    lower_bounds.append(round(float(max(0.0, val - 1.96 * sigma)), 1))
                    upper_bounds.append(round(float(min(100.0, val + 1.96 * sigma)), 1))

                model_used = serving_label
            except Exception as e:
                logger.warning(f"Error during neural inference ({serving_choice}): {e}. Using {format_serving_model_label('SARIMA_Baseline')}.")

    if not forecast_values and serving_choice == "Seasonal_Naive_Baseline" and not hourly_df.empty:
        loads_arr = hourly_df["load_pct"].to_numpy(dtype=float)
        resid_std = float(np.std(np.diff(loads_arr))) if len(loads_arr) > 2 else 3.5
        for h in range(24):
            idx = len(loads_arr) - 168 + h
            if idx < 0:
                idx = len(loads_arr) - 24 + (h % 24)
            val = float(np.clip(loads_arr[max(0, min(idx, len(loads_arr) - 1))], 2.0, 99.0))
            forecast_values.append(round(val, 1))
            sigma = max(2.0, resid_std) * np.sqrt(1.0 + 0.04 * h)
            lower_bounds.append(round(float(max(0.0, val - 1.96 * sigma)), 1))
            upper_bounds.append(round(float(min(100.0, val + 1.96 * sigma)), 1))
        model_used = serving_label

    if not forecast_values:
        baseline = SeasonalBaselineModel(seasonal_period=24)
        if not hourly_df.empty:
            baseline.fit(hourly_df["load_pct"])
        f_vals, l_bounds, u_bounds = baseline.predict(horizon=24, start_hour=now.hour)
        forecast_values = [round(float(v), 1) for v in f_vals]
        lower_bounds = [round(float(v), 1) for v in l_bounds]
        upper_bounds = [round(float(v), 1) for v in u_bounds]
        model_used = serving_label if serving_choice == "SARIMA_Baseline" else format_serving_model_label("SARIMA_Baseline")

    # Construct hourly forecast response points
    points = []
    for h in range(24):
        slot_time = now + timedelta(hours=h + 1)
        points.append({
            "timestamp": slot_time.isoformat(),
            "hour": slot_time.strftime("%I %p"),
            "predicted_load_pct": forecast_values[h],
            "lower_bound": lower_bounds[h],
            "upper_bound": upper_bounds[h],
            "is_peak": False
        })

    # Identify peak
    peak_pt = max(points, key=lambda x: x["predicted_load_pct"])
    peak_pt["is_peak"] = True
    peak_load = peak_pt["predicted_load_pct"]
    peak_time_str = datetime.fromisoformat(peak_pt["timestamp"]).strftime("%I:%M %p")

    # 5-second plain English summary & action recommendation
    if peak_load >= settings.ALERT_THRESHOLD_CRITICAL:
        status = "CRITICAL"
        summary_sentence = (
            f"CRITICAL OVERLOAD AHEAD: Forecast projects {peak_load:.1f}% load at {peak_time_str} "
            f"(bounds reach {peak_pt['upper_bound']:.1f}%). High risk of packet loss and dropped calls."
        )
        recommended_action = "PRIORITY 1: Deploy temporary Cell-on-Wheels (COW) and trigger high-band carrier offload before peak window."
    elif peak_load >= settings.ALERT_THRESHOLD_LOAD:
        status = "AT_RISK"
        summary_sentence = (
            f"WARNING: Forecast approaches congestion threshold with {peak_load:.1f}% peak at {peak_time_str}. "
            f"Headroom constrained during evening prime hours."
        )
        recommended_action = "Schedule dynamic carrier aggregation bandwidth boost; monitor neighbor sector azimuths."
    else:
        status = "HEALTHY"
        summary_sentence = (
            f"Operating within safe headroom. Peak forecast load is {peak_load:.1f}% at {peak_time_str}. No congestion expected."
        )
        recommended_action = "NOMINAL: Safe headroom. Enable Radio Micro-Sleep during 02:00 AM – 06:00 AM off-peak to save power."

    return {
        "tower_id": tower.tower_id,
        "tower_name": tower.name,
        "city": tower.city,
        "current_load_pct": round(current_load, 1),
        "peak_forecast_load_pct": round(peak_load, 1),
        "peak_forecast_time": peak_time_str,
        "capacity_threshold_pct": settings.ALERT_THRESHOLD_LOAD,
        "status": status,
        "model_used": model_used,
        "summary_sentence": summary_sentence,
        "recommended_action": recommended_action,
        "forecast_points": points
    }

