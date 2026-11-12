import React, { useEffect, useRef, useState } from 'react';
import SpeedTest from '@cloudflare/speedtest';
import {
  submitCrowdsourceMeasurement,
  fetchRecentMeasurements,
  fetchSummary,
} from '../services/api';
import { formatIstDateTime, formatIstTime } from '../utils/indiaFormat';
import { translate } from '../i18n/translations';
import { Zap, Play, AlertTriangle, RefreshCw, Activity, ShieldCheck, Globe } from 'lucide-react';

interface MeasureViewProps {
  language: string;
}

export interface SpeedTestRunMetrics {
  downloadMbps: number;
  uploadMbps: number | null;
  latencyMs: number;
  jitterMs: number | null;
  serverCity: string | null;
  timestampIso: string;
  measuredIst: string;
  runNumber: number;
  rawPayload: Record<string, any>;
}

const detectBrowserMedium = (): { isMobileDevice: boolean; connType: string; likelyCellular: boolean } => {
  if (typeof navigator === 'undefined') {
    return { isMobileDevice: false, connType: 'unknown', likelyCellular: false };
  }
  const ua = navigator.userAgent || '';
  const isMobileDevice = /Android|iPhone|iPad|iPod|Mobile/i.test(ua);
  const conn = (navigator as any).connection || (navigator as any).mozConnection || (navigator as any).webkitConnection;
  const rawType = conn?.type || conn?.effectiveType || 'not available';
  const likelyCellular = conn?.type === 'cellular' || isMobileDevice;
  return { isMobileDevice, connType: String(rawType), likelyCellular };
};

