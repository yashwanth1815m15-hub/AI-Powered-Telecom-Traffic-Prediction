# Technical Handover Package: Module 1 to Module 2 & 3
**Project:** AI-Powered Telecom Traffic Prediction (India 15-Year Horizon: 2010 – 2024)  
**Handover From:** Module 1 – Data Ingestion, Integrity Validation & Preprocessing  
**Handover To:**  
- **Module 2:** Telecom Visualization & Monitoring Dashboard (Student 2)  
- **Module 3:** AI/ML Prediction Models — LSTM, Bi-LSTM, GRU, ARIMA, Transformers (Student 3)  
**Sub-File Reference:** Accompanies `MAIN_MODULE1_INDIA_TELECOM_MASTER_DOCUMENT.md`  

---

## 1. Exported Datasets & Target Locations

All datasets are validated, exported, and ready for ingestion:

```
Telecom_Traffic_Prediction_Module1/
├── 02_Processed_Data/
│   ├── cleaned_traffic_data.csv   # Store D2: 720 rows × 39 features (All entities)
│   ├── train.csv                  # Chronological Train: 576 rows (Jan 2010 – Dec 2021 = 80%)
│   ├── val.csv                    # Chronological Validation: 72 rows (Jan 2022 – Jun 2023 = 10%)
│   ├── test.csv                   # Chronological Test: 72 rows (Jul 2023 – Dec 2024 = 10%)
│   └── scaler_params.json         # Per-entity MinMax bounds for inverse transformation
```

---

## 2. Ingestion Interface for Module 3 (AI Model Training)

### Target Variables for Forecasting
- **Primary Regression Target:** `data_usage` (or `norm_data_usage` for neural network loss functions).
- **Secondary Quality Targets:** `latency`, `packet_loss`, `bandwidth_utilization`.

### Recommended Sliding Window Sequence Formatting
For sequential models (LSTM, GRU, RNN, Transformer):
- **Input Lookback Window ($L$):** $L = 12$ months (captures one full annual seasonality cycle).
- **Forecast Horizons ($H$):**
  - Short-Term: $H = 1$ month ahead
  - Medium-Term: $H = 3$ months ahead (quarterly capacity planning)
  - Long-Term: $H = 12$ months ahead (annual capex & spectrum planning)

```python
import numpy as np
import pandas as pd

def create_sequences(data: np.ndarray, lookback: int = 12, horizon: int = 1):
    X, y = [], []
    for i in range(len(data) - lookback - horizon + 1):
        X.append(data[i : i + lookback])
        y.append(data[i + lookback : i + lookback + horizon])
    return np.array(X), np.array(y)
```

### Tensor Dimensions
- **Input Tensor ($X$):** Shape `(batch_size, 12, num_features)`
- **Output Tensor ($y$):** Shape `(batch_size, horizon)`

### Recommended Exogenous Feature Subset (12 Core Features)
```python
FEATURE_SUBSET = [
    "norm_data_usage",
    "norm_active_users",
    "norm_call_volume",
    "norm_bandwidth_utilization",
    "sin_month",
    "cos_month",
    "sin_quarter",
    "cos_quarter",
    "traffic_lag_1",
    "traffic_lag_12",
    "rolling_mean_3",
    "rolling_std_12"
]
```

---

## 3. Inverse Normalization Protocol for Evaluation Metrics

When evaluating models on Root Mean Squared Error (RMSE), Mean Absolute Error (MAE), or Mean Absolute Percentage Error (MAPE), predictions must be transformed back to real physical units (Terabytes):

```python
import json

with open("02_Processed_Data/scaler_params.json", "r") as f:
    scalers = json.load(f)

def inverse_transform(cell_id: str, metric: str, y_pred_norm: np.ndarray) -> np.ndarray:
    bounds = scalers[cell_id][metric]
    return y_pred_norm * bounds["range"] + bounds["min"]
```

---

## 4. Ingestion Interface for Module 2 (Visualization & Dashboard)

Student 2 can directly load `02_Processed_Data/cleaned_traffic_data.csv` to power dashboard widgets:
1. **Network Tier Selector:** Filter by `cell_id` (`Cell_001_Metro_NCR`, `Cell_002_CategoryA_Urban`, `Cell_003_CategoryB_Regional`, `Cell_004_National_Feed`).
2. **Timeline Slider:** Date range filter spanning 2010 to 2024.
3. **KPI Scorecards:**
   - Current National Monthly Traffic: ~58,000 PB/quarter (~19,000 PB/month)
   - Active VLR Subscriber Base: ~1.06 Billion active SIMs
   - Average Data Consumption: ~24.1 GB / user / month
   - 5G Traffic Penetration: ~22.1%
