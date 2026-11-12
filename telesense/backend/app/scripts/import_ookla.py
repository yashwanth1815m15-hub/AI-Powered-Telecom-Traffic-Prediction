"""
Offline Ookla Open Data India Mobile Performance Tiles Importer.

Fetches the latest quarterly mobile performance parquet file anonymously from
s3://ookla-open-data (https://ookla-open-data.s3.us-west-2.amazonaws.com/),
filters strictly to tiles inside India's real boundary polygon
(backend/data/india_states.geojson), and stores aggregated + top India tiles
locally in backend/data/ookla_india_tiles.json.

Never calls S3 from the live web app.
Attribution: Speedtest by Ookla Global Fixed and Mobile Network Performance Maps
(CC BY-NC-SA 4.0 / Open Data License: https://github.com/teamookla/ookla-open-data).
"""

from __future__ import annotations

import json
import logging
import math
import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pyarrow.parquet as pq
import requests

from app.services.geo_validator import get_india_state_for_point

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("telesense.import_ookla")

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_PATH = REPO_ROOT / "backend" / "data" / "ookla_india_tiles.json"

OOKLA_S3_BASE = "https://ookla-open-data.s3.us-west-2.amazonaws.com"
OOKLA_PREFIX = "parquet/performance/type=mobile/"
OOKLA_LICENSE = "CC BY-NC-SA 4.0 (Ookla Open Data)"
OOKLA_ATTRIBUTION = "Real mobile speed (Ookla, quarterly) — Speedtest by Ookla Open Data"
OOKLA_SOURCE_URL = "https://github.com/teamookla/ookla-open-data"


def quadkey_to_bbox_center(quadkey: str) -> Tuple[float, float]:
    """Converts Bing Maps quadkey (zoom ~16) to (lat, lon) center coordinates."""
    tile_x = 0
    tile_y = 0
    level = len(quadkey)
    for i in range(level):
        bit = level - i
        mask = 1 << (bit - 1)
        digit = quadkey[i]
        if digit == "1":
            tile_x |= mask
        elif digit == "2":
            tile_y |= mask
        elif digit == "3":
            tile_x |= mask
            tile_y |= mask

    n = 2.0 ** level
    lon_left = (tile_x / n) * 360.0 - 180.0
    lon_right = ((tile_x + 1) / n) * 360.0 - 180.0
    lat_top = math.degrees(math.atan(math.sinh(math.pi * (1.0 - 2.0 * tile_y / n))))
    lat_bot = math.degrees(math.atan(math.sinh(math.pi * (1.0 - 2.0 * (tile_y + 1) / n))))
    return round((lat_top + lat_bot) / 2.0, 5), round((lon_left + lon_right) / 2.0, 5)


def discover_latest_ookla_mobile_key() -> Tuple[str, str]:
    """Queries public S3 ListObjectsV2 XML to find latest quarterly mobile parquet file."""
    resp = requests.get(
        f"{OOKLA_S3_BASE}/?list-type=2&prefix={OOKLA_PREFIX}&max-keys=500",
        timeout=25,
    )
    resp.raise_for_status()
    root = ET.fromstring(resp.text)
    ns = {"s3": "http://s3.amazonaws.com/doc/2006-03-01/"}
    keys = [
        k.text
        for k in root.findall(".//s3:Key", ns)
        if k.text and k.text.endswith("_performance_mobile_tiles.parquet")
    ]
    if not keys:
        raise RuntimeError("No Ookla mobile parquet keys found in public S3 bucket.")
    latest_key = sorted(keys)[-1]
    parts = latest_key.split("/")
    year = next((p.split("=")[1] for p in parts if p.startswith("year=")), "")
    quarter = next((p.split("=")[1] for p in parts if p.startswith("quarter=")), "")
    quarter_label = f"Q{quarter} {year}".strip()
    return latest_key, quarter_label


