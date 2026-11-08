import logging
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

logger = logging.getLogger("Preprocessor")


class Preprocessor:
    """
    Production-grade Preprocessing Pipeline for Telecom Network Traffic Data.
    Fulfills B.Tech Major Project Module 1 Tasks:
    - Handle missing and duplicate values
    - Remove outliers and noise
    - Convert timestamps into useful features (Temporal, Cyclical, Lags, Rolling Windows)
    - Normalize and split dataset into training and testing sets chronologically
    """

    NUMERIC_METRICS: List[str] = [
        "data_usage",
        "active_users",
        "call_volume",
        "download_traffic",
        "upload_traffic",
        "latency",
        "packet_loss",
        "bandwidth_utilization",
    ]

    def __init__(self, missing_strategy: str = "interpolate", iqr_multiplier: float = 3.0):
        self.missing_strategy = missing_strategy
        self.iqr_multiplier = iqr_multiplier
        # Stores per-cell min/max bounds for each metric
        self.scalers: Dict[str, Dict[str, Dict[str, float]]] = {}

    def clean(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Cleans telecom traffic data:
        1. Removes exact duplicate records.
        2. Drops missing or corrupted identifiers ('cell_id', 'timestamp').
        3. Removes physically impossible anomalies (negative latency/rates, packet loss > 100%).
        4. Detects and handles missing telemetry:
           - Discards consecutive multi-step missing blocks (gap > 1).
           - Linearly interpolates single isolated gaps (gap == 1).
        5. Caps extreme statistical outlier noise using IQR bounds.
        """
        initial_len = len(df)

        # 1. Deduplicate
        df = df.drop_duplicates().copy()

        # 2. Check essential identifiers
        df = df.dropna(subset=["cell_id", "timestamp"]).copy()

        # 3. Filter physically impossible anomalies
        valid_mask = (
            (df["data_usage"].isna() | (df["data_usage"] >= 0))
            & (df["download_traffic"].isna() | (df["download_traffic"] >= 0))
            & (df["upload_traffic"].isna() | (df["upload_traffic"] >= 0))
            & (df["latency"].isna() | (df["latency"] >= 0))
            & (df["packet_loss"].isna() | ((df["packet_loss"] >= 0) & (df["packet_loss"] <= 100)))
            & (df["bandwidth_utilization"].isna() | ((df["bandwidth_utilization"] >= 0) & (df["bandwidth_utilization"] <= 100)))
        )
        df = df[valid_mask].copy()

        # 4. Handle missing telemetry per cell
        cleaned_cells = []
        for cell_id, group in df.groupby("cell_id", group_keys=False):
            group = group.sort_values("timestamp").copy()

            # Identify consecutive missing values
            for metric in self.NUMERIC_METRICS:
                if metric not in group.columns:
                    continue

                is_na = group[metric].isna()
                if not is_na.any():
                    continue

                # Identify blocks of consecutive missing values
                blocks = (~is_na).cumsum()[is_na]
                block_sizes = blocks.map(blocks.value_counts())

                # Discard rows in multi-step gaps (> 1)
                drop_indices = block_sizes[block_sizes > 1].index
                group = group.drop(index=drop_indices)

                # Interpolate single isolated gaps
                group[metric] = group[metric].interpolate(method="linear").bfill().ffill()

            cleaned_cells.append(group)

        if cleaned_cells:
            df = pd.concat(cleaned_cells, ignore_index=True)
        else:
            df = pd.DataFrame(columns=df.columns)

        # 5. Cap extreme statistical outliers per cell using IQR bounds
        capped_cells = []
        for cell_id, group in df.groupby("cell_id", group_keys=False):
            group = group.copy()
            for metric in self.NUMERIC_METRICS:
                if metric not in group.columns:
                    continue
                q25 = group[metric].quantile(0.25)
                q75 = group[metric].quantile(0.75)
                iqr = q75 - q25
                if iqr > 0:
                    lower_bound = max(0.0, q25 - self.iqr_multiplier * iqr)
                    upper_bound = q75 + self.iqr_multiplier * iqr
                    group[metric] = group[metric].clip(lower=lower_bound, upper=upper_bound)
            capped_cells.append(group)

        if capped_cells:
            df = pd.concat(capped_cells, ignore_index=True)

        logger.info(f"Cleaning complete: {len(df):,} valid rows retained ({initial_len - len(df)} rows dropped/cleaned).")
        return df

    def extract_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Derives engineered features from timestamps and telemetry:
        - Temporal: year, month, day_of_week, day_name, hour_of_day, is_weekend
        - Cyclical: sin_month, cos_month, sin_quarter, cos_quarter, sin_hour, cos_hour, sin_day, cos_day
        - Domain ratios: traffic_per_user, dl_to_ul_ratio, voice_to_data_ratio
        - Autoregressive lags: lag_1, lag_2, lag_3, lag_12
        - Rolling statistics: rolling_mean_3, rolling_std_3, rolling_mean_12, rolling_std_12
        """
        df = df.copy()
        if not pd.api.types.is_datetime64_any_dtype(df["timestamp"]):
            df["timestamp"] = pd.to_datetime(df["timestamp"])

        # 1. Temporal breakdown
        df["year"] = df["timestamp"].dt.year
        df["month"] = df["timestamp"].dt.month
        df["day_of_week"] = df["timestamp"].dt.day_of_week
        df["day_name"] = df["timestamp"].dt.day_name()
        df["hour_of_day"] = df["timestamp"].dt.hour
        df["quarter"] = df["timestamp"].dt.quarter
        df["is_weekend"] = df["day_of_week"].isin([5, 6]).astype(int)
        df["is_holiday"] = df["is_weekend"]

        # 2. Cyclical trigonometric encodings
        df["sin_hour"] = np.sin(2 * np.pi * df["hour_of_day"] / 24.0)
        df["cos_hour"] = np.cos(2 * np.pi * df["hour_of_day"] / 24.0)
        df["sin_day"] = np.sin(2 * np.pi * df["day_of_week"] / 7.0)
        df["cos_day"] = np.cos(2 * np.pi * df["day_of_week"] / 7.0)
        df["sin_month"] = np.sin(2 * np.pi * df["month"] / 12.0)
        df["cos_month"] = np.cos(2 * np.pi * df["month"] / 12.0)
        df["sin_quarter"] = np.sin(2 * np.pi * df["quarter"] / 4.0)
        df["cos_quarter"] = np.cos(2 * np.pi * df["quarter"] / 4.0)

        # 3. Domain Ratios
        if "data_usage" in df.columns and "active_users" in df.columns:
            df["traffic_per_user"] = df["data_usage"] / (df["active_users"] + 1e-5)
        if "download_traffic" in df.columns and "upload_traffic" in df.columns:
            df["dl_to_ul_ratio"] = df["download_traffic"] / (df["upload_traffic"] + 1e-5)
        if "call_volume" in df.columns and "data_usage" in df.columns:
            df["voice_to_data_ratio"] = df["call_volume"] / (df["data_usage"] + 1e-5)

        # 4. Lags and Rolling Windows (Per-Cell Autoregressive Sequential Features)
        featured_cells = []
        for cell_id, group in df.groupby("cell_id", group_keys=False):
            group = group.sort_values("timestamp").copy()
            target_metric = "data_usage" if "data_usage" in group.columns else "download_traffic"
            
            # Autoregressive Lags
            group["traffic_lag_1"] = group[target_metric].shift(1).bfill()
            group["traffic_lag_2"] = group[target_metric].shift(2).bfill()
            group["traffic_lag_3"] = group[target_metric].shift(3).bfill()
            group["traffic_lag_12"] = group[target_metric].shift(12).bfill()

            # Rolling Window Statistics
            group["rolling_mean_3"] = group[target_metric].rolling(window=3, min_periods=1).mean()
            group["rolling_std_3"] = group[target_metric].rolling(window=3, min_periods=1).std().fillna(0.0)
            group["rolling_mean_12"] = group[target_metric].rolling(window=12, min_periods=1).mean()
            group["rolling_std_12"] = group[target_metric].rolling(window=12, min_periods=1).std().fillna(0.0)
            
            # Momentum / Growth Rate
            group["growth_mom_pct"] = ((group[target_metric] - group["traffic_lag_1"]) / (group["traffic_lag_1"] + 1e-5)) * 100.0

            featured_cells.append(group)

        if featured_cells:
            df = pd.concat(featured_cells, ignore_index=True)

        logger.info(f"Feature engineering complete: {len(df.columns)} total features derived.")
        return df

    def normalize(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Applies per-cell min-max normalization to numeric metrics:
        norm_x = (x - min) / (max - min)
        Scales values to [0.0, 1.0] and records bounds in self.scalers for inverse transformation.
        """
        df = df.copy()
        self.scalers = {}

        normalized_cells = []
        for cell_id, group in df.groupby("cell_id", group_keys=False):
            group = group.copy()
            self.scalers[cell_id] = {}

            for metric in self.NUMERIC_METRICS:
                if metric not in group.columns:
                    continue

                min_val = float(group[metric].min())
                max_val = float(group[metric].max())

                self.scalers[cell_id][metric] = {
                    "min": min_val,
                    "max": max_val,
                    "range": max_val - min_val if max_val != min_val else 1.0,
                }

                col_name = f"norm_{metric}"
                if max_val == min_val:
                    group[col_name] = 0.0
                else:
                    group[col_name] = (group[metric] - min_val) / (max_val - min_val)

            normalized_cells.append(group)

        if normalized_cells:
            df = pd.concat(normalized_cells, ignore_index=True)

        logger.info(f"Normalization complete for {len(self.scalers)} cells.")
        return df

    def inverse_transform(self, cell_id: str, metric: str, normalized_val: float) -> float:
        """
        Restores a normalized prediction back to its real physical units.
        """
        if cell_id not in self.scalers or metric not in self.scalers[cell_id]:
            raise KeyError(f"Scaler bounds not found for cell '{cell_id}' and metric '{metric}'.")

        bounds = self.scalers[cell_id][metric]
        return normalized_val * bounds["range"] + bounds["min"]

    def split_data(
        self, df: pd.DataFrame, train_ratio: float = 0.8
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Splits data chronologically into train and test sets to prevent future lookahead data leakage:
        - Train: First train_ratio fraction of timestamps
        - Test: Remaining (1 - train_ratio) fraction of timestamps
        """
        if not pd.api.types.is_datetime64_any_dtype(df["timestamp"]):
            df = df.copy()
            df["timestamp"] = pd.to_datetime(df["timestamp"])

        df_sorted = df.sort_values("timestamp").reset_index(drop=True)
        unique_times = df_sorted["timestamp"].drop_duplicates().sort_values().reset_index(drop=True)

        split_idx = int(len(unique_times) * train_ratio)
        split_time = unique_times.iloc[split_idx]

        train_df = df_sorted[df_sorted["timestamp"] < split_time].copy()
        test_df = df_sorted[df_sorted["timestamp"] >= split_time].copy()

        logger.info(
            f"Chronological split complete: "
            f"Train={len(train_df):,} rows ({train_df['timestamp'].min()} to {train_df['timestamp'].max()}), "
            f"Test={len(test_df):,} rows ({test_df['timestamp'].min()} to {test_df['timestamp'].max()})."
        )
        return train_df, test_df
