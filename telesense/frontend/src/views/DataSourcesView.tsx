import React from 'react';
import { Database, ExternalLink } from 'lucide-react';
import { NetworkHealthSummary } from '../types/telemetry';
import { translate } from '../i18n/translations';

interface DataSourcesViewProps {
  language: string;
  summary?: NetworkHealthSummary | null;
}

export const DataSourcesView: React.FC<DataSourcesViewProps> = ({ language, summary }) => {
  const fetchedDate = summary?.opencellid_fetched_at || '2026-11-11';
  const ocidAttribution = `Cell data: OpenCellID, CC BY-SA 4.0, fetched ${fetchedDate}`;
  const sources = [
    {
      title: "TRAI Press Release No. 104/2026",
      category: "Statutory Telecom Subscriptions",
      badge: "REAL SOURCE",
      url: "https://www.trai.gov.in/sites/default/files/2026-07/PR_No104of2026_0.pdf",
      license: "Government of India Open Data (GODL)",
      key_figures: "1,300.25 M wireless subscribers, 1,282.38 M wireless mobile (incl. M2M)",
      usage: "Macro subscriber capacity ceiling, circle market shares (Jio, Airtel, Vi, BSNL) for user-count modelling."
    },
    {
      title: "TRAI Telecom Services Performance Indicators Reports",
      category: "Data Consumption Benchmark",
      badge: "REAL SOURCE",
      url: "https://www.trai.gov.in/release-publication/reports/performance-indicators-reports",
      license: "Government of India Open Data (GODL)",
      key_figures: "Latest quarter average data per subscriber: 28.39 GB/month",
      usage: "Baseline monthly consumption parameter used to model hourly user traffic demand and bandwidth saturation."
    },
    {
      title: "TRAI Quality of Service Regulations, 2024 (06 of 2024)",
      category: "Statutory QoS Benchmarks",
      badge: "REGULATORY CODE",
      url: "https://www.trai.gov.in/sites/default/files/2024-08/PR_No.47of2024.pdf",
      license: "Statutory Indian Regulation (In force 1 Oct 2024)",
      key_figures: "Drop Call Rate (DCR) target for 4G/5G: <= 2.0% (percentile basis)",
      usage: "Threshold for critical network alerts. DCR > 2.0% triggers an SLA breach alert in TeleSense."
    },
    {
      title: "OpenCellID by Unwired Labs",
      category: "Cell Records (Area Clusters & Individual Cell IDs)",
      badge: "OPEN TELECOM DATA",
      url: "https://opencellid.org/",
      license: "Creative Commons Attribution-ShareAlike 4.0 (CC BY-SA 4.0)",
      key_figures: `${ocidAttribution} • radio, MCC/MNC (cited ITU E.212 / Wikipedia table or MCC/MNC fallback), LAC, cellid, samples — approximate position (about 1 km)`,
      usage: "Offline-cached real Indian cell records grouped into area clusters (0.01° grid binning, effective radius > 2 km). Zooming in reveals individual cell records without any simulated metrics. Never queried live from app runtime."
    },
    {
      title: "Cloudflare Radar India Hourly Series",
      category: "National & Operator Web Traffic Reference",
      badge: "REAL API (OFFLINE CACHE)",
      url: "https://developers.cloudflare.com/radar/",
      license: "Cloudflare Radar Open Telemetry",
      key_figures: "Relative web traffic (Cloudflare Radar), not tower load — India (IN), 7 state subsets & top-ranked India ASNs (network-level web traffic, may include fixed broadband)",
      usage: "Validates forecasting methodology & IST diurnal traffic curves without calling live external APIs during runtime."
    },
    {
      title: "Ookla Open Data Mobile Performance Tiles (s3://ookla-open-data)",
      category: "Real Mobile Speed Benchmark (Quarterly)",
      badge: "REAL OPEN DATA",
      url: "https://github.com/teamookla/ookla-open-data",
      license: "CC BY-NC-SA 4.0 (Ookla Open Data)",
      key_figures: "Real mobile speed (Ookla, quarterly) — Q3 2026 India tiles filtered strictly inside geoBoundaries India polygons",
      usage: "Renders quarterly real Indian mobile download/upload & latency speed tiles with attribution and open-data licence disclosure."
    },
    {
      title: "Cloudflare Speed Test Edge Engine",
      category: "Client Speed Diagnostics",
      badge: "REAL MEASUREMENT",
      url: "https://speed.cloudflare.com/",
      license: "Apache 2.0 (@cloudflare/speedtest)",
      key_figures: "Live Downlink/Uplink Throughput, RTT Latency, Jitter to edge POPs",
      usage: "Powers the /measure crowdsource test directly against Cloudflare edge servers worldwide."
    },
    {
      title: "Esri World Dark Neutral Map & OpenStreetMap",
      category: "Cartographic Basemap",
      badge: "MAP ATTRIBUTION",
      url: "https://www.openstreetmap.org/",
      license: "Open Database License (ODbL) / Esri Terms of Use",
      key_figures: "Zero-watermark high-contrast dark cartography",
      usage: "Renders geospatial coordinates for Indian cell sites and coverage heatmap layers."
    }
  ];

  return (
    <div className="max-w-6xl mx-auto p-4 sm:p-6 space-y-6 text-white">
      {/* Header */}
      <div className="apple-glass-card p-6 sm:p-7 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-3">
            <div className="p-2.5 rounded-2xl bg-cyan-500/10 border border-cyan-500/20 text-cyan-400">
              <Database className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h1 className="text-xl sm:text-2xl font-bold tracking-tight">
                  {translate(language, 'sources_title')}
                </h1>
                <span className="apple-pill px-2.5 py-0.5 text-[10px] font-mono text-emerald-400 font-bold bg-emerald-500/10 border-emerald-500/20">
                  TRANSPARENCY REGISTER
                </span>
              </div>
              <p className="text-xs text-zinc-400 mt-0.5">
                {translate(language, 'sources_subtitle')}
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center space-x-2 text-xs text-zinc-400 font-mono">
          <span>{sources.length} Registered Sources</span>
        </div>
      </div>

      {/* OpenCellID Attribution & Polygon Validation Register (Req 4, 5, 6, 7) */}
      <div className="apple-glass p-4 rounded-2xl border-sky-500/25 bg-sky-500/[0.04] space-y-1.5">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <span className="text-[11px] font-bold uppercase tracking-wider text-sky-400 font-mono">
            {ocidAttribution}
          </span>
          <span className="text-[10px] font-mono px-2.5 py-0.5 rounded-full bg-sky-500/15 text-sky-300 border border-sky-500/30">
            {(summary?.real_opencellid_count ?? 0).toLocaleString()} cell records • {summary?.opencellid_polygon_failed_count ?? 0} polygon failures
          </span>
        </div>
        <p className="text-xs text-zinc-300 leading-relaxed">
          Indian coordinates in OpenCellID are rounded to ~2 decimal places: <strong className="text-white">approximate position (about 1 km)</strong>. These are radio cell records (not confirmed towers) and are clustered by approximate coordinate. Validated offline against geoBoundaries ADM1 India polygons.
        </p>
      </div>

      {/* Assumptions Callout */}
      <div className="apple-glass p-4 rounded-2xl border-amber-500/20 bg-amber-500/[0.03] space-y-2">
        <span className="text-[10px] font-bold uppercase tracking-wider text-amber-400 font-mono">
          Key Operational Assumptions (Transparently Modelled)
        </span>
        <ul className="text-xs text-zinc-300 space-y-1.5 list-disc list-inside leading-relaxed">
          <li>
            <strong className="text-white">85% PRB Threshold:</strong> Operator planning threshold (assumption, configurable by network operations). Neither 3GPP nor TRAI defines 85% as a statutory law; it is standard telecom capacity planning practice before buffer queues incur packet drops.
          </li>
          <li>
            <strong className="text-white">Active Users per Tower:</strong> Modelled based on catchment population (WorldPop / Census density) &times; operator market share (TRAI PR 104/2026) &times; busy-hour activity factor &times; diurnal curve.
          </li>
        </ul>
      </div>

      {/* Source Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {sources.map((src, idx) => (
          <div key={idx} className="apple-glass-card p-5 space-y-3 flex flex-col justify-between">
            <div className="space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="text-[10px] uppercase font-bold text-zinc-400 font-mono">{src.category}</span>
                <span className="px-2 py-0.5 rounded-full text-[9px] font-mono font-bold bg-white/5 border border-white/10 text-cyan-300">
                  {src.badge}
                </span>
              </div>

              <h3 className="text-sm font-bold text-white leading-snug">
                {src.title}
              </h3>

              <div className="p-2.5 rounded-xl bg-black/40 border border-white/[0.04] space-y-1 text-[11px] font-mono">
                <div className="text-zinc-400">
                  <strong className="text-zinc-300">Figures:</strong> {src.key_figures}
                </div>
                <div className="text-zinc-500">
                  <strong className="text-zinc-400">License:</strong> {src.license}
                </div>
              </div>

              <p className="text-xs text-zinc-300 leading-relaxed font-sans">
                <strong className="text-zinc-400">Used for:</strong> {src.usage}
              </p>
            </div>

            <div className="pt-2 border-t border-white/[0.06]">
              <a
                href={src.url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center space-x-1.5 text-xs text-cyan-400 hover:text-cyan-300 hover:underline font-mono"
              >
                <span>Access Primary Document</span>
                <ExternalLink className="w-3.5 h-3.5" />
              </a>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

