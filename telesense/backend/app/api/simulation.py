"""Interactive What-If Scenario Simulator and Presenter Mode API Endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database import get_db
from app.models.telemetry import Tower, Reading
from app.schemas.actions import WhatIfInput, WhatIfResponse
from app.services.recommendation_engine import recommendation_engine
from app.services.presenter_mode import presenter_manager

router = APIRouter(prefix="/api/simulation", tags=["Simulation"])


class PresenterActivateInput(BaseModel):
    scenario_id: str
    city: str = "Mumbai"
    auto_revert_seconds: int = 180


@router.post("/what-if", response_model=WhatIfResponse)
def simulate_what_if(input_data: WhatIfInput, db: Session = Depends(get_db)):
    """Simulates impact of user surge, traffic growth %, or added carrier bandwidth."""
    tower = db.query(Tower).filter(Tower.tower_id == input_data.tower_id).first()
    if not tower:
        raise HTTPException(status_code=404, detail="Tower not found")

    latest = db.query(Reading).filter(Reading.tower_id == input_data.tower_id).order_by(desc(Reading.timestamp)).first()
    base_load = latest.load_pct if latest else 50.0
    base_rec = recommendation_engine.evaluate_tower(tower, latest)

    user_load_delta = (input_data.extra_users / 100.0) * 1.2
    growth_factor = 1.0 + (input_data.traffic_growth_pct / 100.0)
    carrier_mitigation = 0.72 if input_data.add_carrier_bandwidth else 1.0

    sim_load = round(float(min(99.9, max(4.0, (base_load * growth_factor + user_load_delta) * carrier_mitigation))), 2)

    class MockReading:
        load_pct = sim_load
        rsrp_dbm = latest.rsrp_dbm if latest else -85.0
        sinr_db = latest.sinr_db if latest else 15.0
        active_users = int(tower.population_density * 0.15 * (sim_load / 100.0))
        avg_throughput_mbps = max(2.0, (100.0 - sim_load) * 0.65)

    sim_rec = recommendation_engine.evaluate_tower(tower, MockReading())
    delta = sim_load - base_load
    sign = "+" if delta >= 0 else ""

    if input_data.add_carrier_bandwidth:
        impact = f"Adding carrier aggregation changed load by {sign}{delta:.1f}% to {sim_load}%. Action updated to {sim_rec['action']}."
    elif delta > 15.0:
        impact = f"Surge of {sign}{delta:.1f}% pushed load to {sim_load}%. Action escalated from {base_rec['action']} to {sim_rec['action']}."
    else:
        impact = f"Projected load changes by {sign}{delta:.1f}% to {sim_load}%. Action remains {sim_rec['action']}."

    return WhatIfResponse(
        tower_id=tower.tower_id,
        baseline_peak_load_pct=round(base_load, 1),
        simulated_peak_load_pct=round(sim_load, 1),
        baseline_recommendation=base_rec["action"],
        simulated_recommendation=sim_rec["action"],
        impact_summary=impact,
    )


@router.get("/presenter/status")
def get_presenter_status(db: Session = Depends(get_db)):
    """Returns current Presenter Mode scenario state, available 6 scenarios, and timer."""
    presenter_manager.check_auto_revert(db)
    return presenter_manager.get_status()


@router.post("/presenter/activate")
def activate_presenter_scenario(payload: PresenterActivateInput, db: Session = Depends(get_db)):
    """Activates one of 6 simulated demo scenarios for any selected Indian city."""
    try:
        return presenter_manager.activate(
            db=db,
            scenario_id=payload.scenario_id,
            city=payload.city,
            auto_revert_seconds=payload.auto_revert_seconds,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/presenter/apply-action")
def apply_presenter_recommended_action(db: Session = Depends(get_db)):
    """Applies recommended action to active presenter scenario and returns before/after metrics."""
    try:
        return presenter_manager.apply_recommended_action(db)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/presenter/reset")
def reset_presenter_scenario(db: Session = Depends(get_db)):
    """Resets any active presenter scenario back to baseline normal simulation."""
    return presenter_manager.reset(db)


class BaselineProfileInput(BaseModel):
    profile: str = "healthy"


@router.post("/baseline-profile")
def set_baseline_profile(payload: BaselineProfileInput, db: Session = Depends(get_db)):
    """Switches baseline profile between 'healthy' (0 flagged) and 'realistic' (rural weak-coverage sites)."""
    try:
        return presenter_manager.set_baseline_profile(db, payload.profile)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
