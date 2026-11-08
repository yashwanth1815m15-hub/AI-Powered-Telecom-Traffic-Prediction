# Empirical Exploratory Data Analysis (EDA) Report
**Project:** AI-Powered Telecom Traffic Prediction (India 15-Year Horizon: 2010 – 2024)  
**Module:** Module 1 – Data Ingestion, Integrity Validation, Feature Engineering & Statistical Profiling  
**Authoritative Source:** Telecom Regulatory Authority of India (TRAI) & Department of Telecommunications (DoT)  
**Sub-File Reference:** Accompanies `MAIN_MODULE1_INDIA_TELECOM_MASTER_DOCUMENT.md`  

---

## 1. Longitudinal Growth Dynamics & CAGR

Over the 15-year period (2010 Q1 to 2024 Q4, comprising 60 quarters / 180 continuous months), the Indian telecommunications landscape expanded exponentially.

### Compound Annual Growth Rate (CAGR) Formulation
$$\text{CAGR} = \left(\frac{V_{\text{final}}}{V_{\text{initial}}}\right)^{\frac{1}{n}} - 1$$

1. **Wireless Data Traffic Growth**:
   - $V_{2010\text{-Q1}} = 16.50\text{ PB}$
   - $V_{2024\text{-Q4}} = 57,999.40\text{ PB}$
   - Multiplier: **3,515.1× expansion**
   - 15-Year Data CAGR:
     $$\text{CAGR}_{\text{Data}} = \left(\frac{57999.4}{16.5}\right)^{\frac{1}{15}} - 1 = 72.34\%$$

2. **Voice Minutes of Usage (MOU) Growth**:
   - $V_{2010\text{-Q1}} = 687.2\text{ Billion Minutes}$
   - $V_{2024\text{-Q4}} = 3,588.2\text{ Billion Minutes}$
   - Multiplier: **5.22× expansion**
   - 15-Year Voice CAGR:
     $$\text{CAGR}_{\text{Voice}} = \left(\frac{3588.2}{687.2}\right)^{\frac{1}{15}} - 1 = 11.65\%$$

3. **Decoupling Finding**:
   The stark contrast between Data CAGR (72.34%) and Voice CAGR (11.65%) proves that voice traffic reached saturation (~1,000 min/sub/month post-2022), while data consumption continues rapid expansion, driven by OTT video streaming, 4G VoLTE, and 5G services.

---

## 2. Statistical Distributions (Store D2: 720 Processed Records)

| Metric | Physical Unit | Mean | Std Dev | Min | Median | Max | Skewness |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `data_usage` | Terabytes (TB) | 7,842.1 | 12,985.4 | 14.1 | 1,240.5 | 59,391.4 | +1.84 (Right Skewed) |
| `active_users` | Thousands | 82,450.2 | 31,820.6 | 22,495.0 | 85,410.0 | 142,500.0 | -0.18 (Normal/Symmetric) |
| `call_volume` | Millions MOU | 192,410.5 | 98,450.2 | 18,540.0 | 195,200.0 | 412,640.0 | +0.24 (Slightly Skewed) |
| `download_traffic` | Terabytes (TB) | 6,273.7 | 10,388.3 | 11.3 | 992.4 | 47,513.1 | +1.84 (Right Skewed) |
| `upload_traffic` | Terabytes (TB) | 1,568.4 | 2,597.1 | 2.8 | 248.1 | 11,878.3 | +1.84 (Right Skewed) |
| `latency` | Milliseconds (ms) | 48.2 | 24.6 | 12.4 | 42.1 | 96.8 | +0.42 (Improving) |
| `packet_loss` | Percentage (%) | 0.82% | 0.51% | 0.08% | 0.72% | 1.84% | +0.55 (Improving) |
| `bandwidth_utilization`| Percentage (%) | 56.4% | 18.2% | 28.5% | 54.1% | 88.6% | +0.12 (Balanced) |

---

## 3. Stationarity & Autocorrelation Analysis

For time-series models (ARIMA, SARIMA, LSTM):
1. **Raw Level Stationarity:** The raw `data_usage` series is **non-stationary** due to strong deterministic and stochastic upward trends ($p > 0.05$ on Augmented Dickey-Fuller test).
2. **First-Order Differencing ($\Delta Y_t = Y_t - Y_{t-1}$):** Differenced series achieves mean stationarity ($p < 0.01$).
3. **Autoregressive Correlation:** Strongest autocorrelation observed at:
   - $\text{Lag } 1$ ($r = 0.992$): Captures strong persistent momentum.
   - $\text{Lag } 12$ ($r = 0.965$): Captures annual calendar seasonality.

---

## 4. Key Structural Breaks in the Indian Telecom Market

The empirical series exhibits three definitive structural breaks corresponding to major technological and economic shifts:

1. **Break 1: September 2016 (Commercial 4G LTE Rollout)**:
   - Reliance Jio launched free VoLTE calls and low-cost 4G data.
   - Monthly data traffic accelerated by $>10\times$ in under 24 months.
   - Technology share of 2G/3G dropped from 92% to under 15% between 2016 and 2018.
2. **Break 2: March 2020 (COVID-19 Nationwide Lockdowns)**:
   - Strict work-from-home, remote learning, and digital commerce orders caused an immediate 25%+ surge in residential wireless traffic.
   - Traffic never retreated post-lockdowns, creating a permanently elevated baseline.
3. **Break 3: October 2022 (Commercial 5G Launch)**:
   - Rapid multi-band 5G rollout (3.5 GHz & 26 GHz).
   - 5G data traffic share reached 10.82% by March 2024 and surpassed 21% by December 2024.

---

## 5. Visual Asset Catalog in `03_Visualizations_EDA`

All generated visualization charts are stored in `03_Visualizations_EDA`:
- `eda_15yr_data_traffic_growth.png` – 15-Year historical trajectory with milestone annotations.
- `eda_voice_vs_data_traffic_decoupling.png` – Dual-axis voice vs data decoupling curves.
- `eda_technology_transition_2g_to_5g.png` – Stacked technology share migration chart.
- `eda_circle_wise_traffic_distribution.png` – Circle-wise demand rankings across 22 LSAs.
- `eda_correlation_matrix.png` – Full feature correlation matrix.
- `eda_monthly_seasonality_and_trend.png` – Monthly seasonality and 12-month trailing moving averages.
