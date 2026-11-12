import React from 'react';
import { Radio, MapPin, BarChart3, Sliders, UserCheck, Zap, Cpu, Bell, BookOpen, Clock, Presentation } from 'lucide-react';
import { translate } from '../i18n/translations';

interface NavbarProps {
  activeTab: string;
  setActiveTab: (tab: string) => void;
  unreadAlertCount: number;
  openAlertsDrawer: () => void;
  language: string;
  setLanguage: (lang: string) => void;
  isLive: boolean;
  secondsAgo: number;
  presenterActive?: boolean;
  onTogglePresenter?: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  activeTab,
  setActiveTab,
  unreadAlertCount,
  openAlertsDrawer,
  language,
  setLanguage,
  isLive,
  secondsAgo,
  presenterActive = false,
  onTogglePresenter
}) => {
  const tabs = [
    { id: 'noc', label: translate(language, 'nav_noc'), icon: MapPin },
    { id: 'planner', label: translate(language, 'nav_planner'), icon: BarChart3 },
    { id: 'whatif', label: translate(language, 'nav_whatif'), icon: Sliders },
    { id: 'citizen', label: translate(language, 'nav_citizen'), icon: UserCheck },
    { id: 'measure', label: translate(language, 'nav_measure'), icon: Zap },
    { id: 'model', label: translate(language, 'nav_model'), icon: Cpu },
    { id: 'sources', label: translate(language, 'nav_sources'), icon: BookOpen },
  ];

  return (
    <header className="sticky top-0 z-40 bg-black/80 backdrop-blur-2xl border-b border-white/[0.08] px-4 py-2.5">
      <div className="max-w-7xl mx-auto flex items-center justify-between flex-wrap gap-3">
        {/* Apple Style Brand Logo */}
        <div className="flex items-center space-x-3 cursor-pointer" onClick={() => setActiveTab('noc')}>
          <div className="flex items-center justify-center w-9 h-9 rounded-2xl bg-gradient-to-tr from-cyan-500 to-blue-600 shadow-lg shadow-cyan-500/20">
            <Radio className="w-4 h-4 text-white" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <span className="font-extrabold text-lg tracking-tight text-white">TeleSense</span>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 font-bold uppercase">
                AI 2.0
              </span>
            </div>
          </div>
        </div>

        {/* Segmented Pill Navigation */}
        <nav className="flex items-center space-x-1 bg-white/[0.05] p-1 rounded-full border border-white/[0.08] backdrop-blur-xl overflow-x-auto scrollbar-none">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-all whitespace-nowrap cursor-pointer ${
                  isActive
                    ? 'bg-white text-black font-bold shadow-md shadow-white/10'
                    : 'text-zinc-400 hover:text-white hover:bg-white/[0.04]'
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </nav>

        {/* Right Controls: Live Pill, Updated Timer, Alert Bell, Language */}
        <div className="flex items-center space-x-2">
          {/* Live Indicator Pill */}
          <div className="apple-pill px-2.5 py-1 flex items-center space-x-1.5 text-xs">
            <span className={`w-2 h-2 rounded-full ${isLive ? 'bg-emerald-400 animate-pulse' : 'bg-zinc-500'}`} />
            <span className="text-zinc-300 font-mono text-[10px] font-semibold">
              {isLive ? translate(language, 'nav_live') : translate(language, 'nav_sync')}
            </span>
          </div>

          {/* Visible "Updated X seconds ago" Timer */}
          <div className="apple-pill px-2.5 py-1 hidden sm:flex items-center space-x-1 text-[10px] font-mono text-zinc-400">
            <Clock className="w-3 h-3 text-cyan-400" />
            <span>{translate(language, 'nav_updated')} {secondsAgo}{translate(language, 'nav_secAgo')}</span>
          </div>

          {/* Presenter Mode Switch (Ctrl+Shift+D) */}
          {onTogglePresenter && (
            <button
              onClick={onTogglePresenter}
              className={`apple-pill px-2.5 py-1 flex items-center space-x-1.5 text-[10px] font-mono font-bold border transition-all cursor-pointer ${
                presenterActive
                  ? 'bg-amber-500/20 text-amber-300 border-amber-400/50 shadow-sm shadow-amber-500/20'
                  : 'text-zinc-300 hover:text-white border-white/10 hover:bg-white/10'
              }`}
              title={`${translate(language, 'nav_presenter')} (Ctrl+Shift+D)`}
            >
              <Presentation className="w-3.5 h-3.5 text-amber-400" />
              <span className="hidden lg:inline">{translate(language, 'nav_presenter')}</span>
            </button>
          )}

          {/* Alert Bell Button */}
          <button
            onClick={openAlertsDrawer}
            className="apple-pill relative p-2 text-zinc-300 hover:text-white hover:bg-white/10 transition-colors cursor-pointer"
            title={translate(language, 'nav_alertsTooltip')}
          >
            <Bell className="w-4 h-4" />
            {unreadAlertCount > 0 && (
              <span className="absolute -top-1 -right-1 px-1.5 py-0.2 bg-red-500 text-white text-[10px] font-extrabold rounded-full animate-bounce">
                {unreadAlertCount}
              </span>
            )}
          </button>

          {/* Language Selector */}
          <select
            value={language}
            onChange={(e) => setLanguage(e.target.value)}
            aria-label="Language selector"
            className="apple-pill px-2.5 py-1 text-xs text-zinc-200 focus:outline-none cursor-pointer bg-black/40 font-medium"
          >
            <option value="en" className="bg-zinc-900">EN</option>
            <option value="hi" className="bg-zinc-900">हिन्दी</option>
            <option value="te" className="bg-zinc-900">తెలుగు</option>
            <option value="kn" className="bg-zinc-900">ಕನ್ನಡ</option>
          </select>
        </div>
      </div>
    </header>
  );
};
