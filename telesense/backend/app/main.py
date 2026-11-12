"""
TeleSense Backend Application
Entrypoint for FastAPI server.
Manages:
- Database schema creation & initial 6-month historical backfill
- Live continuous APScheduler telemetry loop
- REST APIs for NOC, Network Planners, and Citizens
- Real-time WebSockets
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from datetime import datetime
import gzip
import json
import logging
import os
from pathlib import Path
import sys

from app.database import init_db, SessionLocal
from app.models.telemetry import OpenCellIDCell, Tower
from app.config import DATA_DIR, PROJECT_ROOT, settings
from app.services.telemetry_source import seed_towers_and_backfill
from app.services.alert_engine import deduplicate_open_alerts
from app.services.scheduler import start_scheduler, stop_scheduler

from app.api import towers, alerts, recommendations, simulation, crowdsource, citizen, websocket, model_health, incidents

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("telesense.main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for startup and shutdown procedures."""
    logger.info("Initializing TeleSense database schema...")
    init_db()

    # Seed data if DB is empty
    db = SessionLocal()
    try:
        tower_count = db.query(Tower).count()
        if tower_count == 0:
            logger.info("Database is empty. Seeding Indian cell towers and backfilling initial telemetry...")
            seed_towers_and_backfill(db, backfill_months=6)
        else:
            cleaned = deduplicate_open_alerts(db)
            logger.info(f"Database already populated with {tower_count} towers (deduped {cleaned} legacy alerts).")

        # Load cached offline OpenCellID India cell records if table is empty (cloud/fresh DB boot)
        if db.query(OpenCellIDCell).count() == 0:
            ocid_cache = DATA_DIR / "opencellid_cells_cache.json.gz"
            if ocid_cache.exists():
                with gzip.open(ocid_cache, "rt", encoding="utf-8") as f:
                    rows = json.load(f)
                objs = []
                for r in rows:
                    fa = r.get("fetched_at")
                    fetched_dt = datetime.fromisoformat(str(fa).replace("Z", "+00:00")) if fa else datetime.utcnow()
                    if fetched_dt.tzinfo is not None:
                        fetched_dt = fetched_dt.replace(tzinfo=None)
                    objs.append(OpenCellIDCell(
                        radio=r.get("radio", "LTE"),
                        mcc=int(r["mcc"]),
                        mnc=int(r["mnc"]),
                        lac=int(r["lac"]),
                        cellid=int(r["cellid"]),
                        lat=float(r["lat"]),
                        lon=float(r["lon"]),
                        range=int(r.get("range") or 1000),
                        samples=int(r.get("samples") or 1),
                        source=r.get("source") or "OpenCellID",
                        fetched_at=fetched_dt,
                        city=r.get("city"),
                        state=r.get("state"),
                        in_india_polygon=int(r.get("in_india_polygon", 1)),
                    ))
                db.bulk_save_objects(objs)
                db.commit()
                logger.info(f"Loaded {len(objs)} cached OpenCellID India cell records into database.")
    except Exception as e:
        logger.error(f"Error during data initialization: {e}", exc_info=True)
    finally:
        db.close()

    # Start live background telemetry stream
    logger.info("Starting TeleSense live streaming scheduler...")
    start_scheduler()

    yield

    # Clean shutdown
    logger.info("Shutting down TeleSense live streaming scheduler...")
    stop_scheduler()

# FastAPI App
app = FastAPI(
    title="TeleSense - AI Telecom Traffic & Network Planning API",
    description="Real-time cellular load forecasting, proactive overload alerts, and automated Capex planning recommendations.",
    version="1.0.0",
    lifespan=lifespan
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Register Routers
app.include_router(towers.router)
app.include_router(alerts.router)
app.include_router(recommendations.router)
app.include_router(simulation.router)
app.include_router(crowdsource.router)
app.include_router(citizen.router)
app.include_router(model_health.router)
app.include_router(incidents.router)
app.include_router(websocket.router)

@app.get("/api/docs/project-guide.pdf", tags=["System"])
def download_project_guide():
    """Serves the generated B.Tech Project Guide PDF for direct download."""
    pdf_path = PROJECT_ROOT / "docs" / "PROJECT_GUIDE.pdf"
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="Project guide PDF not found.")
    return FileResponse(
        path=str(pdf_path),
        media_type="application/pdf",
        filename="TeleSense_Project_Guide.pdf",
    )


@app.get("/health", tags=["System"])
@app.get("/api/health", tags=["System"])
def health_check():
    """System health check and status."""
    db = SessionLocal()
    try:
        count = db.query(Tower).count()
        return {
            "status": "healthy",
            "service": "TeleSense AI Engine",
            "active_towers": count,
            "stream_active": True
        }
    finally:
        db.close()


# Serve built React frontend in single-container production deployments (Railway / Render / Docker)
FRONTEND_DIST_DIR = Path(os.environ.get("FRONTEND_DIST_DIR", str(PROJECT_ROOT / "frontend" / "dist"))).resolve()
if (FRONTEND_DIST_DIR / "index.html").exists():
    assets_dir = FRONTEND_DIST_DIR / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="frontend-assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_spa(full_path: str):
        if full_path.startswith(("api/", "ws/", "docs", "redoc", "openapi.json")) or full_path in ("api", "ws", "health"):
            raise HTTPException(status_code=404, detail="Not Found")
        if full_path:
            candidate = (FRONTEND_DIST_DIR / full_path).resolve()
            if str(candidate).startswith(str(FRONTEND_DIST_DIR)) and candidate.is_file():
                return FileResponse(str(candidate))
        return FileResponse(str(FRONTEND_DIST_DIR / "index.html"))


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=False)
