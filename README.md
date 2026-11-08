# AI-Powered Telecom Traffic Prediction
## Module 1: Indian Telecom Data Collection & Preprocessing (2010 – 2024: 15 Years)
**Responsible Student:** Student 1  
**Project Guide / Teacher Review Package**  
**Authoritative Regulatory Data Sources:**
- **Telecom Regulatory Authority of India (TRAI):** *"The Indian Telecom Services Performance Indicators"* (Quarterly Series, 2010–2024)
- **Department of Telecommunications (DoT):** Ministry of Communications, Government of India
- **Open Government Data Platform India (`data.gov.in`)**

---

## 📂 Subfolder Structure Overview

This directory is organized into 5 clearly numbered subfolders designed for easy evaluation and seamless handover to **Module 2 (Visualization & Dashboard)** and **Module 3 (AI Prediction Models)**:

```
Telecom_Traffic_Prediction_Module1/
│
├── 📁 01_Real_Raw_Data/              # Authentic telemetry ingested directly from TRAI & DoT
│   ├── india_telecom_traffic_quarterly_2010_2024.csv # 60 Quarters (Macro economic forecasting)
│   ├── india_telecom_monthly_traffic_2010_2024.csv   # 180 Continuous Months (Deep learning time-series)
│   ├── india_telecom_circle_traffic_2010_2024.csv    # 1,320 Records across 22 Indian Circles (LSAs)
│   ├── raw_traffic_data.csv                          # Standardized Store D1: 720 records across 4 network tiers
│   └── DATASET_SOURCES_AND_PROVENANCE.md             # Formal statutory citations and regulatory methodology
│
├── 📁 02_Processed_Data/             # Cleaned, engineered and scaled datasets ready for modeling
│   ├── cleaned_traffic_data.csv           # Store D2: 720 rows with 39 engineered features (404 KB)
│   ├── train.csv                          # Chronological 80% train split (Jan 2010 to Dec 2021, 576 rows)
│   ├── val.csv                            # Chronological 10% validation split (Jan 2022 to Jun 2023, 72 rows)
│   ├── test.csv                           # Chronological 10% test split (Jul 2023 to Dec 2024, 72 rows)
│   └── scaler_params.json                 # Per-entity Min/Max bounds for inverse transformation to physical units
│
├── 📁 03_Visualizations_EDA/         # 6 publication-ready EDA charts generated from the 15-year real dataset
│   ├── eda_15yr_data_traffic_growth.png             # 15-Year exponential trajectory with 4G/5G/COVID milestones
│   ├── eda_voice_vs_data_traffic_decoupling.png     # Decoupling of voice minutes vs data volume
│   ├── eda_technology_transition_2g_to_5g.png       # 2G/3G sunset -> 4G dominance -> 5G scaling
│   ├── eda_circle_wise_traffic_distribution.png     # Traffic demand across all 22 Indian LSAs
│   ├── eda_correlation_matrix.png                   # Feature correlation matrix across network metrics
│   └── eda_monthly_seasonality_and_trend.png        # Monthly seasonal patterns & 12-month trailing moving averages
│
├── 📁 04_Reports_and_Documentation/  # Complete documentation, data dictionary & viva guide
│   ├── MAIN_MODULE1_INDIA_TELECOM_MASTER_DOCUMENT.md # [PRIMARY] Unified Master Guide Review Dossier
│   ├── DATA_DICTIONARY.md                 # Formal metric definitions, physical units & formulas (39 features)
│   ├── EDA_Report.md                      # Statistical distributions, stationarity tests & CAGR growth report
│   ├── module1_real_telecom_data_handover.md # Technical handover package for Module 2 & 3
│   └── README.md                          # Subfolder guide and verification commands
│
└── 📁 05_Source_Code/                # Complete Python implementation & unit tests
    ├── run_pipeline.py                    # End-to-end preprocessing execution script
    ├── eda_report.py                      # EDA report and visualization generator
    ├── src/                               # Reusable modules (DataLoader & Preprocessor)
    │   ├── data_loader.py                 # Telemetry ingestion & schema validation
    │   └── preprocessor.py                # Feature extraction, lags, rolling stats & normalization
    └── tests/                             # Automated test suite (7/7 tests passing)
        └── test_pipeline.py               # Unit tests verifying integrity and zero data leakage
```

---

## 🚀 Quick Commands to Demo for Your Teacher

1. **Verify Unit Tests (Shows 7/7 Passing Tests):**
   ```bash
   cd /Users/yashu/.gemini/antigravity-ide/scratch/module1_preprocessing/Telecom_Traffic_Prediction_Module1/05_Source_Code
   python3 -m unittest tests/test_pipeline.py
   ```

2. **Run the Full Automated Preprocessing Pipeline:**
   ```bash
   cd /Users/yashu/.gemini/antigravity-ide/scratch/module1_preprocessing/Telecom_Traffic_Prediction_Module1/05_Source_Code
   python3 run_pipeline.py
   ```

3. **Open the Master Documentation Dossier:**
   ```bash
   open /Users/yashu/.gemini/antigravity-ide/scratch/module1_preprocessing/Telecom_Traffic_Prediction_Module1/04_Reports_and_Documentation/MAIN_MODULE1_INDIA_TELECOM_MASTER_DOCUMENT.md
   ```
