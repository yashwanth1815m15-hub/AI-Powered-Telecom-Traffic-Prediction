"""
End-to-End & Consistency Tests for Workstreams A, B, C, D, and E:
- Single source of truth between open alerts, tower status, summary counters, and bell badge
- Hysteresis (3 consecutive intervals) + deduplication (max 1 open per tower+type) + audit log
- Presenter Mode end-to-end chain on any chosen Indian city (activate -> alert -> marker -> action -> before/after drop -> reset)
- Speedtest Cache-Control: no-store + honest mobile counter
- Ookla Q3 2026 India tiles inside India polygon + GeoJSON /india-boundary
"""

from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient

from app.main import app
from app.database import SessionLocal
from app.models.alert import Alert, AlertAuditLog, AlertStreak
from app.models.telemetry import Reading, Tower
from app.services.alert_engine import evaluate_reading_alerts
from app.services.geo_validator import is_inside_india_polygon
from app.services.presenter_mode import presenter_manager


client = TestClient(app)


def test_single_source_of_truth_summary_towers_and_alerts():
    summary_res = client.get("/api/towers/summary")
    assert summary_res.status_code == 200
    summary = summary_res.json()

    towers_res = client.get("/api/towers")
    assert towers_res.status_code == 200
    towers = towers_res.json()

    alerts_res = client.get("/api/alerts?status=OPEN")
    assert alerts_res.status_code == 200
    open_alerts = alerts_res.json()

    status_counts = {"HEALTHY": 0, "AT_RISK": 0, "WEAK_COVERAGE": 0, "CRITICAL": 0, "OUTAGE": 0}
    for t in towers:
        st = t.get("status") or "HEALTHY"
        status_counts[st] = status_counts.get(st, 0) + 1

    assert summary["healthy_count"] == status_counts["HEALTHY"]
    assert summary["at_risk_count"] == status_counts["AT_RISK"]
    assert summary["weak_coverage_count"] == status_counts["WEAK_COVERAGE"]
    assert summary["critical_count"] == (status_counts["CRITICAL"] + status_counts["OUTAGE"])
    assert summary["outage_count"] == status_counts["OUTAGE"]
    assert summary["active_alert_count"] == len(open_alerts)
    assert summary["unread_alert_count"] == sum(1 for a in open_alerts if a["status"] == "ACTIVE")
    assert "IST" in summary.get("simulated_time_ist", "")

    pairs = [(a["tower_id"], a.get("alert_type")) for a in open_alerts]
    assert len(pairs) == len(set(pairs)), "Duplicate open alerts detected for same (tower_id, alert_type)"


def test_alert_hysteresis_and_audit_log_lifecycle():
    db = SessionLocal()
    tower = db.query(Tower).first()
    assert tower is not None
    tid = f"HYST_{tower.tower_id}"
    test_tower = Tower(
        tower_id=tid,
        name="Tirupati Hysteresis Verification Node",
        city="Tirupati",
        area_type="urban",
        lat=13.6288,
        lon=79.4192,
        capacity_mbps=1000.0,
        population_density=8000,
        source_type="SIMULATED",
    )
    db.merge(test_tower)
    db.query(Alert).filter(Alert.tower_id == tid).delete()
    db.query(AlertStreak).filter(AlertStreak.tower_id == tid).delete()
    db.query(AlertAuditLog).filter(AlertAuditLog.tower_id == tid).delete()
    db.commit()

    base_ts = datetime.now(timezone.utc)
    try:
        # Breaches 1 & 2 must NOT open an alert (hysteresis = 3 consecutive intervals)
        for step in range(2):
            r = Reading(
                tower_id=tid,
                timestamp=base_ts + timedelta(seconds=step * 10),
                load_pct=93.0,
                active_users=950,
                avg_throughput_mbps=6.5,
                rsrp_dbm=-82.0,
                sinr_db=15.0,
            )
            opened = evaluate_reading_alerts(db, test_tower, r, immediate=False)
            assert opened == []

        # 3rd consecutive breach opens exactly 1 alert
        r3 = Reading(
            tower_id=tid,
            timestamp=base_ts + timedelta(seconds=20),
            load_pct=93.0,
            active_users=950,
            avg_throughput_mbps=6.5,
            rsrp_dbm=-82.0,
            sinr_db=15.0,
        )
        opened3 = evaluate_reading_alerts(db, test_tower, r3, immediate=False)
        assert any(a.alert_type == "PREDICTED_OVERLOAD" for a in opened3)
        ov_alert = next(a for a in opened3 if a.alert_type == "PREDICTED_OVERLOAD")
        assert "Tirupati" in ov_alert.where_location
        assert "IST" in ov_alert.when_ist

        # Clears 1 & 2 keep alert open (exit hysteresis = 3)
        for step in range(2):
            r_clr = Reading(
                tower_id=tid,
                timestamp=base_ts + timedelta(seconds=30 + step * 10),
                load_pct=45.0,
                active_users=400,
                avg_throughput_mbps=65.0,
                rsrp_dbm=-80.0,
                sinr_db=22.0,
            )
            evaluate_reading_alerts(db, test_tower, r_clr, immediate=False)
            db.refresh(ov_alert)
            assert ov_alert.status == "ACTIVE"

        # 3rd clear auto-resolves & records OPENED + AUTO_RESOLVED in AlertAuditLog
        r_clr3 = Reading(
            tower_id=tid,
            timestamp=base_ts + timedelta(seconds=50),
            load_pct=45.0,
            active_users=400,
            avg_throughput_mbps=65.0,
            rsrp_dbm=-80.0,
            sinr_db=22.0,
        )
        evaluate_reading_alerts(db, test_tower, r_clr3, immediate=False)
        db.refresh(ov_alert)
        assert ov_alert.status == "RESOLVED"

        logs = db.query(AlertAuditLog).filter(AlertAuditLog.tower_id == tid).all()
        actions = {l.action for l in logs}
        assert "OPENED" in actions
        assert "AUTO_RESOLVED" in actions
    finally:
        db.query(Alert).filter(Alert.tower_id == tid).delete()
        db.query(AlertStreak).filter(AlertStreak.tower_id == tid).delete()
        db.query(AlertAuditLog).filter(AlertAuditLog.tower_id == tid).delete()
        db.query(Tower).filter(Tower.tower_id == tid).delete()
        db.commit()
        db.close()


