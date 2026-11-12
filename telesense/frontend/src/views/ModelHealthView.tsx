import React, { useEffect, useState } from 'react';
import { fetchModelHealth, runCloudflarePipeline } from '../services/api';
import { formatIstDateTime } from '../utils/indiaFormat';
import { translate } from '../i18n/translations';
import { Cpu, CheckCircle2, AlertTriangle, RefreshCw, Layers, ShieldCheck, Activity, Database, Info, Play, Terminal } from 'lucide-react';

interface ModelHealthViewProps {
  language: string;
}

export const ModelHealthView: React.FC<ModelHealthViewProps> = ({ language }) => {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [pipelineBusy, setPipelineBusy] = useState<boolean>(false);
  const [pipelineMsg, setPipelineMsg] = useState<string | null>(null);
  const [selectedMetricView, setSelectedMetricView] = useState<'mae' | 'rmse' | 'mape'>('mae');

  const loadHealth = () => {
    setLoading(true);
    fetchModelHealth()
      .then((res) => setData(res))
      .catch((err) => console.error(err))
      .finally(() => setLoading(false));
  };

  const handleRunPipeline = async () => {
    setPipelineBusy(true);
    setPipelineMsg(null);
    try {
      const res = await runCloudflarePipeline();
      setPipelineMsg(res.message || 'Pipeline completed.');
      loadHealth();
    } catch (err: any) {
      setPipelineMsg(err?.message || 'Cloudflare Radar pipeline failed');
    } finally {
      setPipelineBusy(false);
    }
  };

  useEffect(() => {
    loadHealth();
  }, []);

  if (loading || !data) {
    return (
      <div className="py-32 text-center text-zinc-500 text-xs font-mono animate-pulse">
        Reading artifacts/metrics.json benchmark suite &amp; drift state...
      </div>
    );
  }

  const {
    model_architecture,
    metrics_leaderboard,
    simulator_split_dates,
    simulator_diagnostic_note,
    simulator_coverage_note,
    is_shared_simulator_model,
    real_dataset_validation,
    drift_status,
    features_used,
  } = data;

  const rawLeaderboard = metrics_leaderboard || {};
  const simModels: Record<string, any> =
    rawLeaderboard?.metrics && typeof rawLeaderboard.metrics === 'object'
      ? rawLeaderboard.metrics
      : Object.fromEntries(
          Object.entries(rawLeaderboard).filter(
            ([, v]) => v && typeof v === 'object' && 'mae_overall' in (v as Record<string, any>)
          )
        );
  const modelEntries = Object.entries(simModels);
  const splitDates = simulator_split_dates || rawLeaderboard?.split_dates || real_dataset_validation?.split_dates || {};
  const metricPrefix = selectedMetricView === 'mae' ? 'mae' : selectedMetricView === 'rmse' ? 'rmse' : 'mape';

  return (
    <div className="max-w-6xl mx-auto p-4 sm:p-6 space-y-6 text-white">
      {/* Header */}
      <div className="apple-glass-card p-6 sm:p-7 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center space-x-3.5">
          <div className="p-2.5 rounded-2xl bg-cyan-500/10 border border-cyan-500/20 text-cyan-400">
            <Cpu className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h1 className="text-xl sm:text-2xl font-bold tracking-tight">{translate(language, 'ai_title')}</h1>
              <span className="px-2 py-0.5 rounded-full text-[9px] font-mono font-bold bg-amber-500/15 text-amber-300 border border-amber-500/30">
                INDIA-CALIBRATED SIMULATION
              </span>
            </div>
            <p className="text-xs text-zinc-400 mt-0.5">
              {translate(language, 'ai_subtitle')}
            </p>
            <p className="text-xs text-cyan-300 font-medium mt-1" data-testid="radar-vs-simulator-scope-line">
              Radar models validate the method on real web traffic; tower forecasts on the NOC map come from the simulator.
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-2">
          <button
            onClick={loadHealth}
            className="apple-pill px-4 py-2 text-xs text-zinc-200 hover:text-white hover:bg-white/10 transition-colors flex items-center space-x-1.5 cursor-pointer font-semibold"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>{translate(language, 'ai_refresh_btn')}</span>
          </button>
        </div>
      </div>

      {/* Top Level Diagnostics Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="apple-glass-card p-5 space-y-2 border-cyan-500/25 bg-cyan-500/[0.03]">
          <div className="flex items-center justify-between text-xs">
            <span className="text-[10px] font-bold uppercase tracking-wider text-cyan-400 font-mono">
              {translate(language, 'ai_selected_arch')}
            </span>
            <span className="flex items-center space-x-1.5">
              {is_shared_simulator_model !== false && (
                <span className="px-2 py-0.5 rounded-full text-[9px] font-mono font-bold bg-cyan-500/15 text-cyan-300 border border-cyan-500/30">
                  SHARED SIMULATOR MODEL
                </span>
              )}
              <ShieldCheck className="w-4 h-4 text-cyan-400" />
            </span>
          </div>
          <div className="text-xl font-black text-white font-mono tracking-tight" data-testid="serving-model-headline">
            {model_architecture}
          </div>
          <p className="text-xs text-zinc-400">
            Selected strictly by lowest VALIDATION MAE (never test MAE). {simulator_coverage_note || 'Trained on simulated reference tower MUM-C101 and served as a shared simulator model across all 99 simulated NOC towers.'}
          </p>
        </div>

        <div
          className={`apple-glass-card p-5 space-y-2 border ${
            drift_status?.drift_detected ? 'border-red-500/30 bg-red-500/10' : 'border-emerald-500/30 bg-emerald-500/[0.03]'
          }`}
        >
          <div className="flex items-center justify-between text-xs">
            <span
              className={`text-[10px] font-bold uppercase tracking-wider font-mono ${
                drift_status?.drift_detected ? 'text-red-400' : 'text-emerald-400'
              }`}
            >
              {translate(language, 'ai_drift_title')}
            </span>
            {drift_status?.drift_detected ? (
              <AlertTriangle className="w-4 h-4 text-red-400 animate-pulse" />
            ) : (
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
            )}
          </div>
          <div className={`text-lg font-extrabold tracking-tight ${drift_status?.drift_detected ? 'text-red-300' : 'text-emerald-300'}`}>
            {drift_status?.status_label}
          </div>
          <p className="text-[11px] text-zinc-400 leading-relaxed">
            {drift_status?.plain_english_takeaway}
          </p>
          <span className="text-[10px] text-zinc-500 font-mono block">
            Checked: {drift_status?.last_checked_at || '-- IST'}
          </span>
        </div>

        <div className="apple-glass-card p-5 space-y-2">
          <div className="flex items-center justify-between text-xs">
            <span className="text-[10px] font-bold uppercase tracking-wider text-zinc-400 font-mono">
              {translate(language, 'ai_split_window')}
            </span>
            <Layers className="w-4 h-4 text-purple-400" />
          </div>
          <div className="text-xs text-zinc-200 font-mono space-y-1">
            <div>Train: {splitDates.train_start ? `${splitDates.train_start} → ${splitDates.train_end}` : 'Chronological 70%'}</div>
            <div>Val: {splitDates.validation_start ? `${splitDates.validation_start} → ${splitDates.validation_end}` : 'Chronological 15%'}</div>
            <div>Test: {splitDates.test_start ? `${splitDates.test_start} → ${splitDates.test_end}` : 'Chronological 15%'}</div>
          </div>
          <span className="text-[10px] text-zinc-500 block">
            Evaluated: {data.evaluated_at ? formatIstDateTime(data.evaluated_at) : '-- IST'}
          </span>
        </div>
      </div>

      {/* Cloudflare Radar Real India Hourly Traffic Series Validation */}
      {real_dataset_validation && (() => {
        const isValidated =
          Boolean(real_dataset_validation.status_label?.startsWith('Validated on real India traffic series')) &&
          !real_dataset_validation.setup_required;
        const radarMetrics = real_dataset_validation.metrics || {};
        const naiveMae = Number(radarMetrics?.Seasonal_Naive_Baseline?.mae_overall ?? Infinity);

        return (
          <div
            className={`apple-glass-card p-6 space-y-4 ${
              isValidated ? 'border-emerald-500/20 bg-emerald-500/[0.02]' : 'border-amber-500/20 bg-amber-500/[0.02]'
            }`}
          >
            <div className="flex items-center justify-between flex-wrap gap-2">
              <div className="flex items-center space-x-2">
                <Database className={`w-4 h-4 ${isValidated ? 'text-emerald-400' : 'text-amber-400'}`} />
                <h2 className={`text-sm font-bold uppercase tracking-wider font-mono ${isValidated ? 'text-emerald-300' : 'text-amber-300'}`}>
                  {real_dataset_validation.status_label || 'Cloudflare Radar India Evaluation'}
                </h2>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                {real_dataset_validation.series_count && (
                  <span className="text-[10px] font-mono text-emerald-300 px-2.5 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/20" data-testid="radar-series-count-pill">
                    {real_dataset_validation.series_count} related series (states are subsets of India) • {real_dataset_validation.history_hours ?? '--'}h history ({real_dataset_validation.time_resolution || '1h'})
                  </span>
                )}
                <span className="text-[10px] font-mono text-zinc-300 px-2.5 py-0.5 rounded-full bg-white/5 border border-white/10">
                  Unit: {real_dataset_validation.dataset_unit || 'Relative web traffic (Cloudflare Radar), not tower load'}
                </span>
              </div>
            </div>

            <div className="p-3 rounded-xl bg-black/40 border border-white/10 text-xs text-zinc-300 space-y-1">
              <div>{real_dataset_validation.scope_note || 'Relative web traffic (Cloudflare Radar), not tower load.'}</div>
              {real_dataset_validation.radar_coverage_note && (
                <div className="text-[11px] text-emerald-300/90">
                  Coverage: {real_dataset_validation.radar_coverage_note}
                </div>
              )}
              {real_dataset_validation.dataset_scale && (
                <div className="text-[11px] font-mono text-cyan-300/90">
                  Scale: {real_dataset_validation.dataset_scale} • Serving selection: VALIDATION MAE (test MAE reported held-out only)
                </div>
              )}
              <div className="text-[11px] text-amber-300/90" data-testid="operator-broadband-note">
                ASN scope: {real_dataset_validation.operator_broadband_note || 'network-level web traffic, may include fixed broadband'}
              </div>
              {Array.isArray(real_dataset_validation.skipped_top_asns) && real_dataset_validation.skipped_top_asns.length > 0 && (
                <div className="text-[11px] text-zinc-400" data-testid="radar-skipped-asn-note">
                  Skipped non-IN Radar network:{' '}
                  {real_dataset_validation.skipped_top_asns
                    .map((sk: any) => `#${sk.radar_rank_india} AS${sk.asn} ${sk.as_name} (${sk.as_country}, ${sk.as_type}, ${sk.traffic_share_pct}%) — ${sk.reason}`)
                    .join('; ')}
                </div>
              )}
            </div>

            {!isValidated && real_dataset_validation.setup_note && (
              <div className="p-3.5 rounded-xl bg-amber-500/10 border border-amber-500/30 text-xs text-amber-200 flex items-start space-x-2.5">
                <Info className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
                <div>
                  <strong className="font-bold block text-amber-300 mb-0.5">
                    Cloudflare Radar Token Setup Required (Zero Fake Data Shown)
                  </strong>
                  <span>{real_dataset_validation.setup_note}</span>
                </div>
              </div>
            )}

            {real_dataset_validation.split_dates && real_dataset_validation.split_dates.train_start && (
              <div className="p-3.5 rounded-xl bg-black/40 border border-emerald-500/20 text-xs font-mono space-y-1.5">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="text-[10px] uppercase font-bold text-emerald-400">
                    Strict Chronological Evaluation Window ({real_dataset_validation.fetched_at ? formatIstDateTime(real_dataset_validation.fetched_at) : 'Offline Cache'})
                  </span>
                  {real_dataset_validation.date_range_start && (
                    <span className="text-[10px] text-zinc-300">
                      Date Range: <strong className="text-white">{real_dataset_validation.date_range_start} → {real_dataset_validation.date_range_end}</strong>
                    </span>
                  )}
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 pt-1 text-zinc-300">
                  <div><strong className="text-white">Train:</strong> {real_dataset_validation.split_dates.train_start} → {real_dataset_validation.split_dates.train_end}</div>
                  <div><strong className="text-white">Val:</strong> {real_dataset_validation.split_dates.validation_start} → {real_dataset_validation.split_dates.validation_end}</div>
                  <div><strong className="text-white">Test:</strong> {real_dataset_validation.split_dates.test_start} → {real_dataset_validation.split_dates.test_end}</div>
                </div>
              </div>
            )}

            {Object.keys(radarMetrics).length > 0 ? (
              <div className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
                {Object.entries(radarMetrics).map(([name, m]: [string, any]) => {
                  const isBaseline = name.includes('Naive');
                  const beatsBaseline = !isBaseline && Number(m.mae_overall) < naiveMae;
                  const isServingWinner = name === real_dataset_validation.best_model;
                  return (
                    <div key={name} className={`p-3 rounded-xl bg-black/50 border space-y-1 ${isServingWinner ? 'border-emerald-500/40' : 'border-white/[0.06]'}`}>
                      <div className="flex items-center justify-between gap-1">
                        <span className="text-xs font-bold text-white">{name.replace(/_/g, ' ')}</span>
                        {isServingWinner && (
                          <span className="text-[8px] font-mono px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 font-bold">
                            VAL WINNER
                          </span>
                        )}
                      </div>
                      <div className="text-sm font-mono text-cyan-400 font-bold">
                        {m.mae_overall} <span className="text-[10px] text-zinc-400">Test MAE ({m.relative_error_pct ?? '--'}% of mean)</span>
                      </div>
                      <span className="text-[10px] text-zinc-300 font-mono block">
                        Val MAE {m.val_mae_overall ?? '--'} • RMSE {m.rmse_overall}
                      </span>
                      <span className="text-[10px] text-zinc-400 font-mono block">
                        1h {m.mae_1h} • 6h {m.mae_6h ?? '--'} • 24h {m.mae_24h ?? '--'}
                      </span>
                      <span
                        className={`text-[9px] font-mono block font-semibold ${
                          isBaseline ? 'text-zinc-400' : beatsBaseline ? 'text-emerald-400' : 'text-red-400'
                        }`}
                      >
                        {isBaseline
                          ? 'Baseline reference'
                          : beatsBaseline
                          ? `Better than Seasonal-Naive (${Number(m.pct_improvement_vs_naive ?? 0) >= 0 ? '+' : ''}${Number(m.pct_improvement_vs_naive ?? (((naiveMae - Number(m.mae_overall)) / Math.max(naiveMae, 1e-6)) * 100)).toFixed(1)}%)`
                          : 'Does NOT beat Seasonal-Naive'}
                      </span>
                    </div>
                  );
                })}
              </div>

              {/* Per-Series Breakdown Table across all related series (India + State Subsets + Top Radar Operator ASNs) */}
              {Array.isArray(real_dataset_validation.series_results) && real_dataset_validation.series_results.length > 0 && (
                <div className="rounded-xl border border-white/10 bg-black/40 overflow-hidden" data-testid="radar-series-table">
                  <div className="px-4 py-2.5 bg-white/[0.03] border-b border-white/10 flex flex-wrap items-center justify-between gap-2">
                    <span className="text-[11px] font-bold uppercase tracking-wider font-mono text-emerald-300">
                      Per-Series Evaluation ({real_dataset_validation.series_results.length} related series (states are subsets of India) + top Radar India ASNs)
                    </span>
                    <span className="text-[10px] font-mono text-zinc-400">
                      Serving model selected per series by VALIDATION MAE only • Scale 0–100 index
                    </span>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-left border-collapse text-[11px]">
                      <thead>
                        <tr className="bg-black/60 border-b border-white/10 text-zinc-400 font-mono text-[10px] uppercase">
                          <th className="p-2.5">Type</th>
                          <th className="p-2.5">Series Name</th>
                          <th className="p-2.5">Serving (Val MAE)</th>
                          <th className="p-2.5">Test Mean</th>
                          <th className="p-2.5">Naive MAE</th>
                          <th className="p-2.5">Test MAE</th>
                          <th className="p-2.5">Rel. Error (% mean)</th>
                          <th className="p-2.5">1h MAE</th>
                          <th className="p-2.5">6h MAE</th>
                          <th className="p-2.5">24h MAE</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-white/[0.05] font-mono">
                        {real_dataset_validation.series_results.map((sr: any) => (
                          <tr key={sr.series_id} className="hover:bg-white/[0.03]">
                            <td className="p-2.5 text-zinc-400">
                              <span className="capitalize block text-zinc-300">
                                {sr.kind === 'operator_asn' ? 'Operator ASN' : sr.kind?.replace('_', ' ')}
                              </span>
                              {sr.as_type && (
                                <span className="text-[10px] font-sans text-cyan-300/90 block mt-0.5">
                                  {sr.as_type}
                                </span>
                              )}
                            </td>
                            <td className="p-2.5 font-sans font-semibold text-white">
                              <div>
                                {sr.as_name || sr.label}{' '}
                                {sr.as_aka && (
                                  <span className="text-[10px] font-mono text-zinc-400">({sr.as_aka})</span>
                                )}{' '}
                                <span className="text-[10px] font-mono text-zinc-400">({sr.series_id})</span>
                                {sr.radar_rank_india && (
                                  <span className="ml-1.5 text-[9px] font-mono px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-300 border border-emerald-500/25">
                                    Radar IN #{sr.radar_rank_india}{sr.traffic_share_pct != null ? ` • ${sr.traffic_share_pct}%` : ''}
                                  </span>
                                )}
                              </div>
                              {sr.kind === 'operator_asn' && (
                                <span className="block text-[10px] font-normal text-amber-300/80">
                                  {sr.as_type ? `${sr.as_type} • ` : ''}{sr.network_scope_note || 'network-level web traffic, may include fixed broadband'}
                                </span>
                              )}
                            </td>
                            <td className="p-2.5">
                              <span className="px-2 py-0.5 rounded bg-cyan-500/15 border border-cyan-500/30 text-cyan-300 font-bold text-[10px]">
                                {sr.serving_model}
                              </span>
                              <span className="text-[10px] text-zinc-400 ml-1">({sr.serving_val_mae})</span>
                            </td>
                            <td className="p-2.5 text-zinc-300">{sr.series_mean_test}</td>
                            <td className="p-2.5 text-zinc-400">{sr.naive_test_mae}</td>
                            <td className="p-2.5 text-emerald-300 font-bold">{sr.serving_test_mae}</td>
                            <td className="p-2.5 text-amber-300 font-bold">{sr.serving_relative_error_pct}%</td>
                            <td className="p-2.5 text-zinc-300">{sr.mae_1h}</td>
                            <td className="p-2.5 text-zinc-300">{sr.mae_6h}</td>
                            <td className="p-2.5 text-zinc-300">{sr.mae_24h}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* Last 7 Days of Test Window Errors + Diwali (Nov 8, 2026) & Festival Dates Chart + Ablation */}
              {Array.isArray(real_dataset_validation.last_7d_daily_errors) && real_dataset_validation.last_7d_daily_errors.length > 0 && (() => {
                const days = real_dataset_validation.last_7d_daily_errors as any[];
                const maxMae = Math.max(
                  ...days.flatMap((d) => [Number(d.serving_mae || 0), Number(d.naive_mae || 0)]),
                  8
                );
                const w = 640;
                const h = 150;
                const padL = 36;
                const padR = 20;
                const padT = 22;
                const padB = 28;
                const plotW = w - padL - padR;
                const plotH = h - padT - padB;
                const xFor = (idx: number) => padL + (days.length > 1 ? (idx / (days.length - 1)) * plotW : plotW / 2);
                const yFor = (val: number) => padT + plotH - (val / maxMae) * plotH;
                const servingPts = days.map((d, i) => `${xFor(i).toFixed(1)},${yFor(Number(d.serving_mae)).toFixed(1)}`).join(' ');
                const naivePts = days.map((d, i) => `${xFor(i).toFixed(1)},${yFor(Number(d.naive_mae)).toFixed(1)}`).join(' ');
                const ablation = real_dataset_validation.festival_ablation;

                return (
                  <div className="grid grid-cols-1 lg:grid-cols-3 gap-4" data-testid="last-7d-festival-section">
                    <div className="lg:col-span-2 p-4 rounded-xl bg-black/40 border border-white/10 space-y-2.5">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <span className="text-[11px] font-bold uppercase tracking-wider font-mono text-amber-300">
                          Last 7 Days Test Errors — Diwali (Nov 8, 2026) &amp; Festival Markers
                        </span>
                        <div className="flex items-center space-x-3 text-[10px] font-mono">
                          <span className="text-emerald-400">● {real_dataset_validation.best_model} (Serving)</span>
                          <span className="text-zinc-400">● Seasonal-Naive</span>
                        </div>
                      </div>
                      <svg viewBox={`0 0 ${w} ${h}`} className="w-full h-40 overflow-visible">
                        {[0, 0.5, 1].map((frac) => {
                          const yy = padT + plotH * (1 - frac);
                          return (
                            <g key={frac}>
                              <line x1={padL} y1={yy} x2={w - padR} y2={yy} stroke="rgba(255,255,255,0.08)" strokeDasharray="3,3" />
                              <text x={padL - 5} y={yy + 3} textAnchor="end" fontSize="9" fill="#9ca3af">
                                {(maxMae * frac).toFixed(1)}
                              </text>
                            </g>
                          );
                        })}
                        {days.map((d, i) => {
                          const x = xFor(i);
                          return d.is_festival ? (
                            <g key={d.date}>
                              <line
                                x1={x}
                                y1={padT}
                                x2={x}
                                y2={padT + plotH}
                                stroke={d.is_diwali ? '#f59e0b' : '#a855f7'}
                                strokeWidth={d.is_diwali ? 2 : 1.2}
                                strokeDasharray={d.is_diwali ? undefined : '4,3'}
                              />
                              <text
                                x={x}
                                y={12}
                                textAnchor="middle"
                                fontSize="9"
                                fontWeight="bold"
                                fill={d.is_diwali ? '#fbbf24' : '#c084fc'}
                              >
                                {d.is_diwali ? 'Diwali Nov 8' : d.festival_name.split(' ')[0]}
                              </text>
                            </g>
                          ) : null;
                        })}
                        <polyline fill="none" stroke="#9ca3af" strokeWidth="1.8" strokeDasharray="4,3" points={naivePts} />
                        <polyline fill="none" stroke="#34d399" strokeWidth="2.4" points={servingPts} />
                        {days.map((d, i) => (
                          <g key={`pt-${d.date}`}>
                            <circle cx={xFor(i)} cy={yFor(Number(d.serving_mae))} r={d.is_diwali ? 5 : 3.5} fill={d.is_diwali ? '#fbbf24' : '#34d399'} />
                            <text x={xFor(i)} y={padT + plotH + 14} textAnchor="middle" fontSize="9" fill={d.is_festival ? '#fbbf24' : '#a1a1aa'}>
                              {d.date.slice(5)}
                            </text>
                            <text x={xFor(i)} y={yFor(Number(d.serving_mae)) - 7} textAnchor="middle" fontSize="8.5" fill="#e5e7eb">
                              {d.serving_mae}
                            </text>
                          </g>
                        ))}
                      </svg>
                      {Array.isArray(real_dataset_validation.festivals_in_window) && (
                        <div className="space-y-1.5 pt-1">
                          <div className="flex flex-wrap gap-1.5">
                            {real_dataset_validation.festivals_in_window.map((f: any) => (
                              <span
                                key={f.date}
                                className={`text-[9px] font-mono px-2 py-0.5 rounded-full border ${
                                  f.date === '2026-11-08'
                                    ? 'bg-amber-500/20 text-amber-300 border-amber-500/40 font-bold'
                                    : f.in_test_window
                                    ? 'bg-purple-500/15 text-purple-300 border-purple-500/30'
                                    : 'bg-white/5 text-zinc-400 border-white/10'
                                }`}
                              >
                                {f.date}: {f.name}
                              </span>
                            ))}
                          </div>
                          <div className="text-[10px] text-zinc-400 flex flex-wrap items-center gap-1.5" data-testid="festival-calendar-source">
                            <span>{real_dataset_validation.festival_calendar_note || 'Festival dates per Drik Panchang; regional calendars can differ by a day.'}</span>
                            <a
                              href={real_dataset_validation.festival_source_url || 'https://www.drikpanchang.com/calendars/indian/indiancalendar.html?year=2026'}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-cyan-400 hover:text-cyan-300 underline"
                            >
                              {real_dataset_validation.festival_source_name || 'Drik Panchang (Indian Festival Calendar 2026)'}
                            </a>
                          </div>
                        </div>
                      )}
                    </div>

                    {ablation && (
                      <div className="p-4 rounded-xl bg-black/40 border border-purple-500/25 space-y-2.5 flex flex-col justify-between" data-testid="festival-ablation-card">
                        <div className="space-y-1.5">
                          <div className="flex items-center justify-between gap-2">
                            <span className="text-[11px] font-bold uppercase tracking-wider font-mono text-purple-300">
                              Festival Feature Ablation
                            </span>
                            <span className={`text-[9px] font-mono px-2 py-0.5 rounded font-bold border ${
                              ablation.helped_test
                                ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
                                : 'bg-red-500/15 text-red-300 border-red-500/30'
                            }`}>
                              {ablation.helped_test ? 'HELPED ON TEST' : 'DID NOT HELP ON TEST'}
                            </span>
                          </div>
                          <div className="grid grid-cols-2 gap-2 text-xs font-mono pt-1">
                            <div className="p-2 rounded-lg bg-white/[0.03] border border-white/10">
                              <span className="text-[9px] text-zinc-400 block">Base GRU</span>
                              <span className="text-white font-bold">Val {ablation.base_val_mae}</span>
                              <span className="text-cyan-300 block text-[11px]">Test {ablation.base_test_mae} MAE</span>
                            </div>
                            <div className="p-2 rounded-lg bg-white/[0.03] border border-white/10">
                              <span className="text-[9px] text-zinc-400 block">+ Festival Flags</span>
                              <span className="text-white font-bold">Val {ablation.festival_val_mae}</span>
                              <span className="text-red-300 block text-[11px]">Test {ablation.festival_test_mae} MAE</span>
                            </div>
                          </div>
                        </div>
                        <p className="text-xs text-zinc-200 leading-relaxed border-t border-white/10 pt-2">
                          {ablation.conclusion}
                        </p>
                      </div>
                    )}
                  </div>
                );
              })()}
              </div>
            ) : (
              <div className="p-4 rounded-xl bg-black/50 border border-white/10 space-y-3" data-testid="ai-health-no-results">
                <div className="flex items-center justify-between flex-wrap gap-2">
                  <div>
                    <h3 className="text-sm font-bold text-amber-300">{translate(language, 'ai_no_results_title')}</h3>
                    <p className="text-xs text-zinc-300 mt-0.5">{translate(language, 'ai_no_results_desc')}</p>
                  </div>
                  <button
                    onClick={handleRunPipeline}
                    disabled={pipelineBusy}
                    className="px-3.5 py-2 rounded-xl bg-cyan-500 hover:bg-cyan-400 disabled:opacity-50 text-black text-xs font-bold flex items-center space-x-1.5 cursor-pointer"
                  >
                    <Play className="w-3.5 h-3.5" />
                    <span>{pipelineBusy ? translate(language, 'ai_running_pipeline') : translate(language, 'ai_run_pipeline_btn')}</span>
                  </button>
                </div>
                <div className="p-2.5 rounded-lg bg-zinc-950 border border-white/10 font-mono text-[11px] text-cyan-300 flex items-center space-x-2 overflow-x-auto">
                  <Terminal className="w-3.5 h-3.5 text-zinc-400 shrink-0" />
                  <code>PYTHONPATH=backend:. python3 backend/app/scripts/import_cloudflare_radar.py && python3 ml/training/india_radar_pipeline.py</code>
                </div>
                {pipelineMsg && (
                  <div className="text-xs font-mono text-amber-200 bg-amber-500/10 border border-amber-500/30 rounded-lg px-3 py-2">
                    {pipelineMsg}
                  </div>
                )}
              </div>
            )}
          </div>
        );
      })()}

      {/* Simulator Benchmark Leaderboard (Never render empty <table>) */}
      <div className="apple-glass-card overflow-hidden shadow-2xl">
        <div className="p-5 sm:p-6 bg-black/50 border-b border-white/[0.08] flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center space-x-2.5">
            <Activity className="w-4 h-4 text-cyan-400" />
            <div>
              <h2 className="text-sm font-bold text-white uppercase tracking-wider font-mono">
                {translate(language, 'ai_leaderboard_title')}
              </h2>
              <p className="text-[11px] text-zinc-400">
                {simulator_coverage_note || 'Chronological 1h-resampled evaluation on reference tower MUM-C101; served as a shared simulator model across all 99 simulated NOC towers.'}
              </p>
              {simulator_diagnostic_note && (
                <p className="text-[11px] text-emerald-300/90 mt-0.5 font-mono">{simulator_diagnostic_note}</p>
              )}
            </div>
          </div>

          <div className="flex items-center space-x-1 bg-black/60 p-1 rounded-full border border-white/[0.08] w-fit">
            {(['mae', 'rmse', 'mape'] as const).map((view) => (
              <button
                key={view}
                onClick={() => setSelectedMetricView(view)}
                className={`px-3 py-1 rounded-full text-[11px] font-bold uppercase transition-all cursor-pointer ${
                  selectedMetricView === view ? 'bg-white text-black shadow-sm' : 'text-zinc-400 hover:text-white'
                }`}
              >
                {view.toUpperCase()}
              </button>
            ))}
          </div>
        </div>

        {modelEntries.length === 0 ? (
          <div className="p-6 text-center space-y-2">
            <p className="text-sm font-bold text-amber-300">{translate(language, 'ai_no_results_title')}</p>
            <code className="inline-block px-3 py-1.5 rounded-lg bg-black/60 border border-white/10 font-mono text-[11px] text-cyan-300">
              python3 ml/training/train_models.py
            </code>
          </div>
        ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="bg-black/60 border-b border-white/[0.08] text-zinc-400 font-mono text-[10px] uppercase">
                <th className="p-4">Model Architecture</th>
                <th className="p-4">Val MAE (Select)</th>
                <th className="p-4">1-Hour Ahead</th>
                <th className="p-4">6-Hour Ahead</th>
                <th className="p-4">24-Hour Ahead</th>
                <th className="p-4">Test Avg</th>
                <th className="p-4">vs. Seasonal Naive</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/[0.06]">
              {modelEntries.map(([name, m]: [string, any]) => {
                const isBest = name === data.selected_model;
                const valOverall = selectedMetricView === 'mape' ? m.mape_overall ?? m.mape_pct : m[`${metricPrefix}_overall`];
                const val1h = m[`${metricPrefix}_1h`] ?? valOverall;
                const val6h = m[`${metricPrefix}_6h`] ?? valOverall;
                const val24h = m[`${metricPrefix}_24h`] ?? valOverall;
                const simNaiveMae = Number(
                  simModels?.Seasonal_Naive_Baseline?.mae_overall ??
                  simModels?.Seasonal_Naive?.mae_overall ??
                  Infinity
                );
                const beatsSimNaive = !name.includes('Naive') && Number.isFinite(simNaiveMae) && Number(m.mae_overall) < simNaiveMae;

                return (
                  <tr key={name} className={`hover:bg-white/[0.03] transition-colors ${isBest ? 'bg-cyan-500/[0.04]' : ''}`}>
                    <td className="p-4">
                      <div className="flex items-center space-x-2">
                        <span className="font-bold text-white text-xs">{name.replace(/_/g, ' ')}</span>
                        {isBest && (
                          <span className="px-2 py-0.5 rounded-full text-[9px] font-mono bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 font-bold">
                            SELECTED
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="p-4 font-mono text-cyan-300 font-bold">{m.val_mae_overall != null ? `${m.val_mae_overall}% pt` : '--'}</td>
                    <td className="p-4 font-mono text-zinc-300">{val1h}{selectedMetricView === 'mape' ? '%' : '% pt'}</td>
                    <td className="p-4 font-mono text-zinc-300">{val6h}{selectedMetricView === 'mape' ? '%' : '% pt'}</td>
                    <td className="p-4 font-mono text-zinc-300">{val24h}{selectedMetricView === 'mape' ? '%' : '% pt'}</td>
                    <td className="p-4 font-mono font-bold text-white text-sm">{valOverall}{selectedMetricView === 'mape' ? '%' : '% pt'}</td>
                    <td className="p-4 font-mono">
                      {name.includes('Naive') ? (
                        <span className="text-zinc-500 text-[11px]">Baseline</span>
                      ) : beatsSimNaive ? (
                        <span className="text-emerald-400 text-[11px] font-bold">Better than baseline</span>
                      ) : (
                        <span className="text-amber-400 text-[11px]">Does not beat baseline</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        )}
      </div>

      {/* Features Used */}
      <div className="apple-glass-card p-6 space-y-3">
        <span className="text-[10px] font-bold uppercase tracking-wider text-zinc-400 font-mono block">
          Time-Series Input Feature Vector ({(features_used || []).length} Features)
        </span>
        <div className="flex flex-wrap gap-2">
          {(features_used || []).map((f: string) => (
            <span key={f} className="px-3 py-1 rounded-full bg-white/[0.05] border border-white/[0.08] text-xs font-mono text-cyan-300">
              {f}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
};
