"""Tower Management and Telemetry Telecommunications Endpoints."""

import datetime
import json
import sys
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database import get_db
from app.models.telemetry import Tower, Reading, OpenCellIDCell, CrowdsourceMeasurement
from app.models.alert import Alert, Recommendation
from app.schemas.telemetry import (
    TowerResponse,
    NetworkHealthSummary,
    TowerForecastResponse,
    ForecastPoint,
    ReadingResponse
)
from app.config import settings, DATA_DIR, PROJECT_ROOT
from app.api.crowdsource import count_real_mobile_phone_measurements
from app.services.alert_engine import get_fleet_status_from_open_alerts
from app.services.mcc_mnc_india import format_operator_label, MCC_MNC_SOURCE_NAME, MCC_MNC_SOURCE_URL
from app.services.presenter_mode import presenter_manager
from app.services.time_utils import format_ist_datetime, to_ist

router = APIRouter(prefix="/api/towers", tags=["Towers"])


def _serialize_opencellid_record(r: OpenCellIDCell) -> dict:
    """Serializes real OpenCellID fields + cited MCC/MNC label."""
    return {
        "id": r.id,
        "radio": r.radio,
        "mcc": r.mcc,
        "mnc": r.mnc,
        "operator_label": format_operator_label(r.mcc, r.mnc),
        "lac": r.lac,
        "cellid": r.cellid,
        "lat": r.lat,
        "lon": r.lon,
        "samples": r.samples,
        "source": r.source,
        "fetched_at": r.fetched_at.strftime("%Y-%m-%d") if r.fetched_at else None,
        "city": r.city,
        "state": r.state,
        "position_label": "approximate position (about 1 km)",
    }


def determine_status(load_pct: float, rsrp: float) -> str:
    """Classifies tower into Green (HEALTHY), Amber (AT_RISK), or Red (CRITICAL)."""
    if load_pct >= settings.DEFAULT_CRITICAL_THRESHOLD_PCT or rsrp <= settings.RSRP_POOR_THRESHOLD:
        return "CRITICAL"
    elif load_pct >= settings.DEFAULT_WARNING_THRESHOLD_PCT or rsrp <= settings.RSRP_FAIR_THRESHOLD:
        return "AT_RISK"
    return "HEALTHY"


from app.services.seed_towers_data import SEED_TOWERS

TOWER_CIRCLE_LOOKUP = {t["tower_id"]: t.get("circle", t.get("state", "India")) for t in SEED_TOWERS}
TOWER_STATE_LOOKUP = {t["tower_id"]: t.get("state", "India") for t in SEED_TOWERS}

def get_state_for_tower(tower: Tower) -> str:
    """Resolves actual Indian state / UT for cell tower."""
    if tower.tower_id in TOWER_STATE_LOOKUP:
        return TOWER_STATE_LOOKUP[tower.tower_id]
    
    tid = tower.tower_id or ""
    city = tower.city or ""
    if tid.startswith("JHK") or city in ["Ranchi", "Jamshedpur", "Dhanbad"]:
        return "Jharkhand"
    elif tid.startswith("GOA") or city in ["Panaji", "Calangute", "Margao"]:
        return "Goa"
    elif tid.startswith("NE-GTK") or city in ["Gangtok"]:
        return "Sikkim"
    elif tid.startswith("UT-IXZ") or city in ["Port Blair"]:
        return "Andaman & Nicobar"
    return get_circle_for_tower(tower)

