"""
TeleSense Background Scheduler
Driven by APScheduler:
1. Live Telemetry Tick (runs every 3s):
   - Checks presenter auto-revert timer
   - Generates readings for all Indian towers (respecting active presenter scenario overrides)
   - Evaluates alerts with 3-interval hysteresis & cooldown
   - Derives fleet status counts strictly from open alerts (single source of truth)
   - Pushes live updates via WebSockets
"""

import logging
from datetime import datetime, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.telemetry import Tower, Reading
from app.models.alert import Alert
from app.services.telemetry_source import get_telemetry_source
from app.services.alert_engine import (
    evaluate_reading_alerts,
    get_fleet_status_from_open_alerts,
)
from app.services.presenter_mode import presenter_manager, SCENARIO_DEFINITIONS
from app.services.time_utils import format_ist_datetime
from app.api.websocket import ws_manager

logger = logging.getLogger("telesense.scheduler")

scheduler = AsyncIOScheduler()


async def live_telemetry_tick_job():
    """
    Executes one live telemetry cycle:
    Generates readings, runs hysteresis alerts, computes single-source-of-truth
    statuses from open DB alerts, and broadcasts over WebSockets.
    """
    db: Session = SessionLocal()
    try:
        presenter_manager.check_auto_revert(db)
        source = get_telemetry_source()
        towers = db.query(Tower).all()
        if not towers:
            return

        temp_readings = []
        new_alerts_payload = []

        for tower in towers:
            prev_reading = (
                db.query(Reading)
                .filter(Reading.tower_id == tower.tower_id)
                .order_by(Reading.timestamp.desc())
                .first()
            )
            reading_data = source.get_latest_reading(tower)
            reading = Reading(
                tower_id=reading_data["tower_id"],
                timestamp=reading_data["timestamp"].replace(tzinfo=None)
                if getattr(reading_data["timestamp"], "tzinfo", None)
                else reading_data["timestamp"],
                load_pct=reading_data["load_pct"],
                active_users=reading_data["active_users"],
                avg_throughput_mbps=reading_data["avg_throughput_mbps"],
                rsrp_dbm=reading_data["rsrp_dbm"],
                sinr_db=reading_data["sinr_db"],
            )
            db.add(reading)

            override = presenter_manager.get_scenario_override(tower.tower_id)
            hold_types = set()
            scen_ctx = None
            alert_src = "baseline"
            if override and not override["mitigation_applied"]:
                scen = override["scenario"]
                hold_types = set(scen["alert_types"])
                scen_ctx = f"DEMO: {scen['title']} ({tower.city})"
                alert_src = "demo"
            elif override and override["mitigation_applied"]:
                alert_src = "demo"

            alerts = evaluate_reading_alerts(
                db,
                tower,
                reading,
                prev_reading,
                hold_open_types=hold_types,
                scenario_context=scen_ctx,
                provenance="SIMULATED",
                source=alert_src,
            )
            for a in alerts:
                new_alerts_payload.append({
                    "id": a.id or 0,
                    "tower_id": a.tower_id,
                    "tower_name": tower.name,
                    "city": tower.city,
                    "alert_type": a.alert_type,
                    "severity": a.severity,
                    "reason": a.reason,
                    "what": a.what,
                    "where_location": a.where_location,
                    "when_ist": a.when_ist,
                    "mitigation_action": a.mitigation_action,
                    "expected_benefit": a.expected_benefit,
                    "provenance": a.provenance,
                    "created_at": a.created_at.isoformat() if a.created_at else datetime.now(timezone.utc).isoformat(),
                    "start_time": a.start_time.isoformat() if a.start_time else datetime.now(timezone.utc).isoformat(),
                    "end_time": a.end_time.isoformat() if a.end_time else datetime.now(timezone.utc).isoformat(),
                    "duration_hours": a.duration_hours or 1,
                    "peak_load_pct": a.peak_load_pct,
                    "status": a.status or "ACTIVE",
                })
            temp_readings.append((tower, reading))

        db.commit()

        # Single source of truth: derive status strictly from open alerts (baseline vs effective+demo)
        tower_ids = [t.tower_id for t, _ in temp_readings]
        status_map = get_fleet_status_from_open_alerts(db, tower_ids, include_demo=True)
        base_status_map = get_fleet_status_from_open_alerts(db, tower_ids, include_demo=False)
        open_alerts_count = db.query(Alert).filter(Alert.status.in_(["ACTIVE", "ACKNOWLEDGED"])).count()
        unread_count = db.query(Alert).filter(Alert.status == "ACTIVE").count()
        demo_alert_count = db.query(Alert).filter(Alert.source == "demo", Alert.status.in_(["ACTIVE", "ACKNOWLEDGED"])).count()

        latest_readings_payload = []
        for tower, reading in temp_readings:
            st = status_map.get(tower.tower_id, "HEALTHY")
            latest_readings_payload.append({
                "tower_id": tower.tower_id,
                "name": tower.name,
                "city": tower.city,
                "lat": tower.lat,
                "lon": tower.lon,
                "load_pct": reading.load_pct,
                "active_users": reading.active_users,
                "throughput_mbps": reading.avg_throughput_mbps,
                "rsrp_dbm": reading.rsrp_dbm,
                "status": st,
            })

        total = len(latest_readings_payload)
        outage_c = sum(1 for r in latest_readings_payload if r["status"] == "OUTAGE")
        critical_c = sum(1 for r in latest_readings_payload if r["status"] == "CRITICAL")
        warning_c = sum(1 for r in latest_readings_payload if r["status"] == "AT_RISK")
        weak_c = sum(1 for r in latest_readings_payload if r["status"] == "WEAK_COVERAGE")
        healthy_c = total - outage_c - critical_c - warning_c - weak_c

        base_outage_c = sum(1 for tid in tower_ids if base_status_map.get(tid) == "OUTAGE")
        base_critical_c = sum(1 for tid in tower_ids if base_status_map.get(tid) == "CRITICAL")
        base_warning_c = sum(1 for tid in tower_ids if base_status_map.get(tid) == "AT_RISK")
        base_weak_c = sum(1 for tid in tower_ids if base_status_map.get(tid) == "WEAK_COVERAGE")
        avg_load = sum(r["load_pct"] for r in latest_readings_payload) / total if total > 0 else 0.0

        now_utc = datetime.now(timezone.utc)
        await ws_manager.broadcast({
            "type": "TELEMETRY_TICK",
            "timestamp": now_utc.isoformat(),
            "timestamp_ist": format_ist_datetime(now_utc),
            "presenter": presenter_manager.get_status(),
            "summary": {
                "total_towers": total,
                "healthy_towers": healthy_c,
                "warning_towers": warning_c,
                "weak_coverage_towers": weak_c,
                "critical_towers": critical_c + outage_c,
                "outage_towers": outage_c,
                "baseline_critical_towers": base_critical_c + base_outage_c,
                "baseline_warning_towers": base_warning_c,
                "baseline_weak_coverage_towers": base_weak_c,
                "demo_delta_critical": max(0, (critical_c + outage_c) - (base_critical_c + base_outage_c)),
                "demo_delta_at_risk": max(0, warning_c - base_warning_c),
                "demo_delta_weak_coverage": max(0, weak_c - base_weak_c),
                "baseline_profile": presenter_manager.baseline_profile,
                "active_alert_count": open_alerts_count,
                "unread_alert_count": unread_count,
                "demo_alert_count": demo_alert_count,
                "average_load_pct": round(avg_load, 1),
                "status_source": "active_alerts",
            },
            "readings": latest_readings_payload,
            "new_alerts": new_alerts_payload,
        })

    except Exception as e:
        logger.error(f"Error in live telemetry tick: {e}", exc_info=True)
        db.rollback()
    finally:
        db.close()


def start_scheduler():
    """Starts the APScheduler background tasks."""
    if not scheduler.running:
        scheduler.add_job(
            live_telemetry_tick_job,
            "interval",
            seconds=3,
            id="live_telemetry_stream",
            replace_existing=True,
        )
        scheduler.start()
        logger.info("TeleSense background scheduler started (live telemetry interval: 3s).")


def stop_scheduler():
    """Stops the scheduler gracefully."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("TeleSense scheduler stopped.")
