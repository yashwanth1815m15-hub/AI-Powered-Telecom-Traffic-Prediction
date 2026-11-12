"""
TeleSense Crowdsource API
Real mobile measurements from citizens and field testers:
- Ingestion of user-consented measurements
- Rate-limited and validated server-side
- Mobile-data only saved for cellular coverage analysis
- Hex-grid aggregation on map strictly requiring >= 5 samples per bin
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timezone
from urllib.parse import urlparse
import time
import math

from app.database import get_db
from app.models.telemetry import CrowdsourceMeasurement, Tower
from app.schemas.telemetry import CrowdsourceInput, CrowdsourceResponse
from app.services.time_utils import format_ist_datetime, format_ist_timestamp

router = APIRouter(prefix="/api/crowdsource", tags=["Crowdsourced Telemetry"])

AUTOMATED_UA_MARKERS = (
    "testclient",
    "pytest",
    "python-requests",
    "python-urllib",
    "httpx",
    "aiohttp",
    "curl",
    "wget",
    "headlesschrome",
    "headless",
    "playwright",
    "selenium",
    "puppeteer",
    "phantomjs",
    "lighthouse",
    "synthetic",
)
MOBILE_PHONE_UA_MARKERS = ("android", "iphone", "ipad", "ipod", "windows phone", "mobile")
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "[::1]", "testclient", "testserver", ""}


def _parse_host_only(raw: Optional[str]) -> str:
    if not raw:
        return ""
    val = raw.split(",")[0].strip().lower()
    if "://" in val:
        return (urlparse(val).hostname or "").lower()
    if val.startswith("["):
        return val.split("]")[0].lstrip("[").lower()
    return val.split(":")[0].lower()


def extract_client_metadata(request: Request) -> Tuple[str, str, str, str]:
    """Extracts (effective_ip, host, origin_host, user_agent) from headers and socket."""
    cf_ip = (request.headers.get("cf-connecting-ip") or "").strip()
    xff = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    socket_ip = request.client.host if request.client else "127.0.0.1"
    effective_ip = (cf_ip or xff or socket_ip or "127.0.0.1").strip()

    raw_host = request.headers.get("x-forwarded-host") or request.headers.get("host") or ""
    host_only = _parse_host_only(raw_host)

    raw_origin = request.headers.get("origin") or request.headers.get("referer") or ""
    origin_host = _parse_host_only(raw_origin)

    user_agent = (request.headers.get("user-agent") or "").strip()[:256]
    return effective_ip, host_only, origin_host, user_agent


def is_automated_or_localhost(effective_ip: str, host_only: str, origin_host: str, user_agent: str) -> bool:
    """Marks requests originating from automated test runners or localhost/loopback."""
    ua_low = (user_agent or "").lower()
    if not ua_low or any(marker in ua_low for marker in AUTOMATED_UA_MARKERS):
        return True
    if origin_host in LOCAL_HOSTS - {""}:
        return True
    ip_low = (effective_ip or "").lower()
    is_local_ip = ip_low in LOCAL_HOSTS or ip_low.startswith("127.")
    if is_local_ip and (not origin_host or origin_host in LOCAL_HOSTS) and host_only in LOCAL_HOSTS:
        return True
    if is_local_ip and not origin_host:
        return True
    return False


def is_mobile_phone_user_agent(user_agent: str) -> bool:
    """True only for genuine handheld mobile phone/cellular UAs (excluding automated UAs)."""
    ua_low = (user_agent or "").lower()
    if not ua_low or any(marker in ua_low for marker in AUTOMATED_UA_MARKERS):
        return False
    return any(marker in ua_low for marker in MOBILE_PHONE_UA_MARKERS)


def is_real_mobile_phone_measurement(row: CrowdsourceMeasurement) -> bool:
    """Counts only non-test cellular mobile-data samples from real phone User-Agents."""
    if getattr(row, "is_test", 0) != 0:
        return False
    net = f"{row.network_type or ''} {row.connection_type or ''}".upper()
    if "WI-FI" in net or "WIFI" in net or "ETHERNET" in net:
        return False
    return is_mobile_phone_user_agent(getattr(row, "user_agent", "") or "")


def count_real_mobile_phone_measurements(db: Session) -> int:
    rows = db.query(CrowdsourceMeasurement).filter(CrowdsourceMeasurement.is_test == 0).all()
    return sum(1 for r in rows if is_real_mobile_phone_measurement(r))

# In-memory sliding rate limiter: IP -> timestamps
_RATE_LIMITS: Dict[str, List[float]] = {}
RATE_LIMIT_WINDOW_SEC = 60.0
MAX_REQUESTS_PER_WINDOW = 10


def check_rate_limit(client_ip: str) -> None:
    now = time.time()
    history = _RATE_LIMITS.setdefault(client_ip, [])
    # Filter out entries older than window
    history = [t for t in history if now - t < RATE_LIMIT_WINDOW_SEC]
    if len(history) >= MAX_REQUESTS_PER_WINDOW:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Maximum 10 measurements per minute per client."
        )
    history.append(now)
    _RATE_LIMITS[client_ip] = history


def evaluate_connection_quality(download_mbps: float, latency_ms: float) -> str:
    """Plain-English verdict non-technical citizens understand in 5 seconds."""
    if download_mbps >= 40 and latency_ms <= 35:
        return "Excellent: Fast connection for 4K video, live gaming, and video meetings."
    elif download_mbps >= 15 and latency_ms <= 70:
        return "Good: Smooth HD streaming, fast page loads, and clear video calls."
    elif download_mbps >= 5 and latency_ms <= 120:
        return "Fair: Standard browsing and video work. May experience occasional buffering."
    else:
        return "Poor: Slow speeds or high latency. Best for messaging and audio-only calls."


@router.post("/measure", response_model=CrowdsourceResponse)
def submit_crowd_measurement(payload: CrowdsourceInput, request: Request, response: Response, db: Session = Depends(get_db)):
    """
    Ingests anonymous crowdsourced network quality test from mobile users.
    Disables HTTP caching (Cache-Control: no-store) on response.
    """
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    effective_ip, host_only, origin_host, user_agent = extract_client_metadata(request)
    check_rate_limit(effective_ip)

    if not payload.user_consent:
        raise HTTPException(status_code=400, detail="User consent is required to submit crowdsourced diagnostics.")

    # Server-side validation against impossible values
    if payload.download_speed_mbps <= 0 or payload.download_speed_mbps > 5000:
        raise HTTPException(status_code=400, detail="Download speed outside realistic physical bounds (0.01 - 5000 Mbps).")
    if payload.latency_ms <= 0 or payload.latency_ms > 10000:
        raise HTTPException(status_code=400, detail="Latency outside realistic physical bounds (0.5 - 10000 ms).")

    # Coarse location privacy rounding (3 decimal places ~ 110m)
    coarse_lat = round(payload.get_lat(), 3)
    coarse_lon = round(payload.get_lon(), 3)

    verdict = evaluate_connection_quality(payload.download_speed_mbps, payload.latency_ms)
    quality_label = verdict.split(":")[0].strip()

    browser_conn = (payload.browser_connection_type or "").strip()
    if browser_conn and browser_conn.lower() != "not available":
        network_type_val = f"{payload.network_medium} ({browser_conn})"[:64]
    else:
        network_type_val = (payload.network_medium or "Unknown")[:64]

    flagged_test = 1 if is_automated_or_localhost(effective_ip, host_only, origin_host, user_agent) else 0

    now_utc = datetime.now(timezone.utc)
    # Rule: Only save mobile-data results for cellular coverage analysis
    if not payload.is_mobile_data:
        return CrowdsourceResponse(
            id=0,
            quality_label=f"{quality_label} (Wi-Fi)",
            download_speed_mbps=round(payload.download_speed_mbps, 2),
            upload_speed_mbps=round(payload.upload_speed_mbps, 2) if payload.upload_speed_mbps is not None else None,
            latency_ms=round(payload.latency_ms, 1),
            jitter_ms=round(payload.jitter_ms, 1) if payload.jitter_ms is not None else None,
            plain_english_advice=f"{verdict} (Tested over Wi-Fi: Excluded from cellular coverage analysis)",
            timestamp=now_utc,
            measured_ist=format_ist_timestamp(now_utc),
            server_city=payload.server_city,
            run_number=payload.run_number,
            associated_tower_id=None,
            network_type=network_type_val,
            is_test=flagged_test
        )

    # Associate with nearest cell tower if within 15 km
    towers = db.query(Tower).all()
    nearest_tower_id = None
    min_dist = float("inf")
    for t in towers:
        dist = math.sqrt((t.lat - coarse_lat)**2 + (t.lon - coarse_lon)**2) * 111.0
        if dist < min_dist:
            min_dist = dist
            nearest_tower_id = t.tower_id

    # Store anonymous measurement with UA, network type & automated/localhost test flag
    record = CrowdsourceMeasurement(
        timestamp=now_utc.replace(tzinfo=None),
        coarse_lat=coarse_lat,
        coarse_lon=coarse_lon,
        download_speed_mbps=round(payload.download_speed_mbps, 2),
        upload_speed_mbps=round(payload.upload_speed_mbps, 2) if payload.upload_speed_mbps is not None else None,
        latency_ms=round(payload.latency_ms, 1),
        jitter_ms=round(payload.jitter_ms, 1) if payload.jitter_ms is not None else None,
        connection_type=payload.network_medium.upper()[:32],
        quality_label=quality_label,
        nearest_tower_id=nearest_tower_id if min_dist <= 15.0 else None,
        server_city=payload.server_city,
        run_number=payload.run_number,
        user_agent=user_agent or None,
        network_type=network_type_val,
        is_test=flagged_test
    )

    db.add(record)
    db.commit()
    db.refresh(record)

    return CrowdsourceResponse(
        id=record.id,
        quality_label=quality_label,
        download_speed_mbps=record.download_speed_mbps,
        upload_speed_mbps=record.upload_speed_mbps,
        latency_ms=record.latency_ms,
        jitter_ms=record.jitter_ms,
        plain_english_advice=verdict,
        timestamp=record.timestamp,
        measured_ist=format_ist_timestamp(record.timestamp),
        server_city=record.server_city,
        run_number=record.run_number,
        associated_tower_id=record.nearest_tower_id,
        network_type=record.network_type,
        is_test=record.is_test
    )


@router.get("/hex-grid")
def get_hex_grid_coverage(response: Response, min_samples: int = 5, db: Session = Depends(get_db)):
    """
    Returns aggregated coverage on a spatial grid (hex bins of ~0.02 deg ~ 2 km).
    STRICT RULE: Excludes automated/localhost test rows (`is_test == 1`) and
    only returns spatial cells where there are at least min_samples (default: 5) samples.
    """
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    records = db.query(CrowdsourceMeasurement).filter(CrowdsourceMeasurement.is_test == 0).all()
    records = [r for r in records if is_real_mobile_phone_measurement(r)]

    # Spatial binning: round to 0.02 degrees (~2.2 km)
    bins: Dict[str, Dict[str, Any]] = {}
    for r in records:
        lat_bin = round(r.coarse_lat / 0.02) * 0.02
        lon_bin = round(r.coarse_lon / 0.02) * 0.02
        key = f"{lat_bin:.2f}_{lon_bin:.2f}"
        if key not in bins:
            bins[key] = {
                "center_lat": round(lat_bin, 3),
                "center_lon": round(lon_bin, 3),
                "samples": 0,
                "total_download": 0.0,
                "total_latency": 0.0
            }
        bins[key]["samples"] += 1
        bins[key]["total_download"] += r.download_speed_mbps
        bins[key]["total_latency"] += r.latency_ms

    # Filter strictly for bins with >= min_samples
    qualified_hexes = []
    for k, b in bins.items():
        if b["samples"] >= min_samples:
            avg_dl = round(b["total_download"] / b["samples"], 1)
            avg_lat = round(b["total_latency"] / b["samples"], 1)
            qualified_hexes.append({
                "hex_id": k,
                "center_lat": b["center_lat"],
                "center_lon": b["center_lon"],
                "sample_count": b["samples"],
                "avg_download_mbps": avg_dl,
                "avg_latency_ms": avg_lat,
                "quality": "Good" if avg_dl >= 20 else ("Fair" if avg_dl >= 5 else "Poor")
            })

    return {
        "min_samples_threshold": min_samples,
        "qualified_hex_count": len(qualified_hexes),
        "hex_cells": qualified_hexes
    }


@router.get("/recent", response_model=List[CrowdsourceResponse])
def get_recent_measurements(response: Response, limit: int = 20, db: Session = Depends(get_db)):
    """Returns recent non-test mobile-data crowdsourced readings for public transparency."""
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    records = (
        db.query(CrowdsourceMeasurement)
        .filter(CrowdsourceMeasurement.is_test == 0)
        .order_by(CrowdsourceMeasurement.timestamp.desc())
        .limit(limit * 3)
        .all()
    )
    records = [r for r in records if is_real_mobile_phone_measurement(r)][:limit]

    result = []
    for r in records:
        verdict = evaluate_connection_quality(r.download_speed_mbps, r.latency_ms)
        result.append(CrowdsourceResponse(
            id=r.id,
            quality_label=verdict.split(":")[0].strip(),
            download_speed_mbps=r.download_speed_mbps,
            upload_speed_mbps=r.upload_speed_mbps,
            latency_ms=r.latency_ms,
            jitter_ms=r.jitter_ms,
            plain_english_advice=verdict,
            timestamp=r.timestamp,
            measured_ist=format_ist_datetime(r.timestamp),
            server_city=r.server_city,
            run_number=r.run_number,
            associated_tower_id=r.nearest_tower_id,
            network_type=r.network_type,
            is_test=r.is_test
        ))
    return result
