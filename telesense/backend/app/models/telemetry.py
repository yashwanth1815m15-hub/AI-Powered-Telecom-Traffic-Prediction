"""SQLAlchemy Models for Cell Towers, Live Telemetry Readings, and Crowdsource Measurements."""

import datetime
from sqlalchemy import Column, String, Float, Integer, BigInteger, DateTime, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database import Base


class Tower(Base):
    """Represents a physical or virtual cellular base station (gNodeB / eNodeB)."""
    __tablename__ = "towers"

    tower_id = Column(String(32), primary_key=True, index=True)
    name = Column(String(128), nullable=False)
    city = Column(String(64), nullable=False, index=True)
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)
    capacity_mbps = Column(Float, default=1000.0)
    population_density = Column(Integer, default=5000)  # people per sq km
    area_type = Column(String(32), default="urban", index=True)  # urban, semi-urban, rural
    is_chronic_overloader = Column(Integer, default=0) # 1 if chronic bottleneck
    is_weak_signal = Column(Integer, default=0)        # 1 if rural coverage shadow
    source_type = Column(String(32), default="SIMULATED")
    accuracy_radius_m = Column(Float, nullable=True)

    # Relationships
    readings = relationship("Reading", back_populates="tower", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="tower", cascade="all, delete-orphan")
    recommendations = relationship("Recommendation", back_populates="tower", cascade="all, delete-orphan")


class Reading(Base):
    """High-frequency or hourly telemetry observation per cell tower."""
    __tablename__ = "readings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tower_id = Column(String(32), ForeignKey("towers.tower_id"), nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, index=True)

    # Core Telemetry Metrics
    load_pct = Column(Float, nullable=False)              # 0.0 to 100.0 %
    active_users = Column(Integer, nullable=False)        # Connected UEs
    avg_throughput_mbps = Column(Float, nullable=False)   # User plane throughput
    rsrp_dbm = Column(Float, nullable=False)              # Reference Signal Received Power
    sinr_db = Column(Float, nullable=False)               # Signal-to-Interference-plus-Noise Ratio

    # Relationship
    tower = relationship("Tower", back_populates="readings")

    __table_args__ = (
        Index("idx_tower_time", "tower_id", "timestamp"),
    )


class CrowdsourceMeasurement(Base):
    """Anonymized mobile speed & latency telemetry collected via /measure."""
    __tablename__ = "crowdsource_measurements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, index=True)
    download_speed_mbps = Column(Float, nullable=False)
    upload_speed_mbps = Column(Float, nullable=True)
    latency_ms = Column(Float, nullable=False)
    jitter_ms = Column(Float, nullable=True)
    connection_type = Column(String(32), default="4G")     # 5G, 4G, 3G, WiFi
    coarse_lat = Column(Float, nullable=False)            # Rounded to 2 decimal places for privacy
    coarse_lon = Column(Float, nullable=False)
    quality_label = Column(String(64), nullable=False)     # "Good for 4K video", "Weak Signal", etc.
    nearest_tower_id = Column(String(32), nullable=True)
    server_city = Column(String(64), nullable=True)
    run_number = Column(Integer, nullable=True)
    user_agent = Column(String(256), nullable=True)
    network_type = Column(String(64), nullable=True)
    is_test = Column(Integer, default=0, nullable=False)


class OpenCellIDCell(Base):
    """
    Cached physical cell record imported offline from OpenCellID (CC BY-SA 4.0).
    Note: Indian coordinates are rounded to ~1 km (approximate position, not confirmed tower).
    """
    __tablename__ = "opencellid_cells"

    id = Column(Integer, primary_key=True, autoincrement=True)
    radio = Column(String(16), nullable=False, default="LTE")
    mcc = Column(Integer, nullable=False, index=True)
    mnc = Column(Integer, nullable=False, index=True)
    lac = Column(Integer, nullable=False)
    cellid = Column(BigInteger, nullable=False)
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)
    range = Column(Integer, default=1000)
    samples = Column(Integer, default=1)
    source = Column(String(32), nullable=False, default="OpenCellID")
    fetched_at = Column(DateTime, nullable=False, default=datetime.datetime.utcnow)
    city = Column(String(64), nullable=True, index=True)
    state = Column(String(64), nullable=True)
    in_india_polygon = Column(Integer, default=1)

    __table_args__ = (
        UniqueConstraint("mcc", "mnc", "lac", "cellid", "radio", name="uq_ocid_cell_record"),
        Index("idx_ocid_city_coords", "city", "lat", "lon"),
    )

