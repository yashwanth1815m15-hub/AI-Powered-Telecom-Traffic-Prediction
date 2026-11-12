import React, { useEffect, useState } from 'react';
import { RecommendationItem } from '../types/telemetry';
import { fetchPlannerRanked } from '../services/api';
import { BarChart3, Download } from 'lucide-react';
import { formatInrLakhCrore } from '../utils/indiaFormat';
import { translate } from '../i18n/translations';

interface PlannerViewProps {
  language: string;
}

export const PlannerView: React.FC<PlannerViewProps> = ({ language }) => {
  const [recommendations, setRecommendations] = useState<RecommendationItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [selectedFilter, setSelectedFilter] = useState<string>('ALL');

  useEffect(() => {
    setLoading(true);
    fetchPlannerRanked()
      .then((data) => setRecommendations(data))
      .catch((err) => console.error(err))
      .finally(() => setLoading(false));
  }, []);

  // Summary Calculations
  const totalCapexInr = recommendations.reduce((acc, r) => acc + (r.estimated_cost_inr || 0), 0);
  const totalCapexCrores = (totalCapexInr / 10000000).toFixed(2);
  const totalCapexLakhs = (totalCapexInr / 100000).toFixed(1);
  const urgentCount = recommendations.filter((r) => r.priority_rank === 1).length;
  const recommendedCount = recommendations.filter((r) => r.priority_rank === 2).length;

  const filtered = recommendations.filter((r) => {
    if (selectedFilter === 'ALL') return true;
    if (selectedFilter === 'PRIORITY_1') return r.priority_rank === 1;
    if (selectedFilter === 'PRIORITY_2') return r.priority_rank === 2;
    return true;
  });

  const handleExportCsv = () => {
    const headers = ['Rank', 'Tower ID', 'City', 'Action', 'Confidence %', 'Estimated Cost INR', 'Payback Months', 'Evidence'];
    const rows = recommendations.map((r) => [
      r.priority_rank,
      r.tower_id,
      r.city || 'N/A',
      `"${r.action}"`,
      r.confidence_pct,
      r.estimated_cost_inr,
      r.payback_months,
      `"${r.evidence_numbers}"`
    ]);
    const csvContent = 'data:text/csv;charset=utf-8,' + [headers.join(','), ...rows.map((e) => e.join(','))].join('\n');
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement('a');
    link.setAttribute('href', encodedUri);
    link.setAttribute('download', `TeleSense_Capex_Roadmap_${new Date().toISOString().slice(0, 10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="max-w-7xl mx-auto p-4 sm:p-6 space-y-6">
      {/* Apple Executive Header */}
      <div className="apple-glass-card p-6 sm:p-7 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-3">
            <div className="p-2.5 rounded-2xl bg-cyan-500/10 border border-cyan-500/20 text-cyan-400">
              <BarChart3 className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-xl sm:text-2xl font-bold text-white tracking-tight">
                {translate(language, 'planner_title')}
              </h1>
              <p className="text-xs text-zinc-400 mt-0.5">
                {translate(language, 'planner_subtitle')}
              </p>
            </div>
          </div>
        </div>

        <button
          onClick={handleExportCsv}
          className="flex items-center space-x-2 px-4 py-2 bg-white text-black font-bold rounded-full text-xs shadow-lg shadow-white/10 hover:bg-zinc-200 transition-all cursor-pointer self-start sm:self-auto"
        >
          <Download className="w-3.5 h-3.5" />
          <span>Export Capex CSV</span>
        </button>
      </div>

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
        {/* Total Projected Capex */}
        <div className="apple-glass-card p-5 space-y-1">
          <span className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider font-mono block">
            Total Capital Investment
          </span>
          <div className="text-3xl font-black text-cyan-400 font-mono tracking-tight">
            ₹{totalCapexCrores} <span className="text-xs font-normal text-zinc-400">Crores</span>
          </div>
          <span className="text-[11px] text-zinc-500 font-mono block">₹{totalCapexLakhs} Lakhs Total</span>
        </div>

        {/* Priority 1 Urgent Sites */}
        <div className="apple-glass-card p-5 space-y-1 border-red-500/20 bg-red-500/[0.03]">
          <span className="text-[10px] font-bold text-red-400 uppercase tracking-wider font-mono block">
            Priority 1 (Urgent Intervention)
          </span>
          <div className="text-3xl font-black text-red-400 font-mono tracking-tight">
            {urgentCount} <span className="text-xs font-normal text-zinc-400">Sites</span>
          </div>
          <span className="text-[11px] text-zinc-500 block">Chronic saturation & signal holes</span>
        </div>

        {/* Priority 2 Recommended */}
        <div className="apple-glass-card p-5 space-y-1 border-amber-500/20 bg-amber-500/[0.03]">
          <span className="text-[10px] font-bold text-amber-400 uppercase tracking-wider font-mono block">
            Priority 2 (Recommended)
          </span>
          <div className="text-3xl font-black text-amber-400 font-mono tracking-tight">
            {recommendedCount} <span className="text-xs font-normal text-zinc-400">Sites</span>
          </div>
          <span className="text-[11px] text-zinc-500 block">Carrier aggregation & small cells</span>
        </div>

        {/* Decision Framework */}
        <div className="apple-glass-card p-5 space-y-1">
          <span className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider font-mono block">
            Decision Framework
          </span>
          <div className="text-sm font-bold text-white mt-1">
            Rule-Based Engine
          </div>
          <span className="text-[10px] text-zinc-500 block">85% PRB: operator planning threshold (assumption, configurable)</span>
        </div>
      </div>

      {/* Filter Segmented Control */}
      <div className="flex items-center space-x-1.5 bg-black/40 p-1 rounded-full border border-white/[0.08] w-fit">
        <button
          onClick={() => setSelectedFilter('ALL')}
          className={`px-3.5 py-1.5 rounded-full text-xs font-bold transition-all cursor-pointer ${
            selectedFilter === 'ALL' ? 'bg-white text-black' : 'text-zinc-400 hover:text-white'
          }`}
        >
          All Investments ({recommendations.length})
        </button>
        <button
          onClick={() => setSelectedFilter('PRIORITY_1')}
          className={`px-3.5 py-1.5 rounded-full text-xs font-bold transition-all cursor-pointer ${
            selectedFilter === 'PRIORITY_1' ? 'bg-red-500 text-white' : 'text-zinc-400 hover:text-white'
          }`}
        >
          Priority 1 Urgent ({urgentCount})
        </button>
        <button
          onClick={() => setSelectedFilter('PRIORITY_2')}
          className={`px-3.5 py-1.5 rounded-full text-xs font-bold transition-all cursor-pointer ${
            selectedFilter === 'PRIORITY_2' ? 'bg-amber-400 text-black' : 'text-zinc-400 hover:text-white'
          }`}
        >
          Priority 2 Recommended ({recommendedCount})
        </button>
      </div>

      {/* Ranked Roadmap Table */}
      <div className="apple-glass-card overflow-hidden shadow-2xl">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="bg-black/60 border-b border-white/[0.08] text-zinc-400 font-mono text-[10px] uppercase">
                <th className="p-4">Rank</th>
                <th className="p-4">Tower & Circle</th>
                <th className="p-4">Prescribed Infrastructure Action</th>
                <th className="p-4">Estimated Capex</th>
                <th className="p-4">Payback</th>
                <th className="p-4">Evidence & Root Cause</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/[0.06]">
              {loading ? (
                <tr>
                  <td colSpan={6} className="p-12 text-center text-zinc-500 font-mono">
                    Loading investment roadmap...
                  </td>
                </tr>
              ) : filtered.length === 0 ? (
                <tr>
                  <td colSpan={6} className="p-12 text-center text-zinc-500">
                    No recommendations matching filter.
                  </td>
                </tr>
              ) : (
                filtered.map((r) => (
                  <tr key={r.id} className="hover:bg-white/[0.03] transition-colors">
                    <td className="p-4">
                      <span className={`inline-flex items-center justify-center w-6 h-6 rounded-full font-bold font-mono text-xs ${
                        r.priority_rank === 1 ? 'bg-red-500/20 text-red-300 border border-red-500/40' :
                        r.priority_rank === 2 ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40' :
                        'bg-zinc-800 text-zinc-400'
                      }`}>
                        {r.priority_rank}
                      </span>
                    </td>
                    <td className="p-4">
                      <div className="font-bold text-white text-xs">{r.tower_id}</div>
                      <div className="text-[11px] text-zinc-400">{r.city || 'Regional Hub'}</div>
                    </td>
                    <td className="p-4">
                      <span className={`px-2.5 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider ${
                        r.action.includes('NEW TOWER') ? 'bg-red-500/15 text-red-300 border border-red-500/30' :
                        r.action.includes('BANDWIDTH') ? 'bg-cyan-500/15 text-cyan-300 border border-cyan-500/30' :
                        r.action.includes('SMALL CELL') ? 'bg-amber-500/15 text-amber-300 border border-amber-500/30' :
                        'bg-zinc-800 text-zinc-300'
                      }`}>
                        {r.action}
                      </span>
                    </td>
                    <td className="p-4 font-mono font-bold text-zinc-200">
                      {r.estimated_cost_inr > 0 ? (
                        <span>{formatInrLakhCrore(r.estimated_cost_inr)}</span>
                      ) : (
                        <span className="text-emerald-400 font-semibold">₹0 (OpEx Savings)</span>
                      )}
                    </td>
                    <td className="p-4 font-mono text-zinc-400">
                      {r.payback_months > 0 ? `${r.payback_months} Months` : 'Immediate'}
                    </td>
                    <td className="p-4 text-zinc-300 text-[11px] max-w-xs leading-relaxed">
                      <div>{r.reason}</div>
                      <div className="text-zinc-500 font-mono text-[10px] mt-0.5">{r.evidence_numbers}</div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
