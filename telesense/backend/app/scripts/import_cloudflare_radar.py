"""
Offline Cloudflare Radar India Hourly Traffic Ingestion Script.

Never runs inside the live FastAPI request path. Reads CLOUDFLARE_API_TOKEN strictly
from backend/.env (never prints or logs tokens). Fetches hourly HTTP / NetFlows
series for India (IN), top Indian states, and major Indian ISP/mobile ASNs,
persists locally with fetched_at timestamp, and exits cleanly with status 2 if
CLOUDFLARE_API_TOKEN is missing.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("telesense.import_cloudflare_radar")

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
BACKEND_ENV_PATH = REPO_ROOT / "backend" / ".env"
DEFAULT_OUTPUT_PATH = REPO_ROOT / "backend" / "data" / "cloudflare_radar_india.json"

RADAR_HTTP_TIMESERIES_URL = "https://api.cloudflare.com/client/v4/radar/http/timeseries"
RADAR_NETFLOWS_TIMESERIES_URL = "https://api.cloudflare.com/client/v4/radar/netflows/timeseries"
RADAR_TOP_ASES_URL = "https://api.cloudflare.com/client/v4/radar/http/top/ases"
RADAR_ASN_ENTITY_URL = "https://api.cloudflare.com/client/v4/radar/entities/asns/{asn}"

OPERATOR_BROADBAND_NOTE = (
    "network-level web traffic, may include fixed broadband"
)

# Scope: India country (alpha-2) + 7 major Indian states (Cloudflare ADM1 geoIds); operator ASNs are selected dynamically from Radar top/ases.
INDIA_GEO_TARGETS: List[Dict[str, Any]] = [
    {"series_id": "IN", "label": "India (All Traffic)", "kind": "country", "location": "IN"},
    {"series_id": "IN-MH", "label": "Maharashtra", "kind": "state", "geoId": "1264418"},
    {"series_id": "IN-DL", "label": "Delhi NCT", "kind": "state", "geoId": "1273293"},
    {"series_id": "IN-KA", "label": "Karnataka", "kind": "state", "geoId": "1267701"},
    {"series_id": "IN-TN", "label": "Tamil Nadu", "kind": "state", "geoId": "1255053"},
    {"series_id": "IN-TG", "label": "Telangana", "kind": "state", "geoId": "1254788"},
    {"series_id": "IN-UP", "label": "Uttar Pradesh", "kind": "state", "geoId": "1253626"},
    {"series_id": "IN-WB", "label": "West Bengal", "kind": "state", "geoId": "1252881"},
]

# Top India operator ASNs previously resolved from Radar /http/top/ases (used only when building fallback target maps without live API)
DEFAULT_TOP_INDIA_ASNS: List[Dict[str, Any]] = [
    {"series_id": "ASN-55836", "label": "Reliance Jio Infocomm Limited (AS55836)", "kind": "operator_asn", "asn": 55836, "as_name": "Reliance Jio Infocomm Limited", "as_aka": "RELIANCEJIO-IN"},
    {"series_id": "ASN-45609", "label": "Bharti Airtel Ltd. AS for GPRS Service (AS45609)", "kind": "operator_asn", "asn": 45609, "as_name": "Bharti Airtel Ltd. AS for GPRS Service", "as_aka": "BHARTI-MOBILITY-AS-AP"},
    {"series_id": "ASN-24560", "label": "Bharti Airtel Ltd., Telemedia Services (AS24560)", "kind": "operator_asn", "asn": 24560, "as_name": "Bharti Airtel Ltd., Telemedia Services", "as_aka": "AIRTELBROADBAND-AS-AP"},
    {"series_id": "ASN-38266", "label": "Vodafone Idea Ltd (AS38266)", "kind": "operator_asn", "asn": 38266, "as_name": "Vodafone Idea Ltd", "as_aka": "VIL-AS-AP"},
    {"series_id": "ASN-45271", "label": "Vodafone Idea Ltd (AS45271)", "kind": "operator_asn", "asn": 45271, "as_name": "Vodafone Idea Ltd", "as_aka": "ICLNET-AS-AP"},
    {"series_id": "ASN-9829", "label": "National Internet Backbone (AS9829)", "kind": "operator_asn", "asn": 9829, "as_name": "National Internet Backbone", "as_aka": "BSNL-NIB"},
]
INDIA_TARGETS: List[Dict[str, Any]] = [*INDIA_GEO_TARGETS, *DEFAULT_TOP_INDIA_ASNS]


def _infer_as_type(as_name: str, as_aka: str, country: str = "IN") -> str:
    """Infers network type from AS name/handle keywords (Radar Entities API omits an AS type field). Never claims mobile-only."""
    combined = f"{as_name} {as_aka}".upper()
    if country != "IN":
        return "Cloud / Content Provider (Non-IN, inferred from AS name)"
    if "GPRS" in combined or "MOBILITY" in combined:
        return "Mobile / GPRS & Operator Network — may include fixed (inferred from AS name)"
    if "TELEMEDIA" in combined or "AIRTELBROADBAND" in combined:
        return "Fixed Broadband & Access ISP (inferred from AS name)"
    if "BACKBONE" in combined or "NIB" in combined:
        return "National Backbone & Multi-Access ISP (inferred from AS name)"
    if any(k in combined for k in ("JIO", "VIL", "VODAFONE", "IDEA", "ICLNET")):
        return "Mobile & Fixed Telecom ISP (inferred from AS name)"
    return "Telecom / Multi-Service ISP (inferred from AS name)"


def fetch_asn_entity_metadata(token: str, asn: int, client_as_name: Optional[str] = None) -> Dict[str, Any]:
    """Fetches canonical AS name, country, handle & network type (or infers from AS name if API omits type)."""
    headers = {"Authorization": f"Bearer {token}", "User-Agent": "TeleSense-NOC/1.0"}
    resp = requests.get(RADAR_ASN_ENTITY_URL.format(asn=asn), headers=headers, timeout=20)
    resp.raise_for_status()
    asn_obj = (resp.json().get("result") or {}).get("asn") or {}
    handle = str(asn_obj.get("name") or f"AS{asn}").strip()
    aka = str(client_as_name or asn_obj.get("aka") or asn_obj.get("orgName") or "").strip().replace("\\'", "'")
    country = str(asn_obj.get("country") or "").strip().upper()
    as_name = aka if aka and aka != handle else handle
    api_type = str(asn_obj.get("type") or asn_obj.get("orgType") or "").strip()
    as_type = api_type if api_type else _infer_as_type(as_name, handle, country=country)
    label = f"{as_name} — {handle} (AS{asn})" if handle and handle != as_name else f"{as_name} (AS{asn})"
    return {
        "asn": asn,
        "as_name": as_name,
        "as_aka": handle,
        "as_country": country,
        "as_type": as_type,
        "label": label,
    }


def discover_top_india_asns(
    token: str,
    top_limit: int = 15,
    max_indian_networks: int = 6,
    skipped_out: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """
    Queries Cloudflare Radar top India HTTP ASes by traffic share, filters to India-registered ASNs
    (country == 'IN', excluding US/global cloud hosts), and returns the top ranked operator networks.
    """
    headers = {"Authorization": f"Bearer {token}", "User-Agent": "TeleSense-NOC/1.0"}
    resp = requests.get(
        RADAR_TOP_ASES_URL,
        params={"location": "IN", "dateRange": "28d", "limit": top_limit, "format": "json"},
        headers=headers,
        timeout=25,
    )
    if resp.status_code in (401, 403):
        raise PermissionError(f"Cloudflare Radar authentication rejected (HTTP {resp.status_code}).")
    resp.raise_for_status()
    top_rows = (resp.json().get("result") or {}).get("top_0") or []
    selected: List[Dict[str, Any]] = []
    for rank_idx, row in enumerate(top_rows, start=1):
        asn = int(row["clientASN"])
        client_as_name = str(row.get("clientASName") or f"AS{asn}").strip()
        share_pct = round(float(row.get("value") or 0.0), 2)
        meta = fetch_asn_entity_metadata(token, asn, client_as_name=client_as_name)
        if meta.get("as_country") != "IN":
            if skipped_out is not None:
                skipped_out.append({
                    "radar_rank_india": rank_idx,
                    "asn": asn,
                    "as_name": meta.get("as_name"),
                    "as_aka": meta.get("as_aka"),
                    "as_country": meta.get("as_country"),
                    "as_type": meta.get("as_type"),
                    "traffic_share_pct": share_pct,
                    "reason": f"Registered in {meta.get('as_country') or 'non-IN'} (not country=='IN' telecom operator)",
                })
            continue
        selected.append({
            "series_id": f"ASN-{asn}",
            "kind": "operator_asn",
            "asn": asn,
            "radar_rank_india": rank_idx,
            "traffic_share_pct": share_pct,
            "network_scope_note": OPERATOR_BROADBAND_NOTE,
            **meta,
        })
        if len(selected) >= max_indian_networks:
            break
    return selected


def align_series_to_common_window(series_list: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Trims all series to their exact intersecting hourly timestamps and re-normalizes each to [0, 1]."""
    if not series_list:
        return series_list, []
    ts_sets = [{str(p["timestamp"]) for p in (s.get("points") or [])} for s in series_list if s.get("points")]
    if not ts_sets:
        return series_list, []
    common_ts = sorted(set.intersection(*ts_sets))
    common_set = set(common_ts)
    for s in series_list:
        pts_map = {str(p["timestamp"]): float(p["value"]) for p in (s.get("points") or []) if str(p["timestamp"]) in common_set}
        max_val = max((pts_map[t] for t in common_ts), default=1.0) or 1.0
        s["points"] = [
            {"timestamp": t, "value": round(float(pts_map[t] / max_val), 6)}
            for t in common_ts
        ]
        s["history_hours"] = len(common_ts)
        s["start_timestamp"] = common_ts[0] if common_ts else None
        s["end_timestamp"] = common_ts[-1] if common_ts else None
    return series_list, common_ts


