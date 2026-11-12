import React, { useEffect, useMemo, useState } from 'react';
import { PresenterStatus, Tower } from '../types/telemetry';
import {
  activatePresenterScenario,
  applyPresenterAction,
  resetPresenterScenario
} from '../services/api';
import { translate } from '../i18n/translations';
import {
  X,
  Presentation,
  Play,
  RotateCcw,
  Wrench,
  CheckCircle2,
  MapPin,
  Clock,
  ArrowRight,
  ExternalLink,
  AlertTriangle
} from 'lucide-react';

interface PresenterModePanelProps {
  isOpen: boolean;
  onClose: () => void;
  status: PresenterStatus | null;
  towers: Tower[];
  onStateChanged: () => void;
  language: string;
}

const DEFAULT_SCENARIOS = [
  {
    id: 'ipl_surge',
    title_key: 'scen_ipl_title',
    sub_key: 'scen_ipl_sub',
    title: 'IPL Match-Night Surge',
    subtitle: 'Stadium catchment concurrency spike (4K streaming & social uploads, load 90–98%)',
    inspired_by: 'Opensignal Indian Cricket Stadiums Report (May 2023)',
    source_url: 'https://economictimes.indiatimes.com/industry/telecom/telecom-news/eden-gardens-tops-in-5g-download-speeds-this-ipl-open-signal/articleshow/100425243.cms',
    recommended_action: 'ADD BANDWIDTH (CARRIER AGGREGATION) & STAGE CELL-ON-WHEELS'
  },
  {
    id: 'diwali_surge',
    title_key: 'scen_diwali_title',
    sub_key: 'scen_diwali_sub',
    title: 'Festival Night Surge (Diwali)',
    subtitle: 'City-wide evening surge (19:00–22:30 IST) raising macro load cleanly',
    inspired_by: 'Generic simulation, no external source',
    source_url: null,
    recommended_action: 'ADD BANDWIDTH (CARRIER AGGREGATION)'
  },
  {
    id: 'rural_coverage_hole',
    title_key: 'scen_rural_title',
    sub_key: 'scen_rural_sub',
    title: 'Rural Coverage Hole (Weak Signal, Low Load)',
    subtitle: 'Cell-edge signal shadow (~-118 dBm RSRP) with moderate traffic load (~28%)',
    inspired_by: 'Generic simulation, no external source',
    source_url: null,
    recommended_action: 'BUILD LOW-COST SMALL CELL / REPEATER'
  },
  {
    id: 'fiber_cut_outage',
    title_key: 'scen_fiber_title',
    sub_key: 'scen_fiber_sub',
    title: 'Fibre Cut / Outage',
    subtitle: 'Sudden transport break causing sector traffic collapse (< 3% load outage)',
    inspired_by: 'Generic simulation, no external source',
    source_url: null,
    recommended_action: 'REPAIR BACKHAUL & REROUTE NEIGHBOR TRAFFIC'
  },
  {
    id: 'cyclone_backhaul',
    title_key: 'scen_cyclone_title',
    sub_key: 'scen_cyclone_sub',
    title: 'Cyclone / Heavy-Rain Backhaul Failure',
    subtitle: 'Multi-site coastal backhaul isolation causing simultaneous sector outages',
    inspired_by: 'Generic simulation, no external source',
    source_url: null,
    recommended_action: 'RESTORE BACKHAUL & ENABLE ICR DISASTER ROAMING'
  },
  {
    id: 'mela_gathering',
    title_key: 'scen_mela_title',
    sub_key: 'scen_mela_sub',
    title: 'Mela-Style Crowd Gathering',
    subtitle: 'Extreme local congregation surge overloading PRBs & collapsing throughput',
    inspired_by: 'Maha Kumbh 2025 Network Telemetry (Jio & Ericsson / Ookla)',
    source_url: 'https://www.ookla.com/articles/5g-maha-kumbh-feb25',
    statement_url: 'https://telecom.economictimes.indiatimes.com/news/industry/maha-kumbh-2025-ericsson-says-enabled-jio-5g-network-to-handle-400-mn-data-service-requests-at-peak/118603781',
    recommended_action: 'DEPLOY TEMPORARY CELL-ON-WHEELS (CoW) & RE-TUNE QoS'
  }
];

