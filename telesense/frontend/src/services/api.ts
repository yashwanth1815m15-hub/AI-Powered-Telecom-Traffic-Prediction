import {
  Tower,
  NetworkHealthSummary,
  TowerForecastResponse,
  AlertItem,
  AlertAuditLogItem,
  RecommendationItem,
  CitizenQuality,
  RealIncident,
  OpenCellIDClustersResponse,
  OpenCellIDRecordsResponse,
  PresenterStatus,
} from '../types/telemetry';

const API_BASE = '/api';

export async function fetchOpenCellIDClusters(): Promise<OpenCellIDClustersResponse> {
  const res = await fetch(`${API_BASE}/towers/opencellid-clusters`);
  if (!res.ok) throw new Error('Failed to fetch OpenCellID cell clusters');
  return res.json();
}

export async function fetchOpenCellIDRecords(params: {
  lat_min?: number;
  lat_max?: number;
  lon_min?: number;
  lon_max?: number;
  city?: string;
  limit?: number;
}): Promise<OpenCellIDRecordsResponse> {
  const qs = new URLSearchParams();
  if (params.lat_min !== undefined) qs.set('lat_min', String(params.lat_min));
  if (params.lat_max !== undefined) qs.set('lat_max', String(params.lat_max));
  if (params.lon_min !== undefined) qs.set('lon_min', String(params.lon_min));
  if (params.lon_max !== undefined) qs.set('lon_max', String(params.lon_max));
  if (params.city) qs.set('city', params.city);
  if (params.limit !== undefined) qs.set('limit', String(params.limit));
  const res = await fetch(`${API_BASE}/towers/opencellid-records?${qs.toString()}`);
  if (!res.ok) throw new Error('Failed to fetch individual OpenCellID cell records');
  return res.json();
}

export async function fetchOoklaTiles(): Promise<any> {
  const res = await fetch(`${API_BASE}/towers/ookla-tiles`);
  if (!res.ok) throw new Error('Failed to fetch Ookla tiles');
  return res.json();
}

export async function fetchIndiaBoundary(): Promise<any> {
  const res = await fetch(`${API_BASE}/towers/india-boundary`);
  if (!res.ok) throw new Error('Failed to fetch India boundary GeoJSON');
  return res.json();
}

export async function fetchSummary(): Promise<NetworkHealthSummary> {
  const res = await fetch(`${API_BASE}/towers/summary`, { cache: 'no-store' });
  if (!res.ok) throw new Error('Failed to fetch network summary');
  return res.json();
}

export async function fetchTowers(): Promise<Tower[]> {
  const res = await fetch(`${API_BASE}/towers`, { cache: 'no-store' });
  if (!res.ok) throw new Error('Failed to fetch towers');
  return res.json();
}

export async function fetchTowerForecast(towerId: string): Promise<TowerForecastResponse> {
  const res = await fetch(`${API_BASE}/towers/${towerId}/forecast`, { cache: 'no-store' });
  if (!res.ok) throw new Error(`Failed to fetch forecast for ${towerId}`);
  return res.json();
}

export async function fetchAlerts(statusFilter: string = 'OPEN'): Promise<AlertItem[]> {
  const res = await fetch(`${API_BASE}/alerts?status=${encodeURIComponent(statusFilter)}`, { cache: 'no-store' });
  if (!res.ok) throw new Error('Failed to fetch alerts');
  return res.json();
}

export async function fetchAlertAuditLog(limit: number = 60): Promise<AlertAuditLogItem[]> {
  const res = await fetch(`${API_BASE}/alerts/audit-log?limit=${limit}`, { cache: 'no-store' });
  if (!res.ok) throw new Error('Failed to fetch alert audit log');
  return res.json();
}

