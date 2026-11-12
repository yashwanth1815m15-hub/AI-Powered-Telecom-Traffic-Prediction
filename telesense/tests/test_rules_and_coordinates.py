"""
Automated Tests for:
1. UI / API metrics equal artifacts/metrics.json exactly.
2. Speed-test sample validation and the >=5 sample hex-grid aggregation rule.
3. Coordinate validation (all towers inside India and inside stated state bounding boxes).
"""

import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
METRICS_PATH = Path("/Users/yashu/Desktop/telesense/artifacts/metrics.json")

# State bounding boxes for geographic validation
STATE_BBOX = {
    "Andhra Pradesh": (12.5, 19.9, 76.5, 84.8),
    "Arunachal Pradesh": (26.5, 29.5, 91.5, 97.5),
    "Assam": (24.0, 28.2, 89.5, 96.2),
    "Bihar": (24.3, 27.6, 83.3, 88.3),
    "Chhattisgarh": (17.7, 24.1, 80.2, 84.4),
    "Goa": (14.8, 15.8, 73.6, 74.4),
    "Gujarat": (20.0, 24.7, 68.1, 74.5),
    "Haryana": (27.6, 30.9, 74.4, 77.6),
    "Himachal Pradesh": (30.3, 33.3, 75.6, 79.1),
    "Jharkhand": (21.9, 25.3, 83.3, 87.9),
    "Karnataka": (11.5, 18.5, 74.0, 78.6),
    "Kerala": (8.2, 12.8, 74.8, 77.5),
    "Madhya Pradesh": (21.1, 26.9, 74.0, 82.8),
    "Maharashtra": (15.6, 22.0, 72.6, 80.9),
    "Manipur": (23.8, 25.7, 93.0, 94.8),
    "Meghalaya": (25.0, 26.1, 89.8, 92.8),
    "Mizoram": (21.9, 24.6, 92.2, 93.5),
    "Nagaland": (25.2, 27.0, 93.3, 95.3),
    "Odisha": (17.8, 22.6, 81.3, 87.5),
    "Punjab": (29.5, 32.5, 73.8, 76.9),
    "Rajasthan": (23.0, 30.2, 69.5, 78.3),
    "Sikkim": (27.0, 28.2, 88.0, 88.9),
    "Tamil Nadu": (8.0, 13.6, 76.2, 80.4),
    "Telangana": (15.8, 19.9, 77.2, 81.8),
    "Tripura": (23.0, 24.6, 91.1, 92.4),
    "Uttar Pradesh": (23.8, 30.5, 77.0, 84.7),
    "Uttarakhand": (28.7, 31.5, 77.5, 81.1),
    "West Bengal": (21.5, 27.3, 85.8, 89.9),
    "Delhi": (28.4, 28.9, 76.8, 77.4),
    "Delhi NCR": (28.2, 29.1, 76.6, 77.8),
    "Jammu & Kashmir": (32.2, 37.1, 73.4, 80.4),
    "Ladakh": (32.0, 36.0, 75.0, 80.5),
    "Chandigarh": (30.6, 30.8, 76.7, 76.9),
    "Puducherry": (11.8, 12.1, 79.7, 79.9),
    "Andaman & Nicobar": (6.5, 14.0, 92.0, 94.0),
    "Andaman and Nicobar": (6.5, 14.0, 92.0, 94.0)
}


def test_ui_metrics_equal_artifacts_metrics_json():
    """Verifies that API/UI returns numbers matching artifacts/metrics.json."""
    with open(METRICS_PATH, "r") as f:
        file_data = json.load(f)

    response = client.get("/api/model-health")
    assert response.status_code == 200
    api_data = response.json()

    # Simulator metrics equality
    for model_name, file_metrics in file_data["simulator_metrics"].items():
        assert model_name in api_data["metrics_leaderboard"]
        api_model = api_data["metrics_leaderboard"][model_name]
        assert api_model["mae_overall"] == file_metrics["mae_overall"]
        assert api_model["rmse_overall"] == file_metrics["rmse_overall"]
        assert api_model["mae_1h"] == file_metrics["mae_1h"]
        assert api_model["rmse_1h"] == file_metrics["rmse_1h"]

    # Real dataset validation equality (Cloudflare Radar India series)
    real_file = file_data["real_dataset_validation"]
    real_api = api_data["real_dataset_validation"]
    assert real_api["evaluation_method"] == real_file["evaluation_method"]
    assert real_api["split_dates"] == real_file["split_dates"]
    assert real_api["setup_required"] == real_file["setup_required"]
    for model_name, file_metrics in real_file.get("metrics", {}).items():
        assert real_api["metrics"][model_name]["mae_overall"] == file_metrics["mae_overall"]
        assert real_api["metrics"][model_name]["rmse_overall"] == file_metrics["rmse_overall"]


