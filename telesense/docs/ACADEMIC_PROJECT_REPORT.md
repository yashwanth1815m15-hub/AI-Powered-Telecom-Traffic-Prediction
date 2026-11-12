# B.Tech CSE (AI & ML) Major Project Report
# Title: TeleSense: AI-Powered Telecom Traffic Prediction & Autonomous Network Planning Platform

---

## Abstract
Modern 4G/5G cellular networks operate predominantly under reactive management frameworks, where engineering interventions occur only following end-user Quality of Service (QoS) degradation or customer grievance escalation. This project presents **TeleSense**, an always-on, autonomous predictive intelligence platform designed for cellular infrastructure management in the Indian telecommunications landscape. TeleSense continuously ingests radio telemetry across diverse urban and rural topologies, forecasting cell-tower traffic load across multi-step horizons (1 to 24 hours) using PyTorch Deep Sequence Architectures (LSTM and GRU) conditioned on exogenous cyclical temporal encodings. 

On chronological, leak-free evaluation benchmarks in [`artifacts/metrics.json`](../artifacts/metrics.json), the shared simulator LSTM achieves **2.10% pt MAE** on simulated tower load (`1.85` validation MAE vs Seasonal-Naive `2.12` validation MAE / `2.36` test MAE), while on real India Cloudflare Radar web-traffic series (`14` aligned `2,543`-hour series), **LSTM scores `3.35` MAE (`+20.4%`)**, **GRU `3.37` MAE (`+20.0%`)**, and **SARIMA `3.56` MAE (`+15.4%`)** against **Seasonal-Naive `4.21` MAE** (`3.02` vs `3.24` validation MAE). TeleSense couples its predictive engine with a proactive early-warning threshold alarm system ($\ge 85\%$ planning warning, $\ge 95\%$ critical) and an explainable Capital Expenditure (Capex) optimization advisor that prescribes specific infrastructure actions (Carrier Aggregation, Small Cells, Macro Towers, Cell-on-Wheels, or Radio Micro-Sleep) denominated in Indian Rupees (₹) with payback modeling. A web application built with React 18, Leaflet, and WebSockets delivers situational awareness for Network Operations Center (NOC) engineers, network planners, and citizens.

---

## 1. Introduction & Problem Statement
With data consumption in India exceeding 24 GB per subscriber per month, cellular nodes frequently encounter localized saturation events driven by evening video streaming, live sports broadcasting (e.g., IPL cricket tournaments), and cultural festivals. Reactive cellular provisioning suffers from several critical shortcomings:
1. **Quality of Service (QoS) Degradation**: Overloaded sectors experience steep packet drop rates, throughput throttling, and call disconnection before field engineers can intervene.
2. **Suboptimal Capital Allocation**: Network operators frequently over-invest in redundant macro-towers where micro-cell repeaters or carrier aggregation would suffice.
3. **Information Asymmetry**: End-users possess zero visibility into sector load, leading to consumer frustration during peak hours.

**TeleSense** solves this by establishing proactive, predictive network automation: identifying impending bottlenecks hours before they materialize and prescribing cost-effective mitigations.

---

## 2. Mathematical Modeling & Methodology

### 2.1 Chronological Multi-Horizon Windowing (Zero Data Leakage)
Given an observed telemetry time series $\mathbf{x}_{1:T} = [x_1, x_2, \dots, x_T]$, where each observation vector $x_t \in \mathbb{R}^D$ contains cellular load, connected user equipment (UEs), user-plane throughput, and radio frequency metrics (RSRP, SINR):
1. **Chronological Splitting**:
   $$\mathcal{D}_{\text{train}} = \mathbf{x}_{1:T_1}, \quad \mathcal{D}_{\text{val}} = \mathbf{x}_{T_1+1:T_2}, \quad \mathcal{D}_{\text{test}} = \mathbf{x}_{T_2+1:T}$$
   where $T_1 = 0.70 T$ and $T_2 = 0.85 T$. No random shuffling or future lookahead leakage is permitted.
2. **Feature Normalization**: Normalizer parameters $\mu_{\text{train}}, \sigma_{\text{train}}$ are computed strictly on $\mathcal{D}_{\text{train}}$:
   $$\tilde{x}_t = \frac{x_t - \mu_{\text{train}}}{\sigma_{\text{train}}}$$
3. **Exogenous Cyclical Conditioning**: Hour-of-day ($h \in [0, 23]$) and day-of-week ($d \in [0, 6]$) are projected onto continuous unit circles:
   $$\phi_{\text{hour, sin}} = \sin\left(\frac{2\pi h}{24}\right), \quad \phi_{\text{hour, cos}} = \cos\left(\frac{2\pi h}{24}\right)$$
   $$\phi_{\text{dow, sin}} = \sin\left(\frac{2\pi d}{7}\right), \quad \phi_{\text{dow, cos}} = \cos\left(\frac{2\pi d}{7}\right)$$

### 2.2 Deep Sequence Forecasting Model
The forecasting model maps an input history window of length $L = 72$ hours to a multi-step output trajectory of horizon $H = 24$ hours:
$$\hat{\mathbf{y}}_{t+1:t+H} = f_\theta(\mathbf{X}_{t-L+1:t})$$