def test_presenter_mode_full_chain_any_city_and_reset():
    client.post("/api/simulation/presenter/reset")

    towers = client.get("/api/towers").json()
    target_city = next((t["city"] for t in towers if t.get("city") == "Tirupati"), towers[0]["city"])

    # 0. Reject unknown city with N=0 error and do not start
    bad_res = client.post(
        "/api/simulation/presenter/activate",
        json={"scenario_id": "ipl_surge", "city": "AtlantisNonExistent", "auto_revert_seconds": 300},
    )
    assert bad_res.status_code == 400
    assert presenter_manager.get_status()["active"] is False

    # 1. Activate scenario on chosen city
    act_res = client.post(
        "/api/simulation/presenter/activate",
        json={"scenario_id": "ipl_surge", "city": target_city, "auto_revert_seconds": 300},
    )
    assert act_res.status_code == 200
    status = act_res.json()
    assert status["active"] is True
    assert status["banner_label"] == "DEMO SCENARIO ACTIVE"
    assert status["city"] == target_city
    assert status["affected_site_count"] >= 1
    assert len(status["affected_sites"]) == status["affected_site_count"]
    assert status["before_snapshot"]["scenario_peak_load_pct"] >= 90.0
    assert len(status["checklist"]) >= 2

    # 2. Verify live tower status and alerts reflect scenario immediately with source="demo"
    live_towers = client.get("/api/towers").json()
    target_towers = [t for t in live_towers if t["tower_id"] in status["target_tower_ids"]]
    assert any(t["status"] in ("CRITICAL", "AT_RISK", "OUTAGE", "WEAK_COVERAGE") for t in target_towers)

    open_alerts = client.get("/api/alerts?status=OPEN").json()
    demo_alerts = [a for a in open_alerts if a.get("source") == "demo"]
    assert len(demo_alerts) >= 1
    assert any(a["tower_id"] in status["target_tower_ids"] for a in demo_alerts)

    # 3. Verify recommendations populated cleanly
    rec_res = client.get("/api/recommendations")
    assert rec_res.status_code == 200
    assert len(rec_res.json()) > 0

    # 4. Apply recommended mitigation action & verify before -> after load drop
    apply_res = client.post("/api/simulation/presenter/apply-action")
    assert apply_res.status_code == 200
    after_status = apply_res.json()
    assert after_status["mitigation_applied"] is True
    assert after_status["after_snapshot"]["projected_load_pct"] < after_status["before_snapshot"]["scenario_peak_load_pct"]
    assert len(after_status.get("before_after_curve", [])) >= 3

    # 5. Reset cleanly and confirm zero demo alerts remain
    reset_res = client.post("/api/simulation/presenter/reset")
    assert reset_res.status_code == 200
    assert reset_res.json()["active"] is False
    assert presenter_manager.get_status()["active"] is False
    remaining_demo = [a for a in client.get("/api/alerts?status=OPEN").json() if a.get("source") == "demo"]
    assert remaining_demo == []


def test_speedtest_no_store_and_ookla_india_tiles():
    recent_res = client.get("/api/crowdsource/recent?limit=5")
    assert recent_res.status_code == 200
    assert "no-store" in recent_res.headers.get("cache-control", "").lower()

    ookla_res = client.get("/api/towers/ookla-tiles")
    assert ookla_res.status_code == 200
    ookla = ookla_res.json()
    assert ookla["total_india_tiles"] > 0
    assert len(ookla["tiles"]) > 0
    for tile in ookla["tiles"][:50]:
        assert is_inside_india_polygon(tile["lat"], tile["lon"])

    boundary_res = client.get("/api/towers/india-boundary")
    assert boundary_res.status_code == 200
    boundary = boundary_res.json()
    assert len(boundary.get("features", [])) > 0