def get_circle_for_tower(tower: Tower) -> str:
    """Resolves telecom operational circle / Indian state for cell tower."""
    if tower.tower_id in TOWER_CIRCLE_LOOKUP:
        return TOWER_CIRCLE_LOOKUP[tower.tower_id]
    
    tid = tower.tower_id or ""
    city = tower.city or ""
    if tid.startswith("AP") or tid.startswith("TPT") or tid.startswith("RAY") or city in ["Visakhapatnam", "Vijayawada", "Amaravati", "Guntur", "Tirupati", "Chittoor", "Kadapa"]:
        return "Andhra Pradesh"
    elif tid.startswith("TS") or tid.startswith("HYD") or city in ["Hyderabad", "Warangal"]:
        return "Telangana"
    elif tid.startswith("KAR") or tid.startswith("BLR") or city in ["Bengaluru", "Mysuru", "Mangaluru", "Hubballi"]:
        return "Karnataka"
    elif tid.startswith("MUM") or tid.startswith("MAH") or tid.startswith("PUN") or tid.startswith("VID") or city in ["Mumbai", "Pune", "Nagpur", "Nashik", "Navi Mumbai", "Wardha", "Yavatmal", "Amravati"]:
        return "Maharashtra"
    elif tid.startswith("DEL") or tid.startswith("NCR") or city in ["Delhi", "Gurugram", "Noida", "Ghaziabad", "Faridabad"]:
        return "Delhi NCR"
    elif tid.startswith("TN") or tid.startswith("CHN") or city in ["Chennai", "Coimbatore", "Madurai", "Tiruchirappalli"]:
        return "Tamil Nadu"
    elif tid.startswith("KER") or city in ["Kochi", "Thiruvananthapuram", "Kozhikode", "Thrissur"]:
        return "Kerala"
    elif tid.startswith("GUJ") or tid.startswith("AMD") or city in ["Ahmedabad", "Gandhinagar", "Surat", "Vadodara"]:
        return "Gujarat"
    elif tid.startswith("WB") or tid.startswith("KOL") or city in ["Kolkata", "Howrah", "Siliguri"]:
        return "West Bengal"
    elif tid.startswith("UP") or city in ["Lucknow", "Kanpur", "Varanasi", "Prayagraj", "Ayodhya", "Agra", "Meerut"]:
        return "Uttar Pradesh"
    elif tid.startswith("PB") or city in ["Chandigarh", "Amritsar", "Ludhiana", "Jalandhar"]:
        return "Punjab"
    elif tid.startswith("RAJ") or tid.startswith("JAI") or city in ["Jaipur", "Jodhpur", "Udaipur"]:
        return "Rajasthan"
    elif tid.startswith("MP") or city in ["Indore", "Bhopal", "Gwalior"]:
        return "Madhya Pradesh"
    elif tid.startswith("CG") or city in ["Raipur", "Bilaspur"]:
        return "Chhattisgarh"
    elif tid.startswith("BIH") or tid.startswith("PAT") or city in ["Patna", "Gaya", "Muzaffarpur"]:
        return "Bihar"
    elif tid.startswith("JHK") or city in ["Ranchi", "Jamshedpur", "Dhanbad"]:
        return "Jharkhand"
    elif tid.startswith("ODI") or city in ["Bhubaneswar", "Puri", "Cuttack"]:
        return "Odisha"
    elif tid.startswith("ASM") or tid.startswith("GWH") or city in ["Guwahati", "Silchar"]:
        return "Assam"
    elif tid.startswith("NE") or city in ["Shillong", "Agartala", "Imphal", "Dimapur", "Aizawl", "Itanagar", "Gangtok"]:
        return "North East"
    elif tid.startswith("JK") or city in ["Srinagar", "Jammu"]:
        return "Jammu & Kashmir"
    elif tid.startswith("HP") or city in ["Shimla", "Dharamshala", "Manali"]:
        return "Himachal Pradesh"
    elif tid.startswith("UK") or city in ["Dehradun", "Haridwar", "Rishikesh"]:
        return "Uttarakhand"
    elif tid.startswith("GOA") or city in ["Panaji", "Calangute", "Margao"]:
        return "Goa"
    return "India"