def load_cloudflare_token(env_path: Path = BACKEND_ENV_PATH) -> Optional[str]:
    """Reads CLOUDFLARE_API_TOKEN from environment or backend/.env without logging it."""
    env_val = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()
    if env_val:
        return env_val
    if env_path.exists():
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            if k.strip() == "CLOUDFLARE_API_TOKEN":
                cleaned = v.strip().strip('"').strip("'")
                if cleaned:
                    return cleaned
    return None


def _parse_radar_payload(payload: Dict[str, Any]) -> Tuple[List[str], List[float]]:
    """Extracts parallel ISO timestamps and float values from Cloudflare Radar v4 JSON."""
    result = payload.get("result") or {}
    serie = result.get("serie_0") or {}
    timestamps = serie.get("timestamps") or []
    values = serie.get("values") or []
    parsed_ts: List[str] = []
    parsed_vals: List[float] = []
    for ts, val in zip(timestamps, values):
        try:
            parsed_vals.append(float(val))
            parsed_ts.append(str(ts))
        except (TypeError, ValueError):
            continue
    return parsed_ts, parsed_vals


def _request_radar_chunk(
    token: str,
    target: Dict[str, Any],
    date_start: Optional[datetime] = None,
    date_end: Optional[datetime] = None,
    date_range: str = "28d",
    agg_interval: str = "1h",
) -> Tuple[Optional[str], List[str], List[float]]:
    """Requests one <=28d hourly chunk from Radar HTTP or NetFlows endpoints with gentle backoff."""
    headers = {"Authorization": f"Bearer {token}", "User-Agent": "TeleSense-NOC/1.0"}
    params: Dict[str, Any] = {
        "aggInterval": agg_interval,
        "format": "json",
    }
    if date_start is not None and date_end is not None:
        params["dateStart"] = date_start.strftime("%Y-%m-%dT%H:%M:%SZ")
        params["dateEnd"] = date_end.strftime("%Y-%m-%dT%H:%M:%SZ")
    else:
        params["dateRange"] = date_range
    if "location" in target:
        params["location"] = target["location"]
    if "geoId" in target:
        params["geoId"] = target["geoId"]
    if "asn" in target:
        params["asn"] = target["asn"]

    for endpoint_name, url in [("http", RADAR_HTTP_TIMESERIES_URL), ("netflows", RADAR_NETFLOWS_TIMESERIES_URL)]:
        for attempt in range(3):
            resp = requests.get(url, headers=headers, params=params, timeout=25)
            if resp.status_code in (401, 403):
                raise PermissionError(f"Cloudflare Radar authentication rejected (HTTP {resp.status_code}).")
            if resp.status_code == 429:
                retry_s = min(int(resp.headers.get("Retry-After", "2") or 2), 15)
                logger.warning("Rate limited on %s, backing off %ds", target["series_id"], retry_s)
                time.sleep(retry_s)
                continue
            if not resp.ok:
                break
            data = resp.json()
            if not data.get("success"):
                break
            ts, vals = _parse_radar_payload(data)
            if ts and vals:
                return endpoint_name, ts, vals
            break
    return None, [], []


