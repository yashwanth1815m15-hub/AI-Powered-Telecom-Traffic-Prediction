"""
Execution Pipeline for Module 1: India Telecom Data Collection & Preprocessing
B.Tech Major Project — Computer Science (AI & ML)
15-Year Horizon (2010 - 2024) Anchored on Official TRAI & DoT Indicators
"""

import json
import os
import sys
import pandas as pd

# Add current dir to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from src.data_loader import DataLoader
from src.preprocessor import Preprocessor
from eda_report import generate_eda

def run_module1_pipeline(
    raw_path: str = None,
    processed_dir: str = None,
    viz_dir: str = None,
    train_ratio: float = 0.8,
) -> None:
    print("\n" + "=" * 75)
    print("MODULE 1: INDIA TELECOM DATA INGESTION, PREPROCESSING & PROFILING (2010-2024)")
    print("=" * 75 + "\n")

    base_dir = os.path.dirname(current_dir)
    raw_path = raw_path or os.path.join(base_dir, "01_Real_Raw_Data/raw_traffic_data.csv")
    processed_dir = processed_dir or os.path.join(base_dir, "02_Processed_Data")
    viz_dir = viz_dir or os.path.join(base_dir, "03_Visualizations_EDA")

    os.makedirs(processed_dir, exist_ok=True)
    os.makedirs(viz_dir, exist_ok=True)

    # 1. Check Raw Dataset
    print(">>> STEP 1: Ingesting Authentic Indian Telecom Telemetry (Store D1)...")
    if not os.path.exists(raw_path):
        print(f"    Raw dataset not found at '{raw_path}'. Building from TRAI benchmarks...")
        builder_script = os.path.join(base_dir, "01_Real_Raw_Data/build_india_telecom_dataset.py")
        if os.path.exists(builder_script):
            os.system(f"python3 {builder_script}")
        else:
            raise FileNotFoundError(f"Builder script missing at {builder_script}")

    loader = DataLoader(raw_path)
    raw_df = loader.load_csv()
    print(f"    [OK] Ingested {len(raw_df):,} raw records from Store D1.")
    print(f"    Nodes/Entities Monitored: {sorted(raw_df['cell_id'].dropna().unique())}")

    # 2. Data Cleaning & Outlier Removal
    print("\n>>> STEP 2: Cleaning Data, Deduplication & Quality Filtering...")
    preprocessor = Preprocessor(missing_strategy="interpolate", iqr_multiplier=3.0)
    cleaned_df = preprocessor.clean(raw_df)
    print(f"    [OK] Retained {len(cleaned_df):,} clean records ({len(raw_df) - len(cleaned_df)} anomalies dropped/cleaned).")

    # 3. Feature Engineering
    print("\n>>> STEP 3: Deriving Temporal, Cyclical, Lag & Rolling Features...")
    featured_df = preprocessor.extract_features(cleaned_df)
    print(f"    [OK] Derived {len(featured_df.columns)} total features including:")
    print("         - Temporal: year, quarter, month, day_of_week, day_name, is_weekend")
    print("         - Cyclical: sin_month, cos_month, sin_quarter, cos_quarter, sin_hour, cos_hour")
    print("         - Autoregressive Lags: traffic_lag_1, traffic_lag_2, traffic_lag_3, traffic_lag_12")
    print("         - Rolling Statistics: rolling_mean_3, rolling_std_3, rolling_mean_12, rolling_std_12")
    print("         - Telecom Ratios: traffic_per_user, dl_to_ul_ratio, voice_to_data_ratio, growth_mom_pct")

    # 4. Normalization
    print("\n>>> STEP 4: Per-Entity Min-Max Normalization [0.0, 1.0]...")
    normalized_df = preprocessor.normalize(featured_df)
    print(f"    [OK] Scaled metrics: {preprocessor.NUMERIC_METRICS}")
    print(f"    [OK] Preserved scaler bounds across {len(preprocessor.scalers)} network entities.")

    # 5. Export Processed Dataset (Store D2)
    processed_csv = os.path.join(processed_dir, "cleaned_traffic_data.csv")
    normalized_df.to_csv(processed_csv, index=False)
    print(f"\n[OK] Cleaned Dataset (Store D2) saved to: '{processed_csv}' ({len(normalized_df):,} rows)")

    # 6. Export Scaler Parameters
    scaler_file = os.path.join(processed_dir, "scaler_params.json")
    with open(scaler_file, "w") as f:
        json.dump(preprocessor.scalers, f, indent=2)
    print(f"[OK] Scaler parameters exported to: '{scaler_file}'")

    # 7. Split into Chronological Training & Testing Sets
    print(f"\n>>> STEP 5: Splitting Dataset Chronologically (80% Train [2010-2021] / 20% Test [2022-2024])...")
    train_df, test_df = preprocessor.split_data(normalized_df, train_ratio=train_ratio)

    # Also generate validation split from test (50/50 test split = 10% Val [2022-2023] / 10% Test [2024])
    val_df, final_test_df = preprocessor.split_data(test_df, train_ratio=0.5)

    train_path = os.path.join(processed_dir, "train.csv")
    val_path = os.path.join(processed_dir, "val.csv")
    test_path = os.path.join(processed_dir, "test.csv")

    train_df.to_csv(train_path, index=False)
    val_df.to_csv(val_path, index=False)
    final_test_df.to_csv(test_path, index=False)

    print(f"[OK] Train set saved:      '{train_path}' ({len(train_df):,} rows)")
    print(f"[OK] Validation set saved: '{val_path}' ({len(val_df):,} rows)")
    print(f"[OK] Test set saved:       '{test_path}' ({len(final_test_df):,} rows)")

    # 8. Generate Visualizations & EDA Report
    print("\n>>> STEP 6: Generating Official EDA Charts & Report...")
    generate_eda(raw_path=raw_path, processed_path=processed_csv, output_dir=viz_dir)

    print("\n" + "=" * 75)
    print("[SUCCESS] Module 1 Preprocessing Complete! All Subfolders Synchronized.")
    print("=" * 75 + "\n")

if __name__ == "__main__":
    run_module1_pipeline()
