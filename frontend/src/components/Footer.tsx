import React from 'react';
import { Terminal, Shield, Code } from 'lucide-react';

export const Footer: React.FC = () => {
  return (
    <footer className="border-t border-slate-800/80 bg-[#060911] py-12 text-slate-400">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="flex flex-col items-center justify-between gap-6 sm:flex-row">
          {/* Logo & Description */}
          <div className="flex items-center space-x-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-600/20 text-indigo-400">
              <Terminal className="h-4 w-4" />
            </div>
            <div>
              <span className="text-sm font-bold text-white">RepoMind</span>
              <p className="text-xs text-slate-500">
                AI-Powered GitHub Repository Intelligence Platform
              </p>
            </div>
          </div>

          {/* Security & Zero-cost Notice */}
          <div className="flex items-center space-x-2 text-xs text-slate-500">
            <Shield className="h-3.5 w-3.5 text-emerald-400" />
            <span>Zero Remote Code Execution • Public Repositories Only</span>
          </div>

          {/* Links */}
          <div className="flex items-center space-x-4 text-xs">
            <a
              href="https://github.com"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center space-x-1 text-slate-400 hover:text-white"
            >
              <Code className="h-3.5 w-3.5" />
              <span>GitHub</span>
            </a>
            <span className="text-slate-700">•</span>
            <span className="text-slate-500">Hybrid Vector RAG + GraphRAG</span>
          </div>
        </div>

        <div className="mt-8 border-t border-slate-900 pt-6 text-center text-xs text-slate-600">
          RepoMind is an open-source intelligence platform engineered with a Zero-Cost-First strategy.
        </div>
      </div>
    </footer>
  );
};
