"""
Module 3 & Module 4: Real-Life AI/ML Predictive Modeling & Performance Benchmarking
====================================================================================
Project: AI-Powered Telecom Traffic Prediction (India 15-Year Horizon: 2010 - 2024)
Authoritative Baseline: Telecom Regulatory Authority of India (TRAI) & Department of Telecommunications (DoT)

Trains, evaluates, and exports real predictive models on 15 years of Indian telemetry:
1. Baseline Persistence Model (Lag-1)
2. Random Forest Regressor (Ensemble with Growth Momentum)
3. Gradient Boosting Regressor (GBR Sequential Tree Boosting)
4. Deep Neural Network Regressor (Multi-Layer Perceptron)

Exports trained model weights, evaluation metrics (R2, RMSE, MAE, MAPE), and forecast curves.
"""

import os
import sys
import json
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

# Matplotlib configuration for headless servers
os.environ['MPLCONFIGDIR'] = '/tmp/matplotlib_cache'
os.makedirs('/tmp/matplotlib_cache', exist_ok=True)
import matplotlib.pyplot as plt

def calculate_mape(y_true, y_pred):
    """Calculates Mean Absolute Percentage Error (%) safely."""
    y_true, y_pred = np.array(y_true), np.array(y_pred)
    non_zero = y_true != 0
    if not np.any(non_zero):
        return 0.0
    return np.mean(np.abs((y_true[non_zero] - y_pred[non_zero]) / y_true[non_zero])) * 100.0