const SCENARIO_KEYS: Record<string, { title_key: string; sub_key: string }> = {
  ipl_surge: { title_key: 'scen_ipl_title', sub_key: 'scen_ipl_sub' },
  diwali_surge: { title_key: 'scen_diwali_title', sub_key: 'scen_diwali_sub' },
  rural_coverage_hole: { title_key: 'scen_rural_title', sub_key: 'scen_rural_sub' },
  fiber_cut_outage: { title_key: 'scen_fiber_title', sub_key: 'scen_fiber_sub' },
  cyclone_backhaul: { title_key: 'scen_cyclone_title', sub_key: 'scen_cyclone_sub' },
  mela_gathering: { title_key: 'scen_mela_title', sub_key: 'scen_mela_sub' },
};

function formatCountdown(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds));
  const mm = Math.floor(s / 60);
  const ss = s % 60;
  return `${String(mm).padStart(2, '0')}:${String(ss).padStart(2, '0')}`;
}

export const PresenterModePanel: React.FC<PresenterModePanelProps> = ({
  isOpen,
  onClose,
  status,
  towers,
  onStateChanged,
  language
}) => {
  const availableCities = useMemo(() => {
    const citySet = new Set<string>();
    towers.forEach((t) => {
      if (t.city) citySet.add(t.city);
    });
    return Array.from(citySet).sort();
  }, [towers]);

  const [selectedScenario, setSelectedScenario] = useState<string>('ipl_surge');
  const [selectedCity, setSelectedCity] = useState<string>('');
  const [autoRevertMinutes, setAutoRevertMinutes] = useState<number>(10);
  const [busy, setBusy] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    if (!selectedCity && availableCities.length > 0) {
      setSelectedCity(availableCities.includes('Mumbai') ? 'Mumbai' : availableCities[0]);
    }
  }, [availableCities, selectedCity]);

  useEffect(() => {
    if (status?.active && status.scenario_id) {
      setSelectedScenario(status.scenario_id);
      if (status.city) setSelectedCity(status.city);
    }
  }, [status?.active, status?.scenario_id, status?.city]);

  if (!isOpen) return null;

  const scenarios = status?.available_scenarios?.length
    ? status.available_scenarios
    : DEFAULT_SCENARIOS;

  const handleActivate = async (cityOverride?: string) => {
    const targetCity = cityOverride ?? selectedCity;
    if (!targetCity) return;
    setBusy(true);
    setErrorMsg(null);
    try {
      await activatePresenterScenario({
        scenario_id: selectedScenario,
        city: targetCity,
        auto_revert_seconds: autoRevertMinutes * 60
      });
      onStateChanged();
    } catch (err: any) {
      setErrorMsg(err?.message || translate(language, 'error_generic'));
    } finally {
      setBusy(false);
    }
  };

  const handleApplyAction = async () => {
    setBusy(true);
    setErrorMsg(null);
    try {
      await applyPresenterAction();
      onStateChanged();
    } catch (err: any) {
      setErrorMsg(err?.message || translate(language, 'error_generic'));
    } finally {
      setBusy(false);
    }
  };

  const handleReset = async () => {
    setBusy(true);
    setErrorMsg(null);
    try {
      await resetPresenterScenario();
      onStateChanged();
    } catch (err: any) {
      setErrorMsg(err?.message || translate(language, 'error_generic'));
    } finally {
      setBusy(false);
    }
  };

  const affectedSites = status?.affected_sites || [];
  const curve = status?.before_after_curve || [];

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/70 backdrop-blur-sm animate-in fade-in">
      <div className="w-full max-w-xl bg-zinc-950/95 backdrop-blur-2xl border-l border-amber-500/25 h-full flex flex-col shadow-2xl text-white">
        {/* Header */}
        <div className="p-4 sm:p-5 border-b border-white/[0.08] flex items-center justify-between bg-amber-950/20">
          <div className="flex items-center space-x-3">
            <div className="p-2.5 rounded-2xl bg-amber-500/20 text-amber-300 border border-amber-500/35">
              <Presentation className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h2 className="text-base font-bold text-white tracking-tight">
                  {translate(language, 'presenter_title')}
                </h2>
                <span className="text-[9px] font-mono px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/30 font-bold">
                  Ctrl+Shift+D
                </span>
              </div>
              <p className="text-xs text-zinc-400">
                {translate(language, 'presenter_subtitle')}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="apple-pill p-2 text-zinc-400 hover:text-white hover:bg-white/10 transition-colors cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Sticky Top Safety Control: Baseline / Demo switch + Stop demo and restore original view */}
        <div className="sticky top-0 z-20 px-4 py-2.5 bg-zinc-900/95 border-b border-white/10 flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center space-x-1 bg-black/50 p-1 rounded-full border border-white/10">
            <span className="text-[10px] font-mono text-zinc-400 px-2">
              {translate(language, 'presenter_view_switch')}:
            </span>
            <button
              onClick={handleReset}
              disabled={busy || !status?.active}
              className={`px-2.5 py-0.5 rounded-full text-[10px] font-mono font-bold transition-all cursor-pointer ${
                !status?.active
                  ? 'bg-emerald-500/25 text-emerald-300 border border-emerald-500/40'
                  : 'text-zinc-400 hover:text-white'
              }`}
            >
              {translate(language, 'presenter_mode_baseline')}
            </button>
            <button
              onClick={() => handleActivate()}
              disabled={busy || !selectedCity}
              className={`px-2.5 py-0.5 rounded-full text-[10px] font-mono font-bold transition-all cursor-pointer ${
                status?.active
                  ? 'bg-amber-500/25 text-amber-300 border border-amber-500/40'
                  : 'text-zinc-400 hover:text-white'
              }`}
            >
              {translate(language, 'presenter_mode_demo')}
            </button>
          </div>

          <button
            onClick={handleReset}
            disabled={busy || !status?.active}
            data-testid="sticky-stop-demo-btn"
            className="px-3 py-1.5 rounded-xl bg-red-600 hover:bg-red-500 disabled:bg-zinc-800 disabled:text-zinc-500 text-white text-[11px] font-bold flex items-center space-x-1.5 cursor-pointer transition-all"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            <span>{translate(language, 'presenter_stop_sticky')}</span>
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-5 space-y-5">
          {/* Active Banner Status */}
          {status?.active && (
            <div className="p-4 rounded-2xl bg-amber-500/15 border border-amber-500/40 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-mono font-bold uppercase text-amber-300 flex items-center space-x-1.5">
                  <AlertTriangle className="w-3.5 h-3.5" />
                  <span>{status.banner_label || translate(language, 'demo_banner_prefix')}</span>
                </span>
                <span className="text-[11px] font-mono font-bold text-white flex items-center space-x-1">
                  <Clock className="w-3 h-3 text-amber-300" />
                  <span>{formatCountdown(status.seconds_remaining)}</span>
                </span>
              </div>

              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="text-sm font-bold text-white">
                  {status.scenario_title} — {status.city}
                </div>
                <span className="px-2 py-0.5 rounded-full bg-black/50 border border-amber-400/30 text-[10px] font-mono text-amber-200 font-bold">
                  {translate(language, 'demo_affected_sites', {
                    count: status.affected_site_count ?? affectedSites.length
                  })}
                </span>
              </div>

              {/* Affected Sites Chips */}
              {affectedSites.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {affectedSites.map((s) => (
                    <span
                      key={s.tower_id}
                      className="px-2 py-0.5 rounded-lg bg-black/50 border border-white/10 text-[10px] font-mono text-zinc-200"
                    >
                      {s.tower_id} • {s.name}
                    </span>
                  ))}
                </div>
              )}

              {/* Source & Statement Attribution */}
              <div className="text-[11px] text-zinc-300 flex flex-wrap items-center gap-2">
                <span>{status.inspired_by || translate(language, 'presenter_generic_source')}</span>
                {status.source_url && (
                  <a
                    href={status.source_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center space-x-1 text-cyan-300 hover:text-cyan-200 underline font-mono text-[10px]"
                  >
                    <ExternalLink className="w-3 h-3" />
                    <span>{translate(language, 'presenter_source_link')}</span>
                  </a>
                )}
                {status.statement_url && (
                  <a
                    href={status.statement_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center space-x-1 text-emerald-300 hover:text-emerald-200 underline font-mono text-[10px]"
                  >
                    <ExternalLink className="w-3 h-3" />
                    <span>{translate(language, 'presenter_statement_link')}</span>
                  </a>
                )}
              </div>

              {/* What to do now Checklist */}
              {status.checklist && status.checklist.length > 0 && (
                <div className="pt-2 border-t border-amber-500/20 space-y-1.5">
                  <span className="text-[10px] font-mono font-bold uppercase text-amber-200">
                    {translate(language, 'presenter_checklist_title')}
                  </span>
                  {status.checklist.map((step, i) => (
                    <div key={i} className="text-xs text-zinc-100 flex items-start space-x-2">
                      <CheckCircle2 className="w-3.5 h-3.5 text-amber-300 flex-shrink-0 mt-0.5" />
                      <span>{step}</span>
                    </div>
                  ))}
                </div>
              )}

              {/* Before / After Impact Delta */}
              {status.before_snapshot && (
                <div className="grid grid-cols-2 gap-2.5 pt-2">
                  <div className="p-2.5 rounded-xl bg-black/50 border border-white/10">
                    <span className="text-[9px] font-mono uppercase text-zinc-400 block">
                      {translate(language, 'presenter_before_action')}
                    </span>
                    <div className="text-sm font-black font-mono text-red-400 mt-0.5">
                      {Number(status.before_snapshot.scenario_peak_load_pct ?? 0).toFixed(1)}% Load
                    </div>
                    <div className="text-[10px] font-mono text-zinc-400">
                      {Number(status.before_snapshot.scenario_throughput_mbps ?? 0).toFixed(1)} Mbps • {Number(status.before_snapshot.scenario_rsrp_dbm ?? 0).toFixed(1)} dBm
                    </div>
                  </div>
                  <div className="p-2.5 rounded-xl bg-black/50 border border-emerald-500/25">
                    <span className="text-[9px] font-mono uppercase text-emerald-300 block">
                      {status.mitigation_applied
                        ? translate(language, 'presenter_after_action')
                        : translate(language, 'presenter_projected_after')}
                    </span>
                    {status.after_snapshot ? (
                      <>
                        <div className="text-sm font-black font-mono text-emerald-400 mt-0.5">
                          {Number(status.after_snapshot.projected_load_pct ?? 0).toFixed(1)}% Load{' '}
                          <span className="text-[10px]">
                            (−{Number(status.after_snapshot.load_drop_pct ?? 0).toFixed(1)}%)
                          </span>
                        </div>
                        <div className="text-[10px] font-mono text-emerald-200/80">
                          {Number(status.after_snapshot.projected_throughput_mbps ?? 0).toFixed(1)} Mbps • {Number(status.after_snapshot.projected_rsrp_dbm ?? 0).toFixed(1)} dBm
                        </div>
                      </>
                    ) : (
                      <div className="text-[11px] font-mono text-zinc-500 mt-1">
                        {translate(language, 'presenter_click_apply_hint')}
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Before / After Trajectory Chart */}
              {curve.length >= 2 && (
                <div className="p-3 rounded-xl bg-black/50 border border-white/10 space-y-2" data-testid="before-after-chart">
                  <div className="flex items-center justify-between flex-wrap gap-1">
                    <span className="text-[10px] font-mono uppercase text-cyan-300 font-bold">
                      {translate(language, 'presenter_before_after_chart')}
                    </span>
                    {status.capacity_assumption && (
                      <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-cyan-500/15 text-cyan-200 border border-cyan-500/30">
                        {status.capacity_assumption}
                      </span>
                    )}
                  </div>
                  <svg viewBox="0 0 360 95" className="w-full h-24 overflow-visible">
                    <line x1="25" y1="15" x2="345" y2="15" stroke="rgba(255,69,58,0.25)" strokeDasharray="3 3" />
                    <line x1="25" y1="80" x2="345" y2="80" stroke="rgba(255,255,255,0.12)" />
                    {(() => {
                      const xs = curve.map((_, idx) => 25 + (idx / Math.max(1, curve.length - 1)) * 310);
                      const ys = curve.map((p) => 80 - (Math.min(100, Math.max(0, p.load_pct)) / 100) * 65);
                      const d = xs.map((x, idx) => `${idx === 0 ? 'M' : 'L'} ${x.toFixed(1)} ${ys[idx].toFixed(1)}`).join(' ');
                      return (
                        <>
                          <path d={d} fill="none" stroke="#30d158" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
                          {curve.map((pt, idx) => (
                            <g key={pt.label}>
                              <circle cx={xs[idx]} cy={ys[idx]} r="3.5" fill={pt.load_pct >= 85 ? '#ff453a' : '#30d158'} />
                              <text x={xs[idx]} y={Math.max(10, ys[idx] - 6)} textAnchor="middle" fill="#e4e4e7" fontSize="8" fontFamily="monospace">
                                {pt.load_pct.toFixed(0)}%
                              </text>
                              <text x={xs[idx]} y="92" textAnchor="middle" fill="#71717a" fontSize="7.5" fontFamily="monospace">
                                {pt.label}
                              </text>
                            </g>
                          ))}
                        </>
                      );
                    })()}
                  </svg>
                </div>
              )}

              {/* Active Controls */}
              <div className="flex flex-wrap gap-2 pt-1">
                {!status.mitigation_applied && (
                  <button
                    onClick={handleApplyAction}
                    disabled={busy}
                    data-testid="apply-recommended-action-btn"
                    className="flex-1 py-2.5 px-3 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-black text-xs font-bold flex items-center justify-center space-x-1.5 cursor-pointer transition-all disabled:opacity-50"
                  >
                    <Wrench className="w-3.5 h-3.5" />
                    <span>{translate(language, 'presenter_apply_btn')}</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </button>
                )}
                <button
                  onClick={handleReset}
                  disabled={busy}
                  data-testid="reset-normal-btn"
                  className="py-2.5 px-3.5 rounded-xl bg-white/10 hover:bg-white/20 border border-white/15 text-white text-xs font-bold flex items-center space-x-1.5 cursor-pointer transition-all disabled:opacity-50"
                >
                  <RotateCcw className="w-3.5 h-3.5" />
                  <span>{translate(language, 'presenter_reset_btn')}</span>
                </button>
              </div>
            </div>
          )}

          {/* City + Timer Selection */}
          <div className="apple-glass p-4 rounded-2xl border border-white/[0.08] space-y-3">
            <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-300 font-mono">
              {translate(language, 'presenter_step1')}
            </h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="text-[10px] font-mono text-zinc-400 uppercase block mb-1 flex items-center space-x-1">
                  <MapPin className="w-3 h-3 text-cyan-400" />
                  <span>{translate(language, 'presenter_target_city')}</span>
                </label>
                <select
                  value={selectedCity}
                  onChange={(e) => setSelectedCity(e.target.value)}
                  className="w-full bg-black/70 border border-white/15 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-amber-400"
                >
                  {availableCities.map((c) => (
                    <option key={c} value={c} className="bg-zinc-900">
                      {c}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-[10px] font-mono text-zinc-400 uppercase block mb-1 flex items-center space-x-1">
                  <Clock className="w-3 h-3 text-amber-400" />
                  <span>{translate(language, 'presenter_timer_label')}</span>
                </label>
                <select
                  value={autoRevertMinutes}
                  onChange={(e) => setAutoRevertMinutes(Number(e.target.value))}
                  className="w-full bg-black/70 border border-white/15 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-amber-400"
                >
                  <option value={5} className="bg-zinc-900">5 min</option>
                  <option value={10} className="bg-zinc-900">10 min (Default)</option>
                  <option value={15} className="bg-zinc-900">15 min</option>
                  <option value={30} className="bg-zinc-900">30 min</option>
                </select>
              </div>
            </div>
          </div>

          {/* 6 Demo Scenarios */}
          <div className="space-y-2.5">
            <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-300 font-mono px-1">
              {translate(language, 'presenter_step2')}
            </h3>
            <div className="space-y-2">
              {scenarios.map((sc: any) => {
                const isSelected = selectedScenario === sc.id;
                const keys = SCENARIO_KEYS[sc.id];
                const titleText = keys ? translate(language, keys.title_key) : sc.title;
                const subText = keys ? translate(language, keys.sub_key) : sc.subtitle;
                const hasUrl = Boolean(sc.source_url);
                return (
                  <div
                    key={sc.id}
                    onClick={() => setSelectedScenario(sc.id)}
                    role="button"
                    tabIndex={0}
                    onKeyDown={(e) => e.key === 'Enter' && setSelectedScenario(sc.id)}
                    className={`w-full text-left p-3.5 rounded-2xl border transition-all cursor-pointer ${
                      isSelected
                        ? 'bg-amber-500/15 border-amber-400/50 shadow-lg shadow-amber-500/10'
                        : 'bg-white/[0.03] border-white/[0.07] hover:bg-white/[0.06]'
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-xs font-bold text-white">{titleText}</span>
                      <span className="text-[9px] font-mono px-2 py-0.5 rounded-full bg-amber-500/15 text-amber-300 border border-amber-500/25 shrink-0">
                        SIMULATED
                      </span>
                    </div>
                    <p className="text-[11px] text-zinc-300 mt-1">{subText}</p>
                    <div className="text-[10px] text-zinc-400 mt-1.5 flex flex-wrap items-center gap-2">
                      <span>{sc.inspired_by || translate(language, 'presenter_generic_source')}</span>
                      {hasUrl && (
                        <a
                          href={sc.source_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          onClick={(e) => e.stopPropagation()}
                          className="inline-flex items-center space-x-1 text-cyan-400 hover:text-cyan-300 underline font-mono"
                        >
                          <ExternalLink className="w-2.5 h-2.5" />
                          <span>{translate(language, 'presenter_source_link')}</span>
                        </a>
                      )}
                      {sc.statement_url && (
                        <a
                          href={sc.statement_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          onClick={(e) => e.stopPropagation()}
                          className="inline-flex items-center space-x-1 text-emerald-400 hover:text-emerald-300 underline font-mono"
                        >
                          <ExternalLink className="w-2.5 h-2.5" />
                          <span>{translate(language, 'presenter_statement_link')}</span>
                        </a>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {errorMsg && (
            <div className="p-3 rounded-xl bg-red-500/15 border border-red-500/30 text-xs text-red-200 font-mono">
              {errorMsg}
            </div>
          )}

          {/* Activate Button */}
          <button
            onClick={() => handleActivate()}
            disabled={busy || !selectedCity}
            data-testid="activate-scenario-btn"
            className="w-full py-3 px-4 rounded-2xl bg-amber-500 hover:bg-amber-400 text-black font-bold text-xs flex items-center justify-center space-x-2 cursor-pointer shadow-lg shadow-amber-500/20 transition-all disabled:opacity-50"
          >
            <Play className="w-4 h-4" />
            <span>
              {translate(language, 'presenter_activate_btn', {
                title: SCENARIO_KEYS[selectedScenario]
                  ? translate(language, SCENARIO_KEYS[selectedScenario].title_key)
                  : selectedScenario,
                city: selectedCity || '...'
              })}
            </span>
          </button>
        </div>
      </div>
    </div>
  );
};