def test_speed_test_sample_validation():
    """Tests validation of speed-test submissions (bounds, consent, mobile-only for coverage)."""
    # 1. Missing consent -> 400
    resp = client.post("/api/crowdsource/measure", json={
        "user_consent": False,
        "download_speed_mbps": 45.0,
        "latency_ms": 25.0,
        "is_mobile_data": True,
        "lat": 19.076,
        "lon": 72.877
    })
    assert resp.status_code == 400
    assert "consent" in resp.json()["detail"].lower()

    # 2. Impossible download speed (> 5000 Mbps) -> rejected (400 or 422)
    resp = client.post("/api/crowdsource/measure", json={
        "user_consent": True,
        "download_speed_mbps": 99999.0,
        "latency_ms": 25.0,
        "is_mobile_data": True,
        "lat": 19.076,
        "lon": 72.877
    })
    assert resp.status_code in [400, 422]

    # 3. Negative download speed -> rejected (400 or 422)
    resp = client.post("/api/crowdsource/measure", json={
        "user_consent": True,
        "download_speed_mbps": -10.0,
        "latency_ms": 25.0,
        "is_mobile_data": True,
        "lat": 19.076,
        "lon": 72.877
    })
    assert resp.status_code in [400, 422]

    # 4. Wi-Fi measurement -> excluded from cellular coverage analysis
    resp = client.post("/api/crowdsource/measure", json={
        "user_consent": True,
        "download_speed_mbps": 50.0,
        "latency_ms": 20.0,
        "is_mobile_data": False,
        "lat": 19.076,
        "lon": 72.877
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == 0
    assert data["associated_tower_id"] is None
    assert "Wi-Fi" in data["plain_english_advice"]


def test_hex_grid_rule_requires_at_least_5_samples():
    """
    STRICT RULE: Aggregated hex grid on the map only returns cells
    where there are at least 5 samples.
    """
    resp = client.get("/api/crowdsource/hex-grid?min_samples=5")
    assert resp.status_code == 200
    data = resp.json()
    assert data["min_samples_threshold"] == 5

    for cell in data["hex_cells"]:
        assert cell["sample_count"] >= 5, f"Cell {cell['hex_id']} has {cell['sample_count']} samples, but min is 5!"


def test_coordinate_validation_all_towers():
    """
    Validates that every single tower in the API:
    1. Lies strictly within the sovereign geographic bounds of India (lat 6.5-37.5, lon 68.0-97.5).
    2. Lies inside the real India GeoJSON polygon and its stated state polygon.
    """
    from app.services.geo_validator import validate_point_in_state

    resp = client.get("/api/towers")
    assert resp.status_code == 200
    towers = resp.json()
    assert len(towers) > 0

    mismatches = []
    for t in towers:
        lat = t["lat"]
        lon = t["lon"]
        state = t.get("state") or t.get("circle") or "India"

        # India bounding box
        if not (6.5 <= lat <= 37.5 and 68.0 <= lon <= 97.5):
            mismatches.append(f"Tower {t['tower_id']} outside India bounds: ({lat}, {lon})")

        # Real GeoJSON polygon validation
        ok, detected = validate_point_in_state(lat, lon, state)
        if not ok:
            mismatches.append(f"Tower {t['tower_id']} failed real polygon check for {state} (detected={detected}): ({lat}, {lon})")

    assert len(mismatches) == 0, f"Found coordinate mismatches: {mismatches}"


def test_opencellid_cached_clusters_and_honest_labels():
    """
    Verifies OpenCellID records are stored once, validated against India polygon,
    labeled 'approximate position (about 1 km)' with CC BY-SA 4.0 attribution,
    and app endpoints never make live calls to OpenCellID.
    """
    from app.services.geo_validator import is_inside_india_polygon

    resp = client.get("/api/towers/opencellid-clusters")
    assert resp.status_code == 200
    data = resp.json()
    assert data["valid_india_polygon_count"] > 0
    assert data["position_label"] == "approximate position (about 1 km)"
    assert "OpenCellID, CC BY-SA 4.0, fetched" in data["attribution"]

    # Confirm cluster naming reflects area clusters (>2 km) and real fields only
    assert "area cluster" in data.get("cluster_summary_label", "")
    assert data.get("cluster_radius_km", 0) >= 2.0
    for cl in data["clusters"]:
        assert is_inside_india_polygon(cl["lat"], cl["lon"])
        assert cl["position_label"] == "approximate position (about 1 km)"
        assert cl["cluster_label"] == f"area cluster ({cl['cell_count']} cell records)"
        for rec in cl["records"]:
            assert rec["source"] == "OpenCellID"
            for forbidden in ("range", "averageSignal", "average_signal", "rsrp", "rsrp_dbm", "load_pct", "active_users", "recommendation", "avg_throughput_mbps"):
                assert forbidden not in rec

    # Confirm individual cell endpoint exposes strictly real fields when zoomed in
    rec_resp = client.get("/api/towers/opencellid-records?city=Kolkata&limit=25")
    assert rec_resp.status_code == 200
    rec_data = rec_resp.json()
    assert rec_data["returned_count"] > 0
    for rec in rec_data["records"]:
        for required_key in ("radio", "mcc", "mnc", "operator_label", "lac", "cellid", "lat", "lon", "samples", "source", "fetched_at"):
            assert required_key in rec
        for forbidden in ("range", "averageSignal", "average_signal", "rsrp", "rsrp_dbm", "load_pct", "active_users", "recommendation", "avg_throughput_mbps"):
            assert forbidden not in rec

    # Confirm app never calls OpenCellID live
    sync_resp = client.post("/api/towers/opencellid-sync", json={})
    assert sync_resp.status_code == 200
    assert sync_resp.json()["status"] == "CACHED_READ_ONLY"


def test_cited_mcc_mnc_lookup_and_fallback():
    """Operator name shown only when cited; unknown codes fall back to 'MCC xxx / MNC yy'."""
    from app.services.mcc_mnc_india import format_operator_label, lookup_operator

    assert lookup_operator(404, 45) == "Bharti Airtel"
    assert lookup_operator(405, 861) == "Reliance Jio"
    assert lookup_operator(404, 20) == "Vi (Vodafone Idea)"
    assert lookup_operator(404, 0) is None
    assert format_operator_label(404, 0) == "MCC 404 / MNC 00"
    assert format_operator_label(406, 99) == "MCC 406 / MNC 99"


def test_speedtest_excludes_automated_and_localhost_from_real_counter():
    """Automated/localhost speed-test posts get is_test=1 and do not increment real phone count."""
    from app.database import SessionLocal
    from app.models.telemetry import CrowdsourceMeasurement
    from app.api.crowdsource import is_automated_or_localhost, is_mobile_phone_user_agent

    assert is_automated_or_localhost("127.0.0.1", "localhost", "localhost", "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) Mobile/15E148") is True
    assert is_automated_or_localhost("testclient", "testserver", "", "testclient") is True
    assert is_automated_or_localhost("49.36.120.15", "demo.trycloudflare.com", "demo.trycloudflare.com", "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 Mobile Safari/537.36") is False
    assert is_mobile_phone_user_agent("Mozilla/5.0 (Linux; Android 14; Pixel 8) Mobile Safari/537.36") is True
    assert is_mobile_phone_user_agent("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/120.0.0.0 Safari/537.36") is False

    before = client.get("/api/towers/summary").json()["real_measurements_count"]
    resp = client.post("/api/crowdsource/measure", json={
        "user_consent": True,
        "download_speed_mbps": 42.5,
        "latency_ms": 21.0,
        "is_mobile_data": True,
        "network_medium": "Mobile Data",
        "browser_connection_type": "4g",
        "lat": 19.076,
        "lon": 72.877
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_test"] == 1
    assert "4g" in (body.get("network_type") or "").lower()

    after = client.get("/api/towers/summary").json()["real_measurements_count"]
    assert after == before

    # Clean up automated test row created during this test
    db = SessionLocal()
    try:
        if body.get("id", 0) > 0:
            db.query(CrowdsourceMeasurement).filter(CrowdsourceMeasurement.id == body["id"]).delete()
            db.commit()
    finally:
        db.close()
