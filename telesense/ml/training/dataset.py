"""
TeleSense Time-Series Dataset & Feature Engineering
Strict Chronological Windowing Pipeline:
- Zero data leakage: Chronological train (70%) / val (15%) / test (15%) splits
- Normalizer fit strictly on train split
- Cyclical time features (hour_sin/cos, dow_sin/cos, is_weekend)
- Sliding window generator: [t-72 .. t] -> [t+1 .. t+24]
"""

import numpy as np
import pandas as pd
import torch
from torch.utils.data import Dataset
from typing import Tuple, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models.telemetry import Reading


def extract_features(df: pd.DataFrame) -> pd.DataFrame:
    """Derives cyclical time encodings and lag features."""
    df = df.copy()
    if not np.issubdtype(df['timestamp'].dtype, np.datetime64):
        df['timestamp'] = pd.to_datetime(df['timestamp'])

    hours = df['timestamp'].dt.hour
    dows = df['timestamp'].dt.dayofweek

    # Cyclical encodings
    df['hour_sin'] = np.sin(2.0 * np.pi * hours / 24.0)
    df['hour_cos'] = np.cos(2.0 * np.pi * hours / 24.0)
    df['dow_sin'] = np.sin(2.0 * np.pi * dows / 7.0)
    df['dow_cos'] = np.cos(2.0 * np.pi * dows / 7.0)
    df['is_weekend'] = (dows >= 5).astype(float)

    return df


class TrafficSlidingWindowDataset(Dataset):
    """
    Sliding window dataset for sequence forecasting.
    Takes history of `seq_len` steps with multiple exogenous features,
    maps to `forecast_horizon` future target load values.
    """

    def __init__(self, X: np.ndarray, y: np.ndarray):
        self.X = torch.tensor(X, dtype=torch.float32)
        self.y = torch.tensor(y, dtype=torch.float32)

    def __len__(self) -> int:
        return len(self.X)

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor]:
        return self.X[idx], self.y[idx]


def prepare_training_data(
    db: Session,
    tower_id: Optional[str] = "MUM-C101",
    seq_len: int = 72,
    forecast_horizon: int = 24
) -> Tuple[Dataset, Dataset, Dataset, Dict[str, Any], pd.DataFrame]:
    """
    Loads historical readings from DB, processes features,
    splits chronologically, normalizes, and constructs sliding window datasets.
    """
    # 1. Fetch readings
    query = db.query(Reading)
    if tower_id:
        query = query.filter(Reading.tower_id == tower_id)
    query = query.order_by(Reading.timestamp.asc())

    rows = query.all()
    if not rows:
        raise ValueError(f"No telemetry readings found in database for tower {tower_id}.")

    data = [{
        "timestamp": pd.to_datetime(r.timestamp),
        "load_pct": float(r.load_pct),
        "active_users": float(r.active_users),
        "avg_throughput_mbps": float(r.avg_throughput_mbps),
        "rsrp_dbm": float(r.rsrp_dbm),
    } for r in rows]

    raw_df = pd.DataFrame(data).set_index("timestamp").sort_index()
    # Resample to strict 1-hour intervals so 3-second live-stream ticks never corrupt hourly sliding windows
    df = raw_df.resample("1h").mean().interpolate(method="linear").dropna().reset_index()
    df = extract_features(df)

    feature_cols = [
        "load_pct",
        "hour_sin",
        "hour_cos",
        "dow_sin",
        "dow_cos",
        "is_weekend",
        "active_users"
    ]

    total_len = len(df)
    train_end = int(total_len * 0.70)
    val_end = int(total_len * 0.85)

    # 2. Chronological Splitting (STRICT NO-LEAKAGE)
    train_df = df.iloc[:train_end].copy()
    val_df = df.iloc[train_end:val_end].copy()
    test_df = df.iloc[val_end:].copy()

    # 3. Fit MinMax Scaler on TRAIN ONLY
    load_min = float(train_df["load_pct"].min())
    load_max = float(train_df["load_pct"].max()) or 100.0
    users_min = float(train_df["active_users"].min())
    users_max = float(train_df["active_users"].max()) or 1000.0

    scaler_params = {
        "load_min": load_min,
        "load_max": load_max,
        "users_min": users_min,
        "users_max": users_max,
        "feature_cols": feature_cols,
        "split_dates": {
            "train_start": pd.Timestamp(train_df["timestamp"].min()).isoformat(),
            "train_end": pd.Timestamp(train_df["timestamp"].max()).isoformat(),
            "validation_start": pd.Timestamp(val_df["timestamp"].min()).isoformat(),
            "validation_end": pd.Timestamp(val_df["timestamp"].max()).isoformat(),
            "test_start": pd.Timestamp(test_df["timestamp"].min()).isoformat(),
            "test_end": pd.Timestamp(test_df["timestamp"].max()).isoformat(),
        },
        "hourly_df": df,
        "val_start_idx": train_end,
        "test_start_idx": val_end,
    }

    def scale_df(d: pd.DataFrame) -> pd.DataFrame:
        c = d.copy()
        c["load_pct"] = (c["load_pct"] - load_min) / (load_max - load_min + 1e-6)
        c["active_users"] = (c["active_users"] - users_min) / (users_max - users_min + 1e-6)
        return c

    train_scaled = scale_df(train_df)
    val_scaled = scale_df(val_df)
    test_scaled = scale_df(test_df)

    # 4. Construct Sliding Windows
    def create_windows(scaled_sub_df: pd.DataFrame):
        feat_matrix = scaled_sub_df[feature_cols].values
        target_series = scaled_sub_df["load_pct"].values

        X_list, y_list = [], []
        limit = len(scaled_sub_df) - seq_len - forecast_horizon + 1
        for i in range(limit):
            X_list.append(feat_matrix[i:i + seq_len])
            y_list.append(target_series[i + seq_len:i + seq_len + forecast_horizon])

        return np.array(X_list), np.array(y_list)

    X_train, y_train = create_windows(train_scaled)
    X_val, y_val = create_windows(val_scaled)
    X_test, y_test = create_windows(test_scaled)

    train_dataset = TrafficSlidingWindowDataset(X_train, y_train)
    val_dataset = TrafficSlidingWindowDataset(X_val, y_val)
    test_dataset = TrafficSlidingWindowDataset(X_test, y_test)

    return train_dataset, val_dataset, test_dataset, scaler_params, test_df