def fetch_radar_series(
    token: str,
    target: Dict[str, Any],
    date_range: str = "28d",
    agg_interval: str = "1h",
    num_chunks: int = 4,
    sleep_sec: float = 0.35,
) -> Optional[Dict[str, Any]]:
    """
    Fetches as much hourly Cloudflare Radar traffic history as supported by API window rules.
    Stitches overlapping 28-day chunks cleanly using overlap median ratios so normalization
    remains globally continuous across chunk boundaries.
    """
    endpoint_used, ts0, vals0 = _request_radar_chunk(token, target, date_range=date_range, agg_interval=agg_interval)
    if not ts0:
        return None

    stitched: Dict[str, float] = {t: v for t, v in zip(ts0, vals0)}
    earliest_dt = datetime.fromisoformat(ts0[0].replace("Z", "+00:00"))

    for _ in range(max(0, num_chunks - 1)):
        time.sleep(sleep_sec)
        # 48h overlap ensures exact linear scaling alignment between 28d normalized windows
        chunk_end = earliest_dt + timedelta(hours=48)
        chunk_start = chunk_end - timedelta(days=28)
        ep, t_chunk, v_chunk = _request_radar_chunk(
            token,
            target,
            date_start=chunk_start,
            date_end=chunk_end,
            agg_interval=agg_interval,
        )
        if not t_chunk:
            break
        overlap_ratios = [
            stitched[t] / v
            for t, v in zip(t_chunk, v_chunk)
            if t in stitched and v > 0.05 and stitched[t] > 0.05
        ]
        if overlap_ratios:
            overlap_ratios.sort()
            scale = overlap_ratios[len(overlap_ratios) // 2]
        else:
            scale = 1.0

        added = 0
        for t, v in zip(t_chunk, v_chunk):
            if t not in stitched:
                stitched[t] = float(v * scale)
                added += 1
        new_earliest = datetime.fromisoformat(t_chunk[0].replace("Z", "+00:00"))
        if added == 0 or new_earliest >= earliest_dt:
            break
        earliest_dt = new_earliest
        endpoint_used = endpoint_used or ep

    ordered_ts = sorted(stitched.keys())
    max_val = max((stitched[t] for t in ordered_ts), default=1.0) or 1.0
    points = [
        {"timestamp": t, "value": round(float(stitched[t] / max_val), 6)}
        for t in ordered_ts
    ]
    return {
        "series_id": target["series_id"],
        "label": target["label"],
        "kind": target["kind"],
        "endpoint": endpoint_used,
        "resolution": agg_interval,
        "history_hours": len(points),
        "start_timestamp": points[0]["timestamp"] if points else None,
        "end_timestamp": points[-1]["timestamp"] if points else None,
        "unit_label": "Relative web traffic (Cloudflare Radar), not tower load",
        "operator_broadband_note": OPERATOR_BROADBAND_NOTE,
        "asn_selection_method": "Selected programmatically from Cloudflare Radar /radar/http/top/ases (location=IN, country=IN operators ranked by traffic share).",
        "points": points,
    }


def run_cloudflare_radar_import(
    output_path: Path = DEFAULT_OUTPUT_PATH,
    date_range: str = "28d",
    env_path: Path = BACKEND_ENV_PATH,
    num_chunks: int = 4,
    sleep_sec: float = 0.35,
) -> Dict[str, Any]:
    """Ingests all configured India series and writes a local JSON artifact."""
    token = load_cloudflare_token(env_path=env_path)
    if not token:
        return {
            "status": "SETUP_REQUIRED",
            "message": "CLOUDFLARE_API_TOKEN missing in backend/.env. No fake traffic series written.",
            "series_count": 0,
        }

    fetched_at = datetime.now(timezone.utc).isoformat()
    skipped_top_asns: List[Dict[str, Any]] = []
    asn_targets = discover_top_india_asns(token, skipped_out=skipped_top_asns)
    targets = [*INDIA_GEO_TARGETS, *asn_targets]
    collected: List[Dict[str, Any]] = []
    for idx, target in enumerate(targets):
        if idx > 0:
            time.sleep(sleep_sec)
        try:
            item = fetch_radar_series(
                token,
                target,
                date_range=date_range,
                agg_interval="1h",
                num_chunks=num_chunks,
                sleep_sec=sleep_sec,
            )
            if item:
                item["fetched_at"] = fetched_at
                for k in ("asn", "as_name", "as_aka", "as_country", "as_type", "radar_rank_india", "traffic_share_pct", "network_scope_note"):
                    if k in target:
                        item[k] = target[k]
                collected.append(item)
                logger.info(
                    "Fetched %s (%d hourly pts: %s -> %s)",
                    target["series_id"],
                    len(item["points"]),
                    item.get("start_timestamp"),
                    item.get("end_timestamp"),
                )
        except PermissionError as exc:
            logger.error("Auth error: %s", exc)
            return {"status": "AUTH_ERROR", "message": str(exc), "series_count": 0}
        except Exception as exc:
            logger.warning("Failed series %s: %s", target["series_id"], exc)

    if not collected:
        return {
            "status": "NO_DATA",
            "message": "Cloudflare Radar returned zero series.",
            "series_count": 0,
        }

    collected, common_ts = align_series_to_common_window(collected)
    common_hours = len(common_ts)
    common_start = common_ts[0] if common_ts else None
    common_end = common_ts[-1] if common_ts else None

    payload = {
        "source": "Cloudflare Radar API v4",
        "source_url": "https://developers.cloudflare.com/radar/",
        "unit_label": "Relative web traffic (Cloudflare Radar), not tower load",
        "operator_broadband_note": OPERATOR_BROADBAND_NOTE,
        "asn_selection_method": "Selected programmatically from Cloudflare Radar /radar/http/top/ases (location=IN, country=IN operators ranked by traffic share).",
        "skipped_top_asns": skipped_top_asns,
        "fetched_at": fetched_at,
        "date_range": f"{num_chunks}x{date_range}_stitched_common_window",
        "agg_interval": "1h",
        "history_hours": common_hours,
        "start_timestamp": common_start,
        "end_timestamp": common_end,
        "series": collected,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return {
        "status": "OK",
        "output_path": str(output_path),
        "fetched_at": fetched_at,
        "agg_interval": "1h",
        "history_hours": common_hours,
        "series_count": len(collected),
        "total_points": sum(len(s["points"]) for s in collected),
        "skipped_top_asns": skipped_top_asns,
    }


def refresh_cached_asn_metadata(cache_path: Path = DEFAULT_OUTPUT_PATH, env_path: Path = BACKEND_ENV_PATH) -> Dict[str, Any]:
    """Updates cached ASN labels/names/types and aligns all series to identical common hourly timestamps."""
    token = load_cloudflare_token(env_path)
    if not token or not cache_path.exists():
        return {"status": "SKIPPED"}
    payload = json.loads(cache_path.read_text(encoding="utf-8"))
    payload["operator_broadband_note"] = OPERATOR_BROADBAND_NOTE
    skipped_top: List[Dict[str, Any]] = []
    discovered = {t["series_id"]: t for t in discover_top_india_asns(token, skipped_out=skipped_top)}
    payload["skipped_top_asns"] = skipped_top
    updated = 0
    for s in payload.get("series", []):
        sid = str(s.get("series_id") or "")
        if sid.startswith("ASN-"):
            if sid in discovered:
                for k in ("asn", "as_name", "as_aka", "as_country", "as_type", "radar_rank_india", "traffic_share_pct", "network_scope_note", "label"):
                    if k in discovered[sid]:
                        s[k] = discovered[sid][k]
            else:
                asn = int(sid.split("-", 1)[1])
                s.update(fetch_asn_entity_metadata(token, asn))
            updated += 1
    aligned, common_ts = align_series_to_common_window(payload.get("series", []))
    payload["series"] = aligned
    payload["history_hours"] = len(common_ts)
    payload["start_timestamp"] = common_ts[0] if common_ts else None
    payload["end_timestamp"] = common_ts[-1] if common_ts else None
    cache_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return {"status": "OK", "updated_asn_series": updated, "common_hours": len(common_ts), "skipped_top_asns": skipped_top}


def main() -> int:
    if "--refresh-asn-names" in sys.argv:
        res = refresh_cached_asn_metadata()
    else:
        res = run_cloudflare_radar_import()
    print(json.dumps(res, indent=2))
    return 0 if res["status"] == "OK" else 2


if __name__ == "__main__":
    sys.exit(main())

