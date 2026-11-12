"""
India Cloudflare Radar Hourly Traffic Chronological Training & Evaluation Pipeline.

Reads offline-cached India hourly traffic series from
backend/data/cloudflare_radar_india.json (never calls external APIs at runtime),
enforces a strict chronological train / validation / test split, evaluates SARIMA,
PyTorch LSTM, PyTorch GRU, and Seasonal-Naive baseline (t - 168h, same hour last week),
selects models STRICTLY by VALIDATION MAE (never test MAE), computes per-series &
last-7-day Diwali/festival error breakdowns plus a festival feature ablation,
and updates artifacts/metrics.json strictly from real observed metrics.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT_INIT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT_INIT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT_INIT))
if str(REPO_ROOT_INIT / "backend") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT_INIT / "backend"))

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader

from ml.models.neural_sequence import GRUTrafficPredictor, LSTMTrafficPredictor
from ml.models.sarima_baseline import SeasonalBaselineModel
from ml.training.dataset import TrafficSlidingWindowDataset, extract_features

logger = logging.getLogger("telesense.india_radar")

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RADAR_CACHE_PATH = REPO_ROOT / "backend" / "data" / "cloudflare_radar_india.json"
DEFAULT_METRICS_PATH = REPO_ROOT / "artifacts" / "metrics.json"
DEFAULT_BACKEND_ENV_PATH = REPO_ROOT / "backend" / ".env"

RADAR_UNIT_LABEL = "Relative web traffic (Cloudflare Radar), not tower load"
RADAR_SCALE_LABEL = "Normalised [0, 100] relative web traffic index per series (100 = peak hour in fetched window)"
RADAR_VALIDATED_STATUS = "Validated on real India traffic series (Cloudflare Radar)"
OPERATOR_BROADBAND_NOTE = "network-level web traffic, may include fixed broadband"
FESTIVAL_CALENDAR_NOTE = "Festival dates per Drik Panchang; regional calendars can differ by a day."
FESTIVAL_SOURCE_NAME = "Drik Panchang (Indian Festival Calendar 2026)"
FESTIVAL_SOURCE_URL = "https://www.drikpanchang.com/calendars/indian/indiancalendar.html?year=2026"
RADAR_COVERAGE_NOTE = (
    "Pooled global LSTM & GRU models (plus per-series SARIMA & Seasonal-Naive baselines) trained across all "
    "related Cloudflare Radar series (states are subsets of India; ASNs selected by top India Radar traffic rank) — each series selects its serving model by validation MAE."
)
CROSS_DOMAIN_NOTE = (
    "Radar models validate the method on real web traffic; tower forecasts on the NOC map come from the simulator."
)
RADAR_SETUP_NOTE = (
    "CLOUDFLARE_API_TOKEN is not configured in backend/.env and no cached Cloudflare Radar "
    "India file exists yet. Add CLOUDFLARE_API_TOKEN to backend/.env, run "
    "`python -m backend.app.scripts.import_cloudflare_radar`, and then run "
    "`python -m ml.training.india_radar_pipeline` to evaluate SARIMA, LSTM, GRU, and "
    "Seasonal-Naive chronologically on real India hourly web traffic series."
)

# 2026 Indian festival calendar dates in IST (+05:30) per Drik Panchang; regional calendars can differ by a day.
INDIA_2026_FESTIVALS: Dict[str, str] = {
    "2026-08-15": "Independence Day",
    "2026-08-28": "Raksha Bandhan",
    "2026-09-04": "Janmashtami",
    "2026-09-14": "Ganesh Chaturthi",
    "2026-10-02": "Gandhi Jayanti",
    "2026-10-21": "Dussehra (Vijayadashami)",
    "2026-11-06": "Dhanteras",
    "2026-11-07": "Naraka Chaturdashi",
    "2026-11-08": "Diwali (Lakshmi Puja)",
    "2026-11-09": "Govardhan Puja",
    "2026-11-11": "Bhai Dooj",
}
DIWALI_WEEK_DATES = {
    "2026-11-06", "2026-11-07", "2026-11-08", "2026-11-09", "2026-11-10", "2026-11-11"
}

INDIA_SERIES_LABELS: Dict[str, Tuple[str, str]] = {
    "IN": ("India (All Traffic)", "country"),
    "IN-MH": ("Maharashtra", "state"),
    "IN-DL": ("Delhi NCT", "state"),
    "IN-KA": ("Karnataka", "state"),
    "IN-TN": ("Tamil Nadu", "state"),
    "IN-TG": ("Telangana", "state"),
    "IN-UP": ("Uttar Pradesh", "state"),
    "IN-WB": ("West Bengal", "state"),
    "ASN-55836": ("Reliance Jio Infocomm Limited — RELIANCEJIO-IN (AS55836)", "operator_asn"),
    "ASN-45609": ("Bharti Airtel Ltd. AS for GPRS Service — BHARTI-MOBILITY-AS-AP (AS45609)", "operator_asn"),
    "ASN-24560": ("Bharti Airtel Ltd., Telemedia Services — AIRTELBROADBAND-AS-AP (AS24560)", "operator_asn"),
    "ASN-38266": ("Vodafone Idea Ltd — VIL-AS-AP (AS38266)", "operator_asn"),
    "ASN-45271": ("Vodafone Idea Ltd — ICLNET-AS-AP (AS45271)", "operator_asn"),
    "ASN-9829": ("National Internet Backbone — BSNL-NIB (AS9829)", "operator_asn"),
}


def select_best_model_by_validation(metrics_by_model: Dict[str, Dict[str, Any]]) -> str:
    """
    Selects the winning model STRICTLY by lowest `val_mae_overall` (never test MAE).
    Raises ValueError if any candidate lacks `val_mae_overall` so test leakage cannot slip in.
    """
    if not metrics_by_model:
        raise ValueError("Cannot select model from empty metrics dictionary")
    for name, m in metrics_by_model.items():
        if m.get("val_mae_overall") is None:
            raise ValueError(f"Model '{name}' missing val_mae_overall; refusing to fall back to test metrics")
    return min(metrics_by_model.keys(), key=lambda k: float(metrics_by_model[k]["val_mae_overall"]))


def load_cached_radar_series(cache_path: Path = DEFAULT_RADAR_CACHE_PATH) -> Optional[pd.DataFrame]:
    """Loads stored Cloudflare Radar JSON into a normalized DataFrame [series_id, label, kind, timestamp, load_pct]."""
    if not cache_path.exists():
        return None
    raw = json.loads(cache_path.read_text(encoding="utf-8"))
    series_list = raw.get("series") or []
    rows: List[Dict[str, Any]] = []
    for s in series_list:
        sid = str(s.get("series_id", "IN"))
        default_label, default_kind = INDIA_SERIES_LABELS.get(sid, (sid, "unknown"))
        s_label = str(s.get("label") or default_label)
        s_kind = str(s.get("kind") or default_kind)
        for pt in s.get("points") or []:
            ts = pd.to_datetime(pt.get("timestamp"), utc=True, errors="coerce")
            val = pt.get("value")
            if pd.isna(ts) or val is None:
                continue
            rows.append({
                "series_id": sid,
                "label": s_label,
                "kind": s_kind,
                "timestamp": ts.tz_localize(None),
                "load_pct": float(np.clip(float(val) * 100.0 if float(val) <= 1.5 else float(val), 0.0, 100.0)),
                "fetched_at": s.get("fetched_at") or raw.get("fetched_at"),
            })
    if not rows:
        return None
    df = pd.DataFrame(rows).sort_values(["series_id", "timestamp"]).reset_index(drop=True)
    # Enforce exact identical hourly timestamp window across all loaded series
    ts_sets = [set(g["timestamp"]) for _, g in df.groupby("series_id")]
    if ts_sets:
        common_ts = set.intersection(*ts_sets)
        df = df[df["timestamp"].isin(common_ts)].sort_values(["series_id", "timestamp"]).reset_index(drop=True)
    return df


def split_radar_chronological(
    hourly_df: pd.DataFrame,
    train_frac: float = 0.70,
    val_frac: float = 0.15,
) -> Dict[str, Any]:
    """
    Strictly chronological split across all cached India hourly series.
    Zero shuffling / zero random k-fold leakage.
    """
    unique_ts = np.array(sorted(hourly_df["timestamp"].unique()))
    if len(unique_ts) < 240:
        raise ValueError(f"Need at least 240 hourly timestamps for chronological split + 168h seasonal naive; got {len(unique_ts)}")

    n = len(unique_ts)
    train_end_idx = max(1, int(n * train_frac))
    val_end_idx = max(train_end_idx + 1, int(n * (train_frac + val_frac)))

    train_cut = pd.Timestamp(unique_ts[train_end_idx - 1])
    val_cut = pd.Timestamp(unique_ts[val_end_idx - 1])

    train_df = hourly_df[hourly_df["timestamp"] <= train_cut].copy()
    val_df = hourly_df[(hourly_df["timestamp"] > train_cut) & (hourly_df["timestamp"] <= val_cut)].copy()
    test_df = hourly_df[hourly_df["timestamp"] > val_cut].copy()

    if train_df.empty or val_df.empty or test_df.empty:
        raise ValueError("One of train/validation/test chronological splits is empty.")

    return {
        "train": train_df,
        "validation": val_df,
        "test": test_df,
        "dates": {
            "train_start": train_df["timestamp"].min().isoformat(),
            "train_end": train_df["timestamp"].max().isoformat(),
            "validation_start": val_df["timestamp"].min().isoformat(),
            "validation_end": val_df["timestamp"].max().isoformat(),
            "test_start": test_df["timestamp"].min().isoformat(),
            "test_end": test_df["timestamp"].max().isoformat(),
        },
    }


def _build_feature_matrix(df: pd.DataFrame, include_festival: bool = False) -> np.ndarray:
    """Builds numeric features strictly from past/present timestamps (7 base, or 9 with Indian festival flags)."""
    df_feat = extract_features(df.rename(columns={"series_id": "tower_id"}))
    load_scaled = (df_feat["load_pct"].astype(float) / 100.0).to_numpy(dtype=np.float32)
    roll24 = (df_feat["load_pct"].rolling(24, min_periods=1).mean() / 100.0).to_numpy(dtype=np.float32)
    cols = [
        load_scaled,
        df_feat["hour_sin"].to_numpy(dtype=np.float32),
        df_feat["hour_cos"].to_numpy(dtype=np.float32),
        df_feat["dow_sin"].to_numpy(dtype=np.float32),
        df_feat["dow_cos"].to_numpy(dtype=np.float32),
        df_feat["is_weekend"].to_numpy(dtype=np.float32),
        roll24,
    ]
    if include_festival:
        ist_ts = pd.to_datetime(df_feat["timestamp"]) + pd.Timedelta(hours=5, minutes=30)
        ist_dates = ist_ts.dt.strftime("%Y-%m-%d")
        is_fest = ist_dates.isin(INDIA_2026_FESTIVALS.keys()).astype(np.float32).to_numpy()
        is_diwali = ist_dates.isin(DIWALI_WEEK_DATES).astype(np.float32).to_numpy()
        cols.extend([is_fest, is_diwali])
    return np.column_stack(cols).astype(np.float32)


def _build_windows_for_series(
    full_series: pd.DataFrame,
    target_start: pd.Timestamp,
    seq_len: int = 48,
    horizon: int = 24,
    include_festival: bool = False,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Builds sliding windows where prediction targets fall cleanly >= target_start. Returns (X, y_norm, sn_preds, origin_ts)."""
    df = full_series.sort_values("timestamp").reset_index(drop=True)
    n_feats = 9 if include_festival else 7
    if len(df) < seq_len + horizon:
        return (
            np.empty((0, seq_len, n_feats), dtype=np.float32),
            np.empty((0, horizon), dtype=np.float32),
            np.empty((0, horizon), dtype=np.float32),
            np.empty((0,), dtype="datetime64[ns]"),
        )

    features = _build_feature_matrix(df, include_festival=include_festival)
    loads = df["load_pct"].to_numpy(dtype=np.float32)
    timestamps = df["timestamp"].to_numpy()

    xs, ys, sn_preds, origins = [], [], [], []
    for i in range(seq_len, len(df) - horizon + 1):
        first_target_ts = pd.Timestamp(timestamps[i])
        if first_target_ts < target_start:
            continue
        xs.append(features[i - seq_len : i])
        ys.append(loads[i : i + horizon] / 100.0)
        origins.append(timestamps[i])
        sn_block = []
        for h in range(horizon):
            idx = i + h - 168
            if idx >= 0:
                sn_block.append(float(loads[idx]))
            elif i + h - 24 >= 0:
                sn_block.append(float(loads[i + h - 24]))
            else:
                sn_block.append(float(loads[i - 1]))
        sn_preds.append(sn_block)

    if not xs:
        return (
            np.empty((0, seq_len, n_feats), dtype=np.float32),
            np.empty((0, horizon), dtype=np.float32),
            np.empty((0, horizon), dtype=np.float32),
            np.empty((0,), dtype="datetime64[ns]"),
        )
    return (
        np.array(xs, dtype=np.float32),
        np.array(ys, dtype=np.float32),
        np.array(sn_preds, dtype=np.float32),
        np.array(origins),
    )


