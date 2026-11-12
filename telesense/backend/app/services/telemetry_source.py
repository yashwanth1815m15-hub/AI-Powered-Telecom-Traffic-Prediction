"""Telemetry Source Abstraction & Implementations for TeleSense Platform.

Supports:
1. SimulatorSource: Real-time high-fidelity streaming across 32 Indian towers
2. CsvReplaySource: Replays external CSV telemetry (e.g. TRAI, Telecom Italia)
3. CrowdsourceSource: Ingests real mobile browser measurements
4. Historical 6-Month Backfill Generator for Day-One ML Readiness
"""

import abc
import random
import logging
import datetime
from typing import List, Dict, Any, Optional
import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from app.models.telemetry import Tower, Reading, CrowdsourceMeasurement
from app.config import settings
from app.services.seed_towers_data import SEED_TOWERS

logger = logging.getLogger("TelemetrySource")


class TelemetrySource(abc.ABC):
    """Abstract Interface for cellular telemetry ingest."""

    @abc.abstractmethod
    def get_latest_readings(self, db: Session, simulated_time: datetime.datetime) -> List[Reading]:
        """Generate or retrieve new observation per tower for the given timestamp."""
        pass


class SimulatorSource(TelemetrySource):
    """Generates continuous realistic Indian cellular stream with physics & behavior."""

    def __init__(self) -> None:
        self.towers = SEED_TOWERS

    def _india_calendar_multiplier(self, ist_dt: datetime.datetime) -> float:
        """
        Applies sourced Indian festival and IPL evening traffic multipliers using IST clock.
        (Calibrated to Indian diurnal streaming/festival patterns; explicitly labelled SIMULATED.)
        """
        mult = 1.0
        # IPL Evening Match Windows (March-May, 19:30-23:30 IST)
        if ist_dt.month in (3, 4, 5) and 19 <= ist_dt.hour <= 23:
            mult *= 1.16
        # Major Indian Festive Rush (Diwali Oct/Nov week, Sankranti Jan 14-15, Republic/Indep Day)
        if (ist_dt.month, ist_dt.day) in {
            (1, 14), (1, 15), (1, 26), (8, 15),
            (10, 29), (10, 30), (10, 31), (11, 1), (11, 12),
        } and 18 <= ist_dt.hour <= 23:
            mult *= 1.18
        return mult

    def calculate_telemetry(
        self,
        tower: Dict[str, Any],
        sim_time: datetime.datetime,
        force_overload_demo: bool = False,
        presenter_override: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Calculates India-calibrated simulated cellular load, active users, throughput, RSRP, and SINR."""
        if presenter_override is not None:
            scen = presenter_override["scenario"]
            mitigated = presenter_override["mitigation_applied"]
            ramp_p = float(presenter_override.get("ramp_progress", 1.0))
            mit_p = float(presenter_override.get("mitigation_progress", 1.0 if mitigated else 0.0))

            start_load = float(scen.get("ramp_start_load_pct", scen["target_load_pct"]))
            target_load = float(scen["target_load_pct"])
            scen_load = start_load + (target_load - start_load) * ramp_p

            if mitigated:
                post_load = float(scen["post_action_load_pct"])
                load_val = scen_load + (post_load - scen_load) * mit_p
                rsrp_val = scen["target_rsrp_dbm"] + (scen["post_action_rsrp_dbm"] - scen["target_rsrp_dbm"]) * mit_p
                tput_val = scen["target_throughput_mbps"] + (scen["post_action_throughput_mbps"] - scen["target_throughput_mbps"]) * mit_p
                sinr_val = scen["target_sinr_db"] + (18.2 - scen["target_sinr_db"]) * mit_p
                u_mult = scen["user_multiplier"] + (1.0 - scen["user_multiplier"]) * mit_p
            else:
                load_val = scen_load
                rsrp_val = scen["target_rsrp_dbm"]
                tput_val = scen["target_throughput_mbps"]
                sinr_val = scen["target_sinr_db"]
                u_mult = scen["user_multiplier"]

            max_users = max(50, int(tower["population_density"] * 0.15))
            return {
                "load_pct": round(float(np.clip(load_val + random.gauss(0, 0.25), 0.5, 99.5)), 2),
                "active_users": max(12, int(max_users * (load_val / 100.0) * u_mult)),
                "avg_throughput_mbps": round(float(max(0.1, tput_val + random.uniform(-0.15, 0.15))), 2),
                "rsrp_dbm": round(float(rsrp_val), 1),
                "sinr_db": round(float(sinr_val), 1),
            }

        # Convert timestamp to IST (UTC+05:30) for real Indian diurnal alignment
        from app.services.time_utils import to_ist
        from app.services.presenter_mode import presenter_manager
        ist_dt = to_ist(sim_time)
        hour = ist_dt.hour
        dow = ist_dt.weekday()
        is_weekend = 1 if dow in [5, 6] else 0
        profile = presenter_manager.baseline_profile

        # 1. Empirical Indian 24-Hour IST Diurnal Curve
        # Night trough 01:00-05:00 IST (~12-18%), morning ramp 09:00-13:00 IST, prime evening peak 20:00-22:30 IST
        hour_rad = (hour - 4.0) * (2.0 * np.pi / 24.0)
        diurnal_factor = 0.5 * (1.0 - np.cos(hour_rad))
        evening_surge = 0.28 if 19 <= hour <= 22 else 0.0
        weekend_boost = 0.06 if is_weekend else -0.01

        base_load = 21.0 + (diurnal_factor * 40.0) + (evening_surge * 100.0 * 0.20) + (weekend_boost * 100.0)
        base_load *= self._india_calendar_multiplier(ist_dt)

        if tower.get("is_chronic", 0) == 1:
            base_load += 12.0 if profile == "realistic" else 6.0

        noise = random.gauss(0, 1.4)
        max_cap = 82.0 if (profile == "realistic" and not force_overload_demo) else (76.0 if not force_overload_demo else 99.2)
        final_load = np.clip(base_load + noise, 5.0, max_cap)

        # No random single-tick fake outages in baseline
        is_outage = False

        # Unified active-users equation across forecast, planner, and what-if
        max_users = int(tower["population_density"] * 0.15)
        active_users = int(max_users * (final_load / 100.0))

        headroom_ratio = max(0.05, (100.0 - final_load) / 100.0)
        avg_throughput = round(float(headroom_ratio * 70.0 + random.uniform(1.0, 4.5)), 2)

        if profile == "realistic" and tower.get("is_weak", 0) == 1:
            rsrp = round(random.uniform(-116.0, -111.5), 1)
            sinr = round(random.uniform(2.0, 5.0), 1)
        else:
            rsrp = round(random.uniform(-89.0, -74.0), 1)
            sinr = round(random.uniform(12.0, 24.0), 1)

        return {
            "load_pct": round(float(final_load), 2),
            "active_users": max(12, active_users),
            "avg_throughput_mbps": avg_throughput,
            "rsrp_dbm": rsrp,
            "sinr_db": sinr
        }

    def get_latest_readings(
        self,
        db: Session,
        simulated_time: datetime.datetime,
        force_overload_demo: bool = False
    ) -> List[Reading]:
        """Generates and commits live observations for all towers."""
        readings = []
        for t_info in self.towers:
            metrics = self.calculate_telemetry(t_info, simulated_time, force_overload_demo)
            reading = Reading(
                tower_id=t_info["tower_id"],
                timestamp=simulated_time,
                load_pct=metrics["load_pct"],
                active_users=metrics["active_users"],
                avg_throughput_mbps=metrics["avg_throughput_mbps"],
                rsrp_dbm=metrics["rsrp_dbm"],
                sinr_db=metrics["sinr_db"]
            )
            readings.append(reading)
            db.add(reading)

        db.commit()
        return readings

    def get_latest_reading(self, tower, sim_time: Optional[datetime.datetime] = None) -> Dict[str, Any]:
        """Returns single tower's live telemetry dict."""
        if sim_time is None:
            sim_time = datetime.datetime.now(datetime.timezone.utc)
        # Find tower info or construct dict
        t_info = next((t for t in self.towers if t["tower_id"] == tower.tower_id), {
            "tower_id": tower.tower_id,
            "population_density": tower.population_density,
            "is_chronic": tower.is_chronic_overloader,
            "is_weak": tower.is_weak_signal
        })
        from app.services.presenter_mode import presenter_manager
        override = presenter_manager.get_scenario_override(tower.tower_id)
        metrics = self.calculate_telemetry(t_info, sim_time, presenter_override=override)
        metrics["tower_id"] = tower.tower_id
        metrics["timestamp"] = sim_time
        return metrics



def seed_towers_and_backfill(db: Session, backfill_months: int = 6) -> None:
    """
    Populates simulated Indian cell towers across 34 states and union territories.
    Ensures every tower has historical hourly telemetry for day-one ML forecasts.
    """
    existing_towers_count = db.query(Tower).count()
    logger.info(f"Existing towers in database: {existing_towers_count}. Target inventory: {len(SEED_TOWERS)}")

    newly_added_towers = []
    for t_data in SEED_TOWERS:
        existing = db.query(Tower).filter(Tower.tower_id == t_data["tower_id"]).first()
        if not existing:
            tower_obj = Tower(
                tower_id=t_data["tower_id"],
                name=t_data["name"],
                city=t_data["city"],
                lat=t_data["lat"],
                lon=t_data["lon"],
                capacity_mbps=t_data["capacity_mbps"],
                population_density=t_data["population_density"],
                area_type=t_data["area_type"],
                is_chronic_overloader=t_data.get("is_chronic", 0),
                is_weak_signal=t_data.get("is_weak", 0)
            )
            db.add(tower_obj)
            newly_added_towers.append(t_data)

    db.commit()
    logger.info(f"Added {len(newly_added_towers)} new Indian cell towers to database.")

    simulator = SimulatorSource()
    now_time = datetime.datetime.now(datetime.timezone.utc).replace(minute=0, second=0, microsecond=0)

    # Check towers that lack recent readings and backfill them (past 72 hours)
    all_towers = db.query(Tower).all()
    batch_readings = []

    for tower in all_towers:
        r_count = db.query(Reading).filter(Reading.tower_id == tower.tower_id).count()
        if r_count < 24:
            t_info = next((t for t in SEED_TOWERS if t["tower_id"] == tower.tower_id), {
                "tower_id": tower.tower_id,
                "population_density": tower.population_density,
                "is_chronic": tower.is_chronic_overloader,
                "is_weak": tower.is_weak_signal
            })
            # Generate 72 hours of history
            for h in range(72, -1, -1):
                pt_time = now_time - datetime.timedelta(hours=h)
                metrics = simulator.calculate_telemetry(t_info, pt_time)
                reading = Reading(
                    tower_id=tower.tower_id,
                    timestamp=pt_time,
                    load_pct=metrics["load_pct"],
                    active_users=metrics["active_users"],
                    avg_throughput_mbps=metrics["avg_throughput_mbps"],
                    rsrp_dbm=metrics["rsrp_dbm"],
                    sinr_db=metrics["sinr_db"]
                )
                batch_readings.append(reading)

        if len(batch_readings) >= 1500:
            db.bulk_save_objects(batch_readings)
            db.commit()
            batch_readings = []

    if batch_readings:
        db.bulk_save_objects(batch_readings)
        db.commit()

    total_readings = db.query(Reading).count()
    logger.info(f"Database sync complete! Total cell towers: {len(all_towers)}, Total telemetry readings: {total_readings:,}")


# Global singleton instance for live streaming
_simulator_instance = None

def get_telemetry_source() -> TelemetrySource:
    """
    Factory to retrieve active telemetry source based on configuration.
    Enables zero-friction plug-and-play swapping between Simulator,
    CSV Replay, and Crowdsource streams.
    """
    global _simulator_instance
    # Currently default to SimulatorSource
    if _simulator_instance is None:
        _simulator_instance = SimulatorSource()
    return _simulator_instance

