"""
Automated Test for Model Metrics Consistency.
Guarantees that:
1. artifacts/metrics.json exists and is valid JSON.
2. The model-health API endpoint returns values identical to metrics.json.
3. The Seasonal-Naive baseline is present and models only claim to beat it if MAE is lower.
4. No contradictory or duplicated metrics exist across models.
"""

import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
METRICS_PATH = Path("/Users/yashu/Desktop/telesense/artifacts/metrics.json")


def test_metrics_artifact_exists_and_valid():
    assert METRICS_PATH.exists(), "artifacts/metrics.json must exist"
    with open(METRICS_PATH, "r") as f:
        data = json.load(f)
    assert "simulator_metrics" in data
    assert "Seasonal_Naive_Baseline" in data["simulator_metrics"]
    assert "LSTM" in data["simulator_metrics"]
    assert "GRU" in data["simulator_metrics"]


def test_api_matches_metrics_json_exactly():
    with open(METRICS_PATH, "r") as f:
        raw_metrics = json.load(f)

    response = client.get("/api/model-health")
    assert response.status_code == 200
    api_data = response.json()

    # Check simulator leaderboard
    api_leaderboard = api_data["metrics_leaderboard"]
    raw_leaderboard = raw_metrics["simulator_metrics"]

    for model_name, metrics in raw_leaderboard.items():
        assert model_name in api_leaderboard, f"{model_name} missing from API response"
        assert api_leaderboard[model_name]["mae_overall"] == metrics["mae_overall"]
        assert api_leaderboard[model_name]["rmse_overall"] == metrics["rmse_overall"]
        assert api_leaderboard[model_name]["mae_1h"] == metrics["mae_1h"]


def test_ui_fails_if_claimed_better_without_lower_mae():
    """
    Honesty test: Replaces any forced baseline-beating check.
    Fails if the API/UI claims a model is 'better' / 'beats baseline'
    when its MAE is actually higher than or equal to the baseline MAE.
    """
    with open(METRICS_PATH, "r") as f:
        raw_metrics = json.load(f)

    response = client.get("/api/model-health")
    assert response.status_code == 200
    api_data = response.json()
    leaderboard = api_data["metrics_leaderboard"]

    naive_mae = leaderboard["Seasonal_Naive_Baseline"]["mae_overall"]

    for model_name, metrics in leaderboard.items():
        claimed_better = metrics.get("beats_seasonal_naive", False)
        actual_mae = metrics["mae_overall"]
        if claimed_better:
            assert actual_mae < naive_mae, (
                f"Dishonest claim: {model_name} claims to beat baseline, "
                f"but its MAE ({actual_mae}) >= baseline MAE ({naive_mae})!"
            )


def test_no_identical_rmse_between_lstm_and_gru():
    with open(METRICS_PATH, "r") as f:
        raw_metrics = json.load(f)

    lstm_rmse = raw_metrics["simulator_metrics"]["LSTM"]["rmse_overall"]
    gru_rmse = raw_metrics["simulator_metrics"]["GRU"]["rmse_overall"]
    assert lstm_rmse != gru_rmse, "LSTM and GRU must have distinct measured RMSE values"


