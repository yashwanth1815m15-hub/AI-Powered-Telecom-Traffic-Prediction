# TeleSense — Project Defence & Walkthrough Script

This walkthrough strictly reflects the live codebase, offline public datasets, `artifacts/metrics.json` benchmarks, and provenance boundaries currently implemented in TeleSense.

---

## 1. 30-Second Elevator Summary

> *"TeleSense separates real public telecom evidence from simulation. We ingest real offline OpenCellID cell records (`7,542` in-India records grouped into `64` area clusters), Cloudflare Radar hourly web-traffic series (`14` related series spanning India, 7 state subsets, and top-ranked India operator ASNs), Ookla Q3 2026 speed tiles, and live client speed tests on `/measure`. On top of `99` India-calibrated simulated NOC sites, our pipeline evaluates Seasonal-Naive, SARIMA, PyTorch GRU, and PyTorch LSTM strictly on chronological splits, picks the winner by validation MAE only, and feeds an explainable alert + Rupee Capex planner."*

---

## 2. Live Browser Walkthrough (4 Minutes)

1. **NOC Map (`/` — Live Simulation Mode Banner):**
   - Point out the top banner explicitly stating tower loads are **SIMULATED** while OpenCellID cells, Ookla tiles, and `/measure` runs are **REAL**.
   - Zoom into **Mumbai** or **Bengaluru** to show OpenCellID area clusters splitting into individual cell records showing only real fields (`radio`, `MCC/MNC` via ITU/Wikipedia lookup, `LAC`, `cellid`, approximate ~1 km position, `samples`, `fetched_at`) with `MODELLED` / `SIMULATED` tags kept strictly separate.
2. **Tower Forecast Drawer:**
   - Click any simulated tower (`MUM-C101`) to show Level 1 (Live SIMULATED telemetry), Level 2 (24h forecast served by **`PyTorch LSTM (Shared Simulator Model)`** matching AI Health), and Level 3 (explainable action recommendation with explicit rule evidence and `85%` capacity threshold assumption).
3. **Presenter Mode (Demo Scenarios) & Alerts:**
   - Trigger `IPL Match-Night Surge` on Mumbai: show affected site count, telemetry ramp pushing load into 90–98%, alert hysteresis firing, and **Apply Recommended Action** stepping capacity down and clearing overload. Clicking **Reset** removes all `source='demo'` alerts and restores baseline cleanly.
4. **Capex Planner & What-If Lab:**
   - Show prioritized actions across all simulated towers in `₹ Lakhs / Crores`, confirming identical active-user capacity scaling formulas across What-If sliders, forecasts, and planner outputs.
5. **AI Health (`/model-health`):**
   - Highlight the scope banner: *"Radar models validate the method on real web traffic; tower forecasts on the NOC map come from the simulator."*
   - Show the **Cloudflare Radar India evaluation**: **`14` related series (states are subsets of India)** trimmed to the identical `2,543`-hour window + top 6 India-registered ASNs ranked by `/radar/http/top/ases` with explicit AS name and inferred type (`inferred from AS name`, since Radar Entities API omits an ASN type field; never claiming mobile-only), labelled `network-level web traffic, may include fixed broadband`; note Radar #5 `AS8075` Microsoft Corporation was skipped (`country=US`, not an IN telecom operator) and `AS45117` was excluded.
   - Show chronological splits (zero k-fold), per-series validation-MAE winner selection, `1h`/`6h`/`24h` horizons, relative error (`% of mean`), last 7 days test errors marking **Diwali (`2026-11-08`) per Drik Panchang (regional calendars can differ by a day)**, and the **Festival Feature Ablation** showing festival flags **did not help on test** (`Test MAE 3.37 -> 3.86`, `+14.5%`).
   - Show the **Simulator Leaderboard** (`MUM-C101` 1h-resampled, shared across all `99` simulated towers) with the one-line root-cause fix explaining how strict `1h` bucket resampling resolved earlier `11–12 MAE` instability (`Val MAE 1.85`, `Test MAE 2.10`).
6. **Data & Sources & Mobile Speed Test (`/measure`):**
   - Show primary citation links (TRAI PR 104/2026, Performance Indicators, QoS PR 47/2024, OpenCellID CC BY-SA 4.0, Ookla CC BY-NC-SA 4.0, Cloudflare Radar & `@cloudflare/speedtest`, Drik Panchang) and the `>= 5` sample hex aggregation rule excluding automated/localhost test runs.

---

## 3. Core Architecture & Plug-In Question prep

- **Q: Why use Cloudflare Radar if you already simulate towers?**
  - Radar models validate the chronological multi-horizon forecasting methodology across `14` aligned `2,543`h related series on real hourly India web traffic (**LSTM `3.35` MAE [`+20.4%`]**, **GRU `3.37` MAE [`+20.0%`]**, **SARIMA `3.56` MAE [`+15.4%`]** vs **Seasonal-Naive `4.21` MAE**) without calling any live API during app requests. Simulator models forecast synthetic tower PRB load on the NOC map (`MUM-C101` shared checkpoint across `99` simulated sites).
- **Q: Why pick models by validation MAE instead of test MAE?**
  - Using test MAE for model selection leaks the test set into model choice. In both `train_models.py` and `india_radar_pipeline.py`, `select_best_model_by_validation()` ranks exclusively by `val_mae_overall`, and `/api/model-health` + `/api/towers/{id}/forecast` serve that identical winner.
- **Q: How does a real telecom operator feed plug into TeleSense?**
  - Implement a concrete [`TelemetrySource`](../backend/app/services/telemetry_source.py) class (`get_latest_readings(db, simulated_time)`) connected to the operator's PM/OSS counter stream (Kafka / XML / REST KPI feed), backfill historical hourly KPIs into SQLite/PostgreSQL, and re-run `ml/training/train_models.py`.

---

## 4. Known Limitations

1. Tower RF/PRB metrics are simulated because operator per-sector RAN telemetry is proprietary.
2. Operator ASNs on Cloudflare Radar measure aggregate AS web traffic and can include fixed-broadband/enterprise flows alongside mobile handsets.
3. One shared simulator LSTM checkpoint trained on `MUM-C101` is reused for all `99` simulated NOC towers.
4. OpenCellID coordinates in India carry ~1 km rounding uncertainty and represent radio cell observations rather than physical tower structures.
