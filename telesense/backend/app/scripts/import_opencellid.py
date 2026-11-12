"""
Offline OpenCellID Importer & Boundary Validator.

Rules enforced:
1. Reads OPENCELLID_API_KEY strictly from backend/.env (never logs or prints key).
2. Scans Bengaluru, Hyderabad, Chennai, Mumbai, Delhi, Kolkata, Tirupati
   for MCC=404, 405, 406 in that exact order.
3. Calls getInAreaSize first per box; subdivides into smaller sub-boxes if count > 250;
   pages through getInArea with limit=50 and offset.
4. Enforces daily ceiling (< 800 req/day, persistent in backend/data/opencellid_rate_state.json),
   waits between calls (0.35s), and stops cleanly on rate-limit or auth error.
5. Saves each unique cell record once to `opencellid_cells`:
   (radio, mcc, mnc, lac, cellid, lat, lon, range, samples, source='OpenCellID', fetched_at).
6. Validates every point against the real India boundary polygon (geoBoundaries ADM1)
   and reports how many pass / fail.
"""

import argparse
import os
import sys
import json
import time
import datetime
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional

import requests
from dotenv import dotenv_values

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.database import Base, engine, SessionLocal
from app.models.telemetry import OpenCellIDCell
from app.services.geo_validator import get_india_state_for_point

ENV_PATH = BACKEND_DIR / ".env"
RATE_STATE_PATH = BACKEND_DIR / "data" / "opencellid_rate_state.json"

BASE_URL = "https://opencellid.org/cell"
MCCS = [404, 405, 406]
SLEEP_BETWEEN_CALLS_SEC = 0.35
DAILY_REQUEST_LIMIT = 750  # Strictly below 800/day OpenCellID limit
SUBDIVIDE_THRESHOLD = 250  # Use smaller boxes if box count exceeds this
MAX_SUBBOX_DEPTH = 1       # Subdivide large boxes into 2x2 (~0.5 sq km) quadrants
MAX_PAGES_PER_LEAF_BOX = 2 # Up to 100 cells per leaf box (400 per subdivided box)
PER_CITY_REQ_CAP = 75      # Budget across 7 cities (7 * 75 = 525 << 800)

# ~2 sq km boxes (well under OpenCellID 4,000,000 sq m = 4 sq km API limit)
# Format: (lat_min, lon_min, lat_max, lon_max, label)
CITY_BOXES: List[Tuple[str, str, List[Tuple[float, float, float, float, str]]]] = [
    ("Bengaluru", "Karnataka", [
        (12.968, 77.590, 12.981, 77.604, "MG Road / Central"),
        (12.928, 77.618, 12.941, 77.632, "Koramangala"),
    ]),
    ("Hyderabad", "Telangana", [
        (17.440, 78.374, 17.453, 78.388, "HITEC City"),
        (17.415, 78.435, 17.428, 78.449, "Banjara Hills"),
    ]),
    ("Chennai", "Tamil Nadu", [
        (13.035, 80.230, 13.048, 80.244, "T. Nagar / Anna Salai"),
        (12.985, 80.242, 12.998, 80.256, "Guindy / Tidel Park"),
    ]),
    ("Mumbai", "Maharashtra", [
        (19.060, 72.858, 19.073, 72.872, "Bandra Kurla Complex"),
        (19.012, 72.828, 19.025, 72.842, "Dadar / Prabhadevi"),
    ]),
    ("Delhi", "Delhi", [
        (28.625, 77.212, 28.638, 77.226, "Connaught Place"),
        (28.544, 77.246, 28.557, 77.260, "Nehru Place"),
    ]),
    ("Kolkata", "West Bengal", [
        (22.548, 88.348, 22.561, 88.362, "Park Street"),
        (22.568, 88.426, 22.581, 88.440, "Salt Lake Sec V"),
    ]),
    ("Tirupati", "Andhra Pradesh", [
        (13.622, 79.412, 13.635, 79.426, "Tirupati Central"),
        (13.645, 79.392, 13.658, 79.406, "Alipiri Foothills"),
    ]),
]