def _compute_metrics(preds: np.ndarray, actuals: np.ndarray) -> Dict[str, Any]:
    """Computes MAE/RMSE overall, point-in-time 1h/6h/24h horizon MAE, and MAE as % of mean."""
    err = np.abs(preds - actuals)
    sq_err = (preds - actuals) ** 2
    denom = np.where(np.abs(actuals) > 1.0, np.abs(actuals), 1.0)
    mape = float(np.mean(err / denom) * 100.0)
    mean_actual = float(np.mean(actuals)) if actuals.size else 1.0
    mae_all = float(np.mean(err))
    rel_pct = (mae_all / max(mean_actual, 1e-6)) * 100.0

    def _mae_at(h: int) -> float:
        idx = h - 1
        return round(float(np.mean(err[:, idx])), 2) if preds.shape[1] > idx else round(mae_all, 2)

    return {
        "mae_overall": round(mae_all, 2),
        "rmse_overall": round(float(np.sqrt(np.mean(sq_err))), 2),
        "mape_pct": round(mape, 2),
        "relative_error_pct": round(rel_pct, 2),
        "mean_actual": round(mean_actual, 2),
        "mae_1h": _mae_at(1),
        "mae_6h": _mae_at(6),
        "mae_24h": _mae_at(24),
        "n_windows": int(preds.shape[0]),
        "unit": RADAR_UNIT_LABEL,
    }