def train_and_evaluate_models(base_dir: str = None):
    base_dir = base_dir or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    proc_dir = os.path.join(base_dir, "02_Processed_Data")
    model_dir = os.path.join(base_dir, "05_Source_Code/models")
    viz_dir = os.path.join(base_dir, "03_Visualizations_EDA")
    os.makedirs(model_dir, exist_ok=True)
    os.makedirs(viz_dir, exist_ok=True)

    print("\n" + "=" * 75)
    print("MODULE 3 & 4: TRAINING REAL AI/ML MODELS ON 15-YEAR INDIAN TELECOM DATA")
    print("=" * 75 + "\n")

    train_path = os.path.join(proc_dir, "train.csv")
    val_path = os.path.join(proc_dir, "val.csv")
    test_path = os.path.join(proc_dir, "test.csv")

    df_train = pd.read_csv(train_path)
    df_val = pd.read_csv(val_path)
    df_test = pd.read_csv(test_path)

    # Stationarized Momentum Target: Growth Ratio (Y_t / Y_{t-1})
    df_train['growth_ratio'] = df_train['data_usage'] / (df_train['traffic_lag_1'] + 1e-5)
    df_val['growth_ratio'] = df_val['data_usage'] / (df_val['traffic_lag_1'] + 1e-5)
    df_test['growth_ratio'] = df_test['data_usage'] / (df_test['traffic_lag_1'] + 1e-5)

    # Feature Set for Training (Predictors of network traffic demand)
    feature_cols = [
        "active_users",
        "call_volume",
        "download_traffic",
        "upload_traffic",
        "bandwidth_utilization",
        "latency",
        "packet_loss",
        "month",
        "quarter",
        "is_weekend",
        "sin_month",
        "cos_month",
        "sin_quarter",
        "cos_quarter",
        "rolling_mean_3",
        "rolling_std_3",
        "rolling_mean_12",
        "rolling_std_12",
        "traffic_per_user",
        "dl_to_ul_ratio",
        "voice_to_data_ratio"
    ]
    feature_cols = [c for c in feature_cols if c in df_train.columns]

    print(f">>> Features selected for model training ({len(feature_cols)} dimensions):")
    print(f"    {feature_cols[:7]} ... (+{len(feature_cols)-7} more)")

    X_train = df_train[feature_cols].fillna(0.0)
    y_train_ratio = df_train['growth_ratio'].values
    y_train_actual = df_train['data_usage'].values

    X_val = df_val[feature_cols].fillna(0.0)
    y_val_ratio = df_val['growth_ratio'].values
    y_val_actual = df_val['data_usage'].values

    X_test = df_test[feature_cols].fillna(0.0)
    y_test_ratio = df_test['growth_ratio'].values
    y_test_actual = df_test['data_usage'].values
    lag1_test = df_test['traffic_lag_1'].values

    print(f"\n>>> Chronological Dataset Splits:")
    print(f"    * Training Set:   {len(X_train)} samples (2010 to 2021 — 12 continuous years)")
    print(f"    * Validation Set: {len(X_val)} samples (2022 to mid-2023 — 1.5 years)")
    print(f"    * Test Set:       {len(X_test)} samples (mid-2023 to 2024 — Out-of-sample benchmark)")

    # 1. Baseline Persistence Model (Lag-1)
    print("\n>>> [1/4] Evaluating Baseline Persistence Model (Lag-1)...")
    y_pred_baseline = lag1_test
    rmse_base = np.sqrt(mean_squared_error(y_test_actual, y_pred_baseline))
    mae_base = mean_absolute_error(y_test_actual, y_pred_baseline)
    r2_base = r2_score(y_test_actual, y_pred_baseline)
    mape_base = calculate_mape(y_test_actual, y_pred_baseline)
    print(f"    Baseline -> R2: {r2_base:.4f} | RMSE: {rmse_base:,.2f} TB | MAE: {mae_base:,.2f} TB | MAPE: {mape_base:.2f}%")

    # 2. Random Forest Regressor
    print("\n>>> [2/4] Training Random Forest Regressor (150 Estimators)...")
    rf_model = RandomForestRegressor(
        n_estimators=150,
        max_depth=10,
        min_samples_split=2,
        random_state=42,
        n_jobs=-1
    )
    rf_model.fit(X_train, y_train_ratio)
    pred_ratio_rf = rf_model.predict(X_test)
    y_pred_rf = lag1_test * pred_ratio_rf
    rmse_rf = np.sqrt(mean_squared_error(y_test_actual, y_pred_rf))
    mae_rf = mean_absolute_error(y_test_actual, y_pred_rf)
    r2_rf = r2_score(y_test_actual, y_pred_rf)
    mape_rf = calculate_mape(y_test_actual, y_pred_rf)
    print(f"    Random Forest -> R2: {r2_rf:.4f} | RMSE: {rmse_rf:,.2f} TB | MAE: {mae_rf:,.2f} TB | MAPE: {mape_rf:.2f}%")

    # 3. Gradient Boosting Regressor (GBR)
    print("\n>>> [3/4] Training Gradient Boosting Regressor (GBR)...")
    gb_model = GradientBoostingRegressor(
        n_estimators=120,
        learning_rate=0.06,
        max_depth=4,
        random_state=42
    )
    gb_model.fit(X_train, y_train_ratio)
    pred_ratio_gb = gb_model.predict(X_test)
    y_pred_gb = lag1_test * pred_ratio_gb
    rmse_gb = np.sqrt(mean_squared_error(y_test_actual, y_pred_gb))
    mae_gb = mean_absolute_error(y_test_actual, y_pred_gb)
    r2_gb = r2_score(y_test_actual, y_pred_gb)
    mape_gb = calculate_mape(y_test_actual, y_pred_gb)
    print(f"    Gradient Boosting -> R2: {r2_gb:.4f} | RMSE: {rmse_gb:,.2f} TB | MAE: {mae_gb:,.2f} TB | MAPE: {mape_gb:.2f}%")

    # 4. Multi-Layer Perceptron (Deep Neural Network)
    print("\n>>> [4/4] Training Multi-Layer Perceptron Deep Neural Network (MLP 64x32)...")
    scaler_x = StandardScaler()
    X_train_scaled = scaler_x.fit_transform(X_train)
    X_test_scaled = scaler_x.transform(X_test)

    mlp_model = MLPRegressor(
        hidden_layer_sizes=(64, 32),
        activation="relu",
        solver="adam",
        max_iter=600,
        random_state=42
    )
    mlp_model.fit(X_train_scaled, y_train_ratio)
    pred_ratio_mlp = mlp_model.predict(X_test_scaled)
    y_pred_mlp = lag1_test * pred_ratio_mlp
    rmse_mlp = np.sqrt(mean_squared_error(y_test_actual, y_pred_mlp))
    mae_mlp = mean_absolute_error(y_test_actual, y_pred_mlp)
    r2_mlp = r2_score(y_test_actual, y_pred_mlp)
    mape_mlp = calculate_mape(y_test_actual, y_pred_mlp)
    print(f"    Neural Network (MLP) -> R2: {r2_mlp:.4f} | RMSE: {rmse_mlp:,.2f} TB | MAE: {mae_mlp:,.2f} TB | MAPE: {mape_mlp:.2f}%")

    # Leaderboard Summary
    benchmark_df = pd.DataFrame([
        {"Model": "Random Forest Regressor (Ensemble)", "R2_Score": round(r2_rf, 4), "RMSE_TB": round(rmse_rf, 2), "MAE_TB": round(mae_rf, 2), "MAPE_Pct": round(mape_rf, 2)},
        {"Model": "Gradient Boosting Regressor (GBR)", "R2_Score": round(r2_gb, 4), "RMSE_TB": round(rmse_gb, 2), "MAE_TB": round(mae_gb, 2), "MAPE_Pct": round(mape_gb, 2)},
        {"Model": "Baseline (Persistence Lag-1)", "R2_Score": round(r2_base, 4), "RMSE_TB": round(rmse_base, 2), "MAE_TB": round(mae_base, 2), "MAPE_Pct": round(mape_base, 2)},
        {"Model": "Deep Neural Network (MLP 64x32)", "R2_Score": round(r2_mlp, 4), "RMSE_TB": round(rmse_mlp, 2), "MAE_TB": round(mae_mlp, 2), "MAPE_Pct": round(mape_mlp, 2)}
    ]).sort_values(by="RMSE_TB", ascending=True)

    print("\n" + "=" * 75)
    print("AI/ML MODEL LEADERBOARD (OUT-OF-SAMPLE 2024 EVALUATION)")
    print("=" * 75)
    print(benchmark_df.to_string(index=False))

    # Export benchmark comparison
    bench_csv = os.path.join(model_dir, "model_benchmark_comparison.csv")
    benchmark_df.to_csv(bench_csv, index=False)

    # Save model artifacts
    joblib.dump(rf_model, os.path.join(model_dir, "random_forest_telecom_model.joblib"))
    joblib.dump(gb_model, os.path.join(model_dir, "gradient_boosting_telecom_model.joblib"))
    joblib.dump(mlp_model, os.path.join(model_dir, "neural_network_telecom_model.joblib"))
    joblib.dump(scaler_x, os.path.join(model_dir, "feature_scaler.joblib"))

    meta = {
        "feature_names": feature_cols,
        "target": "data_usage",
        "modeling_paradigm": "Growth-Momentum Forecasting",
        "best_model": benchmark_df.iloc[0]["Model"],
        "best_r2": float(benchmark_df.iloc[0]["R2_Score"]),
        "best_rmse_tb": float(benchmark_df.iloc[0]["RMSE_TB"]),
        "best_mape_pct": float(benchmark_df.iloc[0]["MAPE_Pct"])
    }
    with open(os.path.join(model_dir, "model_metadata.json"), "w") as f:
        json.dump(meta, f, indent=2)

    # Generate Actual vs Predicted Plot
    plt.figure(figsize=(11, 5.5), dpi=150)
    plt.plot(range(len(y_test_actual)), y_test_actual, color="#1f77b4", linewidth=2.5, label="Actual Ground Truth Traffic (2024 Test Set)")
    plt.plot(range(len(y_test_actual)), y_pred_rf, color="#d62728", linestyle="--", linewidth=2.2, label=f"Random Forest (R²={r2_rf:.4f}, MAPE={mape_rf:.2f}%)")
    plt.plot(range(len(y_test_actual)), y_pred_gb, color="#2ca02c", linestyle=":", linewidth=2.0, label=f"Gradient Boosting (R²={r2_gb:.4f}, MAPE={mape_gb:.2f}%)")
    plt.title("Out-of-Sample AI Predictions vs Real Indian Telecom Ground Truth (2024)\nModule 3 & 4 Evaluation Benchmark", fontsize=12, fontweight="bold", pad=12)
    plt.xlabel("Test Observations (2024 Sequential Monthly Horizons)", fontsize=10, fontweight="bold")
    plt.ylabel("Data Volume (Terabytes)", fontsize=10, fontweight="bold")
    plt.legend(loc="upper left", frameon=True)
    plt.grid(True, linestyle=":", alpha=0.6)
    plt.tight_layout()
    pred_plot = os.path.join(viz_dir, "eda_actual_vs_predicted_traffic.png")
    plt.savefig(pred_plot)
    plt.close()
    print(f"\n[OK] Actual vs Predicted evaluation chart saved: '{pred_plot}'")

    print("\n" + "=" * 75)
    print("[SUCCESS] Module 3 & Module 4 Completed! Trained Models Ready for Dashboard.")
    print("=" * 75 + "\n")

if __name__ == "__main__":
    train_and_evaluate_models()
