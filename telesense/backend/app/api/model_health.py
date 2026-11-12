"""
TeleSense Model Health, Drift & Benchmarking API.
Reads strictly from artifacts/metrics.json to guarantee 100% metric consistency across API and UI.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import json
import os
import sys
from pathlib import Path
from datetime import datetime, timezone

from app.database import get_db
from app.config import DATA_DIR, PROJECT_ROOT, settings
from ml.training.drift_monitor import evaluate_model_drift
from ml.training.ml_service import format_serving_model_label

router = APIRouter(prefix="/api/model-health", tags=["Model Health & Drift"])

METRICS_PATH = PROJECT_ROOT / "artifacts" / "metrics.json"
RADAR_CACHE_PATH = DATA_DIR / "cloudflare_radar_india.json"


@router.get("")
def get_model_health_status(db: Session = Depends(get_db)):
    """Returns single-source-of-truth model metrics from artifacts/metrics.json."""
    if not METRICS_PATH.exists():
        raise HTTPException(status_code=500, detail="artifacts/metrics.json artifact not found.")

    try:
        with open(METRICS_PATH, "r") as f:
            metrics_data = json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read metrics artifact: {str(e)}")

    drift_info = evaluate_model_drift(db)
    radar_cache_info = {"cached": False, "series_count": 0, "fetched_at": None, "series": []}
    if RADAR_CACHE_PATH.exists():
        try:
            raw_r = json.loads(RADAR_CACHE_PATH.read_text(encoding="utf-8"))
            radar_cache_info = {
                "cached": True,
                "series_count": len(raw_r.get("series") or []),
                "fetched_at": raw_r.get("fetched_at"),
                "unit_label": raw_r.get("unit_label"),
                "series": [
                    {
                        "series_id": s.get("series_id"),
                        "label": s.get("label"),
                        "kind": s.get("kind"),
                        "as_name": s.get("as_name"),
                        "as_aka": s.get("as_aka"),
                        "as_type": s.get("as_type"),
                        "radar_rank_india": s.get("radar_rank_india"),
                        "traffic_share_pct": s.get("traffic_share_pct"),
                        "network_scope_note": s.get("network_scope_note"),
                        "points": s.get("points", [])[:48],
                    }
                    for s in (raw_r.get("series") or [])
                ],
            }
        except Exception:
            pass

    selected_sim_model = metrics_data.get("selected_best_model", "SARIMA_Baseline")
    return {
        "model_architecture": format_serving_model_label(selected_sim_model),
        "sequence_history_hours": metrics_data.get("sequence_history_hours", 72),
        "forecast_horizon_hours": metrics_data.get("forecast_horizon_hours", 24),
        "features_used": metrics_data.get("features_used", []),
        "metrics_leaderboard": metrics_data.get("simulator_metrics", {}),
        "simulator_split_dates": metrics_data.get("simulator_split_dates", {}),
        "simulator_diagnostic_note": metrics_data.get("simulator_diagnostic_note"),
        "trained_on_tower_id": metrics_data.get("trained_on_tower_id", "MUM-C101"),
        "is_shared_simulator_model": metrics_data.get("is_shared_simulator_model", True),
        "simulator_coverage_note": metrics_data.get(
            "simulator_coverage_note",
            "Shared simulator model trained on MUM-C101 and reused across all 99 simulated NOC towers.",
        ),
        "real_dataset_validation": metrics_data.get("real_dataset_validation", {}),
        "cloudflare_radar_token_configured": bool(settings.CLOUDFLARE_API_TOKEN),
        "cloudflare_radar_cache": radar_cache_info,
        "selected_model": selected_sim_model,
        "evaluated_at": metrics_data.get("evaluated_at"),
        "drift_status": drift_info
    }


@router.post("/run-cloudflare-pipeline")
def trigger_cloudflare_import_and_pipeline():
    """
    Runs offline Cloudflare Radar India import + chronological evaluation pipeline
    if CLOUDFLARE_API_TOKEN is present in backend/.env. Never prints or exposes the token.
    """
    if not settings.CLOUDFLARE_API_TOKEN:
        return {
            "ok": False,
            "setup_required": True,
            "message": "CLOUDFLARE_API_TOKEN is missing in backend/.env. Add it and retry, or run the CLI command.",
        }
    try:
        from app.scripts.import_cloudflare_radar import run_cloudflare_radar_import
        from ml.training.india_radar_pipeline import run_india_radar_pipeline

        import_summary = run_cloudflare_radar_import()
        metrics_out = run_india_radar_pipeline()
        return {
            "ok": True,
            "setup_required": False,
            "message": "Cloudflare Radar India import & chronological evaluation completed.",
            "import_summary": import_summary,
            "real_dataset_validation": metrics_out.get("real_dataset_validation"),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Cloudflare Radar pipeline failed: {str(exc)}")