def _train_neural(
    model: nn.Module,
    train_x: np.ndarray,
    train_y: np.ndarray,
    val_x: np.ndarray,
    val_y: np.ndarray,
    epochs: int = 12,
    batch_size: int = 64,
) -> nn.Module:
    optimizer = torch.optim.AdamW(model.parameters(), lr=1.5e-3, weight_decay=1e-4)
    criterion = nn.HuberLoss(delta=0.05)
    loader = DataLoader(TrafficSlidingWindowDataset(train_x, train_y), batch_size=batch_size, shuffle=True)
    best_state = None
    best_val = float("inf")
    for _ in range(epochs):
        model.train()
        for bx, by in loader:
            optimizer.zero_grad()
            loss = criterion(model(bx), by)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
        model.eval()
        with torch.no_grad():
            vx = torch.tensor(val_x, dtype=torch.float32)
            vy = torch.tensor(val_y, dtype=torch.float32)
            vloss = float(criterion(model(vx), vy).item()) if len(val_x) else 0.0
            if vloss <= best_val:
                best_val = vloss
                best_state = {k: v.clone() for k, v in model.state_dict().items()}
    if best_state is not None:
        model.load_state_dict(best_state)
    return model


def _sarima_predictions_for_indices(
    full_s: pd.DataFrame,
    indices: List[int],
    seq_len: int,
    horizon: int,
) -> Tuple[np.ndarray, np.ndarray]:
    full_loads = full_s["load_pct"].reset_index(drop=True)
    full_ts = full_s["timestamp"].reset_index(drop=True)
    preds, actuals = [], []
    for j in indices:
        if j + horizon > len(full_loads) or j < seq_len:
            continue
        sarima = SeasonalBaselineModel(seasonal_period=24).fit(full_loads.iloc[:j])
        fc, _, _ = sarima.predict(horizon=horizon, start_hour=int(pd.Timestamp(full_ts.iloc[j]).hour))
        preds.append(np.asarray(fc, dtype=np.float32))
        actuals.append(full_loads.iloc[j : j + horizon].to_numpy(dtype=np.float32))
    if not preds:
        return np.empty((0, horizon), dtype=np.float32), np.empty((0, horizon), dtype=np.float32)
    return np.array(preds, dtype=np.float32), np.array(actuals, dtype=np.float32)


