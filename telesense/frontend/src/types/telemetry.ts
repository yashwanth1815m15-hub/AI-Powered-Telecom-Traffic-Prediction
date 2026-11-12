/**
 * TeleSense TypeScript Type Definitions
 */

export interface Tower {
  tower_id: string;
  name: string;
  city: string;
  state?: string;
  circle?: string;
  lat: number;
  lon: number;
  capacity_mbps: number;
  population_density: number;
  area_type: string;
  is_chronic_overloader: number;
  is_weak_signal: number;
  current_load_pct?: number;
  active_users?: number;
  throughput_mbps?: number;
  rsrp_dbm?: number;
  status?: "HEALTHY" | "AT_RISK" | "WEAK_COVERAGE" | "WARNING" | "CRITICAL" | "OUTAGE";
  source_type?: string;
  operator?: string;
  frequency_band?: string;
  cell_tech?: string;
  backhaul_type?: string;
}

export interface RealIncident {
  id: string;
  title: string;
  event_name: string;
  venue: string;
  city: string;
  circle: string;
  tower_id: string;
  source_name: string;
  source_url: string;
  statement_url?: string;
  date_recorded: string;
  operators_impacted: string;
  severity: string;
  peak_load_pct: number;
  peak_active_users: number;
  drop_call_rate_pct: number;
  trai_benchmark_limit: string;
  summary: string;
  standard_telecom_solution: string;
  post_fix_expected_load_pct: number;
  post_fix_expected_dcr_pct: number;
  provenance: string;
  error_code_3gpp?: string;
  root_cause?: string;
  demo_inspiration_note?: string;
}

export interface NetworkHealthSummary {
  total_towers: number;
  healthy_count: number;
  at_risk_count: number;
  weak_coverage_count?: number;
  critical_count: number;
  outage_count?: number;
  baseline_healthy_count?: number;
  baseline_at_risk_count?: number;
  baseline_weak_coverage_count?: number;
  baseline_critical_count?: number;
  baseline_outage_count?: number;
  demo_delta_critical?: number;
  demo_delta_at_risk?: number;
  demo_delta_weak_coverage?: number;
  demo_delta_outage?: number;
  baseline_profile?: "healthy" | "realistic" | string;
  active_alert_count?: number;
  unread_alert_count?: number;
  demo_alert_count?: number;
  status_source?: string;
  avg_fleet_load_pct: number;
  simulated_time: string;
  simulated_time_ist?: string;
  data_source: string;
  headline_message: string;
  real_opencellid_count?: number;
  simulated_count?: number;
  real_measurements_count?: number;
  opencellid_cluster_count?: number;
  opencellid_polygon_failed_count?: number;
  opencellid_fetched_at?: string | null;
}

export interface OpenCellIDRecordItem {
  id?: number;
  radio: string;
  mcc: number;
  mnc: number;
  operator_label: string;
  lac: number;
  cellid: number;
  lat: number;
  lon: number;
  samples: number;
  source: string;
  fetched_at: string | null;
  city?: string;
  state?: string;
  position_label?: string;
}

export interface OpenCellIDCluster {
  cluster_id: string;
  city: string;
  state: string;
  lat: number;
  lon: number;
  cell_count: number;
  cluster_label?: string;
  radios: string[];
  mccs: number[];
  operators?: string[];
  total_samples: number;
  position_label: string;
  source: string;
  records: OpenCellIDRecordItem[];
}

export interface OpenCellIDClustersResponse {
  total_cell_records: number;
  valid_india_polygon_count: number;
  failed_india_polygon_count: number;
  cluster_count: number;
  cluster_summary_label?: string;
  clustering_method?: string;
  cluster_radius_km?: number;
  fetched_at: string;
  attribution: string;
  mcc_mnc_source?: string;
  mcc_mnc_source_url?: string;
  position_label: string;
  clusters: OpenCellIDCluster[];
}

export interface OpenCellIDRecordsResponse {
  total_matching: number;
  returned_count: number;
  attribution: string;
  mcc_mnc_source?: string;
  records: OpenCellIDRecordItem[];
}

export interface ForecastPoint {
  timestamp: string;
  forecast_load_pct: number;
  lower_bound_pct: number;
  upper_bound_pct: number;
  is_overload_risk: boolean;
}

export interface TowerForecastResponse {
  tower_id: string;
  tower_name: string;
  city: string;
  current_load_pct: number;
  peak_forecast_load_pct: number;
  peak_forecast_time: string;
  capacity_threshold_pct: number;
  status: "HEALTHY" | "AT_RISK" | "CRITICAL";
  model_used: string;
  summary_sentence: string;
  recommended_action: string;
  forecast_points: ForecastPoint[];
}

