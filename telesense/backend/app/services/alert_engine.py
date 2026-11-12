"""
TeleSense Alert Engine — Single Source of Truth with Hysteresis & Audit Trail.

Features:
- Canonical alert types: PREDICTED_OVERLOAD, WEAK_COVERAGE, OUTAGE, DEGRADED_SPEED.
- Strict deduplication: max 1 open (ACTIVE or ACKNOWLEDGED) alert per (tower_id, alert_type).
- Hysteresis: 3 consecutive breaching intervals to open; 3 consecutive clear intervals to auto-resolve.
- Cooldown window (15 min default) after resolution before re-opening the same (tower_id, alert_type).
- Single source of truth for tower status: HEALTHY / AT_RISK / CRITICAL / OUTAGE derived directly from open alerts.
- Unique per-tower contextual description: what, where (city, state), when (IST), numeric evidence,
  ranked cause hypotheses (never stated as certainty), playbook recommended action, expected benefit, provenance.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

from sqlalchemy.orm import Session

from app.config import settings
from app.models.alert import Alert, AlertAuditLog, AlertStreak
from app.models.telemetry import Reading, Tower
from app.services.seed_towers_data import SEED_TOWERS
from app.services.time_utils import format_ist_datetime

logger = logging.getLogger("telesense.alert_engine")

HYSTERESIS_IN = 3
HYSTERESIS_OUT = 3
COOLDOWN_MINUTES = 15

ALERT_TYPES = ("PREDICTED_OVERLOAD", "WEAK_COVERAGE", "OUTAGE", "DEGRADED_SPEED")

_STATE_BY_TOWER_ID = {t["tower_id"]: t.get("state", "India") for t in SEED_TOWERS}

SEVERITY_RANK = {"OUTAGE": 0, "CRITICAL": 1, "WARNING": 2}


def _resolve_state(tower: Tower) -> str:
    return _STATE_BY_TOWER_ID.get(tower.tower_id, tower.city or "India")


def _utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _as_naive(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def record_alert_audit(
    db: Session,
    alert_id: Optional[int],
    tower_id: str,
    alert_type: str,
    action: str,
    actor: str = "system",
    note: Optional[str] = None,
    timestamp: Optional[datetime] = None,
) -> AlertAuditLog:
    entry = AlertAuditLog(
        alert_id=alert_id,
        tower_id=tower_id,
        alert_type=alert_type,
        action=action,
        actor=actor,
        note=note,
        timestamp=_as_naive(timestamp) or _utcnow_naive(),
    )
    db.add(entry)
    return entry


def deduplicate_open_alerts(db: Session) -> int:
    """Ensures at most 1 open (ACTIVE/ACKNOWLEDGED) alert exists per (tower_id, alert_type)."""
    open_alerts = (
        db.query(Alert)
        .filter(Alert.status.in_(["ACTIVE", "ACKNOWLEDGED"]))
        .order_by(Alert.created_at.desc(), Alert.id.desc())
        .all()
    )
    seen: set[Tuple[str, str]] = set()
    cleaned = 0
    now = _utcnow_naive()
    for a in open_alerts:
        atype = (a.alert_type or "PREDICTED_OVERLOAD").upper()
        key = (a.tower_id, atype)
        if key in seen:
            a.status = "RESOLVED"
            a.resolved_at = now
            cleaned += 1
        else:
            seen.add(key)
    if cleaned > 0:
        db.commit()
    return cleaned


def derive_tower_status_from_alerts(open_alerts: Sequence[Alert]) -> str:
    """
    Canonical tower health classification driven solely by open alerts:
    OUTAGE -> CRITICAL (overloaded/degraded critical) -> AT_RISK (overloaded/degraded warn)
    -> WEAK_COVERAGE (weak signal amber, never overloaded/critical) -> HEALTHY.
    """
    active = [a for a in open_alerts if a.status in ("ACTIVE", "ACKNOWLEDGED")]
    if not active:
        return "HEALTHY"
    types_sevs = {((a.alert_type or "").upper(), (a.severity or "").upper()) for a in active}
    severities = {sev for _, sev in types_sevs}
    if "OUTAGE" in severities:
        return "OUTAGE"
    if any(sev == "CRITICAL" and atype != "WEAK_COVERAGE" for atype, sev in types_sevs):
        return "CRITICAL"
    if any(atype in ("PREDICTED_OVERLOAD", "DEGRADED_SPEED") for atype, _ in types_sevs):
        return "AT_RISK"
    if any(atype == "WEAK_COVERAGE" for atype, _ in types_sevs):
        return "WEAK_COVERAGE"
    return "HEALTHY"


def get_fleet_status_from_open_alerts(
    db: Session,
    tower_ids: Sequence[str],
    include_demo: bool = True,
) -> Dict[str, str]:
    """Returns {tower_id: status} strictly derived from open alerts in DB."""
    query = db.query(Alert).filter(Alert.status.in_(["ACTIVE", "ACKNOWLEDGED"]))
    if not include_demo:
        query = query.filter(Alert.source != "demo")
    open_alerts = query.all()
    by_tower: Dict[str, List[Alert]] = {}
    for a in open_alerts:
        by_tower.setdefault(a.tower_id, []).append(a)
    return {tid: derive_tower_status_from_alerts(by_tower.get(tid, [])) for tid in tower_ids}


def _get_or_create_streak(db: Session, tower_id: str, alert_type: str) -> AlertStreak:
    streak = (
        db.query(AlertStreak)
        .filter(AlertStreak.tower_id == tower_id, AlertStreak.alert_type == alert_type)
        .first()
    )
    if not streak:
        streak = AlertStreak(
            tower_id=tower_id,
            alert_type=alert_type,
            consecutive_breach_count=0,
            consecutive_clear_count=0,
        )
        db.add(streak)
        db.flush()
    return streak


def _build_rich_alert_fields(
    tower: Tower,
    alert_type: str,
    severity: str,
    reading: Reading,
    prev_reading: Optional[Reading],
    scenario_context: Optional[str] = None,
) -> Dict[str, Any]:
    """Produces unique, evidence-backed structured metadata (never identical templated prose)."""
    state = _resolve_state(tower)
    where_loc = f"{tower.name}, {tower.city}, {state}"
    ts_ist = format_ist_datetime(reading.timestamp)
    prev_load = prev_reading.load_pct if prev_reading else reading.load_pct

    evidence = {
        "load_pct": round(float(reading.load_pct), 1),
        "prev_load_pct": round(float(prev_load), 1),
        "active_users": int(reading.active_users),
        "throughput_mbps": round(float(reading.avg_throughput_mbps), 1),
        "rsrp_dbm": round(float(reading.rsrp_dbm), 1),
        "sinr_db": round(float(reading.sinr_db), 1),
        "capacity_mbps": round(float(tower.capacity_mbps), 0),
        "threshold_warning_pct": settings.DEFAULT_WARNING_THRESHOLD_PCT,
        "threshold_critical_pct": settings.DEFAULT_CRITICAL_THRESHOLD_PCT,
    }

    if alert_type == "OUTAGE":
        what = (
            f"Traffic on {tower.tower_id} ({tower.name}) collapsed from {prev_load:.1f}% to "
            f"{reading.load_pct:.1f}% ({reading.active_users} active UEs, {reading.avg_throughput_mbps:.1f} Mbps)"
        )
        causes = [
            {"hypothesis": "Optical backhaul / fibre cut on aggregation ring", "likelihood": "High hypothesis", "clue": "Sudden load drop to near-zero across sector"},
            {"hypothesis": "Site AC grid trip with depleted battery / DG fault", "likelihood": "Medium hypothesis", "clue": "Total baseband unavailability regardless of diurnal hour"},
            {"hypothesis": "Baseband unit (BBU) or RRU hardware fault", "likelihood": "Secondary hypothesis", "clue": f"SINR fell to {reading.sinr_db:.1f} dB"},
        ]
        action = "REPAIR BACKHAUL / REROUTE TRAFFIC: Dispatch NOC field crew to inspect transport link & power rectifier; tilt neighbor cells (+2 deg azimuth offload) immediately."
        benefit = f"Restores service to ~{max(150, int(tower.population_density * 0.08)):,} catchment subscribers and cuts dropped call rate below <=2.0%."
        if scenario_context:
            what = f"{what} [{scenario_context}]"

    elif alert_type == "WEAK_COVERAGE":
        what = (
            f"Persistent weak RF coverage at {tower.tower_id} ({tower.name}): RSRP measured "
            f"{reading.rsrp_dbm:.1f} dBm (SINR {reading.sinr_db:.1f} dB) vs {settings.RSRP_POOR_THRESHOLD:.0f} dBm floor"
        )
        causes = [
            {"hypothesis": "Sparse inter-site distance / terrain obstruction in sector", "likelihood": "High hypothesis", "clue": f"RSRP at {reading.rsrp_dbm:.1f} dBm while PRB load is {reading.load_pct:.1f}%"},
            {"hypothesis": "Antenna electrical tilt / azimuth misalignment", "likelihood": "Medium hypothesis", "clue": f"Low SINR ({reading.sinr_db:.1f} dB) near cell edge"},
            {"hypothesis": "Adjacent sector RF interference or foliage clutter", "likelihood": "Secondary hypothesis", "clue": f"Downlink speed restricted to {reading.avg_throughput_mbps:.1f} Mbps"},
        ]
        if tower.area_type == "rural" or tower.population_density < 2500:
            action = "BUILD LOW-COST SMALL CELL / REPEATER: Install solar-backed sub-GHz/L900 repeater pole or micro site to close rural shadow."
            benefit = "Raises edge RSRP by +12 to +18 dB and cuts call setup failures without full macro tower Capex."
        else:
            action = "BUILD NEW TOWER / 5G SMALL CELL: Deploy street-level 5G small cell densification and retune antenna down-tilt."
            benefit = "Eliminates indoor dark spot and boosts cell-edge throughput above 25 Mbps."
        if scenario_context:
            what = f"{what} [{scenario_context}]"

    elif alert_type == "DEGRADED_SPEED":
        what = (
            f"User-plane throughput degraded at {tower.tower_id} ({tower.name}) to "
            f"{reading.avg_throughput_mbps:.1f} Mbps (PRB load {reading.load_pct:.1f}%, {reading.active_users} users)"
        )
        causes = [
            {"hypothesis": "PRB scheduler contention during concurrent streaming surge", "likelihood": "High hypothesis", "clue": f"{reading.active_users} concurrent UEs sharing {tower.capacity_mbps:.0f} Mbps"},
            {"hypothesis": "Backhaul microwave / transport shaping under rain fade", "likelihood": "Medium hypothesis", "clue": f"Throughput {reading.avg_throughput_mbps:.1f} Mbps below nominal tier"},
            {"hypothesis": "256-QAM modulation step-down from noisy SINR", "likelihood": "Secondary hypothesis", "clue": f"SINR at {reading.sinr_db:.1f} dB"},
        ]
        action = "ADD BANDWIDTH / DEPLOY TEMPORARY CELL-ON-WHEELS: Enable Band 40 + n78 carrier aggregation or stage CoW for peak congestion window."
        benefit = f"Relieves PRB bottleneck by ~35-40% and lifts median user speed from {reading.avg_throughput_mbps:.1f} Mbps above 25+ Mbps."
        if scenario_context:
            what = f"{what} [{scenario_context}]"

    else:  # PREDICTED_OVERLOAD
        what = (
            f"Capacity overload on {tower.tower_id} ({tower.name}) at {reading.load_pct:.1f}% load "
            f"with {reading.active_users} active users (throughput {reading.avg_throughput_mbps:.1f} Mbps)"
        )
        causes = [
            {"hypothesis": "Peak-hour subscriber concurrency exceeding sector PRB headroom", "likelihood": "High hypothesis", "clue": f"Load {reading.load_pct:.1f}% above {settings.DEFAULT_WARNING_THRESHOLD_PCT:.0f}% planning ceiling"},
            {"hypothesis": "Localized gathering / event surge in catchment", "likelihood": "Medium hypothesis", "clue": f"{reading.active_users} UEs active vs {tower.population_density}/km² baseline"},
            {"hypothesis": "Neighbor sector spillover forcing handovers onto this cell", "likelihood": "Secondary hypothesis", "clue": f"RSRP stable ({reading.rsrp_dbm:.1f} dBm) while load climbs"},
        ]
        if severity == "CRITICAL":
            action = "ADD BANDWIDTH / TEMPORARY CELL-ON-WHEELS: Activate dual-carrier aggregation (+40 MHz) and dispatch temporary CoW if event-driven."
            benefit = f"Reduces peak PRB utilization from {reading.load_pct:.1f}% to ~{max(52.0, reading.load_pct - 26.0):.1f}% within headroom."
        else:
            action = "ADD BANDWIDTH (CARRIER AGGREGATION): Pre-allocate secondary carrier & balance idle-mode reselection thresholds."
            benefit = f"Maintains PRB load below {settings.DEFAULT_WARNING_THRESHOLD_PCT:.0f}% threshold during evening busy hours."
        if scenario_context:
            what = f"{what} [{scenario_context}]"

    return {
        "what": what,
        "where_location": where_loc,
        "when_ist": ts_ist,
        "evidence_json": json.dumps(evidence),
        "ranked_causes_json": json.dumps(causes),
        "expected_benefit": benefit,
        "reason": what,
        "mitigation_action": action,
    }


def _evaluate_condition_with_hysteresis(
    db: Session,
    tower: Tower,
    alert_type: str,
    breached: bool,
    severity: str,
    reading: Reading,
    prev_reading: Optional[Reading],
    now: datetime,
    immediate: bool = False,
    hold_open: bool = False,
    scenario_context: Optional[str] = None,
    provenance: str = "SIMULATED",
    source: str = "baseline",
) -> Optional[Alert]:
    """
    Applies hysteresis (3 consecutive intervals in, 3 out) & cooldown per (tower_id, alert_type).
    Returns newly opened Alert if transition occurred, else None.
    """
    streak = _get_or_create_streak(db, tower.tower_id, alert_type)
    open_alert = (
        db.query(Alert)
        .filter(
            Alert.tower_id == tower.tower_id,
            Alert.alert_type == alert_type,
            Alert.status.in_(["ACTIVE", "ACKNOWLEDGED"]),
        )
        .first()
    )

    if breached:
        streak.consecutive_clear_count = 0
        streak.consecutive_breach_count = HYSTERESIS_IN if immediate else (streak.consecutive_breach_count + 1)
        streak.updated_at = now

        if open_alert:
            # Update severity cleanly (supports escalation AND gradual de-escalation red->amber during mitigation)
            if alert_type != "WEAK_COVERAGE":
                open_alert.severity = severity
            open_alert.peak_load_pct = round(float(reading.load_pct), 1)
            if source == "demo":
                open_alert.source = "demo"
            return None

        in_cooldown = (
            not immediate
            and streak.cooldown_until is not None
            and _as_naive(streak.cooldown_until) > now
        )
        if not in_cooldown and streak.consecutive_breach_count >= HYSTERESIS_IN:
            rich = _build_rich_alert_fields(
                tower=tower,
                alert_type=alert_type,
                severity=severity,
                reading=reading,
                prev_reading=prev_reading,
                scenario_context=scenario_context,
            )
            new_alert = Alert(
                tower_id=tower.tower_id,
                alert_type=alert_type,
                severity=severity,
                peak_load_pct=round(float(reading.load_pct), 1),
                reason=rich["reason"],
                mitigation_action=rich["mitigation_action"],
                what=rich["what"],
                where_location=rich["where_location"],
                when_ist=rich["when_ist"],
                evidence_json=rich["evidence_json"],
                ranked_causes_json=rich["ranked_causes_json"],
                expected_benefit=rich["expected_benefit"],
                provenance=provenance,
                source=source,
                start_time=now,
                end_time=now + timedelta(hours=3),
                duration_hours=3,
                status="ACTIVE",
                created_at=now,
            )
            db.add(new_alert)
            db.flush()
            record_alert_audit(
                db=db,
                alert_id=new_alert.id,
                tower_id=tower.tower_id,
                alert_type=alert_type,
                action="OPENED",
                actor="presenter_demo" if immediate else "alert_engine",
                note=rich["what"],
                timestamp=now,
            )
            return new_alert
    else:
        streak.consecutive_breach_count = 0
        streak.consecutive_clear_count = streak.consecutive_clear_count + 1
        streak.updated_at = now

        if open_alert and not hold_open and streak.consecutive_clear_count >= HYSTERESIS_OUT:
            open_alert.status = "RESOLVED"
            open_alert.resolved_at = now
            streak.cooldown_until = now + timedelta(minutes=COOLDOWN_MINUTES)
            record_alert_audit(
                db=db,
                alert_id=open_alert.id,
                tower_id=tower.tower_id,
                alert_type=alert_type,
                action="AUTO_RESOLVED",
                actor="alert_engine",
                note=f"Condition cleared for {HYSTERESIS_OUT} consecutive intervals; {COOLDOWN_MINUTES}m cooldown started.",
                timestamp=now,
            )
            db.flush()

    return None


def evaluate_reading_alerts(
    db: Session,
    tower: Tower,
    current_reading: Reading,
    prev_reading: Optional[Reading] = None,
    immediate: bool = False,
    hold_open_types: Optional[set[str]] = None,
    scenario_context: Optional[str] = None,
    provenance: str = "SIMULATED",
    source: str = "baseline",
) -> List[Alert]:
    """
    Evaluates real-time telemetry across the 4 alert types using 3-interval hysteresis & cooldown.
    """
    new_alerts: List[Alert] = []
    now = _as_naive(current_reading.timestamp) or _utcnow_naive()
    hold_open_types = hold_open_types or set()

    # 1. OUTAGE: sustained drop < 5% (with drop from > 25% or immediate presenter scenario)
    is_outage = bool(
        current_reading.load_pct < 5.0
        and ((prev_reading and prev_reading.load_pct > 25.0) or immediate or "OUTAGE" in hold_open_types)
    )
    a_out = _evaluate_condition_with_hysteresis(
        db, tower, "OUTAGE", is_outage, "OUTAGE", current_reading, prev_reading, now,
        immediate=immediate, hold_open=("OUTAGE" in hold_open_types),
        scenario_context=scenario_context, provenance=provenance, source=source,
    )
    if a_out:
        new_alerts.append(a_out)

    # 2. PREDICTED_OVERLOAD: capacity >= 85% (WARNING) or >= 95% (CRITICAL)
    is_overload = current_reading.load_pct >= settings.DEFAULT_WARNING_THRESHOLD_PCT
    overload_sev = "CRITICAL" if current_reading.load_pct >= settings.DEFAULT_CRITICAL_THRESHOLD_PCT else "WARNING"
    a_cap = _evaluate_condition_with_hysteresis(
        db, tower, "PREDICTED_OVERLOAD", is_overload, overload_sev, current_reading, prev_reading, now,
        immediate=immediate, hold_open=("PREDICTED_OVERLOAD" in hold_open_types),
        scenario_context=scenario_context, provenance=provenance, source=source,
    )
    if a_cap:
        new_alerts.append(a_cap)

    # 3. WEAK_COVERAGE: RSRP below -110 dBm -> strictly amber WARNING ('Weak coverage'), NEVER Critical/Overloaded
    is_weak = current_reading.rsrp_dbm < -110.0 and not is_outage
    weak_sev = "WARNING"
    a_weak = _evaluate_condition_with_hysteresis(
        db, tower, "WEAK_COVERAGE", is_weak, weak_sev, current_reading, prev_reading, now,
        immediate=immediate, hold_open=("WEAK_COVERAGE" in hold_open_types),
        scenario_context=scenario_context, provenance=provenance, source=source,
    )
    if a_weak:
        new_alerts.append(a_weak)

    # 4. DEGRADED_SPEED: throughput < 8.0 Mbps when not in OUTAGE (skip if weak-coverage-only tower unless severe congestion)
    is_slow = (current_reading.avg_throughput_mbps < 8.0) and not is_outage and not (is_weak and not is_overload)
    slow_sev = "CRITICAL" if (current_reading.avg_throughput_mbps < 4.0 and is_overload) else "WARNING"
    a_spd = _evaluate_condition_with_hysteresis(
        db, tower, "DEGRADED_SPEED", is_slow, slow_sev, current_reading, prev_reading, now,
        immediate=immediate, hold_open=("DEGRADED_SPEED" in hold_open_types),
        scenario_context=scenario_context, provenance=provenance, source=source,
    )
    if a_spd:
        new_alerts.append(a_spd)

    return new_alerts


def evaluate_forecast_alerts(db: Session, tower: Tower, forecast_points: list) -> List[Alert]:
    """Evaluates 24h forecast curve; creates/updates single PREDICTED_OVERLOAD per tower if peak >= threshold."""
    if not forecast_points:
        return []
    peak_pt = max(
        forecast_points,
        key=lambda x: getattr(x, "forecast_load_pct", getattr(x, "predicted_load_pct", 0)),
        default=None,
    )
    if not peak_pt:
        return []
    peak_val = float(getattr(peak_pt, "forecast_load_pct", getattr(peak_pt, "predicted_load_pct", 0)))
    if peak_val < settings.DEFAULT_WARNING_THRESHOLD_PCT:
        return []

    existing = (
        db.query(Alert)
        .filter(
            Alert.tower_id == tower.tower_id,
            Alert.alert_type == "PREDICTED_OVERLOAD",
            Alert.status.in_(["ACTIVE", "ACKNOWLEDGED"]),
        )
        .first()
    )
    if existing:
        return []

    now = _utcnow_naive()
    severity = "CRITICAL" if peak_val >= settings.DEFAULT_CRITICAL_THRESHOLD_PCT else "WARNING"
    peak_time_raw = getattr(peak_pt, "timestamp")
    try:
        peak_time = datetime.fromisoformat(str(peak_time_raw).replace(" IST", "")) if isinstance(peak_time_raw, str) else peak_time_raw
    except Exception:
        peak_time = now + timedelta(hours=3)
    peak_time = _as_naive(peak_time) or now

    mock_r = Reading(
        tower_id=tower.tower_id,
        timestamp=peak_time,
        load_pct=peak_val,
        active_users=int(tower.population_density * 0.12 * (peak_val / 100.0)),
        avg_throughput_mbps=round(max(2.5, (100.0 - peak_val) * 0.65), 1),
        rsrp_dbm=-84.0 if not tower.is_weak_signal else -112.0,
        sinr_db=14.0,
    )
    rich = _build_rich_alert_fields(
        tower=tower,
        alert_type="PREDICTED_OVERLOAD",
        severity=severity,
        reading=mock_r,
        prev_reading=None,
        scenario_context="24h predictive forecast horizon",
    )
    alert = Alert(
        tower_id=tower.tower_id,
        alert_type="PREDICTED_OVERLOAD",
        severity=severity,
        peak_load_pct=round(peak_val, 1),
        reason=rich["reason"],
        mitigation_action=rich["mitigation_action"],
        what=rich["what"],
        where_location=rich["where_location"],
        when_ist=format_ist_datetime(peak_time),
        evidence_json=rich["evidence_json"],
        ranked_causes_json=rich["ranked_causes_json"],
        expected_benefit=rich["expected_benefit"],
        provenance="SIMULATED",
        start_time=peak_time - timedelta(hours=1),
        end_time=peak_time + timedelta(hours=2),
        duration_hours=3,
        status="ACTIVE",
        created_at=now,
    )
    db.add(alert)
    db.flush()
    record_alert_audit(
        db=db,
        alert_id=alert.id,
        tower_id=tower.tower_id,
        alert_type="PREDICTED_OVERLOAD",
        action="OPENED",
        actor="forecast_engine",
        note=rich["what"],
        timestamp=now,
    )
    return [alert]