def filter_india_tiles_from_parquet(parquet_path: Path, max_detailed_tiles: int = 3500) -> Dict[str, Any]:
    """
    Reads Ookla parquet file by batches, filters to India's bounding box first,
    then validates exact points against geo_validator India state polygons.
    """
    pf = pq.ParquetFile(parquet_path)
    cols = [c for c in ["quadkey", "tile_x", "tile_y", "avg_d_kbps", "avg_u_kbps", "avg_lat_ms", "tests", "devices"] if c in pf.schema.names]

    india_rows: List[Dict[str, Any]] = []
    state_stats: Dict[str, Dict[str, Any]] = {}

    for batch in pf.iter_batches(batch_size=100_000, columns=cols):
        df = batch.to_pandas()
        if "tile_x" in df.columns and "tile_y" in df.columns:
            # Coarse India bbox pre-filter before quadkey decode
            df = df[(df["tile_y"] >= 6.5) & (df["tile_y"] <= 37.6) & (df["tile_x"] >= 68.0) & (df["tile_x"] <= 97.6)]
            if df.empty:
                continue
            lat_series = df["tile_y"].astype(float).round(5)
            lon_series = df["tile_x"].astype(float).round(5)
        else:
            # Decode quadkeys vectorized-style
            decoded = [quadkey_to_bbox_center(str(qk)) for qk in df["quadkey"]]
            lats = [p[0] for p in decoded]
            lons = [p[1] for p in decoded]
            df = df.assign(_lat=lats, _lon=lons)
            df = df[(df["_lat"] >= 6.5) & (df["_lat"] <= 37.6) & (df["_lon"] >= 68.0) & (df["_lon"] <= 97.6)]
            if df.empty:
                continue
            lat_series = df["_lat"]
            lon_series = df["_lon"]

        for idx, row in df.iterrows():
            lat = float(lat_series.loc[idx])
            lon = float(lon_series.loc[idx])
            state = get_india_state_for_point(lat, lon)
            if not state:
                continue
            dl_mbps = round(float(row["avg_d_kbps"]) / 1000.0, 2)
            ul_mbps = round(float(row["avg_u_kbps"]) / 1000.0, 2)
            lat_ms = int(round(float(row["avg_lat_ms"])))
            tests = int(row["tests"])
            devices = int(row["devices"])
            india_rows.append({
                "quadkey": str(row["quadkey"]),
                "lat": lat,
                "lon": lon,
                "state": state,
                "avg_dl_mbps": dl_mbps,
                "avg_ul_mbps": ul_mbps,
                "avg_latency_ms": lat_ms,
                "tests": tests,
                "devices": devices,
            })
            st = state_stats.setdefault(state, {"tiles": 0, "tests": 0, "devices": 0, "dl_sum": 0.0, "ul_sum": 0.0, "lat_sum": 0.0})
            st["tiles"] += 1
            st["tests"] += tests
            st["devices"] += devices
            st["dl_sum"] += dl_mbps * max(1, tests)
            st["ul_sum"] += ul_mbps * max(1, tests)
            st["lat_sum"] += lat_ms * max(1, tests)

    # Sort detailed tiles by sample density (tests desc) and keep representative pan-India grid coverage
    # Also ensure every covered state keeps top tiles so rural & urban states are both visible on the map
    by_state: Dict[str, List[Dict[str, Any]]] = {}
    for r in india_rows:
        by_state.setdefault(r["state"], []).append(r)

    per_state_cap = max(25, max_detailed_tiles // max(1, len(by_state)))
    sampled_tiles: List[Dict[str, Any]] = []
    for st_name, st_rows in by_state.items():
        st_rows.sort(key=lambda x: x["tests"], reverse=True)
        sampled_tiles.extend(st_rows[:per_state_cap])
    sampled_tiles.sort(key=lambda x: x["tests"], reverse=True)
    sampled_tiles = sampled_tiles[:max_detailed_tiles]

    state_summary = {}
    for st_name, st in sorted(state_stats.items()):
        w = max(1, st["tests"])
        state_summary[st_name] = {
            "tile_count": st["tiles"],
            "total_tests": st["tests"],
            "total_devices": st["devices"],
            "weighted_avg_dl_mbps": round(st["dl_sum"] / w, 2),
            "weighted_avg_ul_mbps": round(st["ul_sum"] / w, 2),
            "weighted_avg_latency_ms": round(st["lat_sum"] / w, 1),
        }

    total_tests = sum(s["tests"] for s in state_stats.values())
    india_avg_dl = round(sum(s["dl_sum"] for s in state_stats.values()) / max(1, total_tests), 2)
    india_avg_ul = round(sum(s["ul_sum"] for s in state_stats.values()) / max(1, total_tests), 2)
    india_avg_lat = round(sum(s["lat_sum"] for s in state_stats.values()) / max(1, total_tests), 1)

    return {
        "total_india_tiles": len(india_rows),
        "displayed_tile_count": len(sampled_tiles),
        "states_covered": len(state_summary),
        "total_india_tests": total_tests,
        "india_weighted_avg_dl_mbps": india_avg_dl,
        "india_weighted_avg_ul_mbps": india_avg_ul,
        "india_weighted_avg_latency_ms": india_avg_lat,
        "state_summary": state_summary,
        "tiles": sampled_tiles,
    }


def run_ookla_import(output_path: Path = DEFAULT_OUTPUT_PATH, max_detailed_tiles: int = 2500) -> Dict[str, Any]:
    """Downloads latest Ookla quarterly mobile parquet, filters strictly to India, and persists JSON."""
    key, quarter_label = discover_latest_ookla_mobile_key()
    url = f"{OOKLA_S3_BASE}/{key}"
    logger.info("Downloading Ookla mobile tiles (%s): %s", quarter_label, url)

    with tempfile.NamedTemporaryFile(suffix=".parquet", delete=True) as tmp:
        with requests.get(url, stream=True, timeout=120) as resp:
            resp.raise_for_status()
            for chunk in resp.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    tmp.write(chunk)
        tmp.flush()

        extracted = filter_india_tiles_from_parquet(Path(tmp.name), max_detailed_tiles=max_detailed_tiles)

    fetched_at = datetime.now(timezone.utc).isoformat()
    result = {
        "source_label": OOKLA_ATTRIBUTION,
        "attribution": f"Speedtest by Ookla Global Mobile Network Performance Map ({quarter_label})",
        "license": OOKLA_LICENSE,
        "source_url": OOKLA_SOURCE_URL,
        "s3_key": key,
        "quarter": quarter_label,
        "fetched_at": fetched_at,
        **extracted,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    logger.info(
        "Saved %d total India Ookla tiles (%d sampled for map) across %d states/UTs.",
        result["total_india_tiles"],
        result["displayed_tile_count"],
        result["states_covered"],
    )
    return result


if __name__ == "__main__":
    summary = run_ookla_import()
    print(json.dumps({k: v for k, v in summary.items() if k != "tiles" and k != "state_summary"}, indent=2))

