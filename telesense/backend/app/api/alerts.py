"""Alerts, Audit Log, and Incident Management API Endpoints."""

import datetime
import json
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database import get_db
from app.models.alert import Alert, AlertAuditLog
from app.models.telemetry import Tower
from app.schemas.actions import AlertAuditLogResponse, AlertResponse
from app.services.alert_engine import SEVERITY_RANK, record_alert_audit
from app.services.seed_towers_data import SEED_TOWERS
from app.services.time_utils import format_ist_datetime

router = APIRouter(prefix="/api/alerts", tags=["Alerts"])

_STATE_LOOKUP = {t["tower_id"]: t.get("state", "India") for t in SEED_TOWERS}


def _safe_json(val: Optional[str], fallback: Any) -> Any:
    if not val:
        return fallback
    try:
        return json.loads(val)
    except Exception:
        return fallback


def _serialize_alert(a: Alert, tower: Optional[Tower]) -> AlertResponse:
    state = _STATE_LOOKUP.get(a.tower_id, tower.city if tower else "India")
    where_loc = a.where_location or (f"{tower.name}, {tower.city}, {state}" if tower else a.tower_id)
    when_ist = a.when_ist or format_ist_datetime(a.created_at)
    return AlertResponse(
        id=a.id,
        tower_id=a.tower_id,
        tower_name=tower.name if tower else a.tower_id,
        city=tower.city if tower else "Unknown",
        state=state,
        alert_type=(a.alert_type or "PREDICTED_OVERLOAD").upper(),
        created_at=a.created_at,
        created_at_ist=format_ist_datetime(a.created_at),
        start_time=a.start_time,
        end_time=a.end_time,
        duration_hours=a.duration_hours,
        peak_load_pct=a.peak_load_pct,
        severity=(a.severity or "WARNING").upper(),
        reason=a.reason,
        mitigation_action=a.mitigation_action,
        status=a.status,
        what=a.what or a.reason,
        where_location=where_loc,
        when_ist=when_ist,
        evidence=_safe_json(a.evidence_json, {"peak_load_pct": a.peak_load_pct}),
        ranked_causes=_safe_json(a.ranked_causes_json, []),
        expected_benefit=a.expected_benefit or "Restores sector headroom within TRAI QoS bounds.",
        provenance=a.provenance or "SIMULATED",
        source=(a.source or "baseline").lower(),
        acknowledged_at=a.acknowledged_at,
        resolved_at=a.resolved_at,
    )


@router.get("", response_model=List[AlertResponse])
def list_alerts(
    status: Optional[str] = Query(None, description="Filter: ACTIVE, ACKNOWLEDGED, RESOLVED, OPEN (ACTIVE+ACKNOWLEDGED)"),
    status_filter: Optional[str] = Query(None, description="Alias for status filter"),
    severity: Optional[str] = Query(None, description="Filter: WARNING, CRITICAL, OUTAGE"),
    alert_type: Optional[str] = Query(None, description="Filter: PREDICTED_OVERLOAD, WEAK_COVERAGE, OUTAGE, DEGRADED_SPEED"),
    limit: int = 100,
    db: Session = Depends(get_db),
):
    """Retrieves alert feed sorted by severity (OUTAGE -> CRITICAL -> WARNING) then timestamp desc."""
    effective_status = (status or status_filter or "").strip().upper()
    query = db.query(Alert)
    if effective_status == "OPEN":
        query = query.filter(Alert.status.in_(["ACTIVE", "ACKNOWLEDGED"]))
    elif effective_status:
        query = query.filter(Alert.status == effective_status)
    if severity:
        query = query.filter(Alert.severity == severity.strip().upper())
    if alert_type:
        query = query.filter(Alert.alert_type == alert_type.strip().upper())

    alerts = query.order_by(desc(Alert.created_at)).limit(limit).all()
    alerts.sort(key=lambda x: (SEVERITY_RANK.get((x.severity or "WARNING").upper(), 3), -(x.created_at.timestamp() if x.created_at else 0)))

    towers_by_id = {t.tower_id: t for t in db.query(Tower).all()}
    return [_serialize_alert(a, towers_by_id.get(a.tower_id)) for a in alerts]


@router.get("/audit-log", response_model=List[AlertAuditLogResponse])
def get_alert_audit_log(limit: int = 100, db: Session = Depends(get_db)):
    """Returns persistent alert lifecycle audit log (OPENED, ACKNOWLEDGED, RESOLVED, AUTO_RESOLVED)."""
    rows = db.query(AlertAuditLog).order_by(desc(AlertAuditLog.timestamp), desc(AlertAuditLog.id)).limit(limit).all()
    return [
        AlertAuditLogResponse(
            id=r.id,
            alert_id=r.alert_id,
            tower_id=r.tower_id,
            alert_type=r.alert_type,
            action=r.action,
            actor=r.actor,
            note=r.note,
            timestamp=r.timestamp,
            timestamp_ist=format_ist_datetime(r.timestamp),
        )
        for r in rows
    ]


@router.post("/{alert_id}/acknowledge")
def acknowledge_alert(alert_id: int, actor: str = "noc_operator", note: Optional[str] = None, db: Session = Depends(get_db)):
    """Acknowledge an active alert ticket and append to persistent audit log."""
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert ticket not found")

    now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    alert.status = "ACKNOWLEDGED"
    alert.acknowledged_at = now
    record_alert_audit(
        db=db,
        alert_id=alert.id,
        tower_id=alert.tower_id,
        alert_type=alert.alert_type or "PREDICTED_OVERLOAD",
        action="ACKNOWLEDGED",
        actor=actor,
        note=note or "Operator acknowledged alert",
        timestamp=now,
    )
    db.commit()
    return {"message": f"Alert {alert_id} acknowledged by operator", "status": alert.status}


@router.post("/{alert_id}/resolve")
def resolve_alert(alert_id: int, actor: str = "noc_operator", note: Optional[str] = None, db: Session = Depends(get_db)):
    """Mark an alert ticket as resolved and append to persistent audit log."""
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert ticket not found")

    now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    alert.status = "RESOLVED"
    alert.resolved_at = now
    record_alert_audit(
        db=db,
        alert_id=alert.id,
        tower_id=alert.tower_id,
        alert_type=alert.alert_type or "PREDICTED_OVERLOAD",
        action="RESOLVED",
        actor=actor,
        note=note or "Operator marked alert resolved",
        timestamp=now,
    )
    db.commit()
    return {"message": f"Alert {alert_id} resolved", "status": alert.status}