@router.get("/summary", response_model=NetworkHealthSummary)
def get_network_health_summary(db: Session = Depends(get_db)):
    """Provides instant 5-second NOC status banner using open alerts as single source of truth."""
    presenter_manager.check_auto_revert(db)
    towers = db.query(Tower).all()
    total = len(towers)
    if total == 0:
        return NetworkHealthSummary(
            total_towers=0, healthy_count=0, at_risk_count=0, critical_count=0,
            outage_count=0, active_alert_count=0, unread_alert_count=0,
            status_source="active_alerts",
            avg_fleet_load_pct=0.0, simulated_time=datetime.datetime.utcnow(),
            simulated_time_ist=format_ist_datetime(),
            data_source=settings.DATA_SOURCE, headline_message="Awaiting telemetry initialization..."
        )

    tower_ids = [t.tower_id for t in towers]
    status_map = get_fleet_status_from_open_alerts(db, tower_ids, include_demo=True)
    base_status_map = get_fleet_status_from_open_alerts(db, tower_ids, include_demo=False)
    healthy, at_risk, weak_cov, critical, outage = 0, 0, 0, 0, 0
    b_healthy, b_at_risk, b_weak_cov, b_critical, b_outage = 0, 0, 0, 0, 0
    total_load = 0.0

    for t in towers:
        latest = db.query(Reading).filter(Reading.tower_id == t.tower_id).order_by(desc(Reading.timestamp)).first()
        load = latest.load_pct if latest else 35.0
        total_load += load

        status = status_map.get(t.tower_id, "HEALTHY")
        if status == "OUTAGE":
            outage += 1
        elif status == "CRITICAL":
            critical += 1
        elif status == "AT_RISK":
            at_risk += 1
        elif status == "WEAK_COVERAGE":
            weak_cov += 1
        else:
            healthy += 1

        bst = base_status_map.get(t.tower_id, "HEALTHY")
        if bst == "OUTAGE":
            b_outage += 1
        elif bst == "CRITICAL":
            b_critical += 1
        elif bst == "AT_RISK":
            b_at_risk += 1
        elif bst == "WEAK_COVERAGE":
            b_weak_cov += 1
        else:
            b_healthy += 1

    active_alert_count = db.query(Alert).filter(Alert.status.in_(["ACTIVE", "ACKNOWLEDGED"])).count()
    unread_alert_count = db.query(Alert).filter(Alert.status == "ACTIVE").count()
    baseline_alert_count = db.query(Alert).filter(Alert.source != "demo", Alert.status.in_(["ACTIVE", "ACKNOWLEDGED"])).count()
    demo_alert_count = db.query(Alert).filter(Alert.source == "demo", Alert.status.in_(["ACTIVE", "ACKNOWLEDGED"])).count()

    avg_load = round(total_load / total, 1)
    total_crit = critical + outage
    b_total_crit = b_critical + b_outage
    headline = f"Network health: {healthy} healthy, {at_risk} overloaded risk, {weak_cov} weak coverage, {total_crit} critical ({active_alert_count} active alerts)"

    sim_time = db.query(Reading.timestamp).order_by(desc(Reading.timestamp)).first()
    ts = sim_time[0] if sim_time else datetime.datetime.utcnow()

    real_ocid = db.query(OpenCellIDCell).filter(OpenCellIDCell.in_india_polygon == 1).count()
    failed_ocid = db.query(OpenCellIDCell).filter(OpenCellIDCell.in_india_polygon == 0).count()
    simulated_count = total
    total_cell_records = real_ocid + simulated_count
    cluster_count = len({
        (c or "India", round(la, 2), round(lo, 2))
        for c, la, lo in db.query(
            OpenCellIDCell.city, OpenCellIDCell.lat, OpenCellIDCell.lon
        ).filter(OpenCellIDCell.in_india_polygon == 1).all()
    })
    latest_fetch = db.query(OpenCellIDCell.fetched_at).order_by(desc(OpenCellIDCell.fetched_at)).first()
    fetched_str = latest_fetch[0].strftime("%Y-%m-%d") if latest_fetch and latest_fetch[0] else None
    real_measurements = count_real_mobile_phone_measurements(db)

    return NetworkHealthSummary(
        total_towers=total_cell_records,
        healthy_count=healthy,
        at_risk_count=at_risk,
        weak_coverage_count=weak_cov,
        critical_count=total_crit,
        outage_count=outage,
        baseline_healthy_count=b_healthy,
        baseline_at_risk_count=b_at_risk,
        baseline_weak_coverage_count=b_weak_cov,
        baseline_critical_count=b_total_crit,
        baseline_outage_count=b_outage,
        demo_delta_critical=max(0, total_crit - b_total_crit),
        demo_delta_at_risk=max(0, at_risk - b_at_risk),
        demo_delta_weak_coverage=max(0, weak_cov - b_weak_cov),
        demo_delta_outage=max(0, outage - b_outage),
        baseline_profile=presenter_manager.baseline_profile,
        active_alert_count=active_alert_count,
        unread_alert_count=unread_alert_count,
        baseline_alert_count=baseline_alert_count,
        demo_alert_count=demo_alert_count,
        status_source="active_alerts",
        avg_fleet_load_pct=avg_load,
        simulated_time=ts,
        simulated_time_ist=format_ist_datetime(ts),
        data_source=settings.DATA_SOURCE,
        headline_message=headline,
        real_opencellid_count=real_ocid,
        simulated_count=simulated_count,
        real_measurements_count=real_measurements,
        opencellid_cluster_count=cluster_count,
        opencellid_polygon_failed_count=failed_ocid,
        opencellid_fetched_at=fetched_str
    )