The LSTM recurrence equations are defined as:
$$\mathbf{f}_t = \sigma(\mathbf{W}_f [\mathbf{h}_{t-1}, \mathbf{x}_t] + \mathbf{b}_f)$$
$$\mathbf{i}_t = \sigma(\mathbf{W}_i [\mathbf{h}_{t-1}, \mathbf{x}_t] + \mathbf{b}_i)$$
$$\tilde{\mathbf{C}}_t = \tanh(\mathbf{W}_c [\mathbf{h}_{t-1}, \mathbf{x}_t] + \mathbf{b}_c)$$
$$\mathbf{C}_t = \mathbf{f}_t \odot \mathbf{C}_{t-1} + \mathbf{i}_t \odot \tilde{\mathbf{C}}_t$$
$$\mathbf{o}_t = \sigma(\mathbf{W}_o [\mathbf{h}_{t-1}, \mathbf{x}_t] + \mathbf{b}_o)$$
$$\mathbf{h}_t = \mathbf{o}_t \odot \tanh(\mathbf{C}_t)$$

The final hidden state $\mathbf{h}_t$ is projected through a multi-layer perceptron to generate the 24-step trajectory. Smooth L1 (Huber) loss is minimized to guarantee robustness against anomalous telemetry spikes:
$$\mathcal{L}_{\delta}(y, \hat{y}) = \begin{cases} 
\frac{1}{2}(y - \hat{y})^2 & \text{for } |y - \hat{y}| \le \delta \\
\delta \cdot \left(|y - \hat{y}| - \frac{1}{2}\delta\right) & \text{otherwise}
\end{cases}$$

### 2.3 Uncertainty Quantization
The 95% confidence interval bounds widen proportionally with the horizon $h \in [1, 24]$:
$$\sigma_h = \sigma_{\text{residual}} \cdot \sqrt{1 + 0.04 \cdot h}$$
$$\text{Lower}_h = \max(0, \hat{y}_h - 1.96 \cdot \sigma_h), \quad \text{Upper}_h = \min(100, \hat{y}_h + 1.96 \cdot \sigma_h)$$

---

## 3. Experimental Scope & Performance Comparison

Simulator forecasting models are trained chronologically on 1h-resampled telemetry for reference tower `MUM-C101` (`4,440` hours) across 99 India-calibrated simulated towers, while real-world validation is evaluated chronologically on 14 related Cloudflare Radar hourly web-traffic series (`IN`, 7 Indian state subsets, and top-ranked India operator ASNs).

---

## 4. Published Telecom Event Case Studies (Simulation Inspirations)

TeleSense includes documented Indian telecom event summaries grounded strictly in primary public sources ([Ookla Maha Kumbh Report](https://www.ookla.com/articles/5g-maha-kumbh-feb25), Jio & Ericsson peak-day statement via [ET Telecom](https://telecom.economictimes.indiatimes.com/news/industry/maha-kumbh-2025-ericsson-says-enabled-jio-5g-network-to-handle-400-mn-data-service-requests-at-peak/118603781), and [Opensignal IPL 2023 Study](https://economictimes.indiatimes.com/industry/telecom/telecom-news/eden-gardens-tops-in-5g-download-speeds-this-ipl-open-signal/articleshow/100425243.cms)); Presenter Mode scenarios simulate crisis ramps clearly marked `SIMULATED`:

1. **Maha Kumbh 2025 5G Connectivity (Prayagraj)**: Documented peak capacity deployments (~20M voice and 400M data service requests/day reported by Reliance Jio & Ericsson) and Ookla median 5G throughput benchmarks.
2. **IPL 2023 Stadium 5G vs 4G Benchmarks**: Documented Opensignal stadium download-speed study across major Indian IPL venues.
3. **Simulated Stress Templates (NOC Demo Mode)**: Synthetic ramps for IPL match-night spikes, Diwali evening surges, rural coverage holes (`RSRP ~ -118 dBm`), coastal cyclone outages, metro fiber cuts (`< 3%` load), and mela crowd surges used solely for operator workflow testing.

---

## 5. Rule-Based Capex Decision Framework

To bridge machine learning predictions with operational utility, TeleSense applies an explainable decision matrix:

| Radio Frequency Condition | Predicted Traffic Load | Prescribed Action | Estimated Capex | Target Payback |
| :--- | :--- | :--- | :---: | :---: |
| **Good Signal** (RSRP $> -90$ dBm) | **High Load** ($\ge 85\%$) | **Add Bandwidth (Carrier Aggregation)** | ₹3,50,000 | 3–6 Months |
| **Poor Signal** (RSRP $< -115$ dBm) | **Moderate Load** ($< 80\%$) | **Build Small Cell / Repeater** | ₹7,50,000 | 12 Months |
| **Poor Signal** (RSRP $< -115$ dBm) | **High Load** ($\ge 85\%$) | **Build New Macro Tower (Priority 1)** | ₹35,00,000 | 24 Months |
| **Good Signal** (RSRP $> -90$ dBm) | **Nominal Load** ($< 60\%$) | **No Action (Radio Micro-Sleep)** | ₹0 | Immediate (Saves ₹8.5/kWh) |
| **Stadium / Event Surge** | **Sudden Peak** ($\ge 95\%$) | **Deploy Temporary COW (Cell-on-Wheels)** | ₹65,000 | Single Event |

---

## 5. Conclusion
TeleSense demonstrates proactive AI-assisted cellular capacity planning using leak-free chronological forecasting, explicit simulator/real-data provenance separation, explainable rupee-denominated Capex rules, and open Indian public datasets.

