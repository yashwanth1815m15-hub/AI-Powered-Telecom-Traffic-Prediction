import React, { useEffect, useState } from 'react';
import { MapPin, BarChart3, Sliders, UserCheck, Zap, Cpu, WifiOff, Presentation, RotateCcw } from 'lucide-react';
import { Tower, NetworkHealthSummary, AlertItem, PresenterStatus } from './types/telemetry';
import {
  fetchTowers,
  fetchSummary,
  fetchAlerts,
  fetchPresenterStatus,
  acknowledgeAlert,
  resolveAlert,
  resetPresenterScenario
} from './services/api';
import { wsClient } from './services/websocket';

import { Navbar } from './components/Navbar';
import { NetworkHealthBanner } from './components/NetworkHealthBanner';
import { NocMapView } from './views/NocMapView';
import { TowerDetailDrawer } from './components/TowerDetailDrawer';
import { AlertsDrawer } from './components/AlertsDrawer';
import { PresenterModePanel } from './components/PresenterModePanel';
import { RealIncidentsModal } from './components/RealIncidentsModal';
import { PlannerView } from './views/PlannerView';
import { WhatIfLabView } from './views/WhatIfLabView';
import { CitizenPortalView } from './views/CitizenPortalView';
import { CrowdsourceMeasureView } from './views/CrowdsourceMeasureView';
import { ModelHealthView } from './views/ModelHealthView';
import { DataSourcesView } from './views/DataSourcesView';
import { translate } from './i18n/translations';

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<string>('noc');
  const [language, setLanguage] = useState<string>('en');
  const [isLive, setIsLive] = useState<boolean>(true);

  const [towers, setTowers] = useState<Tower[]>([]);
  const [summary, setSummary] = useState<NetworkHealthSummary | null>(null);
  const [alerts, setAlerts] = useState<AlertItem[]>([]);

  const [selectedTower, setSelectedTower] = useState<Tower | null>(null);
  const [isAlertsOpen, setIsAlertsOpen] = useState<boolean>(false);
  const [isIncidentsOpen, setIsIncidentsOpen] = useState<boolean>(false);
  const [isPresenterOpen, setIsPresenterOpen] = useState<boolean>(false);
  const [presenterStatus, setPresenterStatus] = useState<PresenterStatus | null>(null);
  const [secondsAgo, setSecondsAgo] = useState<number>(0);
  const [isOnline, setIsOnline] = useState<boolean>(typeof navigator !== 'undefined' ? navigator.onLine : true);

  // Keyboard shortcuts: Ctrl+Shift+D toggles Presenter Mode panel; Esc stops active demo
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key.toLowerCase() === 'd') {
        e.preventDefault();
        setIsPresenterOpen((prev) => !prev);
      } else if (e.key === 'Escape' && presenterStatus?.active) {
        e.preventDefault();
        resetPresenterScenario().then(() => loadInitialData()).catch(() => {});
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [presenterStatus?.active]);

  // Online / Offline Detection
  useEffect(() => {
    const handleOnline = () => setIsOnline(true);
    const handleOffline = () => setIsOnline(false);
    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);
    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  // Counter timer for "Updated X seconds ago"
  useEffect(() => {
    const t = setInterval(() => {
      setSecondsAgo((s) => s + 1);
    }, 1000);
    return () => clearInterval(t);
  }, []);

  // Polling fallback if WebSocket drops
  useEffect(() => {
    const pollTimer = setInterval(() => {
      if (!wsClient.isConnected || secondsAgo > 6) {
        fetchSummary().then((sum) => {
          setSummary(sum);
          setSecondsAgo(0);
        }).catch(() => {});
      }
    }, 4000);
    return () => clearInterval(pollTimer);
  }, [secondsAgo]);

  // Initial Data Load
  const loadInitialData = async () => {
    try {
      const [tList, sum, aList, pStatus] = await Promise.all([
        fetchTowers(),
        fetchSummary(),
        fetchAlerts('OPEN'),
        fetchPresenterStatus().catch(() => null)
      ]);
      setTowers(tList);
      setSummary(sum);
      setAlerts(aList);
      if (pStatus) setPresenterStatus(pStatus);
    } catch (e) {
      console.error('Error fetching initial telemetry data:', e);
    }
  };

  useEffect(() => {
    loadInitialData();

    // Connect WebSocket
    wsClient.connect();
    const unsubscribe = wsClient.subscribe((msg) => {
      if (msg.type === 'TELEMETRY_TICK') {
        setIsLive(true);
        setSecondsAgo(0);
        // Update summary (single source of truth from alert engine)
        if (msg.summary) {
          setSummary((prev) => ({
            ...(prev || {}),
            total_towers: (prev?.real_opencellid_count ?? 0) + (prev?.simulated_count ?? msg.summary.total_towers),
            simulated_count: prev?.simulated_count ?? msg.summary.total_towers,
            healthy_count: msg.summary.healthy_towers,
            at_risk_count: msg.summary.warning_towers,
            weak_coverage_count: msg.summary.weak_coverage_towers ?? 0,
            critical_count: msg.summary.critical_towers,
            outage_count: msg.summary.outage_towers ?? 0,
            baseline_healthy_count: msg.summary.baseline_healthy_towers ?? prev?.baseline_healthy_count,
            baseline_at_risk_count: msg.summary.baseline_warning_towers ?? prev?.baseline_at_risk_count,
            baseline_weak_coverage_count: msg.summary.baseline_weak_coverage_towers ?? prev?.baseline_weak_coverage_count ?? 0,
            baseline_critical_count: msg.summary.baseline_critical_towers ?? prev?.baseline_critical_count,
            demo_delta_critical: msg.summary.demo_delta_critical ?? 0,
            demo_delta_at_risk: msg.summary.demo_delta_at_risk ?? 0,
            demo_delta_weak_coverage: msg.summary.demo_delta_weak_coverage ?? 0,
            baseline_profile: msg.summary.baseline_profile || prev?.baseline_profile || 'healthy',
            active_alert_count: msg.summary.active_alert_count ?? 0,
            unread_alert_count: msg.summary.unread_alert_count ?? 0,
            demo_alert_count: msg.summary.demo_alert_count ?? 0,
            avg_fleet_load_pct: msg.summary.average_load_pct,
            simulated_time: msg.timestamp,
            simulated_time_ist: msg.timestamp_ist || prev?.simulated_time_ist,
            data_source: 'live_stream',
            headline_message: `Network health: ${msg.summary.healthy_towers} healthy, ${msg.summary.warning_towers} overloaded risk, ${msg.summary.weak_coverage_towers ?? 0} weak coverage, ${msg.summary.critical_towers} critical`
          }));
        }

        if (msg.presenter) {
          setPresenterStatus((prev) => ({
            ...(prev || {
              target_tower_ids: [],
              checklist: [],
              available_scenarios: []
            }),
            ...msg.presenter
          }));
        }

        // Update towers load, throughput & alert-derived status
        if (msg.readings && Array.isArray(msg.readings)) {
          const map = new Map<string, any>(msg.readings.map((r: any) => [r.tower_id, r]));
          setTowers((prev) =>
            prev.map((t) => {
              const live = map.get(t.tower_id);
              if (!live) return t;
              return {
                ...t,
                current_load_pct: live.load_pct,
                active_users: live.active_users,
                throughput_mbps: live.throughput_mbps,
                rsrp_dbm: live.rsrp_dbm,
                status: live.status
              };
            })
          );

          // Update selected tower if currently open in drawer
          setSelectedTower((curr) => {
            if (!curr) return null;
            const updated = map.get(curr.tower_id);
            if (!updated) return curr;
            return {
              ...curr,
              current_load_pct: updated.load_pct,
              active_users: updated.active_users,
              throughput_mbps: updated.throughput_mbps,
              rsrp_dbm: updated.rsrp_dbm,
              status: updated.status
            };
          });
        }

        // Sync alerts feed cleanly when new alerts open or hysteresis auto-resolves
        if (
          (msg.new_alerts && Array.isArray(msg.new_alerts) && msg.new_alerts.length > 0) ||
          (msg.auto_resolved && Array.isArray(msg.auto_resolved) && msg.auto_resolved.length > 0)
        ) {
          fetchAlerts('OPEN').then(setAlerts).catch(() => {});
        }
      }
    });

    return () => {
      unsubscribe();
    };
  }, []);

  // Ensure alerts & towers resync cleanly whenever demo transitions active <-> baseline or mitigation applies
  useEffect(() => {
    if (!presenterStatus) return;
    fetchAlerts('OPEN').then(setAlerts).catch(() => {});
  }, [presenterStatus?.active, presenterStatus?.mitigation_applied, presenterStatus?.scenario_id]);

  // Pan map and open tower detail
  const handleSelectTowerAndFly = (towerId: string) => {
    const found = towers.find((t) => t.tower_id === towerId);
    if (found) {
      setSelectedTower(found);
      setActiveTab('noc');
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col font-sans pb-16 md:pb-0">
      {/* Offline Alert Banner */}
      {!isOnline && (
        <div className="bg-amber-500 text-black px-4 py-2 text-xs font-bold text-center flex items-center justify-center space-x-2 shadow-md z-50">
          <WifiOff className="w-4 h-4 text-black" />
          <span>{translate(language, 'offline_banner')}</span>
        </div>
      )}

      {/* Top Navbar */}
      <Navbar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        unreadAlertCount={summary?.unread_alert_count ?? alerts.filter((a) => a.status === 'ACTIVE').length}
        openAlertsDrawer={() => setIsAlertsOpen(true)}
        language={language}
        setLanguage={setLanguage}
        isLive={isLive}
        secondsAgo={secondsAgo}
        presenterActive={Boolean(presenterStatus?.active)}
        onTogglePresenter={() => setIsPresenterOpen((p) => !p)}
      />

      {/* Persistent Demo Scenario Banner on EVERY page */}
      {presenterStatus?.active && (
        <div
          data-testid="global-demo-banner"
          className="bg-amber-500/95 text-black px-4 py-2 text-xs font-bold flex flex-wrap items-center justify-between gap-2 shadow-md z-40"
        >
          <div className="flex items-center space-x-2 flex-wrap gap-y-1">
            <Presentation className="w-4 h-4 text-black flex-shrink-0" />
            <span>
              {translate(language, 'demo_banner_prefix')}:{' '}
              <strong>{presenterStatus.scenario_title}</strong>, {presenterStatus.city} •{' '}
              {translate(language, 'demo_affected_sites', {
                count: presenterStatus.affected_site_count ?? presenterStatus.target_tower_ids.length
              })}{' '}
              •{' '}
              {translate(language, 'demo_ends_in', {
                time: `${Math.floor(presenterStatus.seconds_remaining / 60)}:${String(
                  presenterStatus.seconds_remaining % 60
                ).padStart(2, '0')}`
              })}
            </span>
            {presenterStatus.target_tower_ids.length > 0 && (
              <span className="text-[10px] font-mono bg-black/15 px-2 py-0.5 rounded max-w-md truncate" title={presenterStatus.target_tower_ids.join(', ')}>
                [{presenterStatus.target_tower_ids.slice(0, 6).join(', ')}{presenterStatus.target_tower_ids.length > 6 ? `, +${presenterStatus.target_tower_ids.length - 6}` : ''}]
              </span>
            )}
          </div>
          <div className="flex items-center space-x-2">
            <span className="hidden sm:inline text-[10px] font-mono bg-black/15 px-2 py-0.5 rounded">
              {translate(language, 'demo_esc_hint')}
            </span>
            <button
              onClick={() => setIsPresenterOpen(true)}
              className="px-2.5 py-1 rounded-lg bg-black/15 hover:bg-black/25 text-black text-[11px] font-bold cursor-pointer"
            >
              {translate(language, 'demo_open_panel')}
            </button>
            <button
              onClick={() => resetPresenterScenario().then(() => loadInitialData())}
              data-testid="global-stop-demo-btn"
              className="px-3 py-1 rounded-lg bg-red-600 hover:bg-red-500 text-white text-[11px] font-extrabold flex items-center space-x-1 shadow-sm cursor-pointer"
            >
              <RotateCcw className="w-3 h-3" />
              <span>{translate(language, 'demo_stop_button')}</span>
            </button>
          </div>
        </div>
      )}

      {/* Network Health 5-Second Banner */}
      <NetworkHealthBanner
        summary={summary}
        onOpenRealIncidents={() => setIsIncidentsOpen(true)}
        language={language}
        onBaselineProfileChanged={loadInitialData}
      />

      {/* Main Tab Content */}
      <main className="flex-1 overflow-x-hidden">
        {activeTab === 'noc' && (
          <NocMapView
            towers={towers}
            onSelectTower={(t) => setSelectedTower(t)}
            selectedTowerId={selectedTower?.tower_id}
            language={language}
            presenterStatus={presenterStatus}
          />
        )}

        {activeTab === 'planner' && <PlannerView language={language} />}

        {activeTab === 'whatif' && <WhatIfLabView towers={towers} language={language} />}

        {activeTab === 'citizen' && <CitizenPortalView language={language} />}

        {activeTab === 'measure' && <CrowdsourceMeasureView language={language} />}

        {activeTab === 'model' && <ModelHealthView language={language} />}

        {activeTab === 'sources' && <DataSourcesView language={language} summary={summary} />}
      </main>

      {/* Tower Detail Drawer */}
      <TowerDetailDrawer
        tower={selectedTower}
        onClose={() => setSelectedTower(null)}
        language={language}
      />

      {/* Alerts Feed Drawer */}
      <AlertsDrawer
        isOpen={isAlertsOpen}
        onClose={() => setIsAlertsOpen(false)}
        alerts={alerts}
        onAcknowledge={async (id) => {
          await acknowledgeAlert(id);
          await loadInitialData();
        }}
        onResolve={async (id) => {
          await resolveAlert(id);
          await loadInitialData();
        }}
        onSelectTowerId={handleSelectTowerAndFly}
        language={language}
      />

      {/* Presenter Mode Control Drawer (Ctrl+Shift+D) */}
      <PresenterModePanel
        isOpen={isPresenterOpen}
        onClose={() => setIsPresenterOpen(false)}
        status={presenterStatus}
        towers={towers}
        onStateChanged={loadInitialData}
        language={language}
      />

      {/* Published Telecom Event Studies & Root-Cause Analysis Modal */}
      <RealIncidentsModal
        isOpen={isIncidentsOpen}
        onClose={() => setIsIncidentsOpen(false)}
        onSelectTowerAndFly={(tId) => {
          handleSelectTowerAndFly(tId);
          setIsIncidentsOpen(false);
        }}
        language={language}
      />

      {/* Mobile Bottom Navigation Bar (< md) */}
      <div className="md:hidden fixed bottom-0 left-0 right-0 z-40 bg-black/90 backdrop-blur-2xl border-t border-white/[0.08] px-2 py-2 flex items-center justify-around">
        <button
          onClick={() => setActiveTab('noc')}
          className={`flex flex-col items-center space-y-1 p-1 text-xs font-semibold ${activeTab === 'noc' ? 'text-cyan-400' : 'text-zinc-400'}`}
        >
          <MapPin className="w-5 h-5" />
          <span className="text-[10px]">Map</span>
        </button>
        <button
          onClick={() => setActiveTab('planner')}
          className={`flex flex-col items-center space-y-1 p-1 text-xs font-semibold ${activeTab === 'planner' ? 'text-cyan-400' : 'text-zinc-400'}`}
        >
          <BarChart3 className="w-5 h-5" />
          <span className="text-[10px]">Planner</span>
        </button>
        <button
          onClick={() => setActiveTab('whatif')}
          className={`flex flex-col items-center space-y-1 p-1 text-xs font-semibold ${activeTab === 'whatif' ? 'text-cyan-400' : 'text-zinc-400'}`}
        >
          <Sliders className="w-5 h-5" />
          <span className="text-[10px]">What-If</span>
        </button>
        <button
          onClick={() => setActiveTab('citizen')}
          className={`flex flex-col items-center space-y-1 p-1 text-xs font-semibold ${activeTab === 'citizen' ? 'text-cyan-400' : 'text-zinc-400'}`}
        >
          <UserCheck className="w-5 h-5" />
          <span className="text-[10px]">Citizen</span>
        </button>
        <button
          onClick={() => setActiveTab('measure')}
          className={`flex flex-col items-center space-y-1 p-1 text-xs font-semibold ${activeTab === 'measure' ? 'text-cyan-400' : 'text-zinc-400'}`}
        >
          <Zap className="w-5 h-5" />
          <span className="text-[10px]">Speed</span>
        </button>
        <button
          onClick={() => setActiveTab('model')}
          className={`flex flex-col items-center space-y-1 p-1 text-xs font-semibold ${activeTab === 'model' ? 'text-cyan-400' : 'text-zinc-400'}`}
        >
          <Cpu className="w-5 h-5" />
          <span className="text-[10px]">AI Health</span>
        </button>
      </div>
    </div>
  );
};

export default App;

