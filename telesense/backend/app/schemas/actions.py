"""Pydantic Schemas for Alerts, Recommendations, What-If Simulations, and Citizen Queries."""

from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel


class AlertResponse(BaseModel):
    id: int
    tower_id: str
    tower_name: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    alert_type: str = "PREDICTED_OVERLOAD"
    created_at: datetime
    created_at_ist: Optional[str] = None
    start_time: datetime
    end_time: datetime
    duration_hours: int
    peak_load_pct: float
    severity: str        # WARNING, CRITICAL, OUTAGE
    reason: str          # Plain English summary
    mitigation_action: str
    status: str          # ACTIVE, ACKNOWLEDGED, RESOLVED
    what: Optional[str] = None
    where_location: Optional[str] = None
    when_ist: Optional[str] = None
    evidence: Optional[Dict[str, Any]] = None
    ranked_causes: Optional[List[Dict[str, Any]]] = None
    expected_benefit: Optional[str] = None
    provenance: str = "SIMULATED"
    source: str = "baseline"
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AlertAuditLogResponse(BaseModel):
    id: int
    alert_id: Optional[int] = None
    tower_id: str
    alert_type: str
    action: str
    actor: str
    note: Optional[str] = None
    timestamp: datetime
    timestamp_ist: Optional[str] = None

    class Config:
        from_attributes = True


class RecommendationResponse(BaseModel):
    id: int
    tower_id: str
    tower_name: Optional[str] = None
    city: Optional[str] = None
    area_type: Optional[str] = None
    action: str          # ADD BANDWIDTH, BUILD NEW TOWER, etc.
    confidence_pct: float
    reason: str          # Plain English 5-second explanation
    evidence_numbers: str
    estimated_cost_inr: float
    payback_months: int
    priority_rank: int   # 1: Urgent, 2: Recommended, 3: Nominal
    updated_at: datetime

    class Config:
        from_attributes = True


class WhatIfInput(BaseModel):
    tower_id: str
    extra_users: int = 0
    traffic_growth_pct: float = 0.0
    add_carrier_bandwidth: bool = False


class WhatIfResponse(BaseModel):
    tower_id: str
    baseline_peak_load_pct: float
    simulated_peak_load_pct: float
    baseline_recommendation: str
    simulated_recommendation: str
    impact_summary: str


class CitizenAreaQuality(BaseModel):
    city: str
    area_name: str
    signal_rating: str        # "EXCELLENT", "GOOD", "FAIR", "CONGESTED"
    quality_label: Optional[str] = None
    avg_speed_mbps: float
    best_download_window: str # e.g. "01:00 AM - 05:00 AM (Off-peak, max speed)"
    best_call_window: str     # e.g. "10:00 AM - 04:00 PM (Clear voice, lowest latency)"
    worst_congestion_window: str # e.g. "08:00 PM - 10:00 PM (Heavy video streaming)"
    plain_english_advice: str
    current_load_pct: Optional[float] = None
    nearest_tower_id: Optional[str] = None
    distance_km: Optional[float] = None
    hourly_schedule: Optional[List[Dict[str, Any]]] = None

