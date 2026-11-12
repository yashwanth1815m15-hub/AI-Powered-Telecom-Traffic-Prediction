"""
TeleSense Presenter Mode Engine & Baseline Profile Controller (Phase A + B1)

Guarantees:
- One global demo state (`active`, `scenario_id`, `city`, `started_at`, `ends_at`, `affected_sites`).
- Strict city resolution: refuses to start (raises ValueError -> HTTP 400) if 0 sites match.
- Per-site telemetry overrides feed live header counts, map markers, forecasts, recommendations & alerts.
- Effects ramp over 60–90s; Apply Recommended Action steps capacity (+40% assumption) & load down over 45s.
- Stop / Reset / Esc / Auto-revert deletes all `source='demo'` alerts cleanly & restores baseline within 1 tick.
- Baseline Profile switch: 'healthy' (default, 0 flagged) vs 'realistic' (rural weak-coverage sites).
- External HTTP-200 primary sources only (Opensignal IPL ET Telecom; Ookla & Jio/Ericsson Maha Kumbh).
  All non-externally-sourced scenarios explicitly say "Generic simulation, no external source".
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.config import settings
from app.models.alert import Alert, AlertAuditLog, AlertStreak, Recommendation
from app.models.telemetry import OpenCellIDCell, Reading, Tower
from app.services.alert_engine import evaluate_reading_alerts, record_alert_audit
from app.services.recommendation_engine import recommendation_engine
from app.services.time_utils import format_ist_datetime


SCENARIO_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    "ipl_surge": {
        "id": "ipl_surge",
        "title": "IPL Match-Night Surge",
        "subtitle": "Stadium catchment concurrency spike; load climbs 90–98% across match-zone sectors",
        "inspired_by": "Opensignal 2023 Indian cricket stadium study (via ET Telecom)",
        "source_url": "https://economictimes.indiatimes.com/industry/telecom/telecom-news/eden-gardens-tops-in-5g-download-speeds-this-ipl-open-signal/articleshow/100425243.cms",
        "statement_url": None,
        "alert_types": ["PREDICTED_OVERLOAD", "DEGRADED_SPEED"],
        "city_wide": False,
        "ramp_start_load_pct": 95.2,
        "target_load_pct": 97.6,
        "target_rsrp_dbm": -82.0,
        "target_sinr_db": 15.2,
        "target_throughput_mbps": 4.6,
        "user_multiplier": 1.65,
        "recommended_action": "ADD BANDWIDTH (CARRIER AGGREGATION)",
        "capacity_assumption": "Assumption: +40% effective sector capacity (5G n78 + Band 40 CA & CoW offload)",
        "post_action_load_pct": 62.4,
        "post_action_rsrp_dbm": -80.5,
        "post_action_throughput_mbps": 46.2,
        "checklist": [
            "1. Activate secondary 5G Band n78 (3500 MHz) + Band 40 carrier aggregation (+40% assumed capacity).",
            "2. Enable uplink MIMO beam steering toward stadium & transit corridors.",
            "3. Pre-position Temporary Cell-on-Wheels (CoW) for evening match hours (19:30–23:30 IST).",
            "4. Adjust idle-mode handoff thresholds (+3 dB CIO) to neighboring sectors.",
        ],
    },
    "diwali_surge": {
        "id": "diwali_surge",
        "title": "Festival Night Surge (Diwali)",
        "subtitle": "City-wide evening surge across metro residential and market sectors (19:00–22:30 IST)",
        "inspired_by": "Generic simulation, no external source",
        "source_url": None,
        "statement_url": None,
        "alert_types": ["PREDICTED_OVERLOAD"],
        "city_wide": True,
        "ramp_start_load_pct": 90.4,
        "target_load_pct": 96.4,
        "target_rsrp_dbm": -84.5,
        "target_sinr_db": 14.0,
        "target_throughput_mbps": 7.5,
        "user_multiplier": 1.50,
        "recommended_action": "ADD BANDWIDTH (CARRIER AGGREGATION)",
        "capacity_assumption": "Assumption: +35% effective carrier capacity during festive evening window",
        "post_action_load_pct": 61.8,
        "post_action_rsrp_dbm": -83.5,
        "post_action_throughput_mbps": 42.1,
        "checklist": [
            "1. Pre-allocate supplemental 20 MHz LTE/5G carrier across busy city markets.",
            "2. Enable QoS prioritization for VoLTE/VoNR voice setup during 19:00–22:30 IST rush.",
            "3. Balance PRB scheduling weights between uplink video greetings and downlink traffic.",
            "4. Verify standby DG & grid power readiness for evening peak.",
        ],
    },
    "rural_coverage_hole": {
        "id": "rural_coverage_hole",
        "title": "Rural Coverage Hole (Weak Signal, Low Load)",
        "subtitle": "Weak coverage zone (~ -118.5 dBm RSRP) with low load (~28%)",
        "inspired_by": "Generic simulation, no external source",
        "source_url": None,
        "statement_url": None,
        "alert_types": ["WEAK_COVERAGE"],
        "city_wide": False,
        "ramp_start_load_pct": 28.4,
        "target_load_pct": 28.4,
        "target_rsrp_dbm": -118.5,
        "target_sinr_db": 2.1,
        "target_throughput_mbps": 14.5,
        "user_multiplier": 0.90,
        "recommended_action": "BUILD NEW TOWER / LOW-BAND SMALL CELL",
        "capacity_assumption": "Assumption: Sub-GHz 700/850 MHz small cell infill adds +27 dB link budget",
        "post_action_load_pct": 33.5,
        "post_action_rsrp_dbm": -91.5,
        "post_action_throughput_mbps": 34.6,
        "checklist": [
            "1. Audit macro antenna azimuth & mechanical down-tilt toward rural cluster.",
            "2. Deploy solar-powered sub-GHz (700/850 MHz) small cell / repeater to clear weak coverage.",
            "3. Configure low-band coverage carrier with extended cyclic prefix.",
            "4. Validate voice handover continuity along connecting roads.",
        ],
    },
    "fiber_cut_outage": {
        "id": "fiber_cut_outage",
        "title": "Fibre Cut / Outage",
        "subtitle": "Sudden metro ring transport break causing sector traffic collapse (< 3% load)",
        "inspired_by": "Generic simulation, no external source",
        "source_url": None,
        "statement_url": None,
        "alert_types": ["OUTAGE"],
        "city_wide": False,
        "ramp_start_load_pct": 2.1,
        "target_load_pct": 1.4,
        "target_rsrp_dbm": -123.0,
        "target_sinr_db": -1.5,
        "target_throughput_mbps": 0.2,
        "user_multiplier": 0.05,
        "recommended_action": "REPAIR BACKHAUL",
        "capacity_assumption": "Assumption: Redundant ring reroute & splicing restores 100% transport capacity",
        "post_action_load_pct": 54.0,
        "post_action_rsrp_dbm": -82.5,
        "post_action_throughput_mbps": 46.5,
        "checklist": [
            "1. Dispatch optical splicing crew with OTDR fault locator along aggregation ring.",
            "2. Activate automated neighbor compensation (+3 dB pilot boost on adjacent sites).",
            "3. Switch baseband backhaul onto redundant microwave protection path.",
            "4. Verify recovery heartbeat & close outage incident after 3 clear intervals.",
        ],
    },
    "cyclone_backhaul": {
        "id": "cyclone_backhaul",
        "title": "Cyclone / Severe Storm Multi-Site Outage",
        "subtitle": "Several coastal/city sites down (< 3% load) due to storm backhaul & mains loss",
        "inspired_by": "Generic simulation, no external source",
        "source_url": None,
        "statement_url": None,
        "alert_types": ["OUTAGE"],
        "city_wide": True,
        "ramp_start_load_pct": 2.4,
        "target_load_pct": 1.6,
        "target_rsrp_dbm": -121.0,
        "target_sinr_db": 0.8,
        "target_throughput_mbps": 0.4,
        "user_multiplier": 0.08,
        "recommended_action": "REPAIR BACKHAUL",
        "capacity_assumption": "Assumption: Emergency microwave QPSK fallback & DG restore restores site service",
        "post_action_load_pct": 58.2,
        "post_action_rsrp_dbm": -86.0,
        "post_action_throughput_mbps": 34.0,
        "checklist": [
            "1. Switch microwave E-band links to adaptive QPSK fallback or optical backup.",
            "2. Coordinate intra-circle disaster roaming across surviving carrier sites.",
            "3. Dispatch battery / portable DG emergency fuel to affected sector clusters.",
            "4. Stage satellite backhaul CoW if terrestrial transport remains offline > 4 hours.",
        ],
    },
    "mela_gathering": {
        "id": "mela_gathering",
        "title": "Mela-Style Crowd Gathering",
        "subtitle": "Extreme local congregation spike (> 97% PRB load, degraded speeds)",
        "inspired_by": "Ookla 5G Maha Kumbh Report & Jio/Ericsson Statement (via ET Telecom)",
        "source_url": "https://www.ookla.com/articles/5g-maha-kumbh-feb25",
        "statement_url": "https://telecom.economictimes.indiatimes.com/news/industry/maha-kumbh-2025-ericsson-says-enabled-jio-5g-network-to-handle-400-mn-data-service-requests-at-peak/118603781",
        "alert_types": ["PREDICTED_OVERLOAD", "DEGRADED_SPEED"],
        "city_wide": False,
        "ramp_start_load_pct": 95.8,
        "target_load_pct": 98.4,
        "target_rsrp_dbm": -87.0,
        "target_sinr_db": 6.4,
        "target_throughput_mbps": 2.6,
        "user_multiplier": 2.35,
        "recommended_action": "TEMPORARY CELL (COW)",
        "capacity_assumption": "Assumption: +50% local sector capacity via CoW cluster + 3.5 GHz SA offload",
        "post_action_load_pct": 64.5,
        "post_action_rsrp_dbm": -80.5,
        "post_action_throughput_mbps": 39.2,
        "checklist": [
            "1. Deploy Temporary Cell-on-Wheels (CoW) units at entry corridors & gathering zones.",
            "2. Offload 5G SA devices onto dedicated 3.5 GHz high-capacity sectors.",
            "3. Reserve voice & digital-payment signalling headroom under high PRB utilization.",
            "4. Monitor hourly crowd movement to rebalance sector azimuths.",
        ],
    },
}


class PresenterModeManager:
    """Global Demo Scenario State Machine & Baseline Profile Switcher."""

    RAMP_UP_SECONDS = 75
    MITIGATION_RAMP_SECONDS = 45

    def __init__(self) -> None:
        self.active: bool = False
        self.scenario_id: Optional[str] = None
        self.city: Optional[str] = None
        self.target_tower_ids: List[str] = []
        self.affected_sites: List[Dict[str, Any]] = []
        self.affected_cluster_count: int = 0
        self.activated_at: Optional[datetime] = None
        self.expires_at: Optional[datetime] = None
        self.auto_revert_seconds: int = 300
        self.mitigation_applied: bool = False
        self.mitigation_started_at: Optional[datetime] = None
        self.applied_action_name: Optional[str] = None
        self.before_snapshot: Optional[Dict[str, Any]] = None
        self.after_snapshot: Optional[Dict[str, Any]] = None
        self.before_after_curve: List[Dict[str, Any]] = []
        self.baseline_profile: str = "healthy"  # 'healthy' (default, 0 flagged) or 'realistic'

    def get_scenario_override(self, tower_id: str) -> Optional[Dict[str, Any]]:
        """Returns live interpolated override values for an active demo tower."""
        if not self.active or not self.scenario_id or tower_id not in self.target_tower_ids:
            return None
        scen = SCENARIO_DEFINITIONS.get(self.scenario_id)
        if not scen:
            return None

        now_utc = datetime.now(timezone.utc)
        ramp_progress = 1.0
        if self.activated_at:
            elapsed = max(0.0, (now_utc - self.activated_at).total_seconds())
            ramp_progress = min(1.0, elapsed / float(self.RAMP_UP_SECONDS))

        mit_progress = 0.0
        if self.mitigation_applied and self.mitigation_started_at:
            m_elapsed = max(0.0, (now_utc - self.mitigation_started_at).total_seconds())
            # Starts with initial ~35% immediate relief so apply action shows instant downward step, then completes over 45s
            mit_progress = min(1.0, 0.35 + 0.65 * (m_elapsed / float(self.MITIGATION_RAMP_SECONDS)))

        return {
            "scenario": scen,
            "mitigation_applied": self.mitigation_applied,
            "ramp_progress": ramp_progress,
            "mitigation_progress": mit_progress,
        }

    def resolve_city_targets(self, db: Session, city: str, city_wide: bool = False) -> tuple[List[Tower], int]:
        """Strictly resolves city to simulated sites + OpenCellID clusters. Raises ValueError if 0 match."""
        q = (city or "").strip().lower()
        if not q:
            raise ValueError("Target city name is required. Demo scenario not started.")

        all_towers = db.query(Tower).all()
        exact = [t for t in all_towers if (t.city or "").strip().lower() == q]
        matched = exact if exact else [
            t for t in all_towers
            if q in (t.city or "").lower() or q in (t.name or "").lower()
        ]
        if not matched:
            raise ValueError(f"No matching simulated sites found for '{city}'. Affected sites: 0. Demo not started.")

        cluster_coords = {
            (c or "", round(la, 2), round(lo, 2))
            for c, la, lo in db.query(
                OpenCellIDCell.city, OpenCellIDCell.lat, OpenCellIDCell.lon
            ).filter(OpenCellIDCell.in_india_polygon == 1).all()
            if c and (c.strip().lower() == q or q in c.strip().lower())
        }

        cap = 4 if city_wide else 2
        return matched[:cap], len(cluster_coords)

    def check_auto_revert(self, db: Session) -> bool:
        """Auto-restores baseline cleanly when demo timer expires."""
        if not self.active or not self.expires_at:
            return False
        if datetime.now(timezone.utc) >= self.expires_at:
            self.reset(db, note="Demo scenario auto-revert timer expired", action_name="DEMO_EXPIRED")
            return True
        return False

    def set_baseline_profile(self, db: Session, profile: str) -> Dict[str, Any]:
        """Switches baseline profile between 'healthy' (0 flagged) and 'realistic' (rural weak-coverage sites)."""
        norm = (profile or "").strip().lower()
        if norm not in ("healthy", "realistic"):
            raise ValueError("baseline_profile must be 'healthy' or 'realistic'")
        self.baseline_profile = norm
        now_naive = datetime.now(timezone.utc).replace(tzinfo=None)

        if not self.active:
            towers = db.query(Tower).all()
            weak_candidates = [t for t in towers if t.is_weak_signal == 1][:5]
            weak_ids = {t.tower_id for t in weak_candidates}
            db.query(Alert).filter(Alert.source != "demo", Alert.status.in_(["ACTIVE", "ACKNOWLEDGED"])).update(
                {"status": "RESOLVED", "resolved_at": now_naive}, synchronize_session=False
            )
            db.query(AlertStreak).delete()

            for t in towers:
                is_weak_realistic = (norm == "realistic") and (t.tower_id in weak_ids)
                rsrp = -114.2 if is_weak_realistic else -82.5
                load = 42.0 if not t.is_chronic_overloader else 64.0
                if is_weak_realistic:
                    load = 34.5
                r = Reading(
                    tower_id=t.tower_id,
                    timestamp=now_naive,
                    load_pct=load,
                    active_users=int(max(50, t.population_density * 0.08)),
                    avg_throughput_mbps=22.0 if is_weak_realistic else 48.0,
                    rsrp_dbm=rsrp,
                    sinr_db=4.5 if is_weak_realistic else 17.5,
                )
                db.add(r)
                db.flush()
                if is_weak_realistic:
                    evaluate_reading_alerts(
                        db=db,
                        tower=t,
                        current_reading=r,
                        immediate=True,
                        provenance="SIMULATED",
                        source="baseline",
                        scenario_context="Realistic baseline profile (SIMULATED rural RF shadow)",
                    )
                rec_data = recommendation_engine.evaluate_tower(t, r)
                ex_rec = db.query(Recommendation).filter(Recommendation.tower_id == t.tower_id).first()
                if ex_rec:
                    ex_rec.action = rec_data["action"]
                    ex_rec.reason = rec_data["reason"]
                    ex_rec.evidence_numbers = rec_data["evidence_numbers"]
                    ex_rec.estimated_cost_inr = rec_data["estimated_cost_inr"]
                    ex_rec.payback_months = rec_data["payback_months"]
                    ex_rec.priority_rank = rec_data["priority_rank"]
                    ex_rec.updated_at = now_naive

            record_alert_audit(
                db=db,
                alert_id=None,
                tower_id="FLEET",
                alert_type="BASELINE_PROFILE",
                action="PROFILE_SWITCHED",
                actor="operator",
                note=f"Switched baseline profile to {norm} (SIMULATED)",
                timestamp=now_naive,
            )
            db.commit()
        return self.get_status()

    def activate(
        self,
        db: Session,
        scenario_id: str,
        city: str,
        auto_revert_seconds: int = 300,
    ) -> Dict[str, Any]:
        if scenario_id not in SCENARIO_DEFINITIONS:
            raise ValueError(f"Unknown scenario_id: {scenario_id}")

        scen = SCENARIO_DEFINITIONS[scenario_id]
        # Resolve city strictly BEFORE mutating state so 0-site errors don't disrupt current view
        targets, cluster_count = self.resolve_city_targets(db, city, city_wide=bool(scen.get("city_wide")))

        if self.active:
            self.reset(db, note="Superseded by new demo scenario", action_name="DEMO_REPLACED")

        now_utc = datetime.now(timezone.utc)
        now_naive = now_utc.replace(tzinfo=None)
        primary = targets[0]

        prev_latest = (
            db.query(Reading)
            .filter(Reading.tower_id == primary.tower_id)
            .order_by(desc(Reading.timestamp))
            .first()
        )
        baseline_load = prev_latest.load_pct if prev_latest else 44.0

        self.active = True
        self.scenario_id = scenario_id
        self.city = primary.city
        self.target_tower_ids = [t.tower_id for t in targets]
        self.affected_sites = [
            {
                "tower_id": t.tower_id,
                "name": t.name,
                "city": t.city,
                "area_type": t.area_type,
                "lat": t.lat,
                "lon": t.lon,
            }
            for t in targets
        ]
        self.affected_cluster_count = cluster_count
        self.activated_at = now_utc
        self.auto_revert_seconds = max(30, min(900, int(auto_revert_seconds)))
        self.expires_at = now_utc + timedelta(seconds=self.auto_revert_seconds)
        self.mitigation_applied = False
        self.mitigation_started_at = None
        self.applied_action_name = None

        init_load = float(scen["ramp_start_load_pct"])
        for t in targets:
            prev_r = (
                db.query(Reading)
                .filter(Reading.tower_id == t.tower_id)
                .order_by(desc(Reading.timestamp))
                .first()
            )
            max_u = max(50, int(t.population_density * 0.15))
            active_u = max(12, int(max_u * (init_load / 100.0) * scen["user_multiplier"]))
            r = Reading(
                tower_id=t.tower_id,
                timestamp=now_naive,
                load_pct=init_load,
                active_users=active_u,
                avg_throughput_mbps=scen["target_throughput_mbps"],
                rsrp_dbm=scen["target_rsrp_dbm"],
                sinr_db=scen["target_sinr_db"],
            )
            db.add(r)
            db.flush()

            evaluate_reading_alerts(
                db=db,
                tower=t,
                current_reading=r,
                prev_reading=prev_r,
                immediate=True,
                hold_open_types=set(scen["alert_types"]),
                scenario_context=f"DEMO: {scen['title']} ({t.city})",
                provenance="SIMULATED",
                source="demo",
            )

            rec_data = recommendation_engine.evaluate_tower(t, r, scenario_override_action=scen["recommended_action"])
            ex_rec = db.query(Recommendation).filter(Recommendation.tower_id == t.tower_id).first()
            if ex_rec:
                ex_rec.action = rec_data["action"]
                ex_rec.confidence_pct = rec_data["confidence_pct"]
                ex_rec.reason = rec_data["reason"]
                ex_rec.evidence_numbers = rec_data["evidence_numbers"]
                ex_rec.estimated_cost_inr = rec_data["estimated_cost_inr"]
                ex_rec.payback_months = rec_data["payback_months"]
                ex_rec.priority_rank = rec_data["priority_rank"]
                ex_rec.updated_at = now_naive
            else:
                db.add(Recommendation(tower_id=t.tower_id, updated_at=now_naive, **rec_data))

        record_alert_audit(
            db=db,
            alert_id=None,
            tower_id=primary.tower_id,
            alert_type=scen["alert_types"][0],
            action="DEMO_STARTED",
            actor="presenter_mode",
            note=f"Started {scen['title']} in {primary.city} ({len(targets)} sites affected)",
            timestamp=now_naive,
        )
        db.commit()

        before_load = float(scen["target_load_pct"])
        post_load = float(scen["post_action_load_pct"])
        self.before_snapshot = {
            "tower_id": primary.tower_id,
            "tower_name": primary.name,
            "city": primary.city,
            "baseline_normal_load_pct": round(float(baseline_load), 1),
            "scenario_peak_load_pct": init_load,
            "scenario_target_load_pct": before_load,
            "scenario_rsrp_dbm": scen["target_rsrp_dbm"],
            "scenario_throughput_mbps": scen["target_throughput_mbps"],
            "status": (
                "OUTAGE"
                if "OUTAGE" in scen["alert_types"]
                else ("WEAK_COVERAGE" if "WEAK_COVERAGE" in scen["alert_types"] else "CRITICAL")
            ),
        }
        self.after_snapshot = {
            "projected_load_pct": post_load,
            "projected_rsrp_dbm": scen["post_action_rsrp_dbm"],
            "projected_throughput_mbps": scen["post_action_throughput_mbps"],
            "load_drop_pct": round(max(0.0, init_load - post_load), 1),
            "capacity_assumption": scen["capacity_assumption"],
            "status": "HEALTHY",
        }
        self.before_after_curve = [
            {"label": "Before", "load_pct": round(init_load, 1), "rsrp_dbm": scen["target_rsrp_dbm"]},
            {"label": "+15s", "load_pct": round(init_load + (post_load - init_load) * 0.45, 1), "rsrp_dbm": round((scen["target_rsrp_dbm"] + scen["post_action_rsrp_dbm"]) / 2, 1)},
            {"label": "+30s", "load_pct": round(init_load + (post_load - init_load) * 0.78, 1), "rsrp_dbm": round(scen["post_action_rsrp_dbm"], 1)},
            {"label": "+45s", "load_pct": round(post_load, 1), "rsrp_dbm": scen["post_action_rsrp_dbm"]},
        ]
        return self.get_status()

    def apply_recommended_action(self, db: Session) -> Dict[str, Any]:
        """Applies recommended action: steps load/capacity & transitions alerts down over 45s."""
        if not self.active or not self.scenario_id:
            raise ValueError("No active presenter scenario")

        scen = SCENARIO_DEFINITIONS[self.scenario_id]
        now_utc = datetime.now(timezone.utc)
        now_naive = now_utc.replace(tzinfo=None)
        self.mitigation_applied = True
        self.mitigation_started_at = now_utc
        self.applied_action_name = scen["recommended_action"]

        # Apply immediate relief step (drops load below critical threshold -> amber/green & clears demo alerts)
        start_load = float(scen["ramp_start_load_pct"])
        post_load = float(scen["post_action_load_pct"])
        step_load = round(post_load + (start_load - post_load) * 0.25, 1) if start_load > post_load else post_load

        for tid in self.target_tower_ids:
            t = db.query(Tower).filter(Tower.tower_id == tid).first()
            if not t:
                continue
            max_u = max(50, int(t.population_density * 0.15))
            r = Reading(
                tower_id=tid,
                timestamp=now_naive,
                load_pct=step_load,
                active_users=int(max_u * (step_load / 100.0)),
                avg_throughput_mbps=round((scen["target_throughput_mbps"] + scen["post_action_throughput_mbps"]) * 0.55, 1),
                rsrp_dbm=scen["post_action_rsrp_dbm"],
                sinr_db=18.2,
            )
            db.add(r)

            demo_alerts = (
                db.query(Alert)
                .filter(Alert.tower_id == tid, Alert.source == "demo", Alert.status.in_(["ACTIVE", "ACKNOWLEDGED"]))
                .all()
            )
            for a in demo_alerts:
                a.status = "RESOLVED"
                a.resolved_at = now_naive
                record_alert_audit(
                    db=db,
                    alert_id=a.id,
                    tower_id=tid,
                    alert_type=a.alert_type or "PREDICTED_OVERLOAD",
                    action="RESOLVED",
                    actor="presenter_action",
                    note=f"Applied {scen['recommended_action']} ({scen['capacity_assumption']})",
                    timestamp=now_naive,
                )

            rec_data = recommendation_engine.evaluate_tower(t, r)
            ex_rec = db.query(Recommendation).filter(Recommendation.tower_id == tid).first()
            if ex_rec:
                ex_rec.action = rec_data["action"]
                ex_rec.reason = rec_data["reason"]
                ex_rec.evidence_numbers = rec_data["evidence_numbers"]
                ex_rec.estimated_cost_inr = rec_data["estimated_cost_inr"]
                ex_rec.payback_months = rec_data["payback_months"]
                ex_rec.priority_rank = rec_data["priority_rank"]
                ex_rec.updated_at = now_naive

        db.commit()
        return self.get_status()

    def reset(
        self,
        db: Session,
        note: str = "Operator stopped demo and restored baseline",
        action_name: str = "DEMO_STOPPED",
    ) -> Dict[str, Any]:
        """Deletes all DEMO alerts, clears overrides, and restores exact baseline view."""
        now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
        affected = list(self.target_tower_ids)
        stopped_city = self.city or "FLEET"

        # 1. Remove ALL demo-generated alerts cleanly so zero DEMO alerts remain anywhere
        deleted_count = db.query(Alert).filter(Alert.source == "demo").delete(synchronize_session=False)

        # 2. Restore baseline readings & baseline recommendations for all affected sites
        weak_ids = set()
        if self.baseline_profile == "realistic":
            weak_ids = {t.tower_id for t in db.query(Tower).all() if t.is_weak_signal == 1}
            weak_ids = set(list(weak_ids)[:5])

        for tid in affected:
            db.query(AlertStreak).filter(AlertStreak.tower_id == tid).delete(synchronize_session=False)
            t = db.query(Tower).filter(Tower.tower_id == tid).first()
            if not t:
                continue
            is_weak = (self.baseline_profile == "realistic") and (tid in weak_ids)
            load = 34.5 if is_weak else (44.0 if not t.is_chronic_overloader else 66.0)
            rsrp = -114.0 if is_weak else -83.5
            r = Reading(
                tower_id=tid,
                timestamp=now_naive,
                load_pct=load,
                active_users=int(max(50, t.population_density * 0.07)),
                avg_throughput_mbps=24.0 if is_weak else 48.0,
                rsrp_dbm=rsrp,
                sinr_db=5.0 if is_weak else 17.5,
            )
            db.add(r)
            db.flush()

            if is_weak:
                evaluate_reading_alerts(
                    db=db,
                    tower=t,
                    current_reading=r,
                    immediate=True,
                    provenance="SIMULATED",
                    source="baseline",
                )

            rec_data = recommendation_engine.evaluate_tower(t, r)
            ex_rec = db.query(Recommendation).filter(Recommendation.tower_id == tid).first()
            if ex_rec:
                ex_rec.action = rec_data["action"]
                ex_rec.reason = rec_data["reason"]
                ex_rec.evidence_numbers = rec_data["evidence_numbers"]
                ex_rec.estimated_cost_inr = rec_data["estimated_cost_inr"]
                ex_rec.payback_months = rec_data["payback_months"]
                ex_rec.priority_rank = rec_data["priority_rank"]
                ex_rec.updated_at = now_naive

        record_alert_audit(
            db=db,
            alert_id=None,
            tower_id=affected[0] if affected else "FLEET",
            alert_type="PRESENTER_DEMO",
            action=action_name,
            actor="operator",
            note=f"{note} (city={stopped_city}, cleared {deleted_count} demo alerts)",
            timestamp=now_naive,
        )
        db.commit()

        self.active = False
        self.scenario_id = None
        self.city = None
        self.target_tower_ids = []
        self.affected_sites = []
        self.affected_cluster_count = 0
        self.activated_at = None
        self.expires_at = None
        self.mitigation_applied = False
        self.mitigation_started_at = None
        self.applied_action_name = None
        self.before_snapshot = None
        self.after_snapshot = None
        self.before_after_curve = []
        return self.get_status()

    def get_status(self) -> Dict[str, Any]:
        remaining = 0
        if self.active and self.expires_at:
            remaining = max(0, int((self.expires_at - datetime.now(timezone.utc)).total_seconds()))
        scen = SCENARIO_DEFINITIONS.get(self.scenario_id) if self.scenario_id else None
        return {
            "active": self.active,
            "banner_label": "DEMO SCENARIO ACTIVE" if self.active else None,
            "scenario_id": self.scenario_id,
            "scenario_title": scen["title"] if scen else None,
            "scenario_subtitle": scen["subtitle"] if scen else None,
            "inspired_by": scen["inspired_by"] if scen else None,
            "source_url": scen.get("source_url") if scen else None,
            "statement_url": scen.get("statement_url") if scen else None,
            "capacity_assumption": scen.get("capacity_assumption") if scen else None,
            "city": self.city,
            "target_tower_ids": self.target_tower_ids,
            "affected_sites": self.affected_sites,
            "affected_site_count": len(self.affected_sites),
            "affected_cluster_count": self.affected_cluster_count,
            "started_at_ist": format_ist_datetime(self.activated_at) if self.activated_at else None,
            "ends_at_ist": format_ist_datetime(self.expires_at) if self.expires_at else None,
            "seconds_remaining": remaining,
            "auto_revert_seconds": self.auto_revert_seconds,
            "mitigation_applied": self.mitigation_applied,
            "recommended_action": scen["recommended_action"] if scen else None,
            "checklist": scen["checklist"] if scen else [],
            "before_snapshot": self.before_snapshot,
            "after_snapshot": self.after_snapshot,
            "before_after_curve": self.before_after_curve,
            "baseline_profile": self.baseline_profile,
            "available_scenarios": [
                {
                    "id": s["id"],
                    "title": s["title"],
                    "subtitle": s["subtitle"],
                    "inspired_by": s["inspired_by"],
                    "source_url": s.get("source_url"),
                    "statement_url": s.get("statement_url"),
                    "capacity_assumption": s.get("capacity_assumption"),
                    "recommended_action": s["recommended_action"],
                }
                for s in SCENARIO_DEFINITIONS.values()
            ],
        }


presenter_manager = PresenterModeManager()