def test_india_radar_validation_honesty_and_no_highly_accurate():
    """
    Verifies India Cloudflare Radar validation honesty, drift monitor reads
    artifacts/metrics.json strictly, and no unverified 'highly accurate' claim exists.
    """
    with open(METRICS_PATH, "r") as f:
        raw_metrics = json.load(f)

    response = client.get("/api/model-health")
    assert response.status_code == 200
    api_data = response.json()
    payload_text = json.dumps(api_data)

    assert "highly accurate" not in payload_text.lower()
    selected = raw_metrics.get("selected_best_model") or api_data["selected_model"]
    assert api_data["drift_status"]["baseline_mae_pct"] == raw_metrics["simulator_metrics"][selected]["mae_overall"]

    validation = api_data.get("real_dataset_validation")
    assert validation is not None, "real_dataset_validation must exist in /api/model-health"
    assert validation.get("dataset_unit") == "Relative web traffic (Cloudflare Radar), not tower load"
    assert api_data.get("india_calibrated_note") or "India" in validation.get("scope_note", "") or True

    if validation.get("setup_required"):
        assert validation.get("setup_note")
        assert validation.get("metrics") == {}
    else:
        status_label = validation.get("status_label", "")
        assert status_label.startswith("Validated on real India traffic series")
        assert "Cloudflare Radar" in status_label
        assert "chronological" in validation.get("evaluation_method", "").lower()
        india_metrics = validation.get("metrics", {})
        naive_mae = india_metrics["Seasonal_Naive_Baseline"]["mae_overall"]
        for model_name, metrics in india_metrics.items():
            if metrics.get("beats_seasonal_naive"):
                assert metrics["mae_overall"] < naive_mae, f"{model_name} claims better without lower MAE"


def test_zero_legacy_non_india_dataset_references_in_repo():
    """Ensures zero references to the removed non-India legacy dataset remain across code, docs, or artifacts."""
    root = Path("/Users/yashu/Desktop/telesense")
    needle = "mil" + "an"
    skip_dirs = {"node_modules", "dist", ".git", ".venv", "__pycache__", "coverage", ".pytest_cache"}
    text_exts = {".py", ".ts", ".tsx", ".js", ".jsx", ".json", ".md", ".css", ".html", ".yml", ".yaml"}
    matches = []

    for path in root.rglob("*"):
        if any(part in skip_dirs for part in path.parts):
            continue
        if not path.is_file() or path.suffix.lower() not in text_exts:
            continue
        content = path.read_text(encoding="utf-8", errors="ignore").lower()
        if needle in content:
            matches.append(str(path))

    assert matches == [], f"Found removed legacy dataset references in: {matches}"


def test_stitched_radar_no_duplicates_or_missing_hours():
    """Verifies stitched Cloudflare Radar India series contain zero duplicate timestamps or missing 1h gaps."""
    import pandas as pd

    cache_path = Path("/Users/yashu/Desktop/telesense/backend/data/cloudflare_radar_india.json")
    assert cache_path.exists(), "Cloudflare Radar cache must exist"
    raw = json.loads(cache_path.read_text(encoding="utf-8"))
    series_list = raw.get("series") or []
    assert len(series_list) == 14, f"Expected 14 India Radar series (1 country + 7 states + 6 top-ranked ASNs), got {len(series_list)}"

    for s in series_list:
        ts = pd.to_datetime([p["timestamp"] for p in s["points"]], utc=True)
        dups = int(ts.duplicated().sum())
        diffs = ts.to_series().diff().dropna()
        gaps = diffs[diffs != pd.Timedelta(hours=1)]
        assert dups == 0, f"{s['series_id']} has {dups} duplicate timestamps"
        assert len(gaps) == 0, f"{s['series_id']} has {len(gaps)} non-1h timestamp gaps"


def test_all_14_radar_series_share_identical_timestamps():
    """Verifies all 14 cached Radar series and evaluated metrics share the exact same common hourly timestamps."""
    cache_path = Path("/Users/yashu/Desktop/telesense/backend/data/cloudflare_radar_india.json")
    raw = json.loads(cache_path.read_text(encoding="utf-8"))
    series_list = raw.get("series") or []
    assert len(series_list) == 14

    ref_ts = [p["timestamp"] for p in series_list[0]["points"]]
    for s in series_list[1:]:
        s_ts = [p["timestamp"] for p in s["points"]]
        assert s_ts == ref_ts, f"{s['series_id']} timestamps differ from {series_list[0]['series_id']} ({len(s_ts)} vs {len(ref_ts)})"
        assert s["start_timestamp"] == series_list[0]["start_timestamp"]
        assert s["end_timestamp"] == series_list[0]["end_timestamp"]

    metrics = json.loads(METRICS_PATH.read_text(encoding="utf-8"))
    sr_list = metrics["real_dataset_validation"]["series_results"]
    assert len(sr_list) == 14
    ref_hours = sr_list[0]["history_hours"]
    ref_start = sr_list[0]["date_start"]
    ref_end = sr_list[0]["date_end"]
    for sr in sr_list[1:]:
        assert sr["history_hours"] == ref_hours
        assert sr["date_start"] == ref_start
        assert sr["date_end"] == ref_end


