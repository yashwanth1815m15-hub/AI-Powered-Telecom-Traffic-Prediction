import React, { useState, useEffect } from 'react';
import { CitizenQuality } from '../types/telemetry';
import { checkCitizenArea } from '../services/api';
import { Search, MapPin, Download, AlertCircle, CheckCircle2, Clock, Sparkles, ArrowRight } from 'lucide-react';
import { translate } from '../i18n/translations';

interface CitizenPortalViewProps {
  language: string;
}

export const CitizenPortalView: React.FC<CitizenPortalViewProps> = ({ language }) => {
  const [searchQuery, setSearchQuery] = useState<string>('Andhra Pradesh / Tirupati');
  const [qualityData, setQualityData] = useState<CitizenQuality | null>(null);
  const [loading, setLoading] = useState<boolean>(false);

  // Extensive Indian quick-check localities covering all major circles
  const popularAreas = [
    { label: 'Andhra Pradesh (Tirupati)', query: 'Andhra Pradesh' },
    { label: 'Visakhapatnam, AP', query: 'Visakhapatnam' },
    { label: 'Lucknow, UP', query: 'Lucknow' },
    { label: 'Kochi, Kerala', query: 'Kochi' },
    { label: 'Ahmedabad, Gujarat', query: 'Ahmedabad' },
    { label: 'Prayagraj (Kumbh), UP', query: 'Prayagraj' },
    { label: 'Amritsar (Golden Temple)', query: 'Amritsar' },
    { label: 'Whitefield, Bengaluru', query: 'Whitefield, Bengaluru' },
    { label: 'Cyber City, Gurgaon', query: 'Cyber City, Gurgaon' },
    { label: 'HITEC City, Hyderabad', query: 'HITEC City, Hyderabad' },
    { label: 'Bandra Kurla, Mumbai', query: 'Bandra Kurla' },
    { label: 'Salt Lake, Kolkata', query: 'Salt Lake, Kolkata' },
    { label: 'Dehradun, Uttarakhand', query: 'Dehradun' },
    { label: 'Goa (Miramar / Calangute)', query: 'Goa' },
    { label: 'Srinagar, Kashmir', query: 'Srinagar' },
    { label: 'Bhubaneswar, Odisha', query: 'Bhubaneswar' },
    { label: 'Indore, MP', query: 'Indore' },
    { label: 'Patna, Bihar', query: 'Patna' }
  ];

  const handleSearch = async (loc: string) => {
    setLoading(true);
    try {
      const data = await checkCitizenArea(loc);
      setQualityData(data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    handleSearch('Andhra Pradesh');
  }, []);

  return (
    <div className="max-w-4xl mx-auto p-4 sm:p-6 space-y-6">
      {/* Apple Hero Header */}
      <div className="text-center space-y-2.5 py-4">
        <div className="inline-flex items-center space-x-1.5 px-3 py-1 rounded-full bg-cyan-500/10 border border-cyan-500/20 text-cyan-400 text-xs font-semibold">
          <Sparkles className="w-3.5 h-3.5" />
          <span>{translate(language, 'citizen_badge')}</span>
        </div>
        <h1 className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight">
          {translate(language, 'citizen_title')}
        </h1>
        <p className="text-xs sm:text-sm text-zinc-400 max-w-lg mx-auto font-medium">
          {translate(language, 'citizen_subtitle')}
        </p>
      </div>

      {/* Floating Apple Capsule Search Bar */}
      <div className="apple-glass p-2 pl-4 rounded-full flex items-center space-x-3 shadow-2xl">
        <MapPin className="w-4 h-4 text-cyan-400 flex-shrink-0" />
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSearch(searchQuery)}
          placeholder={translate(language, 'citizen_placeholder')}
          className="flex-1 bg-transparent border-none text-white text-xs sm:text-sm focus:outline-none placeholder-zinc-500 font-medium"
        />
        <button
          onClick={() => handleSearch(searchQuery)}
          className="px-5 py-2 rounded-full bg-cyan-500 hover:bg-cyan-400 text-black font-bold text-xs transition-all cursor-pointer shadow-md shadow-cyan-500/20"
        >
          {translate(language, 'citizen_btn')}
        </button>
      </div>

      {/* Quick Select Region Pills */}
      <div className="flex items-center space-x-2 overflow-x-auto pb-1 text-xs scrollbar-none">
        <span className="text-zinc-500 font-medium text-[11px] whitespace-nowrap">Suggested:</span>
        {popularAreas.map((area) => (
          <button
            key={area.label}
            onClick={() => {
              setSearchQuery(area.query);
              handleSearch(area.query);
            }}
            className="apple-pill px-3 py-1 text-[11px] font-medium text-zinc-300 hover:text-white hover:bg-white/10 whitespace-nowrap transition-all cursor-pointer"
          >
            {area.label}
          </button>
        ))}
      </div>

      {/* 5-Second Citizen Quality Card */}
      {loading ? (
        <div className="py-20 text-center text-zinc-500 text-sm animate-pulse font-mono">
          Querying local cellular nodes and telemetry...
        </div>
      ) : qualityData ? (
        <div className="space-y-5 animate-in fade-in duration-200">
          {/* Main Quality Card */}
          <div className="apple-glass-card p-6 sm:p-7 relative overflow-hidden">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-5 border-b border-white/[0.08]">
              <div>
                <span className="text-[10px] text-zinc-400 uppercase tracking-wider font-mono font-semibold">
                  Coverage Sector
                </span>
                <h2 className="text-xl sm:text-2xl font-black text-white mt-0.5 tracking-tight">
                  {qualityData.area_name}, {qualityData.city}
                </h2>
                <p className="text-xs text-zinc-400 font-mono mt-1">
                  Connected Cell: {qualityData.nearest_tower_id || 'Regional Hub'} ({qualityData.distance_km != null ? `${qualityData.distance_km} km away` : 'Simulated sector'})
                </p>
              </div>

              {/* Status Badge */}
              <div className="px-4 py-2 rounded-full bg-emerald-500/10 border border-emerald-500/25 text-emerald-400 flex items-center space-x-2 self-start sm:self-auto shadow-sm">
                <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                <span className="font-extrabold text-xs tracking-wide uppercase">{qualityData.signal_rating}</span>
              </div>
            </div>

            {/* Plain English Verdict */}
            <div className="py-5">
              <p className="text-sm sm:text-base font-semibold text-zinc-200 leading-relaxed">
                "{qualityData.plain_english_advice}"
              </p>
            </div>

            {/* 3 Metric Pills */}
            <div className="grid grid-cols-3 gap-3 pt-5 border-t border-white/[0.08] text-center">
              <div className="p-3 apple-glass rounded-2xl">
                <span className="text-[10px] text-zinc-400 uppercase font-semibold">Expected Download</span>
                <div className="text-xl font-black text-cyan-400 font-mono mt-0.5">
                  ~{qualityData.avg_speed_mbps} <span className="text-xs font-normal text-zinc-500">Mbps</span>
                </div>
              </div>
              <div className="p-3 apple-glass rounded-2xl">
                <span className="text-[10px] text-zinc-400 uppercase font-semibold">Sector Load</span>
                <div className="text-xl font-black text-white font-mono mt-0.5">
                  {qualityData.current_load_pct != null ? `${qualityData.current_load_pct}%` : '—'}
                </div>
              </div>
              <div className="p-3 apple-glass rounded-2xl">
                <span className="text-[10px] text-zinc-400 uppercase font-semibold">Signal Rating</span>
                <div className="text-xl font-black text-emerald-400 font-mono mt-0.5">
                  {qualityData.signal_rating || '—'}
                </div>
              </div>
            </div>
          </div>

          {/* Optimal Hours vs Congestion Hours */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {/* Best Window */}
            <div className="apple-glass-card p-5 space-y-2 border-emerald-500/20 bg-emerald-500/[0.03]">
              <div className="flex items-center space-x-2 text-emerald-400 text-xs font-bold uppercase tracking-wider">
                <Download className="w-4 h-4" />
                <span>Best Window for Heavy Downloads</span>
              </div>
              <div className="text-sm font-bold text-white font-mono">
                {qualityData.best_download_window}
              </div>
              <p className="text-xs text-zinc-400 leading-relaxed">
                Network cells operate under 25% capacity. Ideal for massive game updates, cloud backups, and offline movies.
              </p>
            </div>

            {/* Congested Window */}
            <div className="apple-glass-card p-5 space-y-2 border-red-500/20 bg-red-500/[0.03]">
              <div className="flex items-center space-x-2 text-red-400 text-xs font-bold uppercase tracking-wider">
                <AlertCircle className="w-4 h-4" />
                <span>Peak Congestion Hours to Avoid</span>
              </div>
              <div className="text-sm font-bold text-white font-mono">
                {qualityData.worst_congestion_window}
              </div>
              <p className="text-xs text-zinc-400 leading-relaxed">
                Evening prime OTT streaming and IPL rush hour. Expect slight buffering and higher gaming latency.
              </p>
            </div>
          </div>

          {/* 24-Hour Hour-by-Hour Guide */}
          {qualityData.hourly_schedule && (
            <div className="apple-glass-card p-5 space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="text-xs font-bold text-zinc-300 uppercase tracking-wider flex items-center space-x-1.5">
                  <Clock className="w-3.5 h-3.5 text-cyan-400" />
                  <span>24-Hour Hour-by-Hour Forecast</span>
                </h3>
                <span className="text-[10px] text-zinc-500 font-mono">Green = Optimal • Red = Peak</span>
              </div>

              <div className="grid grid-cols-4 sm:grid-cols-6 md:grid-cols-8 gap-2">
                {qualityData.hourly_schedule.slice(0, 16).map((slot, i) => (
                  <div
                    key={i}
                    className={`p-2.5 rounded-xl border text-center transition-all ${
                      slot.color === 'green' ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-300' :
                      slot.color === 'red' ? 'bg-red-500/10 border-red-500/20 text-red-300' :
                      slot.color === 'amber' ? 'bg-amber-500/10 border-amber-500/20 text-amber-300' :
                      'apple-glass text-zinc-300'
                    }`}
                  >
                    <span className="text-[10px] font-mono block opacity-75">{slot.hour}</span>
                    <strong className="text-xs font-bold block my-0.5">{slot.status}</strong>
                    <span className="text-[9px] font-mono opacity-80 block">{slot.estimated_speed}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      ) : null}
    </div>
  );
};
