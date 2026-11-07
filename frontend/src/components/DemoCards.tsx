import React from 'react';
import { Star, ArrowUpRight, Sparkles } from 'lucide-react';
import type { DemoRepository } from '../types';

interface DemoCardsProps {
  demos: DemoRepository[];
  onSelectDemo: (url: string) => void;
}

export const DemoCards: React.FC<DemoCardsProps> = ({ demos, onSelectDemo }) => {
  return (
    <div className="w-full max-w-5xl">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <Sparkles className="h-4 w-4 text-indigo-400" />
          <h3 className="text-sm font-semibold tracking-wide text-slate-300 uppercase">
            Featured Public Repositories (One-Click Demo)
          </h3>
        </div>
        <span className="text-xs text-slate-500">Instant test without searching GitHub</span>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {demos.map((demo) => (
          <div
            key={demo.url}
            onClick={() => onSelectDemo(demo.url)}
            className="group relative cursor-pointer rounded-xl border border-slate-800 bg-slate-900/40 p-4 transition-all duration-200 hover:border-indigo-500/50 hover:bg-slate-900/80 hover:shadow-lg hover:shadow-indigo-500/10"
          >
            <div className="flex items-start justify-between">
              <div>
                <span className="inline-block rounded-md bg-slate-800/80 px-2 py-0.5 text-[10px] font-medium text-slate-300">
                  {demo.category}
                </span>
                <h4 className="mt-2 text-base font-bold text-white group-hover:text-indigo-300">
                  {demo.owner}/{demo.name}
                </h4>
              </div>
              <div className="flex h-7 w-7 items-center justify-center rounded-lg border border-slate-800 bg-slate-800/50 text-slate-400 transition-colors group-hover:border-indigo-500/40 group-hover:text-indigo-300">
                <ArrowUpRight className="h-4 w-4" />
              </div>
            </div>

            <p className="mt-2 line-clamp-2 text-xs leading-relaxed text-slate-400">
              {demo.description}
            </p>

            <div className="mt-4 flex items-center justify-between border-t border-slate-800/60 pt-3 text-xs text-slate-500">
              <span className="flex items-center space-x-1.5 font-medium text-slate-400">
                <span className="h-2 w-2 rounded-full bg-indigo-400" />
                <span>{demo.language}</span>
              </span>
              <span className="flex items-center space-x-1 text-amber-400/90 font-mono">
                <Star className="h-3.5 w-3.5 fill-amber-400/30" />
                <span>{demo.stars}</span>
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
