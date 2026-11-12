"""Recommendations and Executive Planner API Endpoints."""

from typing import List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database import get_db
from app.models.alert import Recommendation
from app.models.telemetry import Tower
from app.schemas.actions import RecommendationResponse
from app.services.recommendation_engine import recommendation_engine
from app.config import settings

router = APIRouter(prefix="/api/recommendations", tags=["Recommendations"])


@router.get("", response_model=List[RecommendationResponse])
def list_recommendations(db: Session = Depends(get_db)):
    """Returns active infrastructure and spectrum recommendations for all towers."""
    recs = recommendation_engine.generate_all_recommendations(db)

    results = []
    for r in recs:
        tower = db.query(Tower).filter(Tower.tower_id == r.tower_id).first()
        results.append(RecommendationResponse(
            id=r.id,
            tower_id=r.tower_id,
            tower_name=tower.name if tower else r.tower_id,
            city=tower.city if tower else "Unknown",
            area_type=tower.area_type if tower else "urban",
            action=r.action,
            confidence_pct=r.confidence_pct,
            reason=r.reason,
            evidence_numbers=r.evidence_numbers,
            estimated_cost_inr=r.estimated_cost_inr,
            payback_months=r.payback_months,
            priority_rank=r.priority_rank,
            updated_at=r.updated_at
        ))

    return results


@router.get("/planner-ranked", response_model=List[RecommendationResponse])
def get_planner_ranked(
    city: str = Query(None, description="Filter by city"),
    area_type: str = Query(None, description="Filter by urban/rural"),
    db: Session = Depends(get_db)
):
    """Returns Capex prioritized investment list for telecom planners and executives."""
    all_recs = list_recommendations(db)

    # Filter out "NO ACTION" for the investment planner
    actionable = [r for r in all_recs if "NO ACTION" not in r.action]

    if city:
        actionable = [r for r in actionable if r.city == city]
    if area_type:
        actionable = [r for r in actionable if r.area_type == area_type]

    # Sort primarily by priority_rank (1=Urgent, 2=High, 3=Medium) and estimated cost
    ranked = sorted(actionable, key=lambda x: (x.priority_rank, -x.estimated_cost_inr))
    return ranked


@router.get("/capex-assumptions")
def get_capex_assumptions():
    """Returns editable business assumptions and costs in INR."""
    return {
        "new_macro_tower_cost_inr": settings.CAPEX_NEW_MACRO_TOWER_INR,
        "small_cell_cost_inr": settings.CAPEX_SMALL_CELL_INR,
        "carrier_aggregation_cost_inr": settings.CAPEX_CARRIER_AGG_BANDWIDTH_INR,
        "cow_temporary_tower_cost_inr": settings.CAPEX_TEMPORARY_COW_INR,
        "power_cost_per_kwh_inr": settings.POWER_COST_PER_KWH_INR,
        "radio_micro_sleep_savings_pct": settings.RADIO_MICRO_SLEEP_SAVINGS_PCT,
        "disclaimer": "All figures are estimated telecom industry benchmarks for Indian operator planning."
    }