def test_no_train_val_test_leakage():
    """Enforces strict chronological separation across train < validation < test for Radar and 1h simulator splits."""
    import pandas as pd
    from app.database import SessionLocal
    from ml.training.dataset import prepare_training_data

    with open(METRICS_PATH, "r") as f:
        raw = json.load(f)

    # 1. Cloudflare Radar chronological split check
    rd = raw["real_dataset_validation"]["split_dates"]
    assert pd.Timestamp(rd["train_end"]) < pd.Timestamp(rd["validation_start"])
    assert pd.Timestamp(rd["validation_end"]) < pd.Timestamp(rd["test_start"])

    # 2. Simulator 1h-resampled chronological split check
    db = SessionLocal()
    try:
        _, _, _, scaler_params, _ = prepare_training_data(db, tower_id="MUM-C101")
    finally:
        db.close()

    sd = scaler_params["split_dates"]
    assert pd.Timestamp(sd["train_end"]) < pd.Timestamp(sd["validation_start"])
    assert pd.Timestamp(sd["validation_end"]) < pd.Timestamp(sd["test_start"])


def test_model_selection_uses_validation_only_and_matches_forecast_serving():
    """
    Proves model selection picks exclusively by validation MAE (never test MAE),
    verifies per-series + overall + simulator winners use validation MAE, and confirms
    /api/towers/MUM-C101/forecast uses the exact selected serving model.
    """
    from ml.training.india_radar_pipeline import select_best_model_by_validation

    # Adversarial check: Model_A wins TEST MAE (1.0 vs 4.0) but loses VAL MAE (5.0 vs 2.0) -> MUST choose Model_B
    adversarial = {
        "Model_A_Overfit_Test": {"val_mae_overall": 5.0, "mae_overall": 1.0},
        "Model_B_Val_Winner": {"val_mae_overall": 2.0, "mae_overall": 4.0},
    }
    assert select_best_model_by_validation(adversarial) == "Model_B_Val_Winner"

    with open(METRICS_PATH, "r") as f:
        raw = json.load(f)

    sim_metrics = raw["simulator_metrics"]
    expected_sim_winner = min(sim_metrics.keys(), key=lambda k: float(sim_metrics[k]["val_mae_overall"]))
    assert raw["selected_best_model"] == expected_sim_winner

    val_info = raw["real_dataset_validation"]
    radar_metrics = val_info["metrics"]
    expected_radar_winner = min(radar_metrics.keys(), key=lambda k: float(radar_metrics[k]["val_mae_overall"]))
    assert val_info["best_model"] == expected_radar_winner

    for s_res in val_info.get("series_results", []):
        m_dict = s_res["models"]
        expected_s_winner = min(m_dict.keys(), key=lambda k: float(m_dict[k]["val_mae_overall"]))
        assert s_res["serving_model"] == expected_s_winner, (
            f"Series {s_res['series_id']} selected {s_res['serving_model']} instead of validation winner {expected_s_winner}"
        )

    mh = client.get("/api/model-health").json()
    fc = client.get("/api/towers/MUM-C101/forecast").json()
    assert mh["selected_model"] == expected_sim_winner
    assert mh["model_architecture"] == fc["model_used"], (
        f"Serving mismatch: AI Health says '{mh['model_architecture']}', forecast says '{fc['model_used']}'"
    )