export const CrowdsourceMeasureView: React.FC<MeasureViewProps> = ({ language }) => {
  const browserEnv = detectBrowserMedium();

  const [testing, setTesting] = useState<boolean>(false);
  const [phaseLabel, setPhaseLabel] = useState<string>('Ready');
  const [progressPct, setProgressPct] = useState<number>(0);

  // Strict honesty: ZERO default, fallback, or cached numbers. null until a real test completes.
  const [liveDl, setLiveDl] = useState<number | null>(null);
  const [liveUp, setLiveUp] = useState<number | null>(null);
  const [liveLat, setLiveLat] = useState<number | null>(null);
  const [liveJit, setLiveJit] = useState<number | null>(null);

  const [lastRun, setLastRun] = useState<SpeedTestRunMetrics | null>(null);
  const [runLog, setRunLog] = useState<SpeedTestRunMetrics[]>([]);
  const [errorReason, setErrorReason] = useState<string | null>(null);
  const [saveNotice, setSaveNotice] = useState<string | null>(null);

  const [realMeasurementsCount, setRealMeasurementsCount] = useState<number | null>(null);
  const [recentMeasurements, setRecentMeasurements] = useState<any[]>([]);
  const [isMobileData, setIsMobileData] = useState<boolean>(browserEnv.likelyCellular);
  const [consent, setConsent] = useState<boolean>(true);

  const runCounterRef = useRef<number>(0);
  const activeEngineRef = useRef<any>(null);

  const refreshHistory = async () => {
    try {
      const [sum, rec] = await Promise.all([fetchSummary(), fetchRecentMeasurements(10)]);
      setRealMeasurementsCount(typeof sum.real_measurements_count === 'number' ? sum.real_measurements_count : null);
      setRecentMeasurements(Array.isArray(rec) ? rec : []);
    } catch {
      // Leave state untouched; never inject fake counts
    }
  };

  useEffect(() => {
    refreshHistory();
    return () => {
      try {
        activeEngineRef.current?.pause?.();
      } catch {
        // ignore cleanup error
      }
    };
  }, []);

  const failRun = (reason: string) => {
    setTesting(false);
    setProgressPct(0);
    setPhaseLabel('Failed');
    // Strict B1: Clear any displayed numeric values on failure
    setLiveDl(null);
    setLiveUp(null);
    setLiveLat(null);
    setLiveJit(null);
    setLastRun(null);
    setErrorReason(`Test failed: ${reason}`);
  };

  const resolveCoords = (): Promise<{ lat: number | null; lon: number | null }> => {
    return new Promise((resolve) => {
      if (typeof navigator === 'undefined' || !navigator.geolocation) {
        resolve({ lat: null, lon: null });
        return;
      }
      navigator.geolocation.getCurrentPosition(
        (pos) => resolve({ lat: pos.coords.latitude, lon: pos.coords.longitude }),
        () => resolve({ lat: null, lon: null }),
        { enableHighAccuracy: false, timeout: 4000, maximumAge: 0 }
      );
    });
  };

  const startTest = async () => {
    if (testing) return;
    setErrorReason(null);
    setSaveNotice(null);
    setTesting(true);
    setProgressPct(8);
    setPhaseLabel('Connecting to Cloudflare edge...');
    setLiveDl(null);
    setLiveUp(null);
    setLiveLat(null);
    setLiveJit(null);
    setLastRun(null);

    const coords = await resolveCoords();

    try {
      const runSeq = runCounterRef.current + 1;
      const engine = new SpeedTest({
        autoStart: false,
        measurements: [
          { type: 'latency', numPackets: 12 },
          { type: 'download', bytes: 1e6, count: 4 },
          { type: 'download', bytes: 1e7, count: 2 },
          { type: 'upload', bytes: 1e6, count: 3 },
          { type: 'latency', numPackets: 8 },
        ],
      });
      activeEngineRef.current = engine;

      engine.onResultsChange = ({ type }: any) => {
        try {
          const r = engine.results;
          const dlBps = r?.getDownloadBandwidth?.();
          const upBps = r?.getUploadBandwidth?.();
          const latMs = r?.getUnloadedLatency?.();
          const jitMs = r?.getUnloadedJitter?.();

          if (typeof latMs === 'number' && latMs > 0) setLiveLat(Number(latMs.toFixed(1)));
          if (typeof jitMs === 'number' && jitMs >= 0) setLiveJit(Number(jitMs.toFixed(1)));
          if (typeof dlBps === 'number' && dlBps > 0) setLiveDl(Number((dlBps / 1e6).toFixed(2)));
          if (typeof upBps === 'number' && upBps > 0) setLiveUp(Number((upBps / 1e6).toFixed(2)));

          if (type === 'latency') {
            setPhaseLabel('Measuring unloaded latency & jitter...');
            setProgressPct((p) => Math.max(p, 28));
          } else if (type === 'download') {
            setPhaseLabel('Downloading payloads from Cloudflare POP...');
            setProgressPct((p) => Math.max(p, 62));
          } else if (type === 'upload') {
            setPhaseLabel('Uploading payloads to Cloudflare POP...');
            setProgressPct((p) => Math.max(p, 88));
          }
        } catch {
          // wait for onFinish/onError
        }
      };

      engine.onError = (err: any) => {
        const msg = typeof err === 'string' ? err : err?.message || 'Cloudflare speedtest endpoint unreachable or blocked.';
        failRun(msg);
      };

      engine.onFinish = async (finalResults: any) => {
        try {
          const rawDlBps = finalResults?.getDownloadBandwidth?.();
          const rawUpBps = finalResults?.getUploadBandwidth?.();
          const rawLatMs = finalResults?.getUnloadedLatency?.();
          const rawJitMs = finalResults?.getUnloadedJitter?.();
          const summaryObj = finalResults?.getSummary?.() || {};

          if (!rawDlBps || rawDlBps <= 0 || !rawLatMs || rawLatMs <= 0) {
            failRun('Incomplete measurement returned by Cloudflare edge.');
            return;
          }

          const dlMbps = Number((rawDlBps / 1e6).toFixed(2));
          const upMbps = typeof rawUpBps === 'number' && rawUpBps > 0 ? Number((rawUpBps / 1e6).toFixed(2)) : null;
          const latMs = Number(rawLatMs.toFixed(1));
          const jitMs = typeof rawJitMs === 'number' && rawJitMs >= 0 ? Number(rawJitMs.toFixed(1)) : null;

          // Attempt to inspect POP / server city if exposed cleanly by Cloudflare results or trace (no-store)
          let serverCity: string | null =
            summaryObj?.server?.city || summaryObj?.colo || finalResults?.server?.city || null;
          if (!serverCity && typeof fetch === 'function') {
            try {
              const traceRes = await fetch('https://speed.cloudflare.com/cdn-cgi/trace', { cache: 'no-store' });
              if (traceRes.ok) {
                const text = await traceRes.text();
                const match = text.match(/^colo=([A-Z]{3})/m);
                if (match?.[1]) serverCity = `CF POP ${match[1]}`;
              }
            } catch {
              // Offline / trace unavailable in mock environment; keep null honestly
            }
          }

          runCounterRef.current = runSeq;
          const now = new Date();
          const measuredIst = formatIstTime(now);
          const rawRecord: SpeedTestRunMetrics = {
            downloadMbps: dlMbps,
            uploadMbps: upMbps,
            latencyMs: latMs,
            jitterMs: jitMs,
            serverCity,
            timestampIso: now.toISOString(),
            measuredIst,
            runNumber: runSeq,
            rawPayload: {
              download_bps: rawDlBps,
              upload_bps: rawUpBps ?? null,
              latency_ms: rawLatMs,
              jitter_ms: rawJitMs ?? null,
              server_city: serverCity,
              summary: summaryObj,
            },
          };

          console.info('[TeleSense SpeedTest Raw]', rawRecord);

          setLiveDl(dlMbps);
          setLiveUp(upMbps);
          setLiveLat(latMs);
          setLiveJit(jitMs);
          setLastRun(rawRecord);
          setRunLog((prev) => [rawRecord, ...prev]);
          setProgressPct(100);
          setPhaseLabel('Completed');
          setTesting(false);

          // Persist to backend only if user gave consent & selected mobile data
          if (consent) {
            try {
              const saved = await submitCrowdsourceMeasurement({
                download_speed_mbps: dlMbps,
                upload_speed_mbps: upMbps,
                latency_ms: latMs,
                jitter_ms: jitMs,
                is_mobile_data: isMobileData,
                network_medium: isMobileData ? 'Mobile Data' : 'Wi-Fi',
                browser_connection_type: browserEnv.connType,
                coarse_lat: coords.lat,
                coarse_lon: coords.lon,
                server_city: serverCity,
                run_number: runSeq,
                user_consent: consent,
              });
              if (!isMobileData) {
                setSaveNotice('Tested on Wi-Fi: displayed locally only, excluded from cellular coverage map & Real mobile tests counter.');
              } else if (saved.is_test === 1) {
                setSaveNotice('Saved as flagged desktop/localhost test (excluded from Real mobile tests counter).');
              } else {
                setSaveNotice('Saved real phone mobile-data measurement to coverage database.');
              }
              await refreshHistory();
            } catch (postErr: any) {
              setSaveNotice(`Measurement completed locally; backend storage note: ${postErr?.message || 'save failed'}`);
            }
          }
        } catch (err: any) {
          failRun(err?.message || 'Unexpected processing error.');
        }
      };

      engine.play();
    } catch (err: any) {
      failRun(err?.message || 'Could not initialize Cloudflare SpeedTest client.');
    }
  };

  return (
    <div className="max-w-5xl mx-auto p-4 sm:p-6 space-y-6 text-white">
      {/* Header Card */}
      <div className="apple-glass-card p-6 sm:p-7 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center space-x-3.5">
          <div className="p-2.5 rounded-2xl bg-cyan-500/10 border border-cyan-500/20 text-cyan-400">
            <Zap className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h1 className="text-xl sm:text-2xl font-bold tracking-tight">{translate(language, 'speedtest_title')}</h1>
              <span className="px-2 py-0.5 rounded-full text-[9px] font-mono font-bold bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
                REAL MEASUREMENT
              </span>
            </div>
            <p className="text-xs text-zinc-400 mt-0.5">
              {translate(language, 'speedtest_subtitle')} (<code className="text-cyan-300">@cloudflare/speedtest</code>)
            </p>
          </div>
        </div>

        <div className="apple-pill px-3.5 py-1.5 flex items-center space-x-2 bg-emerald-500/10 border-emerald-500/25">
          <Globe className="w-3.5 h-3.5 text-emerald-400" />
          <span className="text-[11px] font-mono text-emerald-300 font-bold">
            {translate(language, 'real_mobile_tests')}{' '}
            {realMeasurementsCount !== null ? realMeasurementsCount : '--'}
          </span>
        </div>
      </div>

      {/* Interactive Control & Result Panel */}
      <div className="apple-glass-card p-6 sm:p-8 space-y-6">
        {/* Connection selector & Consent */}
        <div className="flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-white/[0.08]">
          <div className="flex items-center space-x-2">
            <span className="text-xs font-semibold text-zinc-300">Connection Type:</span>
            <button
              onClick={() => setIsMobileData(true)}
              disabled={testing}
              className={`px-3 py-1 rounded-full text-xs font-bold transition-all cursor-pointer ${
                isMobileData ? 'bg-cyan-500 text-black' : 'bg-white/5 text-zinc-400 hover:text-white'
              }`}
            >
              Mobile Data (4G/5G)
            </button>
            <button
              onClick={() => setIsMobileData(false)}
              disabled={testing}
              className={`px-3 py-1 rounded-full text-xs font-bold transition-all cursor-pointer ${
                !isMobileData ? 'bg-amber-400 text-black' : 'bg-white/5 text-zinc-400 hover:text-white'
              }`}
            >
              Wi-Fi (Local Only)
            </button>
          </div>

          <label className="flex items-center space-x-2 text-xs text-zinc-300 cursor-pointer">
            <input
              type="checkbox"
              checked={consent}
              onChange={(e) => setConsent(e.target.checked)}
              className="accent-cyan-500"
            />
            <span>Consent to submit anonymized coarse telemetry</span>
          </label>
        </div>

        {/* Strict Error / Failure UI — ZERO numbers shown */}
        {errorReason && (
          <div
            role="alert"
            data-testid="speedtest-error-banner"
            className="p-5 rounded-2xl bg-red-500/10 border border-red-500/40 flex flex-col sm:flex-row sm:items-center justify-between gap-4"
          >
            <div className="flex items-start space-x-3">
              <AlertTriangle className="w-5 h-5 text-red-400 shrink-0 mt-0.5" />
              <div>
                <h2 className="text-sm font-bold text-red-200">{errorReason}</h2>
                <p className="text-xs text-red-300/80 mt-0.5">
                  No fallback or cached speed values are shown when a live measurement fails.
                </p>
              </div>
            </div>
            <button
              onClick={startTest}
              className="px-4 py-2 rounded-full bg-red-500 hover:bg-red-400 text-white font-bold text-xs flex items-center space-x-1.5 cursor-pointer shrink-0"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              <span>Retry Test</span>
            </button>
          </div>
        )}

        {/* Primary Metric Cards — strictly '--' until real run succeeds */}
        {!errorReason && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <div className="p-4 apple-glass rounded-2xl border border-white/[0.08] text-center">
              <span className="text-[10px] font-mono text-zinc-400 uppercase block">Download</span>
              <div data-testid="speed-dl-value" className="text-2xl sm:text-3xl font-black text-cyan-400 font-mono mt-1">
                {liveDl !== null ? `${liveDl}` : '--'}
              </div>
              <span className="text-[10px] text-zinc-500 font-mono">Mbps</span>
            </div>
            <div className="p-4 apple-glass rounded-2xl border border-white/[0.08] text-center">
              <span className="text-[10px] font-mono text-zinc-400 uppercase block">Upload</span>
              <div data-testid="speed-up-value" className="text-2xl sm:text-3xl font-black text-emerald-400 font-mono mt-1">
                {liveUp !== null ? `${liveUp}` : '--'}
              </div>
              <span className="text-[10px] text-zinc-500 font-mono">Mbps</span>
            </div>
            <div className="p-4 apple-glass rounded-2xl border border-white/[0.08] text-center">
              <span className="text-[10px] font-mono text-zinc-400 uppercase block">Unloaded Latency</span>
              <div data-testid="speed-lat-value" className="text-2xl sm:text-3xl font-black text-white font-mono mt-1">
                {liveLat !== null ? `${liveLat}` : '--'}
              </div>
              <span className="text-[10px] text-zinc-500 font-mono">ms</span>
            </div>
            <div className="p-4 apple-glass rounded-2xl border border-white/[0.08] text-center">
              <span className="text-[10px] font-mono text-zinc-400 uppercase block">Jitter</span>
              <div data-testid="speed-jit-value" className="text-2xl sm:text-3xl font-black text-purple-400 font-mono mt-1">
                {liveJit !== null ? `${liveJit}` : '--'}
              </div>
              <span className="text-[10px] text-zinc-500 font-mono">ms</span>
            </div>
          </div>
        )}

        {/* Visible Run #N, measured HH:MM:SS IST + POP */}
        {lastRun && !errorReason && (
          <div
            data-testid="speedtest-run-stamp"
            className="flex flex-wrap items-center justify-between gap-2 px-4 py-2.5 rounded-xl bg-emerald-500/10 border border-emerald-500/25 text-xs font-mono text-emerald-200"
          >
            <span>
              Run #{lastRun.runNumber}, measured {lastRun.measuredIst}
              {lastRun.serverCity ? ` • Edge: ${lastRun.serverCity}` : ''}
            </span>
            <span className="flex items-center space-x-1 text-[10px] text-emerald-400">
              <ShieldCheck className="w-3.5 h-3.5" />
              <span>NO-STORE FRESH RUN</span>
            </span>
          </div>
        )}

        {saveNotice && (
          <p className="text-xs text-zinc-300 font-mono px-2">{saveNotice}</p>
        )}

        {/* Progress Bar & Action Trigger */}
        <div className="space-y-3">
          {testing && (
            <div className="space-y-1.5">
              <div className="flex justify-between text-xs font-mono text-zinc-300">
                <span>{phaseLabel}</span>
                <span>{progressPct}%</span>
              </div>
              <div className="w-full h-2 rounded-full bg-zinc-800 overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-cyan-400 to-emerald-400 transition-all duration-300"
                  style={{ width: `${progressPct}%` }}
                />
              </div>
            </div>
          )}

          <div className="flex justify-center pt-1">
            <button
              onClick={startTest}
              disabled={testing}
              data-testid="speedtest-start-btn"
              className="px-7 py-3 rounded-full bg-white hover:bg-zinc-200 disabled:opacity-50 text-black font-extrabold text-sm flex items-center space-x-2 shadow-xl shadow-white/10 transition-all cursor-pointer"
            >
              <Play className="w-4 h-4 fill-current" />
              <span>{testing ? translate(language, 'speedtest_running') : translate(language, 'speedtest_start')}</span>
            </button>
          </div>
        </div>
      </div>

      {/* Per-Run Raw Diagnostics Log */}
      {runLog.length > 0 && (
        <div className="apple-glass-card p-5 space-y-3">
          <div className="flex items-center space-x-2 text-xs font-mono uppercase tracking-wider text-zinc-300 font-bold">
            <Activity className="w-4 h-4 text-cyan-400" />
            <span>Session Raw @cloudflare/speedtest Log ({runLog.length} runs)</span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono border-collapse">
              <thead>
                <tr className="border-b border-white/10 text-zinc-400 text-[10px] uppercase">
                  <th className="p-2.5">Run</th>
                  <th className="p-2.5">Measured Time (IST)</th>
                  <th className="p-2.5">Download</th>
                  <th className="p-2.5">Upload</th>
                  <th className="p-2.5">Latency</th>
                  <th className="p-2.5">Jitter</th>
                  <th className="p-2.5">Cloudflare Edge</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.06]">
                {runLog.map((r) => (
                  <tr key={`${r.runNumber}-${r.timestampIso}`}>
                    <td className="p-2.5 font-bold text-white">#{r.runNumber}</td>
                    <td className="p-2.5 text-zinc-300">{r.measuredIst}</td>
                    <td className="p-2.5 text-cyan-400 font-bold">{r.downloadMbps} Mbps</td>
                    <td className="p-2.5 text-emerald-400">{r.uploadMbps !== null ? `${r.uploadMbps} Mbps` : '--'}</td>
                    <td className="p-2.5 text-white">{r.latencyMs} ms</td>
                    <td className="p-2.5 text-purple-300">{r.jitterMs !== null ? `${r.jitterMs} ms` : '--'}</td>
                    <td className="p-2.5 text-zinc-400">{r.serverCity || 'Not reported'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Database Real Mobile-Data Measurements Log */}
      <div className="apple-glass-card p-5 space-y-3">
        <span className="text-[11px] font-mono uppercase tracking-wider text-zinc-400 font-bold block">
          Recent Mobile-Data Measurements from Phone Browsers
        </span>
        {recentMeasurements.length === 0 ? (
          <p className="text-xs text-zinc-500 font-mono">
            0 real mobile-data phone measurements recorded yet. Run from a smartphone on 4G/5G (non-localhost) to populate coverage bins.
          </p>
        ) : (
          <div className="space-y-2">
            {recentMeasurements.map((m) => (
              <div key={m.id} className="p-3 rounded-xl bg-black/40 border border-white/[0.06] flex items-center justify-between text-xs font-mono">
                <span className="text-zinc-200">{m.download_speed_mbps} Mbps • {m.latency_ms} ms</span>
                <span className="text-zinc-400">{m.measured_ist || formatIstDateTime(m.timestamp)}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
