import logging
from typing import Optional, Set
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("DataLoader")


class DataLoader:
    """
    Handles ingestion and validation of telecom network traffic data.
    Fulfills Functional Requirement FR1 (Data Ingestion) and Store D1.
    """

    MANDATORY_METRIC_COLUMNS: Set[str] = {
        "record_id",
        "cell_id",
        "timestamp",
        "data_usage",
        "active_users",
        "call_volume",
        "download_traffic",
        "upload_traffic",
        "latency",
        "packet_loss",
        "bandwidth_utilization",
    }

    def __init__(self, source_path: str, required_columns: Optional[Set[str]] = None):
        self.source_path = source_path
        self.required_columns = required_columns or self.MANDATORY_METRIC_COLUMNS

    def load_csv(self) -> pd.DataFrame:
        """
        Loads raw CSV telecom observations, validates required schema,
        detects initial duplicates, and parses ISO timestamps.

        Raises:
            FileNotFoundError: If the source CSV file cannot be found.
            ValueError: If mandatory telecom metric columns are missing.
        """
        logger.info(f"Ingesting raw telecom records from '{self.source_path}'...")
        try:
            df = pd.read_csv(self.source_path)
        except FileNotFoundError:
            logger.error(f"Source file not found at: {self.source_path}")
            raise

        # Check required telecom columns
        missing_cols = self.required_columns - set(df.columns)
        if missing_cols:
            err_msg = f"Dataset missing mandatory telecom metric columns: {sorted(list(missing_cols))}"
            logger.error(err_msg)
            raise ValueError(err_msg)

        initial_count = len(df)

        # Detect and log duplicate records (Tasks: Handle duplicate values)
        duplicate_count = df.duplicated().sum()
        if duplicate_count > 0:
            logger.warning(f"Detected {duplicate_count} duplicate rows in raw ingestion. Dropping duplicates.")
            df = df.drop_duplicates().copy()

        # Parse timestamps into datetime (invalid formats coerced to NaT)
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")

        logger.info(
            f"Ingestion successful: Loaded {len(df):,} valid rows across "
            f"{df['cell_id'].nunique()} cells ({initial_count - len(df)} duplicate rows removed)."
        )
        return df
