import React, { useState, useEffect } from 'react';
import { Tower } from '../types/telemetry';
import { simulateWhatIf } from '../services/api';
import { Sliders, Sparkles, TrendingUp, Users, Radio, ArrowRight, Calculator, HelpCircle, ChevronDown, ChevronUp } from 'lucide-react';
import { translate } from '../i18n/translations';

interface WhatIfLabViewProps {
  towers: Tower[];
  language: string;
}

export const WhatIfLabView: React.FC<WhatIfLabViewProps> = ({ towers, language }) => {
  const [selectedTowerId, setSelectedTowerId] = useState<string>(towers[0]?.tower_id || 'MUM-C101');
  const [extraUsers, setExtraUsers] = useState<number>(800);
  const [trafficGrowthPct, setTrafficGrowthPct] = useState<number>(30.0);
  const [addCarrier, setAddCarrier] = useState<boolean>(false);

  // Editable Mathematical Assumptions for Modelled Users
  const [showFormulaModal, setShowFormulaModal] = useState<boolean>(false);
  const [marketSharePct, setMarketSharePct] = useState<number>(38.0); // TRAI PR 104/2026 default
  const [busyHourFactorPct, setBusyHourFactorPct] = useState<number>(12.0);

  const [simulationResult, setSimulationResult] = useState<any>(null);
  const [loading, setLoading] = useState<boolean>(false);

  useEffect(() => {
    if (towers.length > 0 && !towers.some(t => t.tower_id === selectedTowerId)) {
      setSelectedTowerId(towers[0].tower_id);
    }
  }, [towers]);

  const handleSimulate = async () => {
    if (!selectedTowerId) return;
    setLoading(true);
    try {
      const res = await simulateWhatIf({
        tower_id: selectedTowerId,
        extra_users: extraUsers,
        traffic_growth_pct: trafficGrowthPct,
        add_carrier_bandwidth: addCarrier
      });
      setSimulationResult(res);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    handleSimulate();
  }, [selectedTowerId, extraUsers, trafficGrowthPct, addCarrier]);

  const currentTower = towers.find(t => t.tower_id === selectedTowerId) || towers[0];
  const popDensity = currentTower?.population_density || 12000;
  // Standard Modelled Formula: Population x MarketShare x BusyHourFactor
  const calculatedBaselineUsers = Math.round(popDensity * (marketSharePct / 100.0) * (busyHourFactorPct / 100.0));

  return (
    <div className="max-w-6xl mx-auto p-4 sm:p-6 space-y-6 text-white">
      {/* Header */}
      <div className="apple-glass-card p-6 sm:p-7 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center space-x-3.5">
          <div className="p-2.5 rounded-2xl bg-purple-500/10 border border-purple-500/20 text-purple-400">
            <Sliders className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h1 className="text-xl sm:text-2xl font-bold tracking-tight">{translate(language, 'whatif_title')}</h1>
              <span className="px-2 py-0.5 rounded text-[9px] font-mono font-bold bg-cyan-500/10 text-cyan-300 border border-cyan-500/20">
                MODELLED ENGINE
              </span>
            </div>
            <p className="text-xs text-zinc-400 mt-0.5">
              {translate(language, 'whatif_subtitle')}
            </p>
          </div>
        </div>

        <button
          onClick={() => setShowFormulaModal(!showFormulaModal)}
          className="flex items-center space-x-1.5 px-3.5 py-1.5 rounded-full bg-cyan-500/15 hover:bg-cyan-500/25 border border-cyan-500/30 text-cyan-300 text-xs font-bold transition-all cursor-pointer"
        >
          <Calculator className="w-3.5 h-3.5" />
          <span>{translate(language, 'whatif_formula_btn')}</span>
          {showFormulaModal ? <ChevronUp className="w-3 h-3 ml-1" /> : <ChevronDown className="w-3 h-3 ml-1" />}
        </button>
      </div>

      {/* "How this is calculated" Expandable Panel */}
      {showFormulaModal && (
        <div className="apple-glass-card p-6 border-cyan-500/30 bg-cyan-500/[0.03] space-y-4 animate-in fade-in duration-200">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold uppercase tracking-wider font-mono text-cyan-300 flex items-center space-x-2">
              <Calculator className="w-4 h-4" />
              <span>Modelled Active Users: Calculation Formula & Assumptions</span>
            </h3>
            <span className="text-[10px] font-mono text-zinc-400">Honest Metric Provenance</span>
          </div>

          <p className="text-xs text-zinc-300 leading-relaxed font-sans">
            Real per-tower active subscriber counts are strictly internal to operator core packet gateways (AMF/MME).
            TeleSense computes an explainable <strong>MODELLED</strong> estimate using the standard cellular traffic engineering equation:
          </p>

          <div className="p-3.5 rounded-xl bg-black/60 border border-white/[0.08] text-xs font-mono text-cyan-200">
            Active UEs = Catchment Population &times; Operator Market Share &times; Busy-Hour Activity Factor &times; Diurnal Curve
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-1">
            {/* Operator Market Share Slider */}
            <div className="space-y-1.5">
              <div className="flex justify-between text-xs">
                <span className="text-zinc-400">Operator Market Share:</span>
                <span className="font-bold text-white font-mono">{marketSharePct}% (TRAI PR 104/2026)</span>
              </div>
              <input
                type="range"
                min={15}
                max={50}
                step={1}
                value={marketSharePct}
                onChange={(e) => setMarketSharePct(Number(e.target.value))}
                className="w-full accent-cyan-400 bg-zinc-800 rounded-lg cursor-pointer h-1.5"
              />
            </div>

            {/* Busy-Hour Activity Slider */}
            <div className="space-y-1.5">
              <div className="flex justify-between text-xs">
                <span className="text-zinc-400">Busy-Hour Concurrency:</span>
                <span className="font-bold text-white font-mono">{busyHourFactorPct}% active</span>
              </div>
              <input
                type="range"
                min={5}
                max={25}
                step={1}
                value={busyHourFactorPct}
                onChange={(e) => setBusyHourFactorPct(Number(e.target.value))}
                className="w-full accent-cyan-400 bg-zinc-800 rounded-lg cursor-pointer h-1.5"
              />
            </div>
          </div>

          <div className="text-[11px] font-mono text-zinc-400 pt-1 border-t border-white/[0.06]">
            Target Node ({currentTower?.city}) Catchment Density: {popDensity.toLocaleString()}/km² &rarr; Resulting Modelled Baseline: <strong className="text-white">{calculatedBaselineUsers.toLocaleString()} active UEs</strong>.
          </div>
        </div>
      )}

      {/* Main Grid */}
      <div className="grid grid-cols-1 md:grid-cols-12 gap-6">
        {/* Controls Column (5 cols) */}
        <div className="md:col-span-5 apple-glass-card p-6 space-y-6">
          <h2 className="text-xs font-bold text-zinc-300 uppercase tracking-wider flex items-center space-x-2 font-mono">
            <Sparkles className="w-3.5 h-3.5 text-purple-400" />
            <span>Scenario Stress Parameters</span>
          </h2>

          {/* Select Tower */}
          <div>
            <label className="text-xs font-semibold text-zinc-300 block mb-1.5">Select Cell Tower</label>
            <select
              value={selectedTowerId}
              onChange={(e) => setSelectedTowerId(e.target.value)}
              className="w-full bg-black/60 border border-white/10 rounded-xl px-3.5 py-2.5 text-xs text-white focus:outline-none focus:border-cyan-500 font-mono cursor-pointer"
            >
              {towers.map((t) => (
                <option key={t.tower_id} value={t.tower_id} className="bg-zinc-900">
                  {t.name} ({t.city}) — {t.tower_id}
                </option>
              ))}
            </select>
          </div>

          {/* Slider 1: Additional Connected Users */}
          <div className="space-y-2">
            <div className="flex items-center justify-between text-xs">
              <span className="text-zinc-300 font-semibold flex items-center space-x-1.5">
                <Users className="w-3.5 h-3.5 text-blue-400" />
                <span>Additional Subscribers (UEs)</span>
              </span>
              <span className="font-mono font-bold text-cyan-400 text-xs px-2 py-0.5 rounded-full bg-cyan-500/10 border border-cyan-500/20">
                +{extraUsers} Users
              </span>
            </div>
            <input
              type="range"
              min={0}
              max={2500}
              step={100}
              value={extraUsers}
              onChange={(e) => setExtraUsers(Number(e.target.value))}
              className="w-full accent-cyan-500 bg-zinc-800 rounded-lg cursor-pointer h-2"
            />
            <div className="flex justify-between text-[10px] text-zinc-500 font-mono">
              <span>0 (Baseline)</span>
              <span>+1,250</span>
              <span>+2,500 UEs</span>
            </div>
          </div>

          {/* Slider 2: Annual Data Traffic Growth */}
          <div className="space-y-2">
            <div className="flex items-center justify-between text-xs">
              <span className="text-zinc-300 font-semibold flex items-center space-x-1.5">
                <TrendingUp className="w-3.5 h-3.5 text-amber-400" />
                <span>Annual Data Traffic Growth</span>
              </span>
              <span className="font-mono font-bold text-amber-400 text-xs px-2 py-0.5 rounded-full bg-amber-500/10 border border-amber-500/20">
                +{trafficGrowthPct}% Growth
              </span>
            </div>
            <input
              type="range"
              min={0}
              max={60}
              step={5}
              value={trafficGrowthPct}
              onChange={(e) => setTrafficGrowthPct(Number(e.target.value))}
              className="w-full accent-amber-500 bg-zinc-800 rounded-lg cursor-pointer h-2"
            />
            <div className="flex justify-between text-[10px] text-zinc-500 font-mono">
              <span>0% (Flat)</span>
              <span>+30%</span>
              <span>+60% Surge</span>
            </div>
          </div>

          {/* Toggle: Add Carrier Aggregation */}
          <div className="flex items-center justify-between p-3.5 bg-black/40 border border-white/[0.08] rounded-2xl">
            <div className="flex items-center space-x-3">
              <Radio className="w-4 h-4 text-purple-400" />
              <div>
                <span className="text-xs font-bold text-white block">Add Carrier Aggregation</span>
                <span className="text-[10px] text-zinc-400">+20 MHz Spectrum Band (+40% Capacity)</span>
              </div>
            </div>
            <button
              onClick={() => setAddCarrier(!addCarrier)}
              className={`w-12 h-6 flex items-center rounded-full p-1 cursor-pointer transition-colors ${
                addCarrier ? 'bg-cyan-500' : 'bg-zinc-700'
              }`}
            >
              <div
                className={`bg-white w-4 h-4 rounded-full shadow-md transform transition-transform ${
                  addCarrier ? 'translate-x-6' : 'translate-x-0'
                }`}
              />
            </button>
          </div>
        </div>

        {/* Results Column (7 cols) */}
        <div className="md:col-span-7 space-y-4">
          {simulationResult && (
            <>
              {/* Load Comparison Box */}
              <div className="apple-glass-card p-6 space-y-5">
                <h3 className="text-xs font-bold text-zinc-400 uppercase tracking-wider font-mono">
                  Peak Traffic Load Comparison
                </h3>

                <div className="grid grid-cols-2 gap-4">
                  {/* Baseline Card */}
                  <div className="apple-glass p-4 rounded-2xl text-center space-y-1">
                    <span className="text-[10px] text-zinc-400 uppercase font-semibold block">Baseline Peak Load</span>
                    <div className="text-3xl font-black text-white font-mono">
                      {simulationResult.baseline_peak_load_pct?.toFixed(1)}%
                    </div>
                    <div className="w-full bg-zinc-800 h-1.5 rounded-full overflow-hidden mt-2">
                      <div
                        className="bg-zinc-400 h-full rounded-full"
                        style={{ width: `${Math.min(100, simulationResult.baseline_peak_load_pct)}%` }}
                      />
                    </div>
                    <span className="text-[10px] text-zinc-500 block pt-1">Current unmodified peak</span>
                  </div>

                  {/* Simulated Card */}
                  <div className={`p-4 rounded-2xl border text-center space-y-1 ${
                    simulationResult.simulated_peak_load_pct >= 85
                      ? 'bg-red-500/10 border-red-500/30 text-red-300'
                      : 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
                  }`}>
                    <span className="text-[10px] uppercase font-semibold block">Simulated Peak Load</span>
                    <div className="text-3xl font-black font-mono">
                      {simulationResult.simulated_peak_load_pct?.toFixed(1)}%
                    </div>
                    <div className="w-full bg-black/40 h-1.5 rounded-full overflow-hidden mt-2">
                      <div
                        className={`h-full rounded-full ${
                          simulationResult.simulated_peak_load_pct >= 85 ? 'bg-red-500' : 'bg-emerald-400'
                        }`}
                        style={{ width: `${Math.min(100, simulationResult.simulated_peak_load_pct)}%` }}
                      />
                    </div>
                    <span className="text-[10px] font-bold block pt-1">
                      {simulationResult.simulated_peak_load_pct >= 85 ? 'Overload Risk (>= 85%)' : 'Operating within Headroom'}
                    </span>
                  </div>
                </div>

                {/* Plain English Impact Summary */}
                <div className="p-4 apple-glass rounded-2xl text-xs text-zinc-200 leading-relaxed space-y-1">
                  <strong className="text-cyan-400 block uppercase tracking-wider text-[11px] font-mono">
                    Impact Takeaway:
                  </strong>
                  <p>{simulationResult.impact_summary}</p>
                </div>
              </div>

              {/* Action Transition Comparison */}
              <div className="apple-glass-card p-6 space-y-3">
                <h3 className="text-xs font-bold text-zinc-400 uppercase tracking-wider font-mono">
                  Prescribed Action Transition
                </h3>

                <div className="flex items-center justify-between flex-wrap gap-3 p-4 apple-glass rounded-2xl">
                  <div className="flex-1">
                    <span className="text-[10px] text-zinc-500 uppercase font-semibold block">Baseline Action</span>
                    <span className="text-xs font-bold text-zinc-300 font-mono">
                      {simulationResult.baseline_recommendation}
                    </span>
                  </div>

                  <ArrowRight className="w-5 h-5 text-zinc-500 flex-shrink-0" />

                  <div className="flex-1 text-right">
                    <span className="text-[10px] text-cyan-400 uppercase font-semibold block">Simulated Action</span>
                    <span className="text-xs font-bold text-cyan-300 font-mono">
                      {simulationResult.simulated_recommendation}
                    </span>
                  </div>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};