export interface AlertItem {
  id: number;
  tower_id: string;
  tower_name?: string;
  city?: string;
  state?: string;
  alert_type?: "PREDICTED_OVERLOAD" | "WEAK_COVERAGE" | "OUTAGE" | "DEGRADED_SPEED" | string;
  created_at: string;
  created_at_ist?: string;
  start_time: string;
  end_time: string;
  duration_hours: number;
  peak_load_pct: number;
  severity: "WARNING" | "CRITICAL" | "OUTAGE";
  reason: string;
  mitigation_action: string;
  status: "ACTIVE" | "ACKNOWLEDGED" | "RESOLVED";
  what?: string;
  where_location?: string;
  when_ist?: string;
  evidence?: Record<string, any>;
  ranked_causes?: Array<{ hypothesis: string; likelihood: string; clue: string }>;
  expected_benefit?: string;
  provenance?: "SIMULATED" | "REAL" | string;
  source?: "baseline" | "demo" | string;
  acknowledged_at?: string;
  resolved_at?: string;
}

export interface AlertAuditLogItem {
  id: number;
  alert_id?: number;
  tower_id: string;
  alert_type: string;
  action: string;
  actor: string;
  note?: string;
  timestamp: string;
  timestamp_ist?: string;
}

export interface PresenterScenarioOption {
  id: string;
  title: string;
  subtitle: string;
  inspired_by: string;
  source_url?: string | null;
  statement_url?: string | null;
  recommended_action: string;
}

export interface AffectedSiteItem {
  tower_id: string;
  name: string;
  city: string;
  area_type?: string;
  lat: number;
  lon: number;
}

export interface BeforeAfterCurvePoint {
  label: string;
  load_pct: number;
  rsrp_dbm: number;
}

export interface PresenterStatus {
  active: boolean;
  banner_label?: string | null;
  scenario_id?: string | null;
  scenario_title?: string | null;
  scenario_subtitle?: string | null;
  inspired_by?: string | null;
  source_url?: string | null;
  statement_url?: string | null;
  capacity_assumption?: string | null;
  city?: string | null;
  target_tower_ids: string[];
  affected_sites?: AffectedSiteItem[];
  affected_site_count?: number;
  affected_cluster_count?: number;
  activated_at_ist?: string | null;
  started_at_ist?: string | null;
  ends_at_ist?: string | null;
  seconds_remaining: number;
  auto_revert_seconds: number;
  mitigation_applied: boolean;
  recommended_action?: string | null;
  checklist: string[];
  before_snapshot?: Record<string, any> | null;
  after_snapshot?: Record<string, any> | null;
  before_after_curve?: BeforeAfterCurvePoint[];
  baseline_profile?: "healthy" | "realistic" | string;
  available_scenarios: PresenterScenarioOption[];
}

export interface RecommendationItem {
  id: number;
  tower_id: string;
  tower_name?: string;
  city?: string;
  area_type?: string;
  action: string;
  confidence_pct: number;
  reason: string;
  evidence_numbers: string;
  estimated_cost_inr: number;
  payback_months: number;
  priority_rank: number;
  updated_at: string;
}

export interface CitizenQuality {
  city: string;
  area_name: string;
  signal_rating: string;
  avg_speed_mbps: number;
  best_download_window: string;
  best_call_window: string;
  worst_congestion_window: string;
  plain_english_advice: string;
  current_load_pct?: number;
  nearest_tower_id?: string;
  distance_km?: number;
  hourly_schedule?: Array<{
    hour: string;
    status: string;
    estimated_speed: string;
    color: string;
  }>;
}

export interface CrowdsourceResult {
  id: number;
  quality_label: string;
  download_speed_mbps: number;
  latency_ms: number;
  plain_english_advice: string;
  timestamp: string;
  associated_tower_id?: string;
}

export interface ModelHealthData {
  model_architecture: string;
  sequence_history_hours: number;
  forecast_horizon_hours: number;
  features_used: string[];
  metrics_leaderboard: Record<string, {
    mae_overall: number;
    rmse_overall: number;
    mape_overall: number;
    mae_1h?: number;
    mae_6h?: number;
    mae_12h?: number;
    mae_24h?: number;
    rmse_1h?: number;
    rmse_6h?: number;
    rmse_12h?: number;
    rmse_24h?: number;
    mape_1h?: number;
    mape_6h?: number;
    mape_12h?: number;
    mape_24h?: number;
    [key: string]: any;
  }>;
  selected_model: string;
  trained_on_tower_id?: string;
  is_shared_simulator_model?: boolean;
  simulator_coverage_note?: string;
  simulator_diagnostic_note?: string;
  trained_at?: string;
  drift_status: {
    drift_detected: boolean;
    baseline_mae_pct: number;
    live_mae_pct: number;
    error_deviation_pct: number;
    status_label: string;
    traffic_light: string;
    plain_english_takeaway: string;
    last_checked_at: string;
  };
}

