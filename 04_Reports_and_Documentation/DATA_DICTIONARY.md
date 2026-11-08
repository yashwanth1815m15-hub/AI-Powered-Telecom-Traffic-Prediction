# Data Dictionary: Indian Telecom Network Traffic Data (Store D2)
**Project:** AI-Powered Telecom Traffic Prediction (India 15-Year Horizon: 2010 – 2024)  
**Module 1:** Telecom Data Collection, Ingestion, Quality Profiling & Preprocessing  
**Sub-File Reference:** Accompanies `MAIN_MODULE1_INDIA_TELECOM_MASTER_DOCUMENT.md`  

This data dictionary formally specifies all raw, processed, and engineered features produced by Module 1, ensuring seamless integration with **Module 2 (Visualization & Dashboard)** and **Module 3 (AI Prediction Models)**.

---

## 1. Primary Telemetry & Network Performance Metrics (Raw Ingestion)

| Column Name | Data Type | Physical SI Unit | Valid Range | Description & Role |
| :--- | :--- | :--- | :--- | :--- |
| `record_id` | Integer | Identifier | Monotonic $1, 2, \dots$ | Unique row identifier across observations. |
| `cell_id` | String | Categorical | `Cell_001` to `Cell_004` | Network tier: `Cell_001_Metro_NCR`, `Cell_002_CategoryA_Urban`, `Cell_003_CategoryB_Regional`, `Cell_004_National_Feed`. |
| `timestamp` | Datetime (ISO-8601) | Time | `2010-01-31` to `2024-12-31` | Observation timestamp at monthly sampling granularity. |
| `data_usage` | Float | Terabytes ($\text{TB}$) | $[0.0, \infty)$ | Total wireless data volume consumed during the month ($1\text{ PB} = 1024\text{ TB}$). |
| `active_users` | Integer | Thousands of Users | $[0, 2000000]$ | Visitor Location Register (VLR) peak active mobile subscribers in thousands. |
| `call_volume` | Integer | Millions of MOUs | $[0, 5000000]$ | Total voice minutes of usage processed during the month (millions). |
| `download_traffic` | Float | Terabytes ($\text{TB}$) | $[0.0, \infty)$ | Downlink data volume consumed across the network tier (~80% of total). |
| `upload_traffic` | Float | Terabytes ($\text{TB}$) | $[0.0, \infty)$ | Uplink data volume transmitted by mobile devices (~20% of total). |
| `latency` | Float | Milliseconds ($\text{ms}$) | $[10.0, 150.0]$ | Round-trip packet latency. Improves over time from 2G (95ms) to 5G (18ms) as per TRAI QoS benchmarks. |
| `packet_loss` | Float | Percentage ($\%$) | $[0.0, 5.0]\%$ | Percentage of transmitted packets dropped due to buffer congestion or radio fade. |
| `bandwidth_utilization`| Float | Percentage ($\%$) | $[0.0, 100.0]\%$ | Ratio of consumed throughput to total spectrum capacity ($32\% \to 85\%$). |

---

## 2. Engineered Temporal & Cyclical Features

| Column Name | Data Type | Range / Format | Mathematical Formula & Purpose |
| :--- | :--- | :--- | :--- |
| `year` | Integer | $2010 – 2024$ | Long-term macro growth indicator. |
| `quarter` | Integer | $1 – 4$ | Quarter of the year for quarterly financial cycle alignment. |
| `month` | Integer | $1 – 12$ | Month indicator for seasonal trend modeling. |
| `day_of_week` | Integer | $0 – 6$ | Day of week ($0 = \text{Monday}, 6 = \text{Sunday}$). |
| `day_name` | String | Monday – Sunday | Human-readable day name for visualization dashboards. |
| `is_weekend` | Integer (Binary) | $0$ or $1$ | Binary flag indicating weekend load profile ($1 = \text{Saturday/Sunday}$). |
| `is_holiday` | Integer (Binary) | $0$ or $1$ | Binary flag for holidays/weekend peak periods. |
| `sin_month` / `cos_month` | Float | $[-1.0, 1.0]$ | Cyclical encoding: $\sin(2\pi \cdot \text{month} / 12)$ and $\cos(2\pi \cdot \text{month} / 12)$, ensuring Dec ($12$) and Jan ($1$) are adjacent. |
| `sin_quarter` / `cos_quarter`| Float | $[-1.0, 1.0]$ | Cyclical encoding of quarter: $\sin(2\pi \cdot \text{quarter} / 4)$. |
| `sin_hour` / `cos_hour` | Float | $[-1.0, 1.0]$ | Hourly cyclical encoding for high-frequency sub-sampling. |

---

## 3. Autoregressive Lags & Rolling Window Statistics

| Column Name | Data Type | Formula / Window | Predictive Purpose |
| :--- | :--- | :--- | :--- |
| `traffic_lag_1` | Float | $Y_{t-1}$ | Immediate 1-month prior traffic state (strongest autoregressive predictor). |
| `traffic_lag_2` | Float | $Y_{t-2}$ | 2-month prior traffic state. |
| `traffic_lag_3` | Float | $Y_{t-3}$ | 3-month (quarterly) prior traffic state. |
| `traffic_lag_12` | Float | $Y_{t-12}$ | 12-month prior traffic state (captures exact annual seasonality). |
| `rolling_mean_3` | Float | $\frac{1}{3}\sum_{i=0}^2 Y_{t-i}$ | 3-month moving average smoothing short-term monthly noise. |
| `rolling_std_3` | Float | $\text{Std}(Y_{t:t-2})$ | 3-month rolling volatility/dispersion. |
| `rolling_mean_12` | Float | $\frac{1}{12}\sum_{i=0}^{11} Y_{t-i}$ | 12-month trailing moving average indicating baseline capacity trend. |
| `rolling_std_12` | Float | $\text{Std}(Y_{t:t-11})$ | 12-month annual volatility. |
| `growth_mom_pct` | Float | $\frac{Y_t - Y_{t-1}}{Y_{t-1}} \times 100\%$ | Month-over-month traffic momentum percentage. |

---

## 4. Telecom Domain Ratios

| Column Name | Data Type | Formula | Engineering Significance |
| :--- | :--- | :--- | :--- |
| `traffic_per_user` | Float | $\frac{\text{data\_usage}}{\text{active\_users}}$ | Measures individual user consumption intensity (grew from 50 MB to 24 GB/user). |
| `dl_to_ul_ratio` | Float | $\frac{\text{download\_traffic}}{\text{upload\_traffic}}$ | Downlink-to-uplink asymmetry ratio (typically $4.0 = 80/20$). |
| `voice_to_data_ratio` | Float | $\frac{\text{call\_volume}}{\text{data\_usage}}$ | Decoupling index demonstrating the shift from voice-heavy to data-dominant usage. |

---

## 5. Normalized Feature Space (Scaled $[0.0, 1.0]$)

| Column Prefix | Scaling Method | Formula | Parameter Storage |
| :--- | :--- | :--- | :--- |
| `norm_*` | Per-Entity MinMax | $\hat{x} = \frac{x - x_{\min}}{x_{\max} - x_{\min}}$ | Stored in `scaler_params.json` for exact inverse restoration: $x = \hat{x} \cdot \text{range} + x_{\min}$. |
