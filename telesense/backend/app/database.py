"""SQLAlchemy Database Engine, Session Maker, Base Definition, and Idempotent Column Migrations."""

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker
from app.config import settings

connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """Dependency that provides a database session and closes it cleanly."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _ensure_column(conn, table: str, column: str, ddl_type: str) -> None:
    insp = inspect(conn)
    if not insp.has_table(table):
        return
    cols = {c["name"] for c in insp.get_columns(table)}
    if column not in cols:
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl_type}"))


def init_db():
    """Creates all database tables defined in models and runs safe additive column migrations."""
    import app.models  # noqa: F401
    Base.metadata.create_all(bind=engine)

    with engine.begin() as conn:
        # Alerts rich schema upgrades
        _ensure_column(conn, "alerts", "alert_type", "VARCHAR(32) NOT NULL DEFAULT 'PREDICTED_OVERLOAD'")
        _ensure_column(conn, "alerts", "what", "TEXT")
        _ensure_column(conn, "alerts", "where_location", "VARCHAR(160)")
        _ensure_column(conn, "alerts", "when_ist", "VARCHAR(64)")
        _ensure_column(conn, "alerts", "evidence_json", "TEXT")
        _ensure_column(conn, "alerts", "ranked_causes_json", "TEXT")
        _ensure_column(conn, "alerts", "expected_benefit", "TEXT")
        _ensure_column(conn, "alerts", "provenance", "VARCHAR(32) NOT NULL DEFAULT 'SIMULATED'")
        _ensure_column(conn, "alerts", "source", "VARCHAR(16) NOT NULL DEFAULT 'baseline'")
        _ensure_column(conn, "alerts", "acknowledged_at", "DATETIME")
        _ensure_column(conn, "alerts", "resolved_at", "DATETIME")

        # Crowdsource raw speedtest logging upgrades
        _ensure_column(conn, "crowdsource_measurements", "upload_speed_mbps", "FLOAT")
        _ensure_column(conn, "crowdsource_measurements", "jitter_ms", "FLOAT")
        _ensure_column(conn, "crowdsource_measurements", "server_city", "VARCHAR(64)")
        _ensure_column(conn, "crowdsource_measurements", "run_number", "INTEGER")