def load_api_key() -> str:
    env_vars = dotenv_values(ENV_PATH) if ENV_PATH.exists() else {}
    key = (env_vars.get("OPENCELLID_API_KEY") or os.environ.get("OPENCELLID_API_KEY") or "").strip()
    return key


def scrub(text: str, key: str) -> str:
    if not key:
        return text
    return text.replace(key, "[REDACTED]")


class RateBudgetManager:
    """Persists daily request counter so total requests stay strictly < 800/day."""
    def __init__(self, path: Path, daily_limit: int):
        self.path = path
        self.daily_limit = daily_limit
        self.today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
        self.count = 0
        self._load()

    def _load(self):
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                if data.get("date") == self.today:
                    self.count = int(data.get("requests", 0))
            except Exception:
                self.count = 0

    def can_spend(self, n: int = 1) -> bool:
        return (self.count + n) <= self.daily_limit

    def record(self):
        self.count += 1
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps({"date": self.today, "requests": self.count}, indent=2),
            encoding="utf-8",
        )


def call_ocid_endpoint(
    endpoint: str,
    params: Dict[str, Any],
    api_key: str,
    budget: RateBudgetManager,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Makes one throttled HTTP call to OpenCellID without ever exposing api_key."""
    if not budget.can_spend(1):
        return None, f"Daily safety request budget ({budget.daily_limit}) reached."

    time.sleep(SLEEP_BETWEEN_CALLS_SEC)
    full_params = {"key": api_key, "format": "json", **params}
    try:
        resp = requests.get(f"{BASE_URL}/{endpoint}", params=full_params, timeout=15)
        budget.record()
    except Exception as exc:
        return None, f"Network error calling OpenCellID {endpoint}: {scrub(str(exc), api_key)}"

    try:
        body = resp.json()
    except Exception:
        return None, f"Invalid non-JSON response (HTTP {resp.status_code})"

    if isinstance(body, dict) and ("error" in body or "code" in body):
        code = body.get("code")
        err_msg = scrub(str(body.get("error", "Unknown API error")), api_key)
        # Code 2 = invalid/unknown API key; HTTP 429 / Limit exceeded
        if code in (1, 2) or resp.status_code in (401, 403, 429) or "limit" in err_msg.lower():
            return None, f"STOP_ERROR (HTTP {resp.status_code}, code={code}): {err_msg}"
        return None, f"API_ERROR (HTTP {resp.status_code}, code={code}): {err_msg}"

    if resp.status_code != 200:
        return None, f"HTTP {resp.status_code} from OpenCellID"

    return body, None


def subdivide_bbox(lat_min: float, lon_min: float, lat_max: float, lon_max: float) -> List[Tuple[float, float, float, float]]:
    mid_lat = round((lat_min + lat_max) / 2.0, 5)
    mid_lon = round((lon_min + lon_max) / 2.0, 5)
    return [
        (lat_min, lon_min, mid_lat, mid_lon),
        (lat_min, mid_lon, mid_lat, lon_max),
        (mid_lat, lon_min, lat_max, mid_lon),
        (mid_lat, mid_lon, lat_max, lon_max),
    ]


def fetch_box_cells(
    city: str,
    state: str,
    lat_min: float,
    lon_min: float,
    lat_max: float,
    lon_max: float,
    mcc: int,
    depth: int,
    api_key: str,
    budget: RateBudgetManager,
    city_req_used: List[int],
    db,
    existing_keys: set,
    stats: Dict[str, Any],
) -> Optional[str]:
    """
    1) Calls getInAreaSize first.
    2) If count == 0, stops for this box.
    3) If count > SUBDIVIDE_THRESHOLD and depth < MAX_SUBBOX_DEPTH, subdivides into 4 smaller boxes.
    4) Otherwise pages getInArea with limit=50 & offset, storing each unique record once.
    Returns fatal stop error string if auth/limit error triggered, else None.
    """
    if city_req_used[0] >= PER_CITY_REQ_CAP or not budget.can_spend(1):
        return None

    bbox_str = f"{lat_min:.5f},{lon_min:.5f},{lat_max:.5f},{lon_max:.5f}"
    size_data, err = call_ocid_endpoint(
        "getInAreaSize",
        {"BBOX": bbox_str, "mcc": mcc},
        api_key,
        budget,
    )
    city_req_used[0] += 1
    stats["requests_made"] += 1

    if err:
        if err.startswith("STOP_ERROR"):
            return err
        stats["warnings"].append(f"{city} MCC={mcc} {bbox_str}: {err}")
        return None

    count = int(size_data.get("count", 0))
    if count == 0:
        return None

    if count > SUBDIVIDE_THRESHOLD and depth < MAX_SUBBOX_DEPTH:
        for sub in subdivide_bbox(lat_min, lon_min, lat_max, lon_max):
            fatal = fetch_box_cells(
                city, state, sub[0], sub[1], sub[2], sub[3],
                mcc, depth + 1, api_key, budget, city_req_used, db, existing_keys, stats
            )
            if fatal:
                return fatal
        return None

    limit = 50
    offset = 0
    pages_fetched = 0
    while offset < count and pages_fetched < MAX_PAGES_PER_LEAF_BOX:
        if city_req_used[0] >= PER_CITY_REQ_CAP or not budget.can_spend(1):
            break

        area_data, err = call_ocid_endpoint(
            "getInArea",
            {"BBOX": bbox_str, "mcc": mcc, "limit": limit, "offset": offset},
            api_key,
            budget,
        )
        city_req_used[0] += 1
        stats["requests_made"] += 1
        pages_fetched += 1

        if err:
            if err.startswith("STOP_ERROR"):
                return err
            stats["warnings"].append(f"{city} MCC={mcc} offset={offset}: {err}")
            break

        cells = area_data.get("cells", [])
        if not cells:
            break

        now_utc = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
        batch_added = 0
        for c in cells:
            c_mcc = int(c.get("mcc", mcc))
            c_mnc = int(c.get("mnc", 0))
            c_lac = int(c.get("lac", 0))
            c_cellid = int(c.get("cellid", 0))
            c_radio = str(c.get("radio", "LTE") or "LTE").upper()
            dedupe_key = (c_mcc, c_mnc, c_lac, c_cellid, c_radio)
            if dedupe_key in existing_keys:
                stats["duplicates_skipped"] += 1
                continue

            lat = float(c.get("lat", 0.0))
            lon = float(c.get("lon", 0.0))
            detected_state = get_india_state_for_point(lat, lon)
            in_india = 1 if detected_state is not None else 0
            if in_india:
                stats["polygon_passed"] += 1
            else:
                stats["polygon_failed"] += 1

            record = OpenCellIDCell(
                radio=c_radio,
                mcc=c_mcc,
                mnc=c_mnc,
                lac=c_lac,
                cellid=c_cellid,
                lat=lat,
                lon=lon,
                range=int(c.get("range", 1000) or 1000),
                samples=int(c.get("samples", 1) or 1),
                source="OpenCellID",
                fetched_at=now_utc,
                city=city,
                state=detected_state or state,
                in_india_polygon=in_india,
            )
            db.add(record)
            existing_keys.add(dedupe_key)
            batch_added += 1
            stats["newly_saved"] += 1
            stats["per_city"][city] = stats["per_city"].get(city, 0) + 1
            stats["per_mcc"][mcc] = stats["per_mcc"].get(mcc, 0) + 1

        if batch_added > 0:
            db.commit()

        if len(cells) < limit:
            break
        offset += limit

    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Offline OpenCellID Importer & Boundary Validator")
    parser.add_argument(
        "--skip-imported",
        action="store_true",
        help="Skip (city, mcc) pairs that already have records in opencellid_cells.",
    )
    args = parser.parse_args()

    Base.metadata.create_all(bind=engine)
    api_key = load_api_key()
    if not api_key:
        print("ERROR: OPENCELLID_API_KEY missing in backend/.env")
        return 1

    budget = RateBudgetManager(RATE_STATE_PATH, DAILY_REQUEST_LIMIT)
    if not budget.can_spend(1):
        print(f"STOPPED: Daily request cap ({DAILY_REQUEST_LIMIT}) already reached for {budget.today}.")
        return 1

    db = SessionLocal()
    try:
        existing_rows = db.query(
            OpenCellIDCell.mcc,
            OpenCellIDCell.mnc,
            OpenCellIDCell.lac,
            OpenCellIDCell.cellid,
            OpenCellIDCell.radio,
        ).all()
        existing_keys = set(existing_rows)

        imported_city_mccs = set()
        if args.skip_imported:
            imported_city_mccs = set(
                db.query(OpenCellIDCell.city, OpenCellIDCell.mcc).distinct().all()
            )

        stats: Dict[str, Any] = {
            "requests_made": 0,
            "newly_saved": 0,
            "duplicates_skipped": 0,
            "polygon_passed": 0,
            "polygon_failed": 0,
            "per_city": {},
            "per_mcc": {},
            "warnings": [],
            "fatal_error": None,
        }

        print(f"Starting OpenCellID offline import (daily requests already used today: {budget.count}/{DAILY_REQUEST_LIMIT})...")

        for city, state, boxes in CITY_BOXES:
            city_req_used = [0]
            for mcc in MCCS:
                if args.skip_imported and (city, mcc) in imported_city_mccs:
                    continue
                for lat_min, lon_min, lat_max, lon_max, label in boxes:
                    fatal = fetch_box_cells(
                        city, state, lat_min, lon_min, lat_max, lon_max,
                        mcc, 0, api_key, budget, city_req_used, db, existing_keys, stats
                    )
                    if fatal:
                        stats["fatal_error"] = fatal
                        print(f"STOPPING EARLY: {fatal}")
                        break
                if stats["fatal_error"]:
                    break
            print(f"City {city:10s} | Requests: {city_req_used[0]:3d} | New cells: {stats['per_city'].get(city, 0)}")
            if stats["fatal_error"]:
                break

        from sqlalchemy import func
        total_in_db = db.query(OpenCellIDCell).count()
        total_valid_poly = db.query(OpenCellIDCell).filter(OpenCellIDCell.in_india_polygon == 1).count()
        total_failed_poly = db.query(OpenCellIDCell).filter(OpenCellIDCell.in_india_polygon == 0).count()
        db_city_counts = dict(
            db.query(OpenCellIDCell.city, func.count(OpenCellIDCell.id)).group_by(OpenCellIDCell.city).all()
        )
        db_mcc_counts = dict(
            db.query(OpenCellIDCell.mcc, func.count(OpenCellIDCell.id)).group_by(OpenCellIDCell.mcc).all()
        )

        print("\n=== OpenCellID Import Summary ===")
        print(f"HTTP requests this run : {stats['requests_made']} (Today total: {budget.count}/{DAILY_REQUEST_LIMIT})")
        print(f"Newly saved cells      : {stats['newly_saved']}")
        print(f"Duplicates skipped     : {stats['duplicates_skipped']}")
        print(f"India polygon valid    : {stats['polygon_passed']} passed, {stats['polygon_failed']} failed (this run)")
        print(f"Total DB OpenCellID    : {total_in_db} ({total_valid_poly} valid India polygon, {total_failed_poly} failed)")
        print(f"New per MCC this run   : {stats['per_mcc']}")
        print(f"DB totals per city     : {db_city_counts}")
        print(f"DB totals per MCC      : {db_mcc_counts}")
        if stats["warnings"]:
            print(f"Warnings ({len(stats['warnings'])})        : {stats['warnings'][:5]}")

        if stats["fatal_error"] and stats["newly_saved"] == 0 and total_in_db == 0:
            return 2
        if total_in_db == 0:
            print("WARNING: Zero cells imported across all requests.")
            return 2
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
