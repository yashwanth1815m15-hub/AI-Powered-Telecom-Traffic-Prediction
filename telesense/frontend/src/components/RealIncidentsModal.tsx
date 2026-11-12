import React, { useEffect, useState } from 'react';
import { RealIncident } from '../types/telemetry';
import { fetchIncidents, executeIncidentAction } from '../services/api';
import {
  X,
  Radio,
  CheckCircle2,
  Zap,
  Flame,
  Activity,
  ExternalLink,
  BookOpen
} from 'lucide-react';

interface IncidentsModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSelectTowerAndFly: (towerId: string) => void;
  language: string;
}

export const RealIncidentsModal: React.FC<IncidentsModalProps> = ({
  isOpen,
  onClose,
  onSelectTowerAndFly,
  language
}) => {
  const [incidents, setIncidents] = useState<RealIncident[]>([]);
  const [selectedIncident, setSelectedIncident] = useState<RealIncident | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [actionStatus, setActionStatus] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      fetchIncidents()
        .then((data) => {
          setIncidents(data);
          if (data.length > 0 && !selectedIncident) {
            setSelectedIncident(data[0]);
          }
        })
        .catch((err) => console.error('Failed to fetch real incidents:', err));
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleAction = async (actionType: 'REPLAY_FAILURE' | 'APPLY_SOLUTION') => {
    if (!selectedIncident) return;
    setLoading(true);
    setActionStatus(null);
    try {
      const res = await executeIncidentAction(selectedIncident.id, actionType);
      setActionStatus(res.message);
      onSelectTowerAndFly(selectedIncident.tower_id);
    } catch (err: any) {
      console.error(err);
      setActionStatus('Failed to execute operator action.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-6 bg-black/80 backdrop-blur-2xl animate-in fade-in duration-200">
      <div className="relative w-full max-w-5xl max-h-[92vh] flex flex-col apple-glass-card border border-white/10 rounded-3xl overflow-hidden shadow-2xl bg-zinc-950/90 text-white">
        {/* Header */}
        <div className="p-5 sm:p-6 border-b border-white/[0.08] flex items-center justify-between bg-black/50">
          <div className="flex items-center space-x-3.5">
            <div className="p-2.5 rounded-2xl bg-purple-500/10 border border-purple-500/20 text-purple-400">
              <Radio className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center space-x-2.5">
                <h2 className="text-lg sm:text-xl font-bold tracking-tight text-white">
                  Published Indian Telecom Case Studies & Event Dynamics
                </h2>
                <span className="apple-pill px-2.5 py-0.5 text-[10px] font-mono text-emerald-400 font-bold bg-emerald-500/10 border-emerald-500/20">
                  REAL CITATIONS
                </span>
              </div>
              <p className="text-xs text-zinc-400 mt-0.5">
                Documented mobile network performance studies with primary source citations (Ookla & Opensignal).
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

        {/* Content Body */}
        <div className="flex-1 overflow-y-auto grid grid-cols-1 md:grid-cols-12 divide-y md:divide-y-0 md:divide-x divide-white/[0.08]">
          {/* Left Column: Case Selector */}
          <div className="md:col-span-5 p-4 sm:p-5 space-y-3 overflow-y-auto max-h-[70vh]">
            <span className="text-[10px] font-bold uppercase tracking-wider text-zinc-400 font-mono px-1">
              Documented Industry Studies ({incidents.length})
            </span>

            {incidents.map((inc) => {
              const isSelected = selectedIncident?.id === inc.id;
              return (
                <div
                  key={inc.id}
                  onClick={() => {
                    setSelectedIncident(inc);
                    setActionStatus(null);
                  }}
                  className={`p-4 rounded-2xl border transition-all cursor-pointer ${
                    isSelected
                      ? 'bg-purple-500/15 border-purple-500/40 shadow-lg shadow-purple-500/10'
                      : 'apple-glass hover:bg-white/[0.04] border-white/[0.06]'
                  }`}
                >
                  <div className="flex items-center justify-between text-xs mb-1.5">
                    <span className="font-mono text-[10px] text-zinc-400 font-bold">{inc.date_recorded}</span>
                    <span className="text-[9px] font-bold px-2 py-0.5 rounded-full uppercase bg-amber-500/20 text-amber-300 border border-amber-500/30">
                      {inc.severity.replace('_', ' ')}
                    </span>
                  </div>

                  <h3 className="text-xs sm:text-sm font-bold text-white leading-snug">
                    {inc.title}
                  </h3>

                  <p className="text-[11px] text-zinc-400 mt-1 line-clamp-2">
                    {inc.venue} • {inc.city}
                  </p>

                  {/* Primary Source Link on Card */}
                  <div className="mt-3 flex items-center justify-between text-[11px] font-mono border-t border-white/[0.06] pt-2">
                    <a
                      href={inc.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      onClick={(e) => e.stopPropagation()}
                      className="text-cyan-400 hover:text-cyan-300 flex items-center space-x-1 hover:underline text-[10px]"
                    >
                      <BookOpen className="w-3 h-3" />
                      <span className="truncate max-w-[170px]">{inc.source_name}</span>
                      <ExternalLink className="w-2.5 h-2.5" />
                    </a>
                    <span className="font-bold text-red-400">
                      {inc.peak_load_pct}% Load
                    </span>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Right Column: Case Details & Mitigation */}
          <div className="md:col-span-7 p-5 sm:p-6 space-y-5 overflow-y-auto max-h-[70vh]">
            {selectedIncident ? (
              <div className="space-y-5">
                {/* Case Title & Source Citation */}
                <div>
                  <div className="flex items-center space-x-2 text-[10px] font-mono text-cyan-400 uppercase font-bold">
                    <span>{selectedIncident.circle}</span>
                    <span>•</span>
                    <span>Target Tower: {selectedIncident.tower_id}</span>
                  </div>
                  <h3 className="text-lg sm:text-xl font-black text-white mt-1">
                    {selectedIncident.title}
                  </h3>
                  <p className="text-xs text-zinc-400 mt-1 font-medium">
                    {selectedIncident.venue} • Operators: {selectedIncident.operators_impacted}
                  </p>
                </div>

                {/* Primary Source Reference Box */}
                <div className="apple-glass p-3 rounded-2xl border-cyan-500/20 bg-cyan-500/[0.04] flex items-center justify-between">
                  <div className="flex items-center space-x-2.5">
                    <BookOpen className="w-4 h-4 text-cyan-400" />
                    <div>
                      <span className="text-[10px] uppercase font-bold text-zinc-400 block">Primary Published Report</span>
                      <span className="text-xs font-semibold text-white">{selectedIncident.source_name}</span>
                    </div>
                  </div>
                  <a
                    href={selectedIncident.source_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center space-x-1 px-3 py-1.5 rounded-full bg-cyan-500/20 text-cyan-300 hover:bg-cyan-500/30 text-xs font-bold transition-colors"
                  >
                    <span>View Report</span>
                    <ExternalLink className="w-3 h-3" />
                  </a>
                </div>

                {selectedIncident.statement_url && selectedIncident.statement_url !== selectedIncident.source_url && (
                  <div className="apple-glass p-3 rounded-2xl border-purple-500/20 bg-purple-500/[0.04] flex items-center justify-between">
                    <div className="flex items-center space-x-2.5">
                      <BookOpen className="w-4 h-4 text-purple-400" />
                      <div>
                        <span className="text-[10px] uppercase font-bold text-zinc-400 block">Operator Statement Link</span>
                        <span className="text-xs font-semibold text-white">Jio & Ericsson Official Traffic Statement</span>
                      </div>
                    </div>
                    <a
                      href={selectedIncident.statement_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center space-x-1 px-3 py-1.5 rounded-full bg-purple-500/20 text-purple-300 hover:bg-purple-500/30 text-xs font-bold transition-colors"
                    >
                      <span>View Statement</span>
                      <ExternalLink className="w-3 h-3" />
                    </a>
                  </div>
                )}

                {/* Key Metrics Pill Bar */}
                <div className="grid grid-cols-3 gap-2.5">
                  <div className="apple-glass p-3 rounded-2xl text-center">
                    <span className="text-[10px] text-zinc-400 uppercase font-semibold">Reported Peak Load</span>
                    <div className="text-lg font-black text-red-400 font-mono mt-0.5">
                      {selectedIncident.peak_load_pct}%
                    </div>
                  </div>
                  <div className="apple-glass p-3 rounded-2xl text-center">
                    <span className="text-[10px] text-zinc-400 uppercase font-semibold">Concurrency</span>
                    <div className="text-lg font-black text-white font-mono mt-0.5">
                      {selectedIncident.peak_active_users.toLocaleString()}
                    </div>
                  </div>
                  <div className="apple-glass p-3 rounded-2xl text-center">
                    <span className="text-[10px] text-zinc-400 uppercase font-semibold">Peak DCR</span>
                    <div className="text-lg font-black text-amber-400 font-mono mt-0.5">
                      {selectedIncident.drop_call_rate_pct}%
                    </div>
                  </div>
                </div>

                {/* Documented Summary */}
                <div className="apple-glass p-4 rounded-2xl border-white/[0.08] space-y-2">
                  <span className="text-[10px] text-zinc-400 uppercase font-bold tracking-wider font-mono">
                    Documented Operational Telemetry
                  </span>
                  <p className="text-xs text-zinc-300 leading-relaxed font-medium">
                    {selectedIncident.summary}
                  </p>
                  {selectedIncident.demo_inspiration_note && (
                    <div className="mt-2 p-2.5 rounded-xl bg-amber-500/10 border border-amber-500/20 text-[11px] text-amber-200 font-medium">
                      {selectedIncident.demo_inspiration_note}
                    </div>
                  )}
                </div>

                {/* Operator Resolution */}
                <div className="apple-glass p-4 rounded-2xl border-emerald-500/20 bg-emerald-500/[0.03] space-y-2">
                  <div className="flex items-center space-x-2 text-emerald-400 text-xs font-bold font-mono">
                    <CheckCircle2 className="w-4 h-4" />
                    <span>Standard Operator Mitigation Actions</span>
                  </div>
                  <pre className="text-xs text-zinc-300 leading-relaxed font-sans whitespace-pre-wrap">
                    {selectedIncident.standard_telecom_solution}
                  </pre>
                  <div className="flex items-center space-x-4 pt-1 text-[11px] font-mono text-emerald-300 font-bold border-t border-emerald-500/20">
                    <span>Target Recovery Load: {selectedIncident.post_fix_expected_load_pct}%</span>
                    <span>•</span>
                    <span>Target DCR: {selectedIncident.post_fix_expected_dcr_pct}%</span>
                  </div>
                </div>

                {/* Status Message */}
                {actionStatus && (
                  <div className="p-3.5 rounded-2xl bg-cyan-500/10 border border-cyan-500/30 text-cyan-200 text-xs font-medium flex items-center space-x-2 animate-in fade-in">
                    <Activity className="w-4 h-4 text-cyan-400 flex-shrink-0" />
                    <span>{actionStatus}</span>
                  </div>
                )}

                {/* Action Buttons */}
                <div className="flex items-center space-x-3 pt-2">
                  <button
                    onClick={() => handleAction('REPLAY_FAILURE')}
                    disabled={loading}
                    className="flex-1 py-3 px-4 rounded-2xl bg-red-500/20 hover:bg-red-500/30 border border-red-500/40 text-red-200 hover:text-white text-xs font-bold transition-all cursor-pointer flex items-center justify-center space-x-2 shadow-lg shadow-red-500/10 disabled:opacity-50"
                  >
                    <Flame className="w-4 h-4 text-red-400" />
                    <span>Replay Event Load</span>
                  </button>

                  <button
                    onClick={() => handleAction('APPLY_SOLUTION')}
                    disabled={loading}
                    className="flex-1 py-3 px-4 rounded-2xl bg-emerald-500 hover:bg-emerald-400 text-black text-xs font-bold transition-all cursor-pointer flex items-center justify-center space-x-2 shadow-lg shadow-emerald-500/20 disabled:opacity-50"
                  >
                    <Zap className="w-4 h-4 fill-black" />
                    <span>Apply Mitigation</span>
                  </button>
                </div>
              </div>
            ) : (
              <div className="h-full flex items-center justify-center text-xs text-zinc-500 font-mono">
                Select an incident to view study details
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