export async function acknowledgeAlert(id: number): Promise<void> {
  const res = await fetch(`${API_BASE}/alerts/${id}/acknowledge`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to acknowledge alert');
}

export async function resolveAlert(id: number): Promise<void> {
  const res = await fetch(`${API_BASE}/alerts/${id}/resolve`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to resolve alert');
}

export async function fetchPlannerRanked(): Promise<RecommendationItem[]> {
  const res = await fetch(`${API_BASE}/recommendations/planner-ranked`, { cache: 'no-store' });
  if (!res.ok) throw new Error('Failed to fetch planner recommendations');
  return res.json();
}

export async function simulateWhatIf(payload: {
  tower_id: string;
  extra_users: number;
  traffic_growth_pct: number;
  add_carrier_bandwidth: boolean;
}): Promise<any> {
  const res = await fetch(`${API_BASE}/simulation/what-if`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error('Failed to simulate what-if');
  return res.json();
}

export async function fetchPresenterStatus(): Promise<PresenterStatus> {
  const res = await fetch(`${API_BASE}/simulation/presenter/status`, { cache: 'no-store' });
  if (!res.ok) throw new Error('Failed to fetch presenter status');
  return res.json();
}

export async function activatePresenterScenario(payload: {
  scenario_id: string;
  city: string;
  auto_revert_seconds?: number;
}): Promise<PresenterStatus> {
  const res = await fetch(`${API_BASE}/simulation/presenter/activate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const errBody = await res.json().catch(() => null);
    throw new Error(errBody?.detail || 'Failed to activate presenter scenario');
  }
  return res.json();
}

export async function applyPresenterAction(): Promise<PresenterStatus> {
  const res = await fetch(`${API_BASE}/simulation/presenter/apply-action`, { method: 'POST' });
  if (!res.ok) {
    const errBody = await res.json().catch(() => null);
    throw new Error(errBody?.detail || 'Failed to apply recommended action');
  }
  return res.json();
}

export async function resetPresenterScenario(): Promise<PresenterStatus> {
  const res = await fetch(`${API_BASE}/simulation/presenter/reset`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to reset presenter scenario');
  return res.json();
}

export async function setBaselineProfile(profile: 'healthy' | 'realistic'): Promise<any> {
  const res = await fetch(`${API_BASE}/simulation/baseline-profile`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ profile }),
  });
  if (!res.ok) throw new Error('Failed to switch baseline profile');
  return res.json();
}

export async function checkCitizenArea(queryText: string = 'Mumbai'): Promise<CitizenQuality> {
  const res = await fetch(`${API_BASE}/citizen/check-area?query_text=${encodeURIComponent(queryText)}`);
  if (!res.ok) throw new Error('Failed to check citizen area network');
  return res.json();
}

export async function submitCrowdsourceMeasurement(payload: any): Promise<any> {
  const res = await fetch(`${API_BASE}/crowdsource/measure`, {
    method: 'POST',
    cache: 'no-store',
    headers: {
      'Content-Type': 'application/json',
      'Cache-Control': 'no-store',
    },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error('Failed to submit crowdsource measurement');
  return res.json();
}

export async function fetchRecentMeasurements(limit: number = 15): Promise<any[]> {
  const res = await fetch(`${API_BASE}/crowdsource/recent?limit=${limit}`, { cache: 'no-store' });
  if (!res.ok) throw new Error('Failed to fetch recent measurements');
  return res.json();
}

export async function fetchModelHealth(): Promise<any> {
  const res = await fetch(`${API_BASE}/model-health`, { cache: 'no-store' });
  if (!res.ok) throw new Error('Failed to fetch model health');
  return res.json();
}

export async function runCloudflarePipeline(): Promise<any> {
  const res = await fetch(`${API_BASE}/model-health/run-cloudflare-pipeline`, {
    method: 'POST',
    cache: 'no-store',
  });
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    throw new Error(body?.detail || 'Cloudflare Radar pipeline failed');
  }
  return body;
}

export async function fetchIncidents(): Promise<RealIncident[]> {
  const res = await fetch(`${API_BASE}/incidents`);
  if (!res.ok) throw new Error('Failed to fetch published telecom studies');
  return res.json();
}

export async function executeIncidentAction(incidentId: string, actionType: 'REPLAY_FAILURE' | 'APPLY_SOLUTION'): Promise<any> {
  const res = await fetch(`${API_BASE}/incidents/execute`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ incident_id: incidentId, action_type: actionType }),
  });
  if (!res.ok) throw new Error('Failed to execute incident action');
  return res.json();
}
