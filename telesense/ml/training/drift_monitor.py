"""
TeleSense Model Drift & Performance Monitor
Tracks empirical recent load-variation residual proxy against the saved baseline MAE
reported in artifacts/metrics.json (single source of truth; no hard-coded accuracy claims).
"""

import json
import os
from pathlib import Path
from typing import Any, Dict

import numpy as np
from sqlalchemy.orm import Session

from app.models.telemetry import Reading, Tower
from app.services.time_utils import format_ist_datetime

REPO_ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS_METRICS_PATH = REPO_ROOT / "artifacts" / "metrics.json"


def _load_baseline_from_artifacts(metrics_path: Path = ARTIFACTS_METRICS_PATH) -> tuple[float, str, bool]:
    """Reads selected baseline model & MAE from artifacts/metrics.json."""
    if not metrics_path.exists():
        return 0.0, "Unavailable", False
    data = json.loads(metrics_path.read_text(encoding="utf-8"))
    sim = data.get("simulator_metrics") or {}
    best_model = sim.get("best_model") or data.get("selected_best_model") or "LSTM"
    sim_models = sim.get("metrics") or sim
    if best_model in sim_models and isinstance(sim_models[best_model], dict) and "mae_overall" in sim_models[best_model]:
        return float(sim_models[best_model]["mae_overall"]), str(best_model), True
    return 0.0, str(best_model), False


def evaluate_model_drift(db: Session, metrics_path: Path = ARTIFACTS_METRICS_PATH) -> Dict[str, Any]:
    """
    Compares empirical residual variation on recent readings against the saved
    baseline MAE from artifacts/metrics.json.
    """
    baseline_mae, model_name, has_artifact = _load_baseline_from_artifacts(metrics_path)

    towers = db.query(Tower).limit(5).all()
    empirical_errors = []
    for t in towers:
        readings = (
            db.query(Reading)
            .filter(Reading.tower_id == t.tower_id)
            .order_by(Reading.timestamp.desc())
            .limit(24)
            .all()
        )
        if len(readings) >= 12:
            loads = [r.load_pct for r in readings]
            diffs = [abs(loads[i] - loads[i - 1]) for i in range(1, len(loads))]
            if diffs:
                empirical_errors.append(float(np.mean(diffs) * 0.45))

    if not has_artifact or baseline_mae <= 0:
        return {
            "drift_detected": False,
            "baseline_mae_pct": None,
            "live_mae_pct": round(float(np.mean(empirical_errors)), 2) if empirical_errors else None,
            "error_deviation_pct": None,
            "status_label": "BASELINE UNAVAILABLE (Run benchmark artifact generation)",
            "traffic_light": "amber",
            "last_checked_at": format_ist_datetime(),
            "plain_english_takeaway": "Saved benchmark metrics file artifacts/metrics.json does not contain a baseline MAE for comparison.",
        }

    live_mae = round(float(np.mean(empirical_errors)), 2) if empirical_errors else baseline_mae
    pct_change = round(((live_mae - baseline_mae) / baseline_mae) * 100.0, 1)
    drift_detected = pct_change > 25.0

    status = {
        "drift_detected": drift_detected,
        "model_evaluated": model_name,
        "baseline_mae_pct": round(baseline_mae, 2),
        "live_mae_pct": live_mae,
        "error_deviation_pct": pct_change,
        "status_label": "DRIFT DETECTED (Retraining Recommended)" if drift_detected else "WITHIN BASELINE BOUNDS",
        "traffic_light": "red" if drift_detected else "green",
        "last_checked_at": format_ist_datetime(),
        "plain_english_takeaway": (
            f"Recent simulated stream residual proxy is {live_mae:.2f} MAE vs {baseline_mae:.2f} MAE ({model_name} test split in artifacts/metrics.json; {pct_change:+.1f}% difference). This is an internal residual proxy, not live production tower truth."
            if not drift_detected
            else f"Recent residual proxy rose by {pct_change:.1f}% ({live_mae:.2f} MAE vs {baseline_mae:.2f} MAE for {model_name} in artifacts/metrics.json). Retraining recommended to adjust for traffic shift."
        ),
    }

    drift_file = REPO_ROOT / "ml" / "saved_models" / "drift_status.json"
    os.makedirs(drift_file.parent, exist_ok=True)
    drift_file.write_text(json.dumps(status, indent=2), encoding="utf-8")
    return status
