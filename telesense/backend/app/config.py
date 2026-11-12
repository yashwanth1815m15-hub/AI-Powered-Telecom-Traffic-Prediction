"""Central Configuration for TeleSense Platform.

Manages operational thresholds, simulation parameters, telemetry sources,
telecom signal boundaries, and Capex investment assumption tables.
"""

import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from pydantic_settings import BaseSettings

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
BACKEND_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BACKEND_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)


class Settings(BaseSettings):
    PROJECT_NAME: str = "TeleSense"
    PROJECT_VERSION: str = "2.0.0"
    API_V1_STR: str = "/api"

    # Database
    DATABASE_URL: str = f"sqlite:///{DATA_DIR}/telesense.db"

    # OpenCellID API Key for real base stations ingestion
    OPENCELLID_API_KEY: Optional[str] = None

    # Cloudflare Radar API Token for offline India hourly traffic series ingestion
    CLOUDFLARE_API_TOKEN: Optional[str] = None

    # Telemetry Streaming Source
    # Options: "simulator", "csv_replay", "crowdsource"
    DATA_SOURCE: str = "simulator"

    # Simulator Tick Rate
    # 1 real second = SIMULATED_MINUTES_PER_TICK in simulated time (demo: 10 mins)
    SIMULATED_MINUTES_PER_TICK: int = 10
    SIMULATOR_INTERVAL_SECONDS: float = 2.0  # Emit every 2s

    # Overload & Outage Operational Thresholds
    DEFAULT_WARNING_THRESHOLD_PCT: float = 85.0
    DEFAULT_CRITICAL_THRESHOLD_PCT: float = 95.0
    ALERT_THRESHOLD_LOAD: float = 85.0
    ALERT_THRESHOLD_CRITICAL: float = 95.0
    OUTAGE_DROP_THRESHOLD_PCT: float = 70.0  # Sudden drop threshold

    # Telecom Signal Thresholds (3GPP RSRP / SINR Standards)
    # RSRP in dBm: Good > -90, Fair: -90 to -105, Poor: -105 to -115, Very Poor: < -115
    RSRP_GOOD_THRESHOLD: float = -90.0
    RSRP_FAIR_THRESHOLD: float = -105.0
    RSRP_POOR_THRESHOLD: float = -115.0

    # SINR in dB: Good > 13, Fair: 5 to 13, Poor: < 5
    SINR_GOOD_THRESHOLD: float = 13.0
    SINR_FAIR_THRESHOLD: float = 5.0

    # Business Assumptions (Editable parameter defaults)
    CAPEX_NEW_MACRO_TOWER_INR: float = 3500000.0   # ₹35 Lakhs
    CAPEX_SMALL_CELL_INR: float = 750000.0         # ₹7.5 Lakhs
    CAPEX_CARRIER_AGG_BANDWIDTH_INR: float = 350000.0 # ₹3.5 Lakhs (license + RF upgrade)
    CAPEX_TEMPORARY_COW_INR: float = 65000.0       # ₹65k / event deployment
    POWER_COST_PER_KWH_INR: float = 8.50           # Commercial tariff
    RADIO_MICRO_SLEEP_SAVINGS_PCT: float = 18.5    # 3GPP Rel-17 off-peak savings

    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "*"
    ]

    class Config:
        env_file = ".env"
        extra = "allow"


settings = Settings()
