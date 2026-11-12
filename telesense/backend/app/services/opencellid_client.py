"""
OpenCellID Client & Real Cellular Base Station Ingestion Service.
Interfaces with OpenCellID (the world's largest open database of cell towers)
to query and synchronize real physical BTS/eNodeB/gNodeB infrastructure across India.

Supports:
- Indian MCC: 404 and 405
- Indian MNCs:
    * 405-840, 405-854, 405-855: Reliance Jio Infocomm
    * 404-10, 404-45, 404-90: Bharti Airtel
    * 404-20, 404-860: Vodafone Idea (Vi)
    * 404-34, 404-38: BSNL (Bharat Sanchar Nigam Limited)
"""

import logging
import urllib.request
import json
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.models.telemetry import Tower, Reading
from app.config import settings
from app.services.mcc_mnc_india import format_operator_label

logger = logging.getLogger("telesense.opencellid")


class OpenCellIDClient:
    """Client for OpenCellID Global Database API."""

    BASE_URL = "https://opencellid.org/cell"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or getattr(settings, "OPENCELLID_API_KEY", "")

    def query_cell(self, mcc: int, mnc: int, lac: int, cell_id: int) -> Optional[Dict[str, Any]]:
        """Disabled in live app runtime: the app must never call OpenCellID live."""
        return None

    def fetch_and_import(self, db: Session, city: str = "Mumbai", limit: int = 50) -> Dict[str, Any]:
        """Disabled in live app runtime: offline imports use backend/app/scripts/import_opencellid.py."""
        raise RuntimeError(
            "OpenCellID live calls are disabled inside the running app. "
            "Use offline script app/scripts/import_opencellid.py instead."
        )

    def sync_opencellid_records_to_db(self, db: Session, cells: List[Dict[str, Any]], city_name: str, state_name: str) -> int:
        """
        Inserts OpenCellID records as active cell towers in TeleSense database.
        Validates:
        - Lat 6.5 to 37.5, Lon 68.0 to 97.5 (inside India)
        - Removes/rejects mismatches
        - Records source_type='REAL - OpenCellID' and accuracy_radius_m
        """
        added_count = 0
        for c in cells:
            try:
                lat = float(c.get("lat", 0.0))
                lon = float(c.get("lon", 0.0))
            except (ValueError, TypeError):
                continue

            # Validate coordinate inside India
            if not (6.5 <= lat <= 37.5 and 68.0 <= lon <= 97.5):
                logger.warning(f"Rejecting cell outside India bounds: {lat}, {lon}")
                continue

            mcc = int(c.get("mcc", 405))
            mnc = int(c.get("mnc", 0))
            operator_label = format_operator_label(mcc, mnc)

            tower_id = f"OCID-{mcc}-{mnc}-{c.get('cellid', 101)}"
            existing = db.query(Tower).filter(Tower.tower_id == tower_id).first()
            if not existing:
                accuracy_m = float(c.get("range", 1000.0))
                tower = Tower(
                    tower_id=tower_id,
                    name=f"OpenCellID Node {c.get('cellid', 101)} ({operator_label})",
                    city=city_name,
                    lat=round(lat, 4),
                    lon=round(lon, 4),
                    capacity_mbps=4500.0 if "Jio" in operator_label else 2500.0,
                    population_density=18000 if accuracy_m < 1500 else 6000,
                    area_type="urban" if accuracy_m < 2000 else "semi-urban",
                    is_chronic_overloader=1 if c.get("samples", 100) > 500 else 0,
                    is_weak_signal=0,
                    source_type="REAL - OpenCellID",
                    accuracy_radius_m=accuracy_m
                )
                db.add(tower)
                added_count += 1
        
        db.commit()
        return added_count

