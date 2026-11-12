import React, { useEffect, useMemo, useState } from 'react';
import { AlertItem, AlertAuditLogItem } from '../types/telemetry';
import { fetchAlertAuditLog } from '../services/api';
import { formatIstDateTime } from '../utils/indiaFormat';
import { translate } from '../i18n/translations';
import {
  X,
  AlertOctagon,
  AlertTriangle,
  WifiOff,
  CheckCircle2,
  Clock,
  ShieldAlert,
  Wrench,
  Check,
  MapPin,
  History,
  ListChecks
} from 'lucide-react';

interface AlertsDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  alerts: AlertItem[];
  onAcknowledge: (id: number) => void;
  onResolve: (id: number) => void;
  onSelectTowerId?: (towerId: string) => void;
  language?: string;
}

const SEVERITY_RANK: Record<string, number> = {
  OUTAGE: 3,
  CRITICAL: 2,
  WARNING: 1
};

export const AlertsDrawer: React.FC<AlertsDrawerProps> = ({
  isOpen,
  onClose,
  alerts,
  onAcknowledge,
  onResolve,
  onSelectTowerId,
  language = 'en'
}) => {
  const [activeTab, setActiveTab] = useState<'OPEN' | 'AUDIT'>('OPEN');
  const [auditLogs, setAuditLogs] = useState<AlertAuditLogItem[]>([]);
  const [loadingAudit, setLoadingAudit] = useState(false);

  useEffect(() => {
    if (!isOpen || activeTab !== 'AUDIT') return;
    setLoadingAudit(true);
    fetchAlertAuditLog(80)
      .then((logs) => setAuditLogs(logs))
      .catch((err) => console.warn('Could not load alert audit log:', err))
      .finally(() => setLoadingAudit(false));
  }, [isOpen, activeTab, alerts.length]);

  const sortedOpenAlerts = useMemo(() => {
    const open = alerts.filter((a) => a.status === 'ACTIVE' || a.status === 'ACKNOWLEDGED');
    return [...open].sort((a, b) => {
      const rankDiff = (SEVERITY_RANK[b.severity] || 0) - (SEVERITY_RANK[a.severity] || 0);
      if (rankDiff !== 0) return rankDiff;
      return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
    });
  }, [alerts]);

  const groupedByCity = useMemo(() => {
    const groups: Record<string, AlertItem[]> = {};
    sortedOpenAlerts.forEach((alert) => {
      const cityKey = alert.city || 'Other India';
      if (!groups[cityKey]) groups[cityKey] = [];
      groups[cityKey].push(alert);
    });
    return Object.entries(groups);
  }, [sortedOpenAlerts]);

  if (!isOpen) return null;

  const activeUnreadCount = sortedOpenAlerts.filter((a) => a.status === 'ACTIVE').length;

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/60 backdrop-blur-sm animate-in fade-in">
      <div className="w-full max-w-xl bg-zinc-950/95 backdrop-blur-2xl border-l border-white/10 h-full flex flex-col shadow-2xl text-white">
        {/* Header */}
        <div className="p-4 sm:p-5 border-b border-white/[0.08] flex items-center justify-between bg-black/60">
          <div className="flex items-center space-x-3">
            <div className="p-2.5 rounded-2xl bg-red-500/20 text-red-400 border border-red-500/30">
              <ShieldAlert className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-white tracking-tight">
                {translate(language, 'alerts_title')}
              </h2>
              <p className="text-xs text-zinc-400 font-mono">
                {sortedOpenAlerts.length} open ({activeUnreadCount} unacknowledged) • Single Source of Truth (IST)
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

        {/* Sub-Navigation Tabs: Open Alerts | Audit Log */}
        <div className="px-4 py-2.5 border-b border-white/[0.06] bg-black/30 flex items-center space-x-2">
          <button
            onClick={() => setActiveTab('OPEN')}
            className={`px-3 py-1.5 rounded-xl text-xs font-bold flex items-center space-x-1.5 transition-all cursor-pointer ${
              activeTab === 'OPEN'
                ? 'bg-red-500/20 text-red-300 border border-red-500/30'
                : 'text-zinc-400 hover:text-white hover:bg-white/5 border border-transparent'
            }`}
          >
            <ListChecks className="w-3.5 h-3.5" />
            <span>{translate(language, 'alerts_open_tab', { count: sortedOpenAlerts.length })}</span>
          </button>
          <button
            onClick={() => setActiveTab('AUDIT')}
            className={`px-3 py-1.5 rounded-xl text-xs font-bold flex items-center space-x-1.5 transition-all cursor-pointer ${
              activeTab === 'AUDIT'
                ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30'
                : 'text-zinc-400 hover:text-white hover:bg-white/5 border border-transparent'
            }`}
          >
            <History className="w-3.5 h-3.5" />
            <span>{translate(language, 'alerts_audit_tab')}</span>
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-5 space-y-5">
          {activeTab === 'OPEN' ? (
            sortedOpenAlerts.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center text-center p-8 space-y-3">
                <div className="p-4 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                  <CheckCircle2 className="w-8 h-8" />
                </div>
                <h3 className="text-sm font-bold text-white">{translate(language, 'alerts_empty_title')}</h3>
                <p className="text-xs text-zinc-400 max-w-xs leading-relaxed">
                  {translate(language, 'alerts_empty_desc')}
                </p>
              </div>
            ) : (
              groupedByCity.map(([city, cityAlerts]) => (
                <div key={city} className="space-y-2.5">
                  <div className="flex items-center justify-between px-1">
                    <span className="text-[11px] font-mono font-bold uppercase tracking-wider text-zinc-400 flex items-center space-x-1.5">
                      <MapPin className="w-3 h-3 text-cyan-400" />
                      <span>{city}</span>
                    </span>
                    <span className="text-[10px] font-mono text-zinc-500">
                      {cityAlerts.length} open
                    </span>
                  </div>

                  {cityAlerts.map((alert) => {
                    const isOutage = alert.severity === 'OUTAGE';
                    const isCrit = alert.severity === 'CRITICAL';
                    const evidenceEntries = alert.evidence
                      ? Object.entries(alert.evidence).filter(([k]) => !k.startsWith('_'))
                      : [];

                    return (
                      <div
                        key={alert.id}
                        className={`apple-glass p-4 rounded-2xl border space-y-3 transition-all ${
                          isOutage
                            ? 'border-rose-500/50 bg-rose-500/[0.06]'
                            : isCrit
                            ? 'border-red-500/35 bg-red-500/[0.04]'
                            : 'border-amber-500/35 bg-amber-500/[0.04]'
                        }`}
                      >
                        {/* Top Badges */}
                        <div className="flex items-start justify-between gap-2">
                          <div className="flex items-start space-x-2.5">
                            {isOutage ? (
                              <WifiOff className="w-4 h-4 text-rose-400 flex-shrink-0 mt-0.5" />
                            ) : isCrit ? (
                              <AlertOctagon className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" />
                            ) : (
                              <AlertTriangle className="w-4 h-4 text-amber-400 flex-shrink-0 mt-0.5" />
                            )}
                            <div>
                              <div className="flex flex-wrap items-center gap-1.5 mb-1">
                                <span
                                  className={`text-[9px] font-mono px-2 py-0.5 rounded-full font-bold uppercase ${
                                    isOutage
                                      ? 'bg-rose-500/25 text-rose-200 border border-rose-500/40'
                                      : isCrit
                                      ? 'bg-red-500/20 text-red-300 border border-red-500/30'
                                      : 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                                  }`}
                                >
                                  {alert.alert_type || alert.severity}
                                </span>
                                <span
                                  className={`text-[9px] font-mono px-2 py-0.5 rounded-full font-bold border ${
                                    alert.provenance === 'REAL'
                                      ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
                                      : 'bg-amber-500/15 text-amber-300 border-amber-500/30'
                                  }`}
                                >
                                  {alert.provenance || 'SIMULATED'}
                                </span>
                                {alert.source === 'demo' && (
                                  <span
                                    data-testid="demo-alert-badge"
                                    className="text-[9px] font-mono px-2 py-0.5 rounded-full font-extrabold bg-purple-500/25 text-purple-200 border border-purple-400/50"
                                  >
                                    {translate(language, 'alerts_demo_badge')}
                                  </span>
                                )}
                                <span
                                  className={`text-[9px] font-mono px-2 py-0.5 rounded-full border ${
                                    alert.status === 'ACKNOWLEDGED'
                                      ? 'bg-cyan-500/15 text-cyan-300 border-cyan-500/30'
                                      : 'bg-white/5 text-zinc-300 border-white/10'
                                  }`}
                                >
                                  {alert.status === 'ACKNOWLEDGED' ? 'ACKED' : 'OPEN'}
                                </span>
                              </div>
                              <h3 className="text-xs font-bold text-white">
                                {alert.what || alert.reason}
                              </h3>
                              <p className="text-[11px] text-zinc-400 mt-0.5">
                                Where: <strong className="text-zinc-200">{alert.where_location || `${alert.tower_name || alert.tower_id}, ${alert.city || ''}`}</strong>
                              </p>
                              <p className="text-[10px] text-zinc-500 font-mono flex items-center space-x-1 mt-0.5">
                                <Clock className="w-3 h-3" />
                                <span>{translate(language, 'alerts_forecast_window')}: {alert.when_ist || formatIstDateTime(alert.created_at)}</span>
                              </p>
                            </div>
                          </div>

                          {onSelectTowerId && (
                            <button
                              onClick={() => {
                                onSelectTowerId(alert.tower_id);
                                onClose();
                              }}
                              className="px-2 py-1 rounded-lg bg-white/5 hover:bg-white/15 border border-white/10 text-[10px] font-mono text-cyan-300 cursor-pointer flex-shrink-0"
                            >
                              {alert.tower_id}
                            </button>
                          )}
                        </div>

                        {/* Numeric Evidence Pills */}
                        {evidenceEntries.length > 0 && (
                          <div className="flex flex-wrap gap-1.5 pt-1">
                            {evidenceEntries.slice(0, 6).map(([k, v]) => (
                              <span
                                key={k}
                                className="px-2 py-0.5 rounded-lg bg-black/50 border border-white/10 text-[10px] font-mono text-zinc-300"
                              >
                                <span className="text-zinc-500">{k.replace(/_/g, ' ')}:</span>{' '}
                                <strong className="text-white">{typeof v === 'number' ? v.toFixed(1) : String(v)}</strong>
                              </span>
                            ))}
                          </div>
                        )}

                        {/* Ranked Root-Cause Hypotheses */}
                        {alert.ranked_causes && alert.ranked_causes.length > 0 && (
                          <div className="p-2.5 rounded-xl bg-black/40 border border-white/[0.06] space-y-1">
                            <span className="text-[9px] font-mono font-bold uppercase text-zinc-400">
                              Ranked Cause Hypotheses
                            </span>
                            {alert.ranked_causes.map((c, idx) => (
                              <div key={idx} className="text-[11px] text-zinc-300 flex items-start space-x-1.5">
                                <span className="text-cyan-400 font-mono font-bold">#{idx + 1}</span>
                                <span>
                                  <strong className="text-white">{c.hypothesis}</strong> ({c.likelihood}) — {c.clue}
                                </span>
                              </div>
                            ))}
                          </div>
                        )}

                        {/* Playbook Mitigation & Expected Benefit */}
                        <div className="p-2.5 rounded-xl bg-emerald-500/[0.05] border border-emerald-500/20 space-y-1">
                          <div className="flex items-center space-x-1.5 text-[11px] text-emerald-300 font-bold">
                            <Wrench className="w-3.5 h-3.5 text-emerald-400 flex-shrink-0" />
                            <span>Playbook: {alert.mitigation_action}</span>
                          </div>
                          {alert.expected_benefit && (
                            <p className="text-[10px] text-emerald-200/80 pl-5">
                              Expected Benefit: {alert.expected_benefit}
                            </p>
                          )}
                        </div>

                        {/* Actions */}
                        <div className="flex items-center justify-end space-x-2 pt-1">
                          {alert.status === 'ACTIVE' && (
                            <button
                              onClick={() => onAcknowledge(alert.id)}
                              className="px-3 py-1.5 rounded-xl bg-cyan-500/20 hover:bg-cyan-500/30 border border-cyan-500/30 text-cyan-200 text-[11px] font-bold flex items-center space-x-1 cursor-pointer transition-colors"
                            >
                              <Check className="w-3 h-3" />
                              <span>{translate(language, 'alerts_ack_btn')}</span>
                            </button>
                          )}
                          <button
                            onClick={() => onResolve(alert.id)}
                            className="px-3 py-1.5 rounded-xl bg-emerald-500/20 hover:bg-emerald-500/30 border border-emerald-500/30 text-emerald-200 text-[11px] font-bold flex items-center space-x-1 cursor-pointer transition-colors"
                          >
                            <CheckCircle2 className="w-3 h-3" />
                            <span>{translate(language, 'alerts_resolve_btn')}</span>
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              ))
            )
          ) : loadingAudit ? (
            <div className="py-10 text-center text-xs text-zinc-400 font-mono">
              Loading alert audit trail...
            </div>
          ) : auditLogs.length === 0 ? (
            <div className="py-10 text-center text-xs text-zinc-400 font-mono">
              No audit log transitions recorded yet.
            </div>
          ) : (
            <div className="space-y-2">
              {auditLogs.map((entry) => (
                <div
                  key={entry.id}
                  className="apple-glass p-3 rounded-xl border border-white/[0.07] text-xs space-y-1"
                >
                  <div className="flex items-center justify-between font-mono text-[10px]">
                    <span className="font-bold text-cyan-300">
                      {entry.action} • {entry.tower_id} ({entry.alert_type})
                    </span>
                    <span className="text-zinc-500">{entry.timestamp_ist || formatIstDateTime(entry.timestamp)}</span>
                  </div>
                  {entry.note && <p className="text-[11px] text-zinc-300">{entry.note}</p>}
                  <span className="text-[10px] text-zinc-500 font-mono block">Actor: {entry.actor}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
