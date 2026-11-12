"""Pydantic Request and Response Schemas for Towers and Telemetry Data."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class ReadingBase(BaseModel):
    timestamp: datetime
    load_pct: float
    active_users: int
    avg_throughput_mbps: float
    rsrp_dbm: float
    sinr_db: float


class ReadingResponse(ReadingBase):
    id: int
    tower_id: str

    class Config:
        from_attributes = True


class TowerBase(BaseModel):
    tower_id: str
    name: str
    city: str
    state: str = "India"
    circle: str = "India"
    lat: float
    lon: float
    capacity_mbps: float
    population_density: int
    area_type: str
    is_chronic_overloader: int = 0
    is_weak_signal: int = 0
    source_type: str = "SIMULATED"  # "REAL - OpenCellID" or "SIMULATED"
    accuracy_radius_m: Optional[float] = None
    last_seen: Optional[datetime] = None


class TowerResponse(TowerBase):
    current_load_pct: float = 0.0
    current_active_users: int = 0
    current_throughput_mbps: float = 0.0
    current_rsrp_dbm: float = -90.0
    current_sinr_db: float = 15.0
    status: str = "HEALTHY"  # HEALTHY (Green), AT_RISK (Amber), CRITICAL (Red)
    last_updated: Optional[datetime] = None

    class Config:
        from_attributes = True


class NetworkHealthSummary(BaseModel):
    total_towers: int
    healthy_count: int
    at_risk_count: int
    weak_coverage_count: int = 0
    critical_count: int
    outage_count: int = 0
    baseline_healthy_count: int = 0
    baseline_at_risk_count: int = 0
    baseline_weak_coverage_count: int = 0
    baseline_critical_count: int = 0
    baseline_outage_count: int = 0
    demo_delta_critical: int = 0
    demo_delta_at_risk: int = 0
    demo_delta_weak_coverage: int = 0
    demo_delta_outage: int = 0
    baseline_profile: str = "healthy"
    active_alert_count: int = 0
    unread_alert_count: int = 0
    baseline_alert_count: int = 0
    demo_alert_count: int = 0
    status_source: str = "active_alerts"
    avg_fleet_load_pct: float
    simulated_time: datetime
    simulated_time_ist: Optional[str] = None
    data_source: str
    headline_message: str
    real_opencellid_count: int = 0
    simulated_count: int = 0
    real_measurements_count: int = 0
    opencellid_cluster_count: int = 0
    opencellid_polygon_failed_count: int = 0
    opencellid_fetched_at: Optional[str] = None


class ForecastPoint(BaseModel):
    timestamp: str
    forecast_load_pct: float
    lower_bound_pct: float  # Uncertainty interval lower (95%)
    upper_bound_pct: float  # Uncertainty interval upper (95%)
    actual_load_pct: Optional[float] = None
    is_overload_risk: bool = False


class TowerForecastResponse(BaseModel):
    tower_id: str
    tower_name: str
    city: str
    current_load_pct: float
    peak_forecast_load_pct: float
    peak_forecast_time: str
    capacity_threshold_pct: float
    status: str
    model_used: str
    summary_sentence: str   # 5-second plain English takeaway
    recommended_action: str
    forecast_points: List[ForecastPoint]


class CrowdsourceInput(BaseModel):
    download_speed_mbps: float = Field(..., ge=0.01, le=5000.0)
    upload_speed_mbps: Optional[float] = Field(None, ge=0.0, le=2500.0)
    latency_ms: float = Field(..., ge=0.5, le=5000.0)
    jitter_ms: Optional[float] = Field(None, ge=0.0, le=2000.0)
    is_mobile_data: bool = True
    network_medium: str = "Mobile Data"  # "Mobile Data" or "Wi-Fi"
    browser_connection_type: Optional[str] = "not available"
    coarse_lat: Optional[float] = None
    coarse_lon: Optional[float] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    server_city: Optional[str] = None
    run_number: Optional[int] = None
    user_consent: bool = True

    def get_lat(self) -> float:
        return self.coarse_lat if self.coarse_lat is not None else (self.lat if self.lat is not None else 19.076)

    def get_lon(self) -> float:
        return self.coarse_lon if self.coarse_lon is not None else (self.lon if self.lon is not None else 72.877)


class CrowdsourceResponse(BaseModel):
    id: int
    quality_label: str      # e.g., "Excellent for 4K Streaming & Gaming"
    download_speed_mbps: float
    upload_speed_mbps: Optional[float] = None
    latency_ms: float
    jitter_ms: Optional[float] = None
    plain_english_advice: str
    timestamp: datetime
    measured_ist: Optional[str] = None
    server_city: Optional[str] = None
    run_number: Optional[int] = None
    associated_tower_id: Optional[str] = None
    network_type: Optional[str] = None
    is_test: int = 0

