import React from 'react';
import { Terminal, Cpu, AlertCircle, Code } from 'lucide-react';
import type { HealthStatus, AppView } from '../types';

interface HeaderProps {
  health: HealthStatus | null;
  healthLoading: boolean;
  currentView: AppView;
  onNavigate: (view: AppView) => void;
}

export const Header: React.FC<HeaderProps> = ({
  health,
  healthLoading,
  currentView,
  onNavigate,
}) => {
  return (
    <header className="sticky top-0 z-50 border-b border-slate-800 bg-[#090d16]/90 backdrop-blur-md">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3 sm:px-6 lg:px-8">
        {/* Brand */}
        <div
          onClick={() => onNavigate('landing')}
          className="flex cursor-pointer items-center space-x-3 transition-opacity hover:opacity-90"
        >
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 via-purple-600 to-pink-500 p-0.5 shadow-lg shadow-indigo-500/20">
            <div className="flex h-full w-full items-center justify-center rounded-[10px] bg-slate-950">
              <Terminal className="h-5 w-5 text-indigo-400" />
            </div>
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <span className="text-xl font-bold tracking-tight text-white">RepoMind</span>
              <span className="rounded-full border border-indigo-500/30 bg-indigo-500/10 px-2 py-0.5 text-[10px] font-semibold text-indigo-300">
                AI INTELLIGENCE
              </span>
            </div>
            <p className="text-xs text-slate-400">GitHub Repository Intelligence & RAG</p>
          </div>
        </div>

        {/* Center Navigation */}
        <nav className="hidden items-center space-x-6 md:flex">
          <button
            onClick={() => onNavigate('landing')}
            className={`text-sm font-medium transition-colors ${
              currentView === 'landing'
                ? 'text-indigo-400'
                : 'text-slate-300 hover:text-white'
            }`}
          >
            Overview
          </button>
          <a
            href="#how-it-works"
            className="text-sm font-medium text-slate-300 transition-colors hover:text-white"
          >
            Architecture
          </a>
          <a
            href="#features"
            className="text-sm font-medium text-slate-300 transition-colors hover:text-white"
          >
            Capabilities
          </a>
          <a
            href="#tech-stack"
            className="text-sm font-medium text-slate-300 transition-colors hover:text-white"
          >
            Tech Stack
          </a>
        </nav>

        {/* System & Health Status */}
        <div className="flex items-center space-x-3">
          {healthLoading ? (
            <div className="flex items-center space-x-2 rounded-full border border-slate-800 bg-slate-900/60 px-3 py-1 text-xs text-slate-400">
              <div className="h-2 w-2 animate-ping rounded-full bg-slate-400" />
              <span>Connecting to API...</span>
            </div>
          ) : health ? (
            <div className="flex items-center space-x-2">
              {/* GPU Badge */}
              {health.gpu_available && (
                <div className="hidden items-center space-x-1.5 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-1 text-xs font-medium text-emerald-300 lg:flex">
                  <Cpu className="h-3.5 w-3.5 text-emerald-400" />
                  <span className="max-w-[140px] truncate">{health.gpu_name || 'GPU Accelerated'}</span>
                </div>
              )}
              {/* Backend API Pill */}
              <div className="flex items-center space-x-2 rounded-full border border-slate-800 bg-slate-900/80 px-3 py-1 text-xs text-slate-300">
                <span className="relative flex h-2 w-2">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
                  <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
                </span>
                <span className="font-mono text-emerald-400">v{health.version}</span>
                <span className="hidden text-slate-500 sm:inline">|</span>
                <span className="hidden text-slate-400 sm:inline">FastAPI Online</span>
              </div>
            </div>
          ) : (
            <div className="flex items-center space-x-1.5 rounded-full border border-rose-500/30 bg-rose-500/10 px-3 py-1 text-xs text-rose-300">
              <AlertCircle className="h-3.5 w-3.5 text-rose-400" />
              <span>Backend Offline</span>
            </div>
          )}

          <a
            href="https://github.com"
            target="_blank"
            rel="noopener noreferrer"
            className="flex h-9 w-9 items-center justify-center rounded-lg border border-slate-800 bg-slate-900/80 text-slate-400 transition-colors hover:border-slate-700 hover:text-white"
            title="GitHub"
          >
            <Code className="h-4 w-4" />
          </a>
        </div>
      </div>
    </header>
  );
};