@router.get("/ookla-tiles")
def get_cached_ookla_india_tiles():
    """Returns offline-cached India mobile speed performance tiles from s3://ookla-open-data."""
    ookla_path = DATA_DIR / "ookla_india_tiles.json"
    if not ookla_path.exists():
        return {
            "available": False,
            "source_label": "Real mobile speed (Ookla, quarterly)",
            "attribution": "Speedtest by Ookla Global Mobile Network Performance Map",
            "license": "CC BY-NC-SA 4.0",
            "tiles": [],
            "setup_note": "Run `python -m app.scripts.import_ookla` to cache India mobile performance tiles locally.",
        }
    data = json.loads(ookla_path.read_text(encoding="utf-8"))
    data["available"] = True
    return data


@router.get("/india-boundary")
def get_india_boundary_geojson():
    """Serves local 36-State/UT India GeoJSON polygons for map masking and validation."""
    boundary_path = DATA_DIR / "india_states.geojson"
    if not boundary_path.exists():
        raise HTTPException(status_code=404, detail="India boundary GeoJSON not found")
    return json.loads(boundary_path.read_text(encoding="utf-8"))


@router.get("/opencellid-clusters")
def get_opencellid_clusters(city: Optional[str] = Query(None), db: Session = Depends(get_db)):
    """
    Groups cached OpenCellID cell records into area clusters via 0.01° lat/lon grid binning
    (~1.11 km lat x ~1.05 km lon box; effective spatial radius > 2 km with ~1 km native Indian rounding).
    Never triggers live OpenCellID API calls.
    """
    query = db.query(OpenCellIDCell).filter(OpenCellIDCell.in_india_polygon == 1)
    if city:
        query = query.filter(OpenCellIDCell.city == city)
    rows = query.all()
    failed_count = db.query(OpenCellIDCell).filter(OpenCellIDCell.in_india_polygon == 0).count()

    clusters_map = {}
    latest_dt = None
    for r in rows:
        if latest_dt is None or (r.fetched_at and r.fetched_at > latest_dt):
            latest_dt = r.fetched_at
        lat_key = round(r.lat, 2)
        lon_key = round(r.lon, 2)
        key = (r.city or "India", lat_key, lon_key)
        if key not in clusters_map:
            clusters_map[key] = {
                "cluster_id": f"OCID-{(r.city or 'IND')[:3].upper()}-{lat_key:.2f}_{lon_key:.2f}",
                "city": r.city or "India",
                "state": r.state or "India",
                "lat": lat_key,
                "lon": lon_key,
                "cell_count": 0,
                "cluster_label": "area cluster (0 cell records)",
                "radios": set(),
                "mccs": set(),
                "operators": set(),
                "total_samples": 0,
                "position_label": "approximate position (about 1 km)",
                "source": "OpenCellID",
                "records": []
            }
        c = clusters_map[key]
        c["cell_count"] += 1
        c["radios"].add(r.radio)
        c["mccs"].add(r.mcc)
        c["operators"].add(format_operator_label(r.mcc, r.mnc))
        c["total_samples"] += (r.samples or 1)
        if len(c["records"]) < 15:
            c["records"].append(_serialize_opencellid_record(r))

    clusters = []
    for c in clusters_map.values():
        c["cluster_label"] = f"area cluster ({c['cell_count']} cell records)"
        c["radios"] = sorted(c["radios"])
        c["mccs"] = sorted(c["mccs"])
        c["operators"] = sorted(c["operators"])
        clusters.append(c)

    fetched_date = latest_dt.strftime("%Y-%m-%d") if latest_dt else "N/A"
    return {
        "total_cell_records": len(rows) + failed_count,
        "valid_india_polygon_count": len(rows),
        "failed_india_polygon_count": failed_count,
        "cluster_count": len(clusters),
        "cluster_summary_label": f"{len(clusters)} area clusters ({len(rows):,} cell records)",
        "clustering_method": "0.01° lat/lon grid binning (~1.11 km x ~1.05 km box; effective radius > 2 km with ~1 km native Indian rounding)",
        "cluster_radius_km": 2.2,
        "fetched_at": fetched_date,
        "attribution": f"Cell data: OpenCellID, CC BY-SA 4.0, fetched {fetched_date}",
        "mcc_mnc_source": MCC_MNC_SOURCE_NAME,
        "mcc_mnc_source_url": MCC_MNC_SOURCE_URL,
        "position_label": "approximate position (about 1 km)",
        "clusters": clusters,
    }


