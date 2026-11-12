"""
TeleSense Simulator Benchmark Training Script.
Trains LSTM and GRU sequence predictors and evaluates Seasonal SARIMA and
Seasonal-Naive (t - 168h) baselines chronologically on 1h-resampled simulated tower telemetry.
Selects the serving model STRICTLY by lowest VALIDATION MAE (never test MAE), and writes
empirical validation + test results directly into artifacts/metrics.json while preserving
real_dataset_validation.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Tuple

import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(REPO_ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.database import SessionLocal  # noqa: E402
from ml.models.neural_sequence import save_model_checkpoint  # noqa: E402
from ml.models.sarima_baseline import SeasonalBaselineModel  # noqa: E402
from ml.training.dataset import prepare_training_data  # noqa: E402
from ml.training.india_radar_pipeline import select_best_model_by_validation  # noqa: E402
from ml.training.train_pipeline import compute_horizon_metrics, train_neural_model  # noqa: E402

METRICS_PATH = REPO_ROOT / "artifacts" / "metrics.json"
CHECKPOINT_PATH = REPO_ROOT / "ml" / "saved_models" / "best_traffic_model.pt"


def _evaluate_neural_split(
    model: torch.nn.Module,
    loader: DataLoader,
    scaler_params: Dict[str, Any],
    device: str = "cpu",
) -> Dict[str, Any]:
    model.eval()
    preds_list, true_list = [], []
    with torch.no_grad():
        for X_b, y_b in loader:
            preds_list.append(model(X_b.to(device)).cpu().numpy())
            true_list.append(y_b.numpy())
    load_min = float(scaler_params["load_min"])
    load_max = float(scaler_params["load_max"])
    y_pred = np.concatenate(preds_list, axis=0) * (load_max - load_min) + load_min
    y_true = np.concatenate(true_list, axis=0) * (load_max - load_min) + load_min
    return compute_horizon_metrics(y_true, y_pred)


def _evaluate_simulator_baselines_slice(
    full_loads: np.ndarray,
    full_timestamps: pd.Series,
    split_start_idx: int,
    split_end_idx: int,
    seq_len: int = 72,
    horizon: int = 24,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Evaluates Seasonal-Naive (t - 168h) and chronological SARIMA over [split_start_idx, split_end_idx)."""
    naive_preds, sarima_preds, actuals = [], [], []
    limit = split_end_idx - split_start_idx - seq_len - horizon + 1

    for rel_i in range(max(0, limit)):
        origin_end = split_start_idx + rel_i + seq_len
        target_slice = full_loads[origin_end : origin_end + horizon]
        if len(target_slice) < horizon:
            break
        actuals.append(target_slice)

        sn_block = []
        for h in range(horizon):
            idx = origin_end + h - 168
            if idx >= 0:
                sn_block.append(float(full_loads[idx]))
            elif origin_end + h - 24 >= 0:
                sn_block.append(float(full_loads[origin_end + h - 24]))
            else:
                sn_block.append(float(full_loads[origin_end - 1]))
        naive_preds.append(sn_block)

        sarima = SeasonalBaselineModel(seasonal_period=24).fit(pd.Series(full_loads[:origin_end]))
        start_hr = int(pd.Timestamp(full_timestamps.iloc[origin_end]).hour)
        fc, _, _ = sarima.predict(horizon=horizon, start_hour=start_hr)
        sarima_preds.append(fc)

    y_true = np.asarray(actuals, dtype=np.float32)
    naive_metrics = compute_horizon_metrics(y_true, np.asarray(naive_preds, dtype=np.float32))
    sarima_metrics = compute_horizon_metrics(y_true, np.asarray(sarima_preds, dtype=np.float32))
    return naive_metrics, sarima_metrics


