import unittest
import numpy as np
import pandas as pd
from src.data_loader import DataLoader
from src.preprocessor import Preprocessor


class TestModule1Pipeline(unittest.TestCase):
    def setUp(self):
        timestamps = pd.date_range("2026-01-01 00:00:00", periods=10, freq="h")
        self.mock_df = pd.DataFrame({
            "record_id": list(range(1, 11)),
            "cell_id": ["Cell_001"] * 10,
            "timestamp": [ts.isoformat() for ts in timestamps],
            "data_usage": [1000.0, 1200.0, np.nan, 1400.0, 1500.0, 1600.0, 1700.0, 1800.0, 1900.0, 2000.0],
            "active_users": [50, 60, 70, 80, 90, 100, 110, 120, 130, 140],
            "call_volume": [10, 12, 14, 16, 18, 20, 22, 24, 26, 28],
            "download_traffic": [100.0, 120.0, np.nan, 140.0, np.nan, np.nan, 170.0, 180.0, 190.0, 200.0],
            "upload_traffic": [20.0, 24.0, 26.0, 28.0, 30.0, 32.0, 34.0, 36.0, 38.0, 40.0],
            "latency": [25.0, 26.0, 27.0, 28.0, 30.0, 32.0, 34.0, 35.0, 36.0, 37.0],
            "packet_loss": [0.05, 0.06, 0.07, 0.08, 0.10, 0.12, 0.14, 0.15, 0.16, 0.18],
            "bandwidth_utilization": [40.0, 48.0, 52.0, 56.0, 60.0, 64.0, 68.0, 72.0, 76.0, 80.0],
        })

    def test_schema_validation(self):
        bad_df = pd.DataFrame({"record_id": [1], "cell_id": ["Cell_001"]})
        bad_df.to_csv("test_bad.csv", index=False)
        loader = DataLoader("test_bad.csv")
        with self.assertRaises(ValueError):
            loader.load_csv()

    def test_duplicate_removal(self):
        df_with_dups = pd.concat([self.mock_df, self.mock_df.iloc[[0]]], ignore_index=True)
        df_with_dups.to_csv("test_dups.csv", index=False)
        loader = DataLoader("test_dups.csv")
        loaded = loader.load_csv()
        self.assertEqual(len(loaded), len(self.mock_df))

    def test_clean_single_interpolation_and_multistep_drop(self):
        preprocessor = Preprocessor()
        df = self.mock_df.copy()
        cleaned = preprocessor.clean(df)

        # Record 3 was single gap in download_traffic -> linearly interpolated
        rec3 = cleaned[cleaned["record_id"] == 3]
        self.assertFalse(rec3.empty)
        self.assertAlmostEqual(rec3["download_traffic"].values[0], 130.0, places=1)

        # Records 5 & 6 were multi-gap -> must be dropped
        self.assertTrue(cleaned[cleaned["record_id"] == 5].empty)
        self.assertTrue(cleaned[cleaned["record_id"] == 6].empty)

    def test_physical_anomaly_filtering(self):
        preprocessor = Preprocessor()
        df = self.mock_df.copy()
        df.loc[0, "packet_loss"] = 150.0  # Invalid packet loss > 100%
        df.loc[1, "latency"] = -10.0      # Non-physical negative latency
        cleaned = preprocessor.clean(df)
        self.assertTrue(cleaned[cleaned["record_id"] == 1].empty)
        self.assertTrue(cleaned[cleaned["record_id"] == 2].empty)

    def test_cyclical_feature_engineering(self):
        preprocessor = Preprocessor()
        df = self.mock_df.copy()
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        featured = preprocessor.extract_features(df)
        self.assertIn("hour_of_day", featured.columns)
        self.assertIn("day_name", featured.columns)
        self.assertIn("sin_hour", featured.columns)
        self.assertIn("cos_hour", featured.columns)
        # Check hour 0 has sin=0, cos=1
        self.assertAlmostEqual(featured["sin_hour"].iloc[0], 0.0, places=3)
        self.assertAlmostEqual(featured["cos_hour"].iloc[0], 1.0, places=3)

    def test_per_cell_normalization_and_inversion(self):
        preprocessor = Preprocessor()
        df = self.mock_df.dropna().copy()
        normalized = preprocessor.normalize(df)
        self.assertIn("norm_download_traffic", normalized.columns)
        self.assertIn("norm_active_users", normalized.columns)
        self.assertGreaterEqual(normalized["norm_download_traffic"].min(), 0.0)
        self.assertLessEqual(normalized["norm_download_traffic"].max(), 1.0)

        # Test inverse transform
        val = preprocessor.inverse_transform("Cell_001", "active_users", 0.5)
        expected = (df["active_users"].min() + df["active_users"].max()) / 2.0
        self.assertAlmostEqual(val, expected, places=1)

    def test_chronological_split(self):
        preprocessor = Preprocessor()
        df = self.mock_df.dropna().copy()
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        train, test = preprocessor.split_data(df, train_ratio=0.8)
        self.assertTrue(len(train) > 0)
        self.assertTrue(len(test) > 0)
        self.assertTrue(train["timestamp"].max() < test["timestamp"].min())


if __name__ == "__main__":
    unittest.main()
