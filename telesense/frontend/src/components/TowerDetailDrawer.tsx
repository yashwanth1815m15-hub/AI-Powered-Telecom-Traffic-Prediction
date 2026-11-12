import React, { useEffect, useState } from 'react';
import { Tower, TowerForecastResponse } from '../types/telemetry';
import { fetchTowerForecast } from '../services/api';
import { ForecastChart } from './ForecastChart';
import { translate } from '../i18n/translations';
import {
  X,
  Radio,
  Users,
  Gauge,
  Signal,
  ArrowUpRight,
  CheckCircle2,
  AlertTriangle,
  AlertOctagon,
  Info,
  SlidersHorizontal,
  ChevronDown,
  HelpCircle
} from 'lucide-react';

interface DrawerProps {
  tower: Tower | null;
  onClose: () => void;
  language: string;
}

export const TowerDetailDrawer: React.FC<DrawerProps> = ({ tower, onClose, language }) => {
  const [forecast, setForecast] = useState<TowerForecastResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [isEngineerMode, setIsEngineerMode] = useState<boolean>(false);

  useEffect(() => {
    if (!tower) return;
    setLoading(true);
    fetchTowerForecast(tower.tower_id)
      .then((data) => setForecast(data))
      .catch((err) => console.error('Failed to load forecast:', err))
      .finally(() => setLoading(false));
  }, [tower?.tower_id]);

  if (!tower) return null;

  const load = tower.current_load_pct ?? null;
  const status = tower.status || 'HEALTHY';
  const isRealSource = (tower as any).source_type === 'REAL' || (tower as any).source_type?.includes('OpenCellID') || tower.tower_id.startsWith('OCID');

  return (
    <div className="fixed inset-y-0 right-0 w-full sm:w-[520px] z-50 bg-zinc-950/95 backdrop-blur-3xl border-l border-white/10 shadow-2xl flex flex-col overflow-hidden animate-in slide-in-from-right duration-250 text-white">
      {/* Drawer Header */}
      <div className="p-4 sm:p-5 bg-black/60 border-b border-white/[0.08] flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className={`p-2.5 rounded-2xl ${
            (status === 'CRITICAL' || status === 'OUTAGE') ? 'bg-red-500/20 text-red-400 border border-red-500/30' :
            (status === 'AT_RISK' || status === 'WARNING' || status === 'WEAK_COVERAGE') ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30' :
            'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
          }`}>
            <Radio className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h3 className="font-bold text-white text-base tracking-tight truncate max-w-[220px]">
                {tower.name}
              </h3>
              <span className={`text-[9px] font-mono px-2 py-0.5 rounded-full font-bold uppercase tracking-wider ${
                (status === 'CRITICAL' || status === 'OUTAGE') ? 'bg-red-500/20 text-red-300 border border-red-500/30' :
                (status === 'AT_RISK' || status === 'WARNING' || status === 'WEAK_COVERAGE') ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30' :
                'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
              }`}>
                {status}
              </span>
            </div>
            <div className="flex items-center space-x-2 mt-0.5 flex-wrap gap-y-1">
              <span className={`text-[9px] font-mono font-bold px-2 py-0.5 rounded-full border ${
                isRealSource ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30' : 'bg-amber-500/10 text-amber-400 border-amber-500/30'
              }`}>
                {isRealSource ? 'REAL - OpenCellID' : 'SIMULATED SITE'}
              </span>
              {isRealSource && (
                <span className="text-[10px] text-emerald-300/90 font-mono bg-emerald-500/10 px-1.5 py-0.5 rounded border border-emerald-500/20">
                  approximate position (about 1 km)
                </span>
              )}
              <span className="text-[11px] text-zinc-400 font-mono">
                {tower.city} • {tower.area_type}
              </span>
            </div>
          </div>
        </div>

        <div className="flex items-center space-x-2">
          {/* Simple / Engineer View Toggle */}
          <button
            onClick={() => setIsEngineerMode(!isEngineerMode)}
            className={`px-2.5 py-1 rounded-full text-[10px] font-mono font-bold border transition-colors flex items-center space-x-1 cursor-pointer ${
              isEngineerMode
                ? 'bg-cyan-500/20 border-cyan-500/40 text-cyan-300'
                : 'bg-white/5 border-white/10 text-zinc-400 hover:text-white'
            }`}
            title="Toggle between Simple Plain-English and Detailed Engineering labels"
          >
            <SlidersHorizontal className="w-3 h-3" />
            <span>{isEngineerMode ? translate(language, 'tower_engineer') : translate(language, 'tower_simple')}</span>
          </button>

          <button
            onClick={onClose}
            className="apple-pill p-2 text-zinc-400 hover:text-white hover:bg-white/10 transition-colors cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Drawer Scrollable Body: 3 Distinct Levels */}
      <div className="flex-1 overflow-y-auto p-4 sm:p-5 space-y-4">
        {status === 'WEAK_COVERAGE' && (
          <div className="p-3 rounded-xl bg-amber-500/15 border border-amber-500/35 text-xs text-amber-200 font-semibold">
            {translate(language, 'tower_weak_cov_note')}
          </div>
        )}

        {/* =========================================================================
            LEVEL 1: STATUS
        ========================================================================= */}
        <div className="apple-glass p-4 rounded-2xl border border-white/[0.08] space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold uppercase tracking-wider text-cyan-400 font-mono flex items-center space-x-1.5">
              <span>{translate(language, 'tower_level1')}</span>
            </span>
            <span className="text-[10px] font-mono text-zinc-500">Real-time Telemetry</span>
          </div>

          <div className="grid grid-cols-2 gap-2.5">
            {/* Live Load */}
            <div className="bg-black/40 p-3 rounded-xl border border-white/[0.04] space-y-1">
              <div className="flex items-center justify-between text-[10px] text-zinc-400 font-semibold uppercase">
                <span>{isEngineerMode ? 'Capacity Utilization' : 'Current Load'}</span>
                <span className="px-1.5 py-0.2 rounded text-[8px] font-bold bg-amber-500/10 text-amber-300 font-mono border border-amber-500/20">
                  SIMULATED
                </span>
              </div>
              <div className="text-xl font-black text-white font-mono">
                {load !== null ? `${load.toFixed(1)}%` : '--'}
              </div>
              <div className="w-full bg-zinc-800 h-1 rounded-full overflow-hidden">
                <div
                  className={`h-full ${(load ?? 0) >= 95 ? 'bg-red-500' : ((load ?? 0) >= 85 ? 'bg-amber-400' : 'bg-emerald-400')}`}
                  style={{ width: `${Math.min(100, load ?? 0)}%` }}
                />
              </div>
            </div>

            {/* Active Users */}
            <div className="bg-black/40 p-3 rounded-xl border border-white/[0.04] space-y-1">
              <div className="flex items-center justify-between text-[10px] text-zinc-400 font-semibold uppercase">
                <span className="flex items-center space-x-1">
                  <Users className="w-3 h-3 text-blue-400" />
                  <span>{isEngineerMode ? 'Connected UEs' : 'Active Users'}</span>
                </span>
                <span className="px-1.5 py-0.2 rounded text-[8px] font-bold bg-cyan-500/10 text-cyan-300 font-mono border border-cyan-500/20">
                  MODELLED
                </span>
              </div>
              <div className="text-xl font-black text-white font-mono">
                {tower.active_users != null ? tower.active_users.toLocaleString() : '--'}
              </div>
              <span className="text-[10px] text-zinc-500 block">
                {isEngineerMode ? 'RRC Connected' : 'Users in area'}
              </span>
            </div>

            {/* Throughput */}
            <div className="bg-black/40 p-3 rounded-xl border border-white/[0.04] space-y-1">
              <div className="flex items-center justify-between text-[10px] text-zinc-400 font-semibold uppercase">
                <span className="flex items-center space-x-1">
                  <Gauge className="w-3 h-3 text-cyan-400" />
                  <span>{isEngineerMode ? 'User-Plane DL' : 'Average Speed'}</span>
                </span>
                <span className="px-1.5 py-0.2 rounded text-[8px] font-bold bg-amber-500/10 text-amber-300 font-mono border border-amber-500/20">
                  SIMULATED
                </span>
              </div>
              <div className="text-lg font-bold text-cyan-400 font-mono">
                {tower.throughput_mbps != null ? tower.throughput_mbps.toFixed(1) : '--'} <span className="text-[10px] font-normal text-zinc-400">Mbps</span>
              </div>
              <span className="text-[10px] text-zinc-500 block">
                {isEngineerMode ? 'Downlink throughput' : 'Typical download'}
              </span>
            </div>

            {/* Signal Strength (RSRP) */}
            <div className="bg-black/40 p-3 rounded-xl border border-white/[0.04] space-y-1">
              <div className="flex items-center justify-between text-[10px] text-zinc-400 font-semibold uppercase">
                <span className="flex items-center space-x-1">
                  <Signal className="w-3 h-3 text-amber-400" />
                  <span>{isEngineerMode ? 'RSRP Power' : 'Signal Quality'}</span>
                </span>
                <span className="px-1.5 py-0.2 rounded text-[8px] font-bold bg-amber-500/10 text-amber-300 font-mono border border-amber-500/20">
                  SIMULATED
                </span>
              </div>
              <div className="text-lg font-bold text-white font-mono">
                {tower.rsrp_dbm != null ? tower.rsrp_dbm.toFixed(1) : '--'} <span className="text-[10px] text-zinc-400">dBm</span>
              </div>
              <span className={`text-[10px] font-bold ${
                tower.rsrp_dbm == null ? 'text-zinc-500' : tower.rsrp_dbm > -90 ? 'text-emerald-400' : (tower.rsrp_dbm > -105 ? 'text-amber-400' : 'text-red-400')
              }`}>
                {tower.rsrp_dbm == null ? 'Awaiting telemetry' : tower.rsrp_dbm > -90 ? 'Strong Signal' : (tower.rsrp_dbm > -105 ? 'Fair Signal' : 'Weak Signal')}
              </span>
            </div>
          </div>
        </div>

        {/* =========================================================================
            LEVEL 2: WHY (Root Cause & Predictive Trajectory)
        ========================================================================= */}
        <div className="apple-glass p-4 rounded-2xl border border-white/[0.08] space-y-3">
          <div className="flex items-center justify-between flex-wrap gap-1">
            <span className="text-[11px] font-bold uppercase tracking-wider text-purple-400 font-mono">
              Level 2: Why (Root Cause & Forecast)
            </span>
            <div className="flex items-center space-x-2">
              {forecast?.model_used && (
                <span data-testid="drawer-serving-model" className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-cyan-500/10 border border-cyan-500/25 text-cyan-300">
                  Serving: {forecast.model_used}
                </span>
              )}
              <span className="text-[10px] font-mono text-zinc-500">AI Horizon 1–24h</span>
            </div>
          </div>

          {forecast && (
            <div className={`p-3.5 rounded-xl border text-xs leading-relaxed ${
              forecast.status === 'CRITICAL' ? 'bg-red-500/10 border-red-500/25 text-red-200' :
              forecast.status === 'AT_RISK' ? 'bg-amber-500/10 border-amber-500/25 text-amber-200' :
              'bg-white/[0.03] border-white/[0.06] text-zinc-300'
            }`}>
              <div className="flex items-start space-x-2.5">
                {forecast.status === 'CRITICAL' ? <AlertOctagon className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" /> :
                 forecast.status === 'AT_RISK' ? <AlertTriangle className="w-4 h-4 text-amber-400 flex-shrink-0 mt-0.5" /> :
                 <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0 mt-0.5" />}
                <div>
                  <span className="font-bold block text-white text-[11px]">Temporal Diagnostic</span>
                  <p className="mt-0.5 text-zinc-300">{forecast.summary_sentence}</p>
                </div>
              </div>
            </div>
          )}

          {/* 24-Hour Predictive Forecast Curve */}
          {loading ? (
            <div className="py-8 text-center text-xs text-zinc-500 font-mono animate-pulse">
              Loading multi-horizon forecast...
            </div>
          ) : forecast ? (
            <ForecastChart
              currentLoad={tower.current_load_pct ?? 50.0}
              points={forecast.forecast_points}
              thresholdPct={85.0}
            />
          ) : null}
        </div>

        {/* =========================================================================
            LEVEL 3: ACTION (Prescribed Operational Recommendation)
        ========================================================================= */}
        <div className="apple-glass p-4 rounded-2xl border border-emerald-500/20 bg-emerald-500/[0.02] space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold uppercase tracking-wider text-emerald-400 font-mono flex items-center space-x-1">
              <ArrowUpRight className="w-3.5 h-3.5" />
              <span>Level 3: Action</span>
            </span>
            <span className="text-[10px] font-mono text-zinc-500">Autonomous Advice</span>
          </div>

          <div className="bg-black/40 p-3.5 rounded-xl border border-emerald-500/20 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-white">
                {forecast ? forecast.recommended_action : 'NOMINAL: Monitor fleet status.'}
              </span>
              <span className="text-[9px] font-mono text-emerald-300 px-2 py-0.5 rounded-full bg-emerald-500/20 font-bold">
                RECOMMENDED
              </span>
            </div>
            <p className="text-[11px] text-zinc-400 leading-relaxed">
              Based on signal quality (RSRP: {tower.rsrp_dbm ? tower.rsrp_dbm.toFixed(1) : '-88'} dBm) and projected load trajectory.
            </p>
          </div>
        </div>

      </div>
    </div>
  );
};