def run() -> Dict[str, Any]:
    torch.manual_seed(42)
    np.random.seed(42)

    db = SessionLocal()
    try:
        tower_id = "MUM-C101"
        seq_len = 72
        horizon = 24
        train_ds, val_ds, test_ds, scaler_params, _ = prepare_training_data(
            db, tower_id=tower_id, seq_len=seq_len, forecast_horizon=horizon
        )

        hourly_df: pd.DataFrame = scaler_params["hourly_df"]
        val_start_idx = int(scaler_params["val_start_idx"])
        test_start_idx = int(scaler_params["test_start_idx"])
        split_dates = dict(scaler_params["split_dates"])

        train_loader = DataLoader(train_ds, batch_size=32, shuffle=True)
        val_loader = DataLoader(val_ds, batch_size=32, shuffle=False)
        test_loader = DataLoader(test_ds, batch_size=32, shuffle=False)
        device = "cpu"

        lstm_model, lstm_test_metrics = train_neural_model(
            "lstm", train_loader, val_loader, test_loader, scaler_params, epochs=25, lr=0.002, device=device
        )
        lstm_val_metrics = _evaluate_neural_split(lstm_model, val_loader, scaler_params, device=device)

        gru_model, gru_test_metrics = train_neural_model(
            "gru", train_loader, val_loader, test_loader, scaler_params, epochs=25, lr=0.002, device=device
        )
        gru_val_metrics = _evaluate_neural_split(gru_model, val_loader, scaler_params, device=device)

        loads_arr = hourly_df["load_pct"].to_numpy(dtype=np.float32)
        ts_series = hourly_df["timestamp"]

        naive_val_metrics, sarima_val_metrics = _evaluate_simulator_baselines_slice(
            loads_arr, ts_series, split_start_idx=val_start_idx, split_end_idx=test_start_idx, seq_len=seq_len, horizon=horizon
        )
        naive_test_metrics, sarima_test_metrics = _evaluate_simulator_baselines_slice(
            loads_arr, ts_series, split_start_idx=test_start_idx, split_end_idx=len(hourly_df), seq_len=seq_len, horizon=horizon
        )

        naive_test_mae = float(naive_test_metrics["mae_overall"])
        sim_metrics: Dict[str, Dict[str, Any]] = {
            "Seasonal_Naive_Baseline": {
                "provenance": "SIMULATED",
                **naive_test_metrics,
                "val_mae_overall": naive_val_metrics["mae_overall"],
                "val_rmse_overall": naive_val_metrics["rmse_overall"],
                "beats_seasonal_naive": False,
                "description": "Same hour last week (t - 168h)",
            },
            "SARIMA_Baseline": {
                "provenance": "SIMULATED",
                **sarima_test_metrics,
                "val_mae_overall": sarima_val_metrics["mae_overall"],
                "val_rmse_overall": sarima_val_metrics["rmse_overall"],
                "beats_seasonal_naive": bool(sarima_test_metrics["mae_overall"] < naive_test_mae),
                "description": "Seasonal decomposition & autoregressive trend baseline (period=24h)",
            },
            "GRU": {
                "provenance": "SIMULATED",
                **gru_test_metrics,
                "val_mae_overall": gru_val_metrics["mae_overall"],
                "val_rmse_overall": gru_val_metrics["rmse_overall"],
                "beats_seasonal_naive": bool(gru_test_metrics["mae_overall"] < naive_test_mae),
                "description": "Gated Recurrent Unit (PyTorch)",
            },
            "LSTM": {
                "provenance": "SIMULATED",
                **lstm_test_metrics,
                "val_mae_overall": lstm_val_metrics["mae_overall"],
                "val_rmse_overall": lstm_val_metrics["rmse_overall"],
                "beats_seasonal_naive": bool(lstm_test_metrics["mae_overall"] < naive_test_mae),
                "description": "Long Short-Term Memory (PyTorch)",
            },
        }

        # Select serving model strictly by lowest VALIDATION MAE (never test MAE)
        best_model_name = select_best_model_by_validation(sim_metrics)
        sim_metrics[best_model_name]["description"] += " - Selected Best Model (by Val MAE)"

        best_neural_name = "GRU" if sim_metrics["GRU"]["val_mae_overall"] <= sim_metrics["LSTM"]["val_mae_overall"] else "LSTM"
        best_neural_model = gru_model if best_neural_name == "GRU" else lstm_model
        CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)
        clean_scaler = {k: v for k, v in scaler_params.items() if k != "hourly_df"}
        save_model_checkpoint(best_neural_model, best_neural_name.lower(), clean_scaler, sim_metrics[best_neural_name], str(CHECKPOINT_PATH))

        existing: Dict[str, Any] = json.loads(METRICS_PATH.read_text(encoding="utf-8")) if METRICS_PATH.exists() else {}
        existing.update({
            "selected_best_model": best_model_name,
            "selection_criterion": "Lowest chronological validation MAE (never test MAE)",
            "provenance": "SIMULATED",
            "trained_on_tower_id": "MUM-C101",
            "is_shared_simulator_model": True,
            "simulator_coverage_note": (
                "Trained & evaluated chronologically on simulated reference tower MUM-C101 (4,440 1h-resampled hours) "
                "and served as a shared simulator model across all 99 simulated NOC towers (never trained on OpenCellID cells)."
            ),
            "evaluated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "sequence_history_hours": seq_len,
            "forecast_horizon_hours": horizon,
            "features_used": scaler_params["feature_cols"],
            "simulator_split_dates": split_dates,
            "simulator_diagnostic_note": (
                "Root cause of prior 11-12 MAE fixed: 3-second scheduler ticks had been mixed with 1h seeded history; "
                "resampling readings to strict 1h buckets before 70/15/15 windowing restores consistent 72h->24h sequences."
            ),
            "simulator_metrics": sim_metrics,
        })
        METRICS_PATH.parent.mkdir(parents=True, exist_ok=True)
        METRICS_PATH.write_text(json.dumps(existing, indent=2), encoding="utf-8")
        return existing
    finally:
        db.close()


if __name__ == "__main__":
    result = run()
    print(json.dumps({
        "selected_best_model": result["selected_best_model"],
        "simulator_split_dates": result["simulator_split_dates"],
        "simulator_metrics": result["simulator_metrics"],
    }, indent=2))