def run_india_radar_pipeline(
    cache_path: Path = DEFAULT_RADAR_CACHE_PATH,
    metrics_path: Path = DEFAULT_METRICS_PATH,
    epochs: int = 12,
    seq_len: int = 48,
    horizon: int = 24,
) -> Dict[str, Any]:
    """
    Evaluates SARIMA, LSTM, GRU (+ festival-ablation GRU), and Seasonal-Naive on
    offline-stored India Cloudflare Radar hourly traffic series strictly chronologically,
    selecting models solely by validation MAE and reporting held-out test metrics.
    """
    existing = json.loads(metrics_path.read_text(encoding="utf-8")) if metrics_path.exists() else {}
    raw_meta = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
    raw_series_by_id = {str(s.get("series_id")): s for s in (raw_meta.get("series") or [])}
    hourly_df = load_cached_radar_series(cache_path)

    if hourly_df is None or hourly_df.empty:
        existing["real_dataset_validation"] = {
            "dataset_name": "Cloudflare Radar India Hourly Traffic Series",
            "dataset_unit": RADAR_UNIT_LABEL,
            "dataset_scale": RADAR_SCALE_LABEL,
            "status_label": "Setup required — Cloudflare Radar India cache not present",
            "setup_required": True,
            "cache_file": str(cache_path.relative_to(REPO_ROOT) if cache_path.is_relative_to(REPO_ROOT) else cache_path),
            "fetched_at": None,
            "evaluation_method": "Strict chronological time-ordered split (train earlier / validation middle / test latest; never random k-fold)",
            "split_dates": {
                "train_start": None, "train_end": None,
                "validation_start": None, "validation_end": None,
                "test_start": None, "test_end": None,
            },
            "setup_note": RADAR_SETUP_NOTE,
            "scope_note": f"{RADAR_UNIT_LABEL}. Evaluates forecasting method against a Seasonal-Naive baseline (same hour last week).",
            "beats_seasonal_naive": False,
            "best_model": None,
            "metrics": {},
            "series_results": [],
            "last_7d_daily_errors": [],
            "festival_ablation": None,
        }
        metrics_path.parent.mkdir(parents=True, exist_ok=True)
        metrics_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")
        return existing

    splits = split_radar_chronological(hourly_df)
    val_start = pd.Timestamp(splits["dates"]["validation_start"])
    test_start = pd.Timestamp(splits["dates"]["test_start"])

    # Containers for global training and per-series slicing
    tx_base, ty_all, tx_fest = [], [], []
    vx_base, vy_all, vsn_all, vx_fest = [], [], [], []
    tsx_base, tsy_all, tsn_all, tsx_fest = [], [], [], []
    per_series_slices: Dict[str, Dict[str, Any]] = {}

    val_sarima_preds_all, val_sarima_acts_all = [], []
    test_sarima_preds_all, test_sarima_acts_all = [], []
    test_window_origins: List[pd.Timestamp] = []

    for sid, full_s in hourly_df.groupby("series_id"):
        full_s = full_s.sort_values("timestamp").reset_index(drop=True)
        s_label = str(full_s["label"].iloc[0])
        s_kind = str(full_s["kind"].iloc[0])
        tr_s = full_s[full_s["timestamp"] < val_start].copy()
        trval_s = full_s[full_s["timestamp"] < test_start].copy()

        # 1. Train windows
        if len(tr_s) >= seq_len + horizon:
            feats_b = _build_feature_matrix(tr_s, include_festival=False)
            feats_f = _build_feature_matrix(tr_s, include_festival=True)
            loads_tr = tr_s["load_pct"].to_numpy(dtype=np.float32)
            for i in range(seq_len, len(tr_s) - horizon + 1):
                tx_base.append(feats_b[i - seq_len : i])
                tx_fest.append(feats_f[i - seq_len : i])
                ty_all.append(loads_tr[i : i + horizon] / 100.0)

        # 2. Validation windows + validation SARIMA
        vx_b, vy_s, vsn_s, _ = _build_windows_for_series(trval_s, val_start, seq_len=seq_len, horizon=horizon, include_festival=False)
        vx_f, _, _, _ = _build_windows_for_series(trval_s, val_start, seq_len=seq_len, horizon=horizon, include_festival=True)
        val_idx_s = trval_s.index[trval_s["timestamp"] >= val_start].tolist()
        vs_p, vs_a = _sarima_predictions_for_indices(trval_s, val_idx_s, seq_len=seq_len, horizon=horizon)

        # 3. Held-out Test windows + test SARIMA
        tsx_b, tsy_s, tsn_s, t_orig = _build_windows_for_series(full_s, test_start, seq_len=seq_len, horizon=horizon, include_festival=False)
        tsx_f, _, _, _ = _build_windows_for_series(full_s, test_start, seq_len=seq_len, horizon=horizon, include_festival=True)
        test_idx_s = full_s.index[full_s["timestamp"] >= test_start].tolist()
        ts_p, ts_a = _sarima_predictions_for_indices(full_s, test_idx_s, seq_len=seq_len, horizon=horizon)

        if len(vx_b) and len(tsx_b):
            vx_base.append(vx_b)
            vx_fest.append(vx_f)
            vy_all.append(vy_s)
            vsn_all.append(vsn_s)
            val_sarima_preds_all.append(vs_p)
            val_sarima_acts_all.append(vs_a)

            t_slice_start = sum(len(a) for a in tsx_base)
            tsx_base.append(tsx_b)
            tsx_fest.append(tsx_f)
            tsy_all.append(tsy_s)
            tsn_all.append(tsn_s)
            test_sarima_preds_all.append(ts_p)
            test_sarima_acts_all.append(ts_a)
            t_slice_end = t_slice_start + len(tsx_b)
            test_window_origins.extend([pd.Timestamp(x) for x in t_orig])

            per_series_slices[sid] = {
                "series_id": sid,
                "label": s_label,
                "kind": s_kind,
                "history_hours": int(len(full_s)),
                "date_start": full_s["timestamp"].min().isoformat(),
                "date_end": full_s["timestamp"].max().isoformat(),
                "val_x": vx_b,
                "val_y_pct": vy_s * 100.0,
                "val_naive_pct": vsn_s,
                "val_sarima_preds": vs_p,
                "val_sarima_acts": vs_a,
                "test_slice": (t_slice_start, t_slice_end),
                "test_y_pct": tsy_s * 100.0,
                "test_naive_pct": tsn_s,
                "test_sarima_preds": ts_p,
                "test_sarima_acts": ts_a,
            }

    train_x_b = np.array(tx_base, dtype=np.float32)
    train_x_f = np.array(tx_fest, dtype=np.float32)
    train_y = np.array(ty_all, dtype=np.float32)

    val_x_b = np.concatenate(vx_base, axis=0)
    val_x_f = np.concatenate(vx_fest, axis=0)
    val_y_norm = np.concatenate(vy_all, axis=0)
    val_y_pct = val_y_norm * 100.0
    val_naive_pct = np.concatenate(vsn_all, axis=0)

    test_x_b = np.concatenate(tsx_base, axis=0)
    test_x_f = np.concatenate(tsx_fest, axis=0)
    test_y_pct = np.concatenate(tsy_all, axis=0) * 100.0
    test_naive_pct = np.concatenate(tsn_all, axis=0)

    torch.manual_seed(42)
    lstm_model = _train_neural(LSTMTrafficPredictor(in_features=7, hidden_dim=64, num_layers=2, forecast_horizon=horizon), train_x_b, train_y, val_x_b, val_y_norm, epochs=epochs)
    gru_model = _train_neural(GRUTrafficPredictor(in_features=7, hidden_dim=64, num_layers=2, forecast_horizon=horizon), train_x_b, train_y, val_x_b, val_y_norm, epochs=epochs)
    torch.manual_seed(42)
    gru_fest_model = _train_neural(GRUTrafficPredictor(in_features=9, hidden_dim=64, num_layers=2, forecast_horizon=horizon), train_x_f, train_y, val_x_f, val_y_norm, epochs=epochs)

    lstm_model.eval()
    gru_model.eval()
    gru_fest_model.eval()
    with torch.no_grad():
        val_lstm_pct = lstm_model(torch.tensor(val_x_b, dtype=torch.float32)).numpy() * 100.0
        val_gru_pct = gru_model(torch.tensor(val_x_b, dtype=torch.float32)).numpy() * 100.0
        val_gru_fest_pct = gru_fest_model(torch.tensor(val_x_f, dtype=torch.float32)).numpy() * 100.0

        test_lstm_pct = lstm_model(torch.tensor(test_x_b, dtype=torch.float32)).numpy() * 100.0
        test_gru_pct = gru_model(torch.tensor(test_x_b, dtype=torch.float32)).numpy() * 100.0
        test_gru_fest_pct = gru_fest_model(torch.tensor(test_x_f, dtype=torch.float32)).numpy() * 100.0

    # Overall Validation & Held-out Test metrics
    val_sarima_p = np.concatenate(val_sarima_preds_all, axis=0)
    val_sarima_a = np.concatenate(val_sarima_acts_all, axis=0)
    test_sarima_p = np.concatenate(test_sarima_preds_all, axis=0)
    test_sarima_a = np.concatenate(test_sarima_acts_all, axis=0)

    val_metrics_overall = {
        "Seasonal_Naive_Baseline": _compute_metrics(val_naive_pct, val_y_pct),
        "SARIMA": _compute_metrics(val_sarima_p, val_sarima_a),
        "LSTM": _compute_metrics(val_lstm_pct, val_y_pct),
        "GRU": _compute_metrics(val_gru_pct, val_y_pct),
    }
    test_metrics_overall = {
        "Seasonal_Naive_Baseline": _compute_metrics(test_naive_pct, test_y_pct),
        "SARIMA": _compute_metrics(test_sarima_p, test_sarima_a),
        "LSTM": _compute_metrics(test_lstm_pct, test_y_pct),
        "GRU": _compute_metrics(test_gru_pct, test_y_pct),
    }

    naive_test_mae = test_metrics_overall["Seasonal_Naive_Baseline"]["mae_overall"]
    for name, m in test_metrics_overall.items():
        m["val_mae_overall"] = val_metrics_overall[name]["mae_overall"]
        m["val_rmse_overall"] = val_metrics_overall[name]["rmse_overall"]
        if name == "Seasonal_Naive_Baseline":
            m["beats_seasonal_naive"] = False
            m["pct_improvement_vs_naive"] = 0.0
            m["comparison_label"] = "Baseline reference (same hour last week)"
        else:
            beats = bool(m["mae_overall"] < naive_test_mae)
            pct_imp = round(((naive_test_mae - m["mae_overall"]) / max(naive_test_mae, 1e-6)) * 100.0, 2)
            m["beats_seasonal_naive"] = beats
            m["pct_improvement_vs_naive"] = pct_imp
            m["comparison_label"] = (
                f"Better than Seasonal-Naive ({m['mae_overall']:.2f} vs {naive_test_mae:.2f} MAE, {pct_imp:+.1f}%)"
                if beats
                else f"Does not beat Seasonal-Naive ({m['mae_overall']:.2f} vs {naive_test_mae:.2f} MAE, {pct_imp:+.1f}%)"
            )

    best_model = select_best_model_by_validation(test_metrics_overall)
    best_beats = bool(test_metrics_overall[best_model]["mae_overall"] < naive_test_mae and best_model != "Seasonal_Naive_Baseline")

    # Per-series validation-only selection & test breakdown across all aligned Radar series
    series_results: List[Dict[str, Any]] = []
    for sid in sorted(per_series_slices.keys()):
        sd = per_series_slices[sid]
        a, b = sd["test_slice"]
        with torch.no_grad():
            vx_t = torch.tensor(sd["val_x"], dtype=torch.float32)
            v_lstm = lstm_model(vx_t).numpy() * 100.0
            v_gru = gru_model(vx_t).numpy() * 100.0

        s_val = {
            "Seasonal_Naive_Baseline": _compute_metrics(sd["val_naive_pct"], sd["val_y_pct"]),
            "SARIMA": _compute_metrics(sd["val_sarima_preds"], sd["val_sarima_acts"]),
            "LSTM": _compute_metrics(v_lstm, sd["val_y_pct"]),
            "GRU": _compute_metrics(v_gru, sd["val_y_pct"]),
        }
        s_test = {
            "Seasonal_Naive_Baseline": _compute_metrics(sd["test_naive_pct"], sd["test_y_pct"]),
            "SARIMA": _compute_metrics(sd["test_sarima_preds"], sd["test_sarima_acts"]),
            "LSTM": _compute_metrics(test_lstm_pct[a:b], sd["test_y_pct"]),
            "GRU": _compute_metrics(test_gru_pct[a:b], sd["test_y_pct"]),
        }
        for mname, tm in s_test.items():
            tm["val_mae_overall"] = s_val[mname]["mae_overall"]
            tm["beats_seasonal_naive"] = bool(tm["mae_overall"] < s_test["Seasonal_Naive_Baseline"]["mae_overall"]) if mname != "Seasonal_Naive_Baseline" else False

        s_serving = select_best_model_by_validation(s_test)
        meta_row = raw_series_by_id.get(sid, {})
        series_results.append({
            "series_id": sid,
            "label": sd["label"],
            "kind": sd["kind"],
            "as_name": meta_row.get("as_name"),
            "as_aka": meta_row.get("as_aka"),
            "as_type": meta_row.get("as_type"),
            "radar_rank_india": meta_row.get("radar_rank_india"),
            "traffic_share_pct": meta_row.get("traffic_share_pct"),
            "network_scope_note": OPERATOR_BROADBAND_NOTE if sd["kind"] == "operator_asn" else None,
            "history_hours": sd["history_hours"],
            "date_start": sd["date_start"],
            "date_end": sd["date_end"],
            "scale": RADAR_SCALE_LABEL,
            "series_mean_test": s_test["Seasonal_Naive_Baseline"]["mean_actual"],
            "serving_model": s_serving,
            "serving_selection_criterion": "Lowest validation MAE (never test MAE)",
            "serving_val_mae": s_test[s_serving]["val_mae_overall"],
            "serving_test_mae": s_test[s_serving]["mae_overall"],
            "serving_relative_error_pct": s_test[s_serving]["relative_error_pct"],
            "naive_test_mae": s_test["Seasonal_Naive_Baseline"]["mae_overall"],
            "beats_seasonal_naive": s_test[s_serving]["beats_seasonal_naive"],
            "mae_1h": s_test[s_serving]["mae_1h"],
            "mae_6h": s_test[s_serving]["mae_6h"],
            "mae_24h": s_test[s_serving]["mae_24h"],
            "models": s_test,
        })

    # Last 7 days of the test window (IST dates) + Diwali / Festival markers
    fest_val_metrics = _compute_metrics(val_gru_fest_pct, val_y_pct)
    fest_test_metrics = _compute_metrics(test_gru_fest_pct, test_y_pct)
    base_val_mae = val_metrics_overall["GRU"]["mae_overall"]
    base_test_mae = test_metrics_overall["GRU"]["mae_overall"]
    delta_mae = round(fest_test_metrics["mae_overall"] - base_test_mae, 2)
    delta_pct = round((delta_mae / max(base_test_mae, 1e-6)) * 100.0, 2)
    helped_val = bool(fest_val_metrics["mae_overall"] < base_val_mae)
    helped_test = bool(fest_test_metrics["mae_overall"] < base_test_mae)

    if helped_val and helped_test:
        fest_conclusion = f"Festival features helped: Val MAE {base_val_mae:.2f}->{fest_val_metrics['mae_overall']:.2f} & Test MAE {base_test_mae:.2f}->{fest_test_metrics['mae_overall']:.2f} ({delta_pct:+.1f}%)."
    elif not helped_test:
        fest_conclusion = (
            f"Festival features did not help on test (Test MAE worsened {base_test_mae:.2f}->{fest_test_metrics['mae_overall']:.2f}, "
            f"{delta_pct:+.1f}%; Val MAE {base_val_mae:.2f}->{fest_val_metrics['mae_overall']:.2f}). Excluded from serving model."
        )
    else:
        fest_conclusion = f"Mixed effect: Val MAE {base_val_mae:.2f}->{fest_val_metrics['mae_overall']:.2f}; Test MAE {base_test_mae:.2f}->{fest_test_metrics['mae_overall']:.2f} ({delta_pct:+.1f}%)."

    # Compute per-day error over last 7 distinct IST dates in test window
    origin_ist_dates = [
        (ts + pd.Timedelta(hours=5, minutes=30)).strftime("%Y-%m-%d")
        for ts in test_window_origins
    ]
    serving_test_preds = {
        "Seasonal_Naive_Baseline": test_naive_pct,
        "SARIMA": test_sarima_p,
        "LSTM": test_lstm_pct,
        "GRU": test_gru_pct,
    }[best_model]

    err_df = pd.DataFrame({
        "date": origin_ist_dates,
        "naive_err": np.mean(np.abs(test_naive_pct - test_y_pct), axis=1),
        "sarima_err": np.mean(np.abs(test_sarima_p - test_sarima_a), axis=1) if len(test_sarima_p) == len(test_y_pct) else np.nan,
        "lstm_err": np.mean(np.abs(test_lstm_pct - test_y_pct), axis=1),
        "gru_err": np.mean(np.abs(test_gru_pct - test_y_pct), axis=1),
        "fest_gru_err": np.mean(np.abs(test_gru_fest_pct - test_y_pct), axis=1),
        "serving_err": np.mean(np.abs(serving_test_preds - test_y_pct), axis=1),
        "actual_mean": np.mean(test_y_pct, axis=1),
    })
    last_7_dates = sorted(err_df["date"].unique())[-7:]
    last_7d_daily: List[Dict[str, Any]] = []
    for d in last_7_dates:
        sub = err_df[err_df["date"] == d]
        m_act = float(sub["actual_mean"].mean())
        s_mae = float(sub["serving_err"].mean())
        fest_name = INDIA_2026_FESTIVALS.get(d)
        last_7d_daily.append({
            "date": d,
            "festival_name": fest_name,
            "is_diwali": bool(d == "2026-11-08"),
            "is_festival": bool(fest_name is not None),
            "naive_mae": round(float(sub["naive_err"].mean()), 2),
            "sarima_mae": round(float(sub["sarima_err"].mean()), 2),
            "lstm_mae": round(float(sub["lstm_err"].mean()), 2),
            "gru_mae": round(float(sub["gru_err"].mean()), 2),
            "festival_gru_mae": round(float(sub["fest_gru_err"].mean()), 2),
            "serving_mae": round(s_mae, 2),
            "relative_error_pct": round((s_mae / max(m_act, 1e-6)) * 100.0, 2),
            "mean_traffic_index": round(m_act, 2),
            "n_windows": int(len(sub)),
        })

    # Festivals falling inside dataset date span [date_start .. date_end]
    full_start_str = splits["dates"]["train_start"][:10]
    full_end_str = splits["dates"]["test_end"][:10]
    festivals_in_window = [
        {"date": d, "name": name, "in_test_window": bool(d >= splits["dates"]["test_start"][:10])}
        for d, name in sorted(INDIA_2026_FESTIVALS.items())
        if full_start_str <= d <= full_end_str
    ]

    series_list_eval = sorted(per_series_slices.keys())
    max_series_hours = int(hourly_df.groupby("series_id").size().max())

    existing["real_dataset_validation"] = {
        "dataset_name": "Cloudflare Radar India Hourly Traffic Series",
        "dataset_unit": RADAR_UNIT_LABEL,
        "dataset_scale": RADAR_SCALE_LABEL,
        "status_label": RADAR_VALIDATED_STATUS,
        "setup_required": False,
        "selection_criterion": "Model selected strictly by lowest VALIDATION MAE (never test MAE); held-out test metrics reported separately.",
        "cache_file": str(cache_path.relative_to(REPO_ROOT) if cache_path.is_relative_to(REPO_ROOT) else cache_path),
        "fetched_at": raw_meta.get("fetched_at") or datetime.now(timezone.utc).isoformat(),
        "date_range_start": hourly_df["timestamp"].min().isoformat(),
        "date_range_end": hourly_df["timestamp"].max().isoformat(),
        "evaluation_method": "Strict chronological time-ordered split (train earlier / validation middle / test latest; zero k-fold leakage)",
        "split_dates": splits["dates"],
        "time_resolution": raw_meta.get("agg_interval") or "1h",
        "history_hours": max_series_hours,
        "series_count": len(series_list_eval),
        "total_hourly_records": int(len(hourly_df)),
        "series_evaluated": series_list_eval,
        "skipped_top_asns": raw_meta.get("skipped_top_asns") or [],
        "operator_broadband_note": raw_meta.get("operator_broadband_note") or OPERATOR_BROADBAND_NOTE,
        "festival_calendar_note": FESTIVAL_CALENDAR_NOTE,
        "festival_source_name": FESTIVAL_SOURCE_NAME,
        "festival_source_url": FESTIVAL_SOURCE_URL,
        "radar_coverage_note": RADAR_COVERAGE_NOTE,
        "cross_domain_note": CROSS_DOMAIN_NOTE,
        "scope_note": (
            f"{RADAR_UNIT_LABEL}. {RADAR_SCALE_LABEL}. "
            f"{len(series_list_eval)} related series (states are subsets of India), with India ASNs chosen by Cloudflare Radar top India traffic rank."
        ),
        "best_model": best_model,
        "beats_seasonal_naive": best_beats,
        "metrics": test_metrics_overall,
        "series_results": series_results,
        "last_7d_daily_errors": last_7d_daily,
        "festivals_in_window": festivals_in_window,
        "festival_ablation": {
            "base_model": "GRU (7 cyclical+load features)",
            "festival_model": "GRU (+ 2026 Indian festival & Diwali-week flags)",
            "base_val_mae": base_val_mae,
            "festival_val_mae": fest_val_metrics["mae_overall"],
            "base_test_mae": base_test_mae,
            "festival_test_mae": fest_test_metrics["mae_overall"],
            "delta_test_mae": delta_mae,
            "delta_test_mae_pct": delta_pct,
            "helped_validation": helped_val,
            "helped_test": helped_test,
            "conclusion": fest_conclusion,
        },
    }
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    return existing


def main() -> None:
    parser = argparse.ArgumentParser(description="Cloudflare Radar India hourly traffic evaluator")
    parser.add_argument("--cache-path", type=Path, default=DEFAULT_RADAR_CACHE_PATH)
    parser.add_argument("--metrics-path", type=Path, default=DEFAULT_METRICS_PATH)
    parser.add_argument("--epochs", type=int, default=12)
    args = parser.parse_args()
    res = run_india_radar_pipeline(cache_path=args.cache_path, metrics_path=args.metrics_path, epochs=args.epochs)
    print(json.dumps(res["real_dataset_validation"], indent=2))


if __name__ == "__main__":
    main()
