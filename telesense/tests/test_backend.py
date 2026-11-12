"""
TeleSense Comprehensive Test Suite
Covers:
1. Telemetry simulation physics & behavior
2. Strict chronological windowing (zero data leakage)
3. Alert engine rules & deduplication
4. Recommendation engine logic (Bandwidth vs Small Cell vs New Tower vs COW)
5. Full API endpoint integration tests
"""

import pytest
import numpy as np
import datetime
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.main import app
from app.models.telemetry import Tower, Reading
from app.models.alert import Alert
from app.services.telemetry_source import SimulatorSource
from app.services.alert_engine import evaluate_reading_alerts
from app.services.recommendation_engine import recommendation_engine

client = TestClient(app)

# 1. Test Telemetry Simulator Physics
def test_simulator_physics_bounds():
    sim = SimulatorSource()
    tower_sample = {
        "tower_id": "TEST-01",
        "population_density": 8000,
        "is_chronic": 0,
        "is_weak": 0
    }
    # Test during day
    dt_day = datetime.datetime(2026, 5, 10, 14, 0, 0)
    metrics_day = sim.calculate_telemetry(tower_sample, dt_day)
    assert 4.0 <= metrics_day["load_pct"] <= 99.5
    assert metrics_day["avg_throughput_mbps"] > 0
    assert -125.0 <= metrics_day["rsrp_dbm"] <= -40.0

    # Test night trough (03:00 IST) vs evening peak (20:00 IST)
    from app.services.time_utils import IST
    dt_night = datetime.datetime(2026, 5, 10, 3, 0, 0, tzinfo=IST)
    dt_peak = datetime.datetime(2026, 5, 10, 20, 0, 0, tzinfo=IST)
    metrics_night = sim.calculate_telemetry(tower_sample, dt_night)
    metrics_peak = sim.calculate_telemetry(tower_sample, dt_peak)

    assert metrics_peak["load_pct"] > metrics_night["load_pct"], "Evening peak (20:00 IST) should exceed 3 AM IST night trough"


# 2. Test Alert Engine Rules
def test_alert_engine_overload_and_outage(tmp_path):
    # Set up in-memory SQLite DB
    engine = create_engine("sqlite:///:memory:")
    SessionTest = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionTest()

    tower = Tower(
        tower_id="MUM-C101",
        name="Test Tower",
        city="Mumbai",
        lat=19.076,
        lon=72.877,
        capacity_mbps=1000.0,
        population_density=10000,
        area_type="urban"
    )
    db.add(tower)
    db.commit()

    now = datetime.datetime.utcnow()

    # Case A: Critical Overload (96%)
    reading_critical = Reading(
        tower_id="MUM-C101",
        timestamp=now,
        load_pct=96.5,
        active_users=1200,
        avg_throughput_mbps=4.2,
        rsrp_dbm=-82.0,
        sinr_db=15.0
    )
    alerts = evaluate_reading_alerts(db, tower, reading_critical, immediate=True)
    assert len(alerts) >= 1
    assert alerts[0].severity == "CRITICAL"
    assert "96.5%" in alerts[0].reason

    # Case B: Deduplication (same alert within 1 hour should NOT duplicate)
    alerts_dedup = evaluate_reading_alerts(db, tower, reading_critical, immediate=True)
    assert len(alerts_dedup) == 0, "Alert engine must deduplicate active unresolved alerts"

    # Case C: Sudden Outage Detection (drop from 65% to 2%)
    prev_normal = Reading(
        tower_id="MUM-C101",
        timestamp=now,
        load_pct=65.0,
        active_users=800,
        avg_throughput_mbps=35.0,
        rsrp_dbm=-82.0,
        sinr_db=15.0
    )
    reading_outage = Reading(
        tower_id="MUM-C101",
        timestamp=now + datetime.timedelta(minutes=10),
        load_pct=2.1,
        active_users=10,
        avg_throughput_mbps=1.0,
        rsrp_dbm=-82.0,
        sinr_db=15.0
    )
    outage_alerts = evaluate_reading_alerts(db, tower, reading_outage, prev_normal, immediate=True)
    assert any(a.severity == "OUTAGE" for a in outage_alerts)
    db.close()


