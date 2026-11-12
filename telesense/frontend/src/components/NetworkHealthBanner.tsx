import React, { useState } from 'react';
import { NetworkHealthSummary } from '../types/telemetry';
import { Radio, AlertOctagon, Database } from 'lucide-react';
import { formatIstTime } from '../utils/indiaFormat';
import { setBaselineProfile } from '../services/api';
import { translate } from '../i18n/translations';

interface BannerProps {
  summary: NetworkHealthSummary | null;
  onOpenRealIncidents?: () => void;
  language: string;
  onBaselineProfileChanged?: () => void;
}

export const NetworkHealthBanner: React.FC<BannerProps> = ({
  summary,
  onOpenRealIncidents,
  language,
  onBaselineProfileChanged,
}) => {
  const [dataSource, setDataSource] = useState<'simulated' | 'radar' | 'operator'>('simulated');
  const [showOperatorInfo, setShowOperatorInfo] = useState<boolean>(false);
  const [switchingProfile, setSwitchingProfile] = useState<boolean>(false);

  if (!summary) return null;

  const activeProfile = summary.baseline_profile === 'realistic' ? 'realistic' : 'healthy';
  const baseCritical = summary.baseline_critical_count ?? summary.critical_count;
  const demoDeltaCritical = summary.demo_delta_critical ?? 0;
  const baseWeakCov = summary.baseline_weak_coverage_count ?? (summary.weak_coverage_count ?? 0);
  const demoDeltaWeakCov = summary.demo_delta_weak_coverage ?? 0;
  const baseAtRisk = summary.baseline_at_risk_count ?? summary.at_risk_count;
  const demoDeltaAtRisk = summary.demo_delta_at_risk ?? 0;

  const handleProfileSwitch = async (profile: 'healthy' | 'realistic') => {
    if (switchingProfile || profile === activeProfile) return;
    setSwitchingProfile(true);
    try {
      await setBaselineProfile(profile);
      onBaselineProfileChanged?.();
    } catch (err) {
      console.error(err);
    } finally {
      setSwitchingProfile(false);
    }
  };

  return (
    <div className="bg-black/70 backdrop-blur-xl border-b border-white/[0.06] px-4 py-2.5 space-y-2">
      {/* Top Banner: Mode Notice, Data Source Toggle, Baseline Toggle, and Real Measurements Counter */}
      <div className="max-w-7xl mx-auto flex items-center justify-between flex-wrap gap-2.5 pt-0.5 pb-1 border-b border-white/[0.04]">
        <div className="flex items-center space-x-2 text-xs flex-wrap gap-y-1">
          <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse inline-block" />
          <span className="text-zinc-200 font-medium">
            {translate(language, 'sim_notice')}
          </span>
          <span className="px-2 py-0.5 rounded bg-amber-500/15 border border-amber-500/30 text-amber-300 font-mono text-[9px] font-bold">
            {translate(language, 'badge_simulated_load')}
          </span>
        </div>

        {/* Right side: Source Toggle, Baseline Profile Switch, and Real Measurements Counter */}
        <div className="flex items-center space-x-2.5 flex-wrap gap-2">
          {/* Baseline Switch: Healthy baseline (default 0 flagged) vs Realistic baseline (SIMULATED) */}
          <div className="flex items-center space-x-1 bg-white/[0.05] p-1 rounded-full border border-white/[0.08]">
            <span className="text-[10px] text-zinc-400 px-2 font-mono">
              {translate(language, 'baseline_switch_label')}
            </span>
            <button
              onClick={() => handleProfileSwitch('healthy')}
              disabled={switchingProfile}
              className={`px-2 py-0.5 rounded-full text-[10px] font-mono font-bold transition-all cursor-pointer ${
                activeProfile === 'healthy'
                  ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                  : 'text-zinc-400 hover:text-white'
              }`}
              title="Healthy simulated baseline (0 flagged sites by default)"
            >
              {translate(language, 'baseline_healthy')}
            </button>
            <button
              onClick={() => handleProfileSwitch('realistic')}
              disabled={switchingProfile}
              className={`px-2 py-0.5 rounded-full text-[10px] font-mono font-bold transition-all cursor-pointer ${
                activeProfile === 'realistic'
                  ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                  : 'text-zinc-400 hover:text-white'
              }`}
              title="Realistic simulated baseline (rural weak-coverage cells present)"
            >
              {translate(language, 'baseline_realistic')}
            </button>
            <span className="text-[8px] font-mono px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-300 border border-amber-500/20">
              {translate(language, 'baseline_simulated_tag')}
            </span>
          </div>

          <div className="flex items-center space-x-1 bg-white/[0.05] p-1 rounded-full border border-white/[0.08]">
            <span className="text-[10px] text-zinc-400 px-2 font-mono flex items-center space-x-1">
              <Database className="w-3 h-3 text-cyan-400 inline" />
              <span>{translate(language, 'source_label')}</span>
            </span>
            <button
              onClick={() => setDataSource('simulated')}
              className={`px-2.5 py-0.5 rounded-full text-[10px] font-mono font-bold transition-all cursor-pointer ${
                dataSource === 'simulated'
                  ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 shadow-sm'
                  : 'text-zinc-400 hover:text-white'
              }`}
            >
              {translate(language, 'source_india_sim')}
            </button>
            <button
              onClick={() => setDataSource('radar')}
              className={`px-2.5 py-0.5 rounded-full text-[10px] font-mono font-bold transition-all cursor-pointer ${
                dataSource === 'radar'
                  ? 'bg-purple-500/20 text-purple-300 border border-purple-500/40 shadow-sm'
                  : 'text-zinc-400 hover:text-white'
              }`}
              title="Relative web traffic (Cloudflare Radar), not tower load"
            >
              {translate(language, 'source_cloudflare_radar')}
            </button>
            <div className="relative">
              <button
                onClick={() => setShowOperatorInfo(!showOperatorInfo)}
                className={`px-2.5 py-0.5 rounded-full text-[10px] font-mono font-bold transition-all flex items-center space-x-1 cursor-pointer ${
                  showOperatorInfo
                    ? 'bg-zinc-800 text-zinc-200 border border-zinc-700'
                    : 'text-zinc-500 hover:text-zinc-300'
                }`}
              >
                <span>{translate(language, 'source_operator_feed')}</span>
                <span className="text-[8px] bg-zinc-800/80 text-zinc-400 px-1 rounded border border-white/5">
                  {translate(language, 'source_not_connected')}
                </span>
              </button>
              {showOperatorInfo && (
                <div className="absolute right-0 top-full mt-2 w-72 p-3 rounded-xl bg-zinc-950 border border-white/10 shadow-2xl text-[11px] text-zinc-300 z-50">
                  <div className="flex items-center justify-between mb-1">
                    <strong className="text-white font-bold">
                      {translate(language, 'source_operator_feed')} ({translate(language, 'source_not_connected')})
                    </strong>
                    <button onClick={() => setShowOperatorInfo(false)} className="text-zinc-400 hover:text-white text-xs px-1">
                      ✕
                    </button>
                  </div>
                  <p className="text-zinc-400 leading-relaxed">
                    Live Indian operator integration requires enterprise 3GPP Northbound / OSS credentials (Jio, Airtel, Vi, BSNL). Disconnected in local mode.
                  </p>
                </div>
              )}
            </div>
          </div>

          <div className="apple-pill px-3 py-1 flex items-center space-x-1.5 bg-emerald-500/10 border-emerald-500/25">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
            <span className="text-[10px] text-emerald-300 font-semibold uppercase">
              {translate(language, 'real_mobile_tests')}
            </span>
            <span className="text-xs font-bold text-emerald-400 font-mono">
              {summary.real_measurements_count ?? 0}
            </span>
          </div>
        </div>
      </div>

      {/* Main Network Status Row (Single Source of Truth from Open Alerts) */}
      <div className="max-w-7xl mx-auto flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center space-x-3">
          <div className="p-2 rounded-xl bg-cyan-500/10 border border-cyan-500/20 text-cyan-400">
            <Radio className="w-4 h-4 animate-pulse" />
          </div>
          <div>
            <h2 className="text-xs sm:text-sm font-bold text-white tracking-tight flex items-center space-x-2">
              <span>
                {translate(language, 'network_headline', {
                  healthy: summary.healthy_count,
                  risk: summary.at_risk_count,
                  weak: summary.weak_coverage_count ?? 0,
                  critical: summary.critical_count,
                })}
              </span>
            </h2>
            <p className="text-[11px] text-zinc-400 font-mono">
              {dataSource === 'radar'
                ? translate(language, 'radar_diurnal_line')
                : translate(language, 'fleet_summary_line', {
                    time: formatIstTime(summary.simulated_time),
                    simulated: summary.simulated_count ?? summary.total_towers,
                    clusters: summary.opencellid_cluster_count ?? 0,
                  })}
            </p>
          </div>
        </div>

        {/* Single-Source-of-Truth Metrics with baseline + (+N demo) breakdown */}
        <div className="flex items-center space-x-2 flex-wrap gap-y-1">
          <div className="apple-pill px-3 py-1 flex items-center space-x-1.5">
            <span className="text-xs font-bold text-white font-mono">
              {summary.total_towers.toLocaleString()} {translate(language, 'cell_records_label')}
              <span className="text-[10px] text-zinc-400 font-normal ml-1">
                ({(summary.real_opencellid_count || 0).toLocaleString()} OpenCellID, {summary.simulated_count ?? summary.total_towers} {translate(language, 'simulated_short')})
              </span>
            </span>
          </div>

          <div className="apple-pill px-3 py-1 flex items-center space-x-1.5 bg-emerald-500/10 border-emerald-500/20">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
            <span className="text-[10px] text-emerald-300 font-semibold uppercase">{translate(language, 'status_healthy')}</span>
            <span className="text-xs font-bold text-emerald-400 font-mono">{summary.healthy_count}</span>
          </div>

          <div className="apple-pill px-3 py-1 flex items-center space-x-1.5 bg-amber-500/10 border-amber-500/20">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
            <span className="text-[10px] text-amber-300 font-semibold uppercase">{translate(language, 'status_at_risk')}</span>
            <span className="text-xs font-bold text-amber-400 font-mono" data-testid="header-at-risk-count">
              {demoDeltaAtRisk > 0 ? `${baseAtRisk} (+${demoDeltaAtRisk} demo)` : summary.at_risk_count}
            </span>
          </div>

          {(baseWeakCov > 0 || demoDeltaWeakCov > 0) && (
            <div className="apple-pill px-3 py-1 flex items-center space-x-1.5 bg-yellow-500/10 border-yellow-500/20">
              <span className="w-1.5 h-1.5 rounded-full bg-yellow-400" />
              <span className="text-[10px] text-yellow-300 font-semibold uppercase">{translate(language, 'status_weak_coverage')}</span>
              <span className="text-xs font-bold text-yellow-400 font-mono" data-testid="header-weak-cov-count">
                {demoDeltaWeakCov > 0 ? `${baseWeakCov} (+${demoDeltaWeakCov} demo)` : baseWeakCov}
              </span>
            </div>
          )}

          <div className="apple-pill px-3 py-1 flex items-center space-x-1.5 bg-red-500/10 border-red-500/20">
            <span className="w-1.5 h-1.5 rounded-full bg-red-400" />
            <span className="text-[10px] text-red-300 font-semibold uppercase">{translate(language, 'status_critical')}</span>
            <span className="text-xs font-bold text-red-400 font-mono" data-testid="header-critical-count">
              {demoDeltaCritical > 0 ? `${baseCritical} (+${demoDeltaCritical} demo)` : summary.critical_count}
            </span>
          </div>

          <div className="apple-pill px-3 py-1 flex items-center space-x-1.5">
            <span className="text-[10px] text-zinc-400 uppercase font-semibold">{translate(language, 'fleet_load')}</span>
            <span className="text-xs font-bold text-cyan-400 font-mono">{summary.avg_fleet_load_pct}%</span>
          </div>

          {onOpenRealIncidents && (
            <button
              onClick={onOpenRealIncidents}
              className="flex items-center space-x-1.5 px-3.5 py-1 rounded-full bg-purple-500/15 hover:bg-purple-500/25 border border-purple-500/35 text-purple-200 hover:text-white text-[11px] font-bold shadow-lg shadow-purple-500/15 transition-all cursor-pointer"
              title="Real Published Indian Telecom Case Studies"
            >
              <Radio className="w-3.5 h-3.5 text-purple-400 animate-pulse" />
              <span>{translate(language, 'documented_events_btn')}</span>
              <span className="px-1.5 py-0.2 bg-purple-500/30 rounded-full text-[9px] font-bold text-purple-200">
                2
              </span>
            </button>
          )}
        </div>
      </div>

      {(summary.real_opencellid_count ?? 0) === 0 && (
        <div className="max-w-7xl mx-auto px-3 py-1.5 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-200 text-xs flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <AlertOctagon className="w-4 h-4 text-amber-400 shrink-0" />
            <span>
              <strong>OpenCellID Setup Notice:</strong> 0 OpenCellID records imported. Set{' '}
              <code className="bg-black/40 px-1 py-0.5 rounded text-amber-300 font-mono">OPENCELLID_API_KEY</code> in{' '}
              <code className="text-zinc-300 font-mono">backend/.env</code>.
            </span>
          </div>
        </div>
      )}
    </div>
  );
};
