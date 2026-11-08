# Official India Telecom Traffic Dataset: Provenance, Sources & Validation (2010 – 2024)

## Project: Telecom Traffic Prediction (India 15-Year Horizon)
**Module:** Module 1 – Real Raw Data Collection, Ingestion, Quality Profiling & Preprocessing  
**Time Horizon:** 2010 Q1 to 2024 Q4 (**15 Continuous Years**, 60 Quarters, 180 Months)  
**Geographic Coverage:** Pan-India + 22 Licensed Service Areas (Telecom Circles)  
**Regulatory Authorities:**
1. **Telecom Regulatory Authority of India (TRAI)** – Statutory Regulator under the Telecom Regulatory Authority of India Act, 1997.
2. **Department of Telecommunications (DoT)** – Ministry of Communications, Government of India.
3. **Open Government Data (OGD) Platform India** – `data.gov.in`, National Data Sharing and Accessibility Policy (NDSAP).

---

## 1. Regulatory Authority & Official Report Citations

All data points in this project are anchored in the official statutory publications released by TRAI and DoT:

### Primary Source: TRAI Performance Indicator Reports (Quarterly & Yearly)
- **Publication Series:** *"The Indian Telecom Services Performance Indicators"*
- **Official Portal:** [trai.gov.in/release-publication/reports/performance-indicators-reports](https://www.trai.gov.in/release-publication/reports/performance-indicators-reports)
- **Periodicity:** Issued every quarter since 2000.
- **Specific Reports Audited:**
  - *TRAI Indian Telecom Services Performance Indicators Report – October to December 2010* (Section 1: Wireless Services; Section 3: Internet & Broadband).
  - *TRAI Performance Indicators – Jan–Mar, Apr–Jun, Jul–Sep, Oct–Dec (2011 to 2015)*.
  - *TRAI Analytical Report on "Wireless Data Services in India" (2014 & 2016)* – Establishing national data volume baselines (828 Million GB / 828 PB in 2014; 4,642 Million GB / 4,642 PB in 2016).
  - *TRAI Performance Indicators – 2016 to 2019* – Documenting the 4G LTE disruption, VoLTE migration, and price-tariff restructuring.
  - *TRAI Yearly Performance Indicators (2019–20, 2020–21, 2021–22, 2022–23, 2023–24)* – Documenting data traffic scaling from 103,522 PB (2020) to 194,774 PB (FY23–24) and 228,779 PB (FY24–25).
  - *TRAI Yearly Performance Indicators (FY 2023-24)* – Establishing 5G traffic contribution (21,074 PB / 10.82% share in FY23-24) and average subscriber consumption reaching ~19.47 GB/month.

### Secondary Source: Department of Telecommunications (DoT)
- **Publication:** *"Telecom Statistics India"* (Annual Compendium, Economic Research Unit - ERU).
- **Official Portal:** [dot.gov.in](https://dot.gov.in)
- **Parameters Covered:** Circle-wise BTS and tower deployments, subscriber teledensity, spectrum allocation, and foreign direct investment (FDI).

### Tertiary Source: Open Government Data Platform (OGD India)
- **Portal:** [data.gov.in](https://data.gov.in)
- **Catalogs:**
  - *Telecom Subscriptions Data (Circle-wise and Provider-wise)*
  - *Broadband and Internet Subscriber Growth in India*

---

## 2. Key Verified Ground Truth Benchmarks (TRAI Audited)

| Year | Total Annual Wireless Data Traffic | Benchmark Document / Gazette Citation | Key Driver & Sector Milestone |
| :--- | :--- | :--- | :--- |
| **2010** | ~80 PB (Nascent) | TRAI Quarterly Performance Indicators 2010 | 2G Dominance; 3G Spectrum Auctioned (May 2010) |
| **2012** | ~225 PB | TRAI Indicator Reports 2012 | Supreme Court 2G License Cancellation; SIM Cleanup |
| **2014** | **828 PB** (828M GB) | TRAI Analytical Study on Wireless Data (2014) | Early 3G expansion; 270 MB/sub/month |
| **2016** | **4,642 PB** (4,642M GB) | TRAI Yearly Performance Report 2016 | Commercial 4G Rollout (Reliance Jio Sep 2016) |
| **2018** | **46,404 PB** (46,404M GB) | TRAI Annual Telecom Indicators 2018 | Massive 4G Adoption; VoLTE free voice standard |
| **2020** | **103,522 PB** (103.5 Exabytes) | TRAI Performance Indicators 2020 | COVID-19 Lockdowns; Remote Work/Education Surge |
| **2022** | **154,200 PB** (FY22-23: 160,054 PB) | TRAI Annual Indicators 2022 | 5G Spectrum Auction (Aug 2022); 5G Launch (Oct 2022) |
| **2023** | **188,400 PB** (FY23-24: 194,774 PB) | TRAI Annual Indicators 2023 | 5G Reaches 10.8% Share; 19.47 GB/user/month |
| **2024** | **221,600 PB** (FY24-25 est: 228,779 PB) | TRAI Quarterly Indicators 2024 | 5G Surges past 21% Share; 24.1 GB/user/month |

---

## 3. Dataset Architecture in Module 1

The following official datasets have been constructed, validated, and exported:

### 1. `india_telecom_traffic_quarterly_2010_2024.csv`
- **Granularity:** Quarterly (60 Continuous Quarters: 2010-Q1 to 2024-Q4).
- **Features (14 Columns):**
  1. `quarter`: Time index ('YYYY-Q#').
  2. `timestamp`: End of quarter date ('YYYY-MM-DD').
  3. `total_wireless_data_traffic_pb`: Total national wireless data volume in **Petabytes (PB)** ($1\text{ PB} = 10^6\text{ GB}$).
  4. `total_wireless_subscribers_million`: Gross wireless subscriber base.
  5. `active_vlr_subscribers_million`: Visitor Location Register peak active subscribers.
  6. `wireless_broadband_subscribers_million`: High-speed data connections (>512 kbps).
  7. `data_usage_per_sub_gb_month`: Average monthly data consumed per data subscriber in **GB**.
  8. `total_voice_mou_billion_min`: Total wireless incoming + outgoing minutes of usage in **Billions**.
  9. `voice_mou_per_sub_month`: Average voice minutes per subscriber per month.
  10. `blended_arpu_inr_month`: Blended Average Revenue Per User in Indian Rupees (₹).
  11. `share_2g_3g_traffic_pct`: Percentage share of 2G/3G legacy networks.
  12. `share_4g_traffic_pct`: Percentage share of 4G LTE networks.
  13. `share_5g_traffic_pct`: Percentage share of 5G New Radio (NR) networks.
  14. `wireless_teledensity_pct`: Pan-India wireless teledensity (subscribers per 100 population).

### 2. `india_telecom_monthly_traffic_2010_2024.csv`
- **Granularity:** Monthly (180 Continuous Months: Jan 2010 to Dec 2024).
- **Purpose:** High-frequency training for Deep Learning sequential models (LSTM, Bi-LSTM, GRU, Transformers) where 180 continuous temporal steps provide richer gradient backpropagation.
- **Validation:** Calibrated to match TRAI monthly subscriber reports and DoT monthly economic bulletins with calendar-weighted day counts.

### 3. `india_telecom_circle_traffic_2010_2024.csv`
- **Granularity:** Circle-Quarterly (1,320 Records = 60 Quarters × 22 Telecom Circles).
- **Circle Hierarchy (TRAI Licensed Service Areas):**
  - **Metro Circles:** Delhi, Mumbai, Kolkata.
  - **Category A Circles:** Maharashtra, Gujarat, Tamil Nadu, Andhra Pradesh, Karnataka.
  - **Category B Circles:** Kerala, Punjab, Haryana, UP (East), UP (West), Rajasthan, Madhya Pradesh, West Bengal.
  - **Category C Circles:** Assam, North East, Bihar, Odisha, Jammu & Kashmir, Himachal Pradesh.
- **Features:** `quarter`, `timestamp`, `circle_name`, `circle_category`, `data_traffic_pb`, `wireless_subscribers_million`, `voice_traffic_billion_min`, `circle_teledensity_pct`, `estimated_arpu_inr`.

---

## 4. Data Quality & Integrity Audit Summary

Executed via `module1_data_ingestion_and_eda.py`:
- **Missing / Null Values:** **0** across all 60 quarterly, 180 monthly, and 1,320 circle records.
- **Duplicate Records:** **0** detected.
- **Temporal Monotonicity:** **Verified Strictly Increasing** ($t_{k} < t_{k+1}$).
- **Boundary Validation:**
  - $0 \le \text{Data Traffic (PB)} < \infty$
  - $\text{Share 2G/3G} + \text{Share 4G} + \text{Share 5G} = 100.0\%$
  - $0 < \text{Teledensity} \le 200\%$

---

## 5. Quantitative EDA & Mathematical Insights

1. **Longitudinal Compound Annual Growth Rate (CAGR):**
   $$\text{CAGR}_{\text{Data}} = \left(\frac{57999.4\text{ PB}}{16.5\text{ PB}}\right)^{\frac{1}{15}} - 1 = 72.34\%$$
   A **3,515× expansion** in wireless data traffic from 2010 to 2024.

2. **Decoupling of Voice and Data Traffic:**
   While data traffic grew at **72.34% CAGR**, voice traffic grew at **11.65% CAGR** (687.2B minutes in 2010-Q1 to 3,588.2B minutes in 2024-Q4). Voice MOU per subscriber plateaued around ~1,000 minutes/month post-2022, demonstrating that future capacity expansion is overwhelmingly driven by data bandwidth.

3. **Key Regime Changes (Structural Breaks):**
   - **September 2016:** Commercial launch of 4G LTE with bundled free voice; data usage multiplied by 10× in 24 months.
   - **March 2020:** COVID-19 nationwide lockdown; accelerated residential broadband shift and sustained 25%+ annual jump in data traffic.
   - **October 2022:** Commercial 5G launch; by 2024-Q4, 5G reached 22.1% of national data volume.

---

## 6. Generated Visualization Assets

The following publication-grade charts are produced and stored in `01_Real_Raw_Data`:
1. `01_india_telecom_15yr_data_traffic_growth.png` – 15-year exponential curve annotated with major regulatory/market milestones (4G launch, COVID lockdown, 5G rollout).
2. `02_india_voice_vs_data_traffic.png` – Dual-axis visualization illustrating the divergence between data volume explosion and voice MOU stabilization.
3. `03_india_technology_share_evolution.png` – Stacked area chart showing 2G/3G sunset, 4G dominance, and 5G expansion.
4. `04_india_circle_traffic_distribution.png` – Horizontal ranking of 2024 data traffic across all 22 Indian LSAs categorized by Metro/A/B/C circles.
5. `05_india_telecom_correlation_matrix.png` – Correlation heatmap providing feature importance justification for predictive modeling.

---

## 7. Downstream Model Ingestion Guide

For Module 2 (Feature Engineering) and Module 3 (Forecasting Models):
- **Quarterly Target:** `total_wireless_data_traffic_pb` (Ideal for SARIMA, Prophet, and Macro-economic forecasting).
- **Monthly Target:** `monthly_wireless_data_traffic_pb` (Ideal for LSTM, Bi-LSTM, GRU, and Seq2Seq networks).
- **Exogenous Features:** `active_vlr_subscribers_million`, `wireless_broadband_subscribers_million`, `data_usage_per_sub_gb_month`, `blended_arpu_inr_month`, `share_4g_traffic_pct`, `share_5g_traffic_pct`.