@router.get("/opencellid-records")
def get_opencellid_individual_records(
    lat_min: Optional[float] = Query(None),
    lat_max: Optional[float] = Query(None),
    lon_min: Optional[float] = Query(None),
    lon_max: Optional[float] = Query(None),
    city: Optional[str] = Query(None),
    limit: int = Query(400, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """
    Returns individual cached OpenCellID cell records for zoomed-in map inspection.
    Exposes strictly real fields (radio, MCC/MNC + cited operator, LAC, cell ID,
    approximate position, sample count, source, fetched date). Never calls OpenCellID live.
    """
    query = db.query(OpenCellIDCell).filter(OpenCellIDCell.in_india_polygon == 1)
    if city:
        query = query.filter(OpenCellIDCell.city == city)
    if lat_min is not None:
        query = query.filter(OpenCellIDCell.lat >= lat_min)
    if lat_max is not None:
        query = query.filter(OpenCellIDCell.lat <= lat_max)
    if lon_min is not None:
        query = query.filter(OpenCellIDCell.lon >= lon_min)
    if lon_max is not None:
        query = query.filter(OpenCellIDCell.lon <= lon_max)

    total_matching = query.count()
    rows = query.order_by(OpenCellIDCell.samples.desc(), OpenCellIDCell.id.asc()).limit(limit).all()
    latest_dt = max((r.fetched_at for r in rows if r.fetched_at), default=None)
    fetched_date = latest_dt.strftime("%Y-%m-%d") if latest_dt else "N/A"
    return {
        "total_matching": total_matching,
        "returned_count": len(rows),
        "attribution": f"Cell data: OpenCellID, CC BY-SA 4.0, fetched {fetched_date}",
        "mcc_mnc_source": MCC_MNC_SOURCE_NAME,
        "records": [_serialize_opencellid_record(r) for r in rows],
    }


@router.get("", response_model=List[TowerResponse])
def list_towers(
    city: str = Query(None, description="Filter by city"),
    area_type: str = Query(None, description="Filter by urban/rural"),
    db: Session = Depends(get_db)
):
    """Lists all cell towers with their latest live telemetry readings."""
    query = db.query(Tower)
    if city:
        query = query.filter(Tower.city == city)
    if area_type:
        query = query.filter(Tower.area_type == area_type)

    towers = query.all()
    status_map = get_fleet_status_from_open_alerts(db, [t.tower_id for t in towers])
    response_list = []

    for t in towers:
        latest = db.query(Reading).filter(Reading.tower_id == t.tower_id).order_by(desc(Reading.timestamp)).first()

        load = latest.load_pct if latest else 25.0
        users = latest.active_users if latest else 100
        tput = latest.avg_throughput_mbps if latest else 45.0
        rsrp = latest.rsrp_dbm if latest else -85.0
        sinr = latest.sinr_db if latest else 16.0
        updated = latest.timestamp if latest else datetime.datetime.utcnow()

        status = status_map.get(t.tower_id, "HEALTHY")

        response_list.append(TowerResponse(
            tower_id=t.tower_id,
            name=t.name,
            city=t.city,
            state=get_state_for_tower(t),
            circle=get_circle_for_tower(t),
            lat=t.lat,
            lon=t.lon,
            capacity_mbps=t.capacity_mbps,
            population_density=t.population_density,
            area_type=t.area_type,
            is_chronic_overloader=t.is_chronic_overloader,
            is_weak_signal=t.is_weak_signal,
            source_type="REAL - OpenCellID" if t.tower_id.startswith("OCID") else "SIMULATED",
            current_load_pct=load,
            current_active_users=users,
            current_throughput_mbps=tput,
            current_rsrp_dbm=rsrp,
            current_sinr_db=sinr,
            status=status,
            last_updated=updated
        ))

    return response_list


@router.get("/{tower_id}", response_model=TowerResponse)
def get_tower(tower_id: str, db: Session = Depends(get_db)):
    """Retrieves specific tower metadata and live status."""
    t = db.query(Tower).filter(Tower.tower_id == tower_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Tower not found")

    latest = db.query(Reading).filter(Reading.tower_id == t.tower_id).order_by(desc(Reading.timestamp)).first()
    load = latest.load_pct if latest else 25.0
    users = latest.active_users if latest else 100
    tput = latest.avg_throughput_mbps if latest else 45.0
    rsrp = latest.rsrp_dbm if latest else -85.0
    sinr = latest.sinr_db if latest else 16.0
    updated = latest.timestamp if latest else datetime.datetime.utcnow()
    status = get_fleet_status_from_open_alerts(db, [t.tower_id]).get(t.tower_id, "HEALTHY")

    return TowerResponse(
        tower_id=t.tower_id,
        name=t.name,
        city=t.city,
        state=get_state_for_tower(t),
        circle=get_circle_for_tower(t),
        lat=t.lat,
        lon=t.lon,
        capacity_mbps=t.capacity_mbps,
        population_density=t.population_density,
        area_type=t.area_type,
        is_chronic_overloader=t.is_chronic_overloader,
        is_weak_signal=t.is_weak_signal,
        source_type="REAL - OpenCellID" if t.tower_id.startswith("OCID") else "SIMULATED",
        current_load_pct=load,
        current_active_users=users,
        current_throughput_mbps=tput,
        current_rsrp_dbm=rsrp,
        current_sinr_db=sinr,
        status=status,
        last_updated=updated
    )


@router.get("/{tower_id}/history", response_model=List[ReadingResponse])
def get_tower_history(tower_id: str, limit: int = 72, db: Session = Depends(get_db)):
    """Returns past 48 to 72 hours of hourly actuals for time-series charts."""
    readings = db.query(Reading).filter(
        Reading.tower_id == tower_id
    ).order_by(desc(Reading.timestamp)).limit(limit).all()

    return list(reversed(readings))


@router.get("/{tower_id}/forecast", response_model=TowerForecastResponse)
def get_tower_forecast(tower_id: str, db: Session = Depends(get_db)):
    """Generates continuous 24h multi-horizon forecast using the validation-selected serving model."""
    t = db.query(Tower).filter(Tower.tower_id == tower_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Tower not found")

    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    from ml.training.ml_service import (
        format_serving_model_label,
        generate_tower_forecast,
        get_serving_model_choice,
    )

    ml_fc = generate_tower_forecast(db, t)
    serving_model_label = str(ml_fc.get("model_used") or format_serving_model_label(get_serving_model_choice()))

    latest = db.query(Reading).filter(Reading.tower_id == tower_id).order_by(desc(Reading.timestamp)).first()
    current_load = round(float(latest.load_pct if latest else ml_fc.get("current_load_pct", 45.0)), 2)
    base_time_ist = to_ist(latest.timestamp if latest else datetime.datetime.utcnow())

    override = presenter_manager.get_scenario_override(t.tower_id)
    import numpy as np

    points: List[ForecastPoint] = []
    peak_val = 0.0
    peak_time_str = ""
    raw_points = ml_fc.get("forecast_points") or []

    for h in range(1, 25):
        fc_time = base_time_ist + datetime.timedelta(hours=h)
        src_pt = raw_points[h - 1] if h - 1 < len(raw_points) else {}
        pred = float(src_pt.get("predicted_load_pct", current_load))
        lower = float(src_pt.get("lower_bound", max(0.0, pred - 5.0)))
        upper = float(src_pt.get("upper_bound", min(100.0, pred + 5.0)))

        if override and not override["mitigation_applied"] and h <= 6:
            scen = override["scenario"]
            pred = max(pred, scen["target_load_pct"]) if scen["target_load_pct"] >= 50 else scen["target_load_pct"]
            pred = round(float(np.clip(pred, 1.5, 98.5)), 2)
            sigma = 1.8 + (h * 0.18)
            lower = round(float(max(0.0, pred - 1.96 * sigma)), 2)
            upper = round(float(min(100.0, pred + 1.96 * sigma)), 2)
        elif override and override["mitigation_applied"] and h <= 6:
            pred = float(override["scenario"]["post_action_load_pct"])
            pred = round(float(np.clip(pred, 1.5, 98.5)), 2)
            sigma = 1.8 + (h * 0.18)
            lower = round(float(max(0.0, pred - 1.96 * sigma)), 2)
            upper = round(float(min(100.0, pred + 1.96 * sigma)), 2)
        else:
            pred = round(float(np.clip(pred, 1.5, 98.5)), 2)
            lower = round(float(max(0.0, min(lower, pred))), 2)
            upper = round(float(min(100.0, max(upper, pred))), 2)

        is_risk = pred >= settings.DEFAULT_WARNING_THRESHOLD_PCT

        if pred > peak_val:
            peak_val = pred
            peak_time_str = fc_time.strftime("%H:%M IST")

        points.append(ForecastPoint(
            timestamp=fc_time.strftime("%Y-%m-%d %H:%M IST"),
            forecast_load_pct=pred,
            lower_bound_pct=lower,
            upper_bound_pct=upper,
            is_overload_risk=is_risk
        ))

    fleet_status = get_fleet_status_from_open_alerts(db, [t.tower_id]).get(t.tower_id, "HEALTHY")
    if peak_val >= settings.DEFAULT_CRITICAL_THRESHOLD_PCT or fleet_status in ("CRITICAL", "OUTAGE"):
        summary = f"Expected to hit critical {peak_val:.1f}% load at {peak_time_str}. Action: Urgent 5G beam steering and neighbor offloading required."
        rec_action = "CRITICAL: Offload traffic immediately to neighbor cells."
        status = fleet_status if fleet_status in ("CRITICAL", "OUTAGE") else "CRITICAL"
    elif peak_val >= settings.DEFAULT_WARNING_THRESHOLD_PCT or fleet_status == "AT_RISK":
        summary = f"Expected to hit {peak_val:.1f}% load at {peak_time_str}. Action: Pre-allocate carrier aggregation or shift traffic."
        rec_action = "WARNING: Carrier aggregation recommended."
        status = "AT_RISK"
    else:
        summary = f"Operating normally. Peak anticipated load is {peak_val:.1f}% at {peak_time_str}. Headroom safe."
        rec_action = "NOMINAL: No action needed."
        status = "HEALTHY"

    return TowerForecastResponse(
        tower_id=t.tower_id,
        tower_name=t.name,
        city=t.city,
        current_load_pct=current_load,
        peak_forecast_load_pct=peak_val,
        peak_forecast_time=peak_time_str,
        capacity_threshold_pct=settings.DEFAULT_WARNING_THRESHOLD_PCT,
        status=status,
        model_used=serving_model_label,
        summary_sentence=summary,
        recommended_action=rec_action,
        forecast_points=points
    )


class OpenCellIDSyncRequest(BaseModel):
    api_key: Optional[str] = None
    city: Optional[str] = "Mumbai"
    state: Optional[str] = "Maharashtra"


@router.post("/opencellid-sync")
def sync_opencellid_towers(payload: OpenCellIDSyncRequest, db: Session = Depends(get_db)):
    """
    Returns cached OpenCellID ingestion statistics from local SQLite database.
    The live app never calls OpenCellID live; data is imported via offline CLI.
    """
    ocid_valid = db.query(OpenCellIDCell).filter(OpenCellIDCell.in_india_polygon == 1).count()
    ocid_failed = db.query(OpenCellIDCell).filter(OpenCellIDCell.in_india_polygon == 0).count()
    latest_fetch = db.query(OpenCellIDCell.fetched_at).order_by(desc(OpenCellIDCell.fetched_at)).first()
    fetched_date = latest_fetch[0].strftime("%Y-%m-%d") if latest_fetch and latest_fetch[0] else None
    sim_count = db.query(Tower).count()
    return {
        "status": "CACHED_READ_ONLY",
        "message": "Live OpenCellID API calls are disabled inside the running app. Returning offline-imported cached cell records.",
        "cached_opencellid_cells": ocid_valid,
        "polygon_failed_cells": ocid_failed,
        "simulated_sites": sim_count,
        "fetched_at": fetched_date,
        "attribution": f"Cell data: OpenCellID, CC BY-SA 4.0, fetched {fetched_date}" if fetched_date else "Cell data: OpenCellID, CC BY-SA 4.0",
        "supported_mcc": [404, 405, 406],
    }

