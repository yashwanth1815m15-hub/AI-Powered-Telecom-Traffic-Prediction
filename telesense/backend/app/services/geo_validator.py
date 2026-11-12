"""
Real India Geographic Boundary Polygon Validator.
Uses geoBoundaries IND ADM1 36-State/UT GeoJSON polygons (CC0 1.0 Public Domain)
stored locally in backend/data/india_states.geojson.
"""

import json
import unicodedata
from pathlib import Path
from typing import Optional, List, Tuple, Dict, Any

GEOJSON_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "india_states.geojson"

_INDEX: Optional[List[Tuple[str, Tuple[float, float, float, float], Dict[str, Any]]]] = None


def normalize_name(s: str) -> str:
    """Strips diacritics/macrons and normalizes whitespace/case for reliable comparison."""
    if not s:
        return ""
    nfkd = unicodedata.normalize("NFKD", s)
    ascii_str = "".join(c for c in nfkd if not unicodedata.combining(c))
    return ascii_str.strip().lower()


STATE_ALIASES = {
    "delhi ncr": "delhi",
    "andaman & nicobar": "andaman and nicobar islands",
    "andaman and nicobar": "andaman and nicobar islands",
    "jammu & kashmir": "jammu and kashmir",
    "dadra & nagar haveli": "dadra and nagar haveli and daman and diu",
    "daman & diu": "dadra and nagar haveli and daman and diu",
    "orissa": "odisha",
    "uttaranchal": "uttarakhand",
    "pondicherry": "puducherry",
}


def canonical_state(s: str) -> str:
    n = normalize_name(s)
    return STATE_ALIASES.get(n, n)


def _bbox_of_geom(coords: Any, gtype: str) -> Tuple[float, float, float, float]:
    xs: List[float] = []
    ys: List[float] = []
    polys = [coords] if gtype == "Polygon" else coords
    for poly in polys:
        for pt in poly[0]:
            xs.append(pt[0])
            ys.append(pt[1])
    return (min(xs), min(ys), max(xs), max(ys))


def _load_index() -> List[Tuple[str, Tuple[float, float, float, float], Dict[str, Any]]]:
    global _INDEX
    if _INDEX is not None:
        return _INDEX
    if not GEOJSON_PATH.exists():
        raise FileNotFoundError(f"India boundary polygon file missing: {GEOJSON_PATH}")
    with open(GEOJSON_PATH, "r", encoding="utf-8") as f:
        gj = json.load(f)
    idx = []
    for feat in gj.get("features", []):
        props = feat.get("properties", {})
        name = props.get("shapeName", "")
        geom = feat["geometry"]
        bbox = _bbox_of_geom(geom["coordinates"], geom["type"])
        idx.append((name, bbox, geom))
    _INDEX = idx
    return _INDEX


def _point_in_ring(x: float, y: float, ring: List[List[float]]) -> bool:
    """Ray-casting algorithm (lon=x, lat=y)."""
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi + 1e-18) + xi):
            inside = not inside
        j = i
    return inside


def _point_in_geom(lat: float, lon: float, geom: Dict[str, Any]) -> bool:
    gtype = geom["type"]
    polys = [geom["coordinates"]] if gtype == "Polygon" else geom["coordinates"]
    for poly in polys:
        if _point_in_ring(lon, lat, poly[0]):
            if not any(_point_in_ring(lon, lat, hole) for hole in poly[1:]):
                return True
    return False


def get_india_state_for_point(lat: float, lon: float) -> Optional[str]:
    """Returns canonical-case Indian State/UT name if point lies inside India polygon, else None."""
    for name, (minx, miny, maxx, maxy), geom in _load_index():
        if minx <= lon <= maxx and miny <= lat <= maxy:
            if _point_in_geom(lat, lon, geom):
                # Strip macrons for clean display
                return "".join(
                    c for c in unicodedata.normalize("NFKD", name) if not unicodedata.combining(c)
                )
    return None


def is_inside_india_polygon(lat: float, lon: float) -> bool:
    """True strictly if coordinate lies within any Indian State/UT polygon."""
    return get_india_state_for_point(lat, lon) is not None


def validate_point_in_state(lat: float, lon: float, stated_state: str) -> Tuple[bool, Optional[str]]:
    """Checks if coordinate is inside India AND inside its stated state."""
    detected = get_india_state_for_point(lat, lon)
    if detected is None:
        return False, None
    if not stated_state or canonical_state(stated_state) == "india":
        return True, detected
    # Delhi NCR spans Delhi + Gurugram (Haryana) + Noida/Ghaziabad (Uttar Pradesh)
    if normalize_name(stated_state) == "delhi ncr":
        ok = canonical_state(detected) in {"delhi", "haryana", "uttar pradesh"}
        return ok, detected
    return canonical_state(detected) == canonical_state(stated_state), detected

