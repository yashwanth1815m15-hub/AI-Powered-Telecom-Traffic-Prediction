"""Explainable Rules-Based Recommendation Engine for TeleSense.

Determines optimal capital expenditure (Capex) and spectrum interventions:
- ADD BANDWIDTH (Carrier aggregation / extra spectrum)
- BUILD NEW TOWER (Priority 1 macro site)
- BUILD SMALL CELL (Coverage densification in urban/rural)
- TEMPORARY CELL-ON-WHEELS (Event surges like IPL / Festivals)
- NO ACTION (Micro-sleep power-saving opportunity)
"""

import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.telemetry import Tower, Reading
from app.models.alert import Recommendation
from app.config import settings

logger = logging.getLogger("RecommendationEngine")


class RecommendationEngine:
    """Evaluates tower signal strength, capacity headroom, and usage to prescribe actions."""

    def evaluate_tower(
        self,
        tower: Tower,
        latest_reading: Reading,
        scenario_override_action: Optional[str] = None,
    ) -> Dict[str, Any]:
        load = latest_reading.load_pct if latest_reading else 35.0
        rsrp = latest_reading.rsrp_dbm if latest_reading else -85.0
        sinr = latest_reading.sinr_db if latest_reading else 15.0
        density = tower.population_density
        area_type = tower.area_type
        is_chronic = tower.is_chronic_overloader

        # 0. Active Outage / Backhaul failure -> urgent Repair Backhaul
        if load < 5.0 or (scenario_override_action and "BACKHAUL" in scenario_override_action.upper()):
            action = scenario_override_action or "REPAIR BACKHAUL / REROUTE TRAFFIC"
            return {
                "action": action,
                "confidence_pct": 97.5,
                "reason": f"Transport / backhaul outage detected ({load:.1f}% load, RSRP {rsrp:.1f} dBm). Dispatch optical/power restoration crew and enable neighbor offload.",
                "evidence_numbers": f"Load: {load:.1f}% | RSRP: {rsrp:.1f} dBm | SINR: {sinr:.1f} dB | Density: {density}/km²",
                "estimated_cost_inr": 45000.0,
                "payback_months": 1,
                "priority_rank": 1,
            }

        # Explicit Temporary Cell-on-Wheels demo/event override
        if scenario_override_action and "CELL-ON-WHEELS" in scenario_override_action.upper():
            return {
                "action": scenario_override_action,
                "confidence_pct": 96.0,
                "reason": f"Temporary high-density congregation surge ({load:.1f}% load, {getattr(latest_reading, 'active_users', 0)} active UEs). Deploy temporary Cell-on-Wheels & secondary carrier offload.",
                "evidence_numbers": f"Peak Load: {load:.1f}% | RSRP: {rsrp:.1f} dBm | SINR: {sinr:.1f} dB | Throughput: {getattr(latest_reading, 'avg_throughput_mbps', 0.0):.1f} Mbps",
                "estimated_cost_inr": settings.CAPEX_TEMPORARY_COW_INR,
                "payback_months": 1,
                "priority_rank": 1,
            }

        # 1. Classify Signal Quality
        is_good_signal = rsrp > settings.RSRP_GOOD_THRESHOLD or (rsrp > settings.RSRP_FAIR_THRESHOLD and sinr > 10.0)
        is_poor_signal = rsrp <= settings.RSRP_FAIR_THRESHOLD

        # 2. Classify Traffic Load
        is_high_load = load >= settings.DEFAULT_WARNING_THRESHOLD_PCT or is_chronic == 1
        is_extreme_load = load >= settings.DEFAULT_CRITICAL_THRESHOLD_PCT

        # Rule 1: Dual Bottleneck (Poor Signal + High Load) -> Urgent Macro Tower
        if is_poor_signal and is_high_load:
            action = scenario_override_action or "BUILD NEW TOWER (PRIORITY 1)"
            confidence = 96.5
            cost = settings.CAPEX_NEW_MACRO_TOWER_INR
            payback = 14
            rank = 1
            reason = f"Critical coverage hole combined with severe congestion ({load:.1f}% load, RSRP: {rsrp} dBm). Subscribers experiencing chronic dropped calls."
            evidence = f"Peak Load: {load:.1f}% | RSRP: {rsrp:.1f} dBm | SINR: {sinr:.1f} dB | Density: {density}/km²"

        # Rule 2: Pure Capacity Problem (Good/Fair Signal + High Load) -> Add Bandwidth
        elif is_good_signal and is_high_load:
            action = scenario_override_action or "ADD BANDWIDTH (CARRIER AGGREGATION)"
            confidence = 94.0
            cost = settings.CAPEX_CARRIER_AGG_BANDWIDTH_INR
            payback = 6
            rank = 2
            reason = f"Excellent radio coverage (RSRP {rsrp} dBm), but channel capacity is saturated ({load:.1f}%). Deploy additional 40 MHz 5G carrier or activate 4x4 MIMO."
            evidence = f"Load: {load:.1f}% | RSRP: {rsrp:.1f} dBm (Good) | SINR: {sinr:.1f} dB | Capacity: {tower.capacity_mbps} Mbps"

        # Rule 3: Pure Coverage Shadow (Poor Signal + Low/Moderate Load)
        elif is_poor_signal and not is_high_load:
            if area_type == "rural" or density < 2000:
                action = scenario_override_action or "BUILD LOW-COST SMALL CELL / REPEATER"
                cost = settings.CAPEX_SMALL_CELL_INR
                payback = 18
                rank = 3
                reason = f"Rural dead-zone (RSRP: {rsrp} dBm). Low population density makes full macro tower uneconomical; deploy solar-powered small cell or shared rural pole."
            else:
                action = scenario_override_action or "BUILD 5G SMALL CELL"
                cost = settings.CAPEX_SMALL_CELL_INR
                payback = 10
                rank = 2
                reason = f"Urban signal shadow behind high-rises (RSRP: {rsrp} dBm). Deploy streetlight-mounted 5G small cells to eliminate indoor dead zones."
            confidence = 91.0
            evidence = f"RSRP: {rsrp:.1f} dBm (Weak) | Load: {load:.1f}% | Density: {density}/km² | Area: {area_type}"

        # Rule 4: Normal Operation (Good Signal + Normal Load)
        else:
            action = "NO ACTION (RADIO MICRO-SLEEP)"
            confidence = 98.0
            cost = 0.0
            payback = 0
            rank = 4
            reason = f"Healthy network headroom ({load:.1f}% load, RSRP: {rsrp} dBm). Maintain nominal operation and enable 3GPP Rel-17 radio micro-sleep between 01:00-05:00 IST for 18.5% energy savings."
            evidence = f"Load: {load:.1f}% | RSRP: {rsrp:.1f} dBm | SINR: {sinr:.1f} dB | Headroom: {max(0.0, 100.0 - load):.1f}%"

        return {
            "action": action,
            "confidence_pct": confidence,
            "reason": reason,
            "evidence_numbers": evidence,
            "estimated_cost_inr": cost,
            "payback_months": payback,
            "priority_rank": rank
        }

    def generate_all_recommendations(self, db: Session) -> List[Recommendation]:
        """Scans all towers and upserts current recommendations."""
        towers = db.query(Tower).all()
        recs = []

        for t in towers:
            latest = db.query(Reading).filter(Reading.tower_id == t.tower_id).order_by(desc(Reading.timestamp)).first()
            evaluation = self.evaluate_tower(t, latest)

            rec = db.query(Recommendation).filter(Recommendation.tower_id == t.tower_id).first()
            if not rec:
                rec = Recommendation(tower_id=t.tower_id)
                db.add(rec)

            rec.action = evaluation["action"]
            rec.confidence_pct = evaluation["confidence_pct"]
            rec.reason = evaluation["reason"]
            rec.evidence_numbers = evaluation["evidence_numbers"]
            rec.estimated_cost_inr = evaluation["estimated_cost_inr"]
            rec.payback_months = evaluation["payback_months"]
            rec.priority_rank = evaluation["priority_rank"]
            recs.append(rec)

        db.commit()
        return recs


recommendation_engine = RecommendationEngine()