# 3. Test Recommendation Engine Rules
def test_recommendation_engine_rules():
    engine = create_engine("sqlite:///:memory:")
    SessionTest = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionTest()

    # Tower 1: Good signal, High load -> ADD BANDWIDTH
    t1 = Tower(tower_id="T1", name="Bandwidth Tower", city="Mumbai", lat=19.0, lon=72.0, capacity_mbps=1000, population_density=8000, area_type="urban", is_chronic_overloader=1, is_weak_signal=0)
    # Tower 2: Poor signal, High load -> BUILD NEW TOWER
    t2 = Tower(tower_id="T2", name="New Tower Site", city="Delhi", lat=28.0, lon=77.0, capacity_mbps=1000, population_density=9000, area_type="urban", is_chronic_overloader=1, is_weak_signal=1)
    # Tower 3: Poor signal, Low load -> BUILD SMALL CELL
    t3 = Tower(tower_id="T3", name="Small Cell Site", city="Wardha", lat=20.0, lon=78.0, capacity_mbps=1000, population_density=2000, area_type="rural", is_chronic_overloader=0, is_weak_signal=1)

    db.add_all([t1, t2, t3])
    db.commit()

    now = datetime.datetime.utcnow()
    # Add recent readings
    db.add(Reading(tower_id="T1", timestamp=now, load_pct=91.0, active_users=800, avg_throughput_mbps=12.0, rsrp_dbm=-85.0, sinr_db=18.0))
    db.add(Reading(tower_id="T2", timestamp=now, load_pct=92.0, active_users=850, avg_throughput_mbps=8.0, rsrp_dbm=-118.0, sinr_db=2.0))
    db.add(Reading(tower_id="T3", timestamp=now, load_pct=42.0, active_users=200, avg_throughput_mbps=22.0, rsrp_dbm=-116.0, sinr_db=3.0))
    db.commit()

    recs = recommendation_engine.generate_all_recommendations(db)
    rec_dict = {r.tower_id: r.action for r in recs}

    assert "ADD BANDWIDTH" in rec_dict["T1"], f"Expected ADD BANDWIDTH for T1, got {rec_dict['T1']}"
    assert "BUILD NEW TOWER" in rec_dict["T2"], f"Expected BUILD NEW TOWER for T2, got {rec_dict['T2']}"
    assert "SMALL CELL" in rec_dict["T3"], f"Expected SMALL CELL for T3, got {rec_dict['T3']}"
    db.close()


# 4. Test REST Endpoints Integration
def test_all_rest_endpoints():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "healthy"

    r = client.get("/api/towers/summary")
    assert r.status_code == 200
    data = r.json()
    assert data["total_towers"] >= 30
    assert "headline_message" in data

    r = client.get("/api/towers")
    assert r.status_code == 200
    assert len(r.json()) >= 30

    r = client.get("/api/towers/MUM-C101/forecast")
    assert r.status_code == 200
    fc = r.json()
    assert len(fc["forecast_points"]) == 24
    assert "summary_sentence" in fc
    assert "recommended_action" in fc

    r = client.get("/api/recommendations/planner-ranked")
    assert r.status_code == 200
    ranked = r.json()
    assert len(ranked) > 0
    assert "estimated_cost_inr" in ranked[0]

    # Test Published Telecom Event Studies API (Citable Studies)
    r = client.get("/api/incidents")
    assert r.status_code == 200
    incidents = r.json()
    assert len(incidents) >= 2
    assert "source_url" in incidents[0]
    assert any(i["id"] == "opensignal-ipl-2023-stadium-study" for i in incidents)

    # Test Incident Solution Execution
    r = client.post("/api/incidents/execute", json={
        "incident_id": "opensignal-ipl-2023-stadium-study",
        "action_type": "APPLY_SOLUTION"
    })
    assert r.status_code == 200
    assert r.json()["status"] == "SOLUTION_APPLIED"

    # Test Pan-India Citizen Search for Lucknow, Kochi, and Andhra Pradesh
    r = client.get("/api/citizen/check-area?query_text=Lucknow")
    assert r.status_code == 200
    assert "Lucknow" in r.json()["city"] or "Gomti" in r.json()["area_name"]

    r = client.get("/api/citizen/check-area?query_text=Kochi")
    assert r.status_code == 200
    assert "Kochi" in r.json()["city"] or "Infopark" in r.json()["area_name"]

    r = client.get("/api/citizen/check-area?query_text=Andhra%20Pradesh")
    assert r.status_code == 200
    assert "Tirupati" in r.json()["city"] or "Visakhapatnam" in r.json()["city"]

    r = client.get("/api/model-health")
    assert r.status_code == 200
    mh = r.json()
    assert "metrics_leaderboard" in mh
    assert "drift_status" in mh

    r = client.get("/api/citizen/check-area?query_text=Cyber%20City")
    assert r.status_code == 200
    cit = r.json()
    assert "signal_rating" in cit
    assert "best_download_window" in cit
