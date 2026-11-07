import React from 'react';
import {
  ExternalLink,
  Layers,
  SearchCode,
  ShieldCheck,
  MessageSquareCode,
  GitPullRequest,
} from 'lucide-react';

export const Features: React.FC = () => {
  const capabilities = [
    {
      icon: ExternalLink,
      title: 'Clickable Source Citations',
      desc: 'Every statement references the exact file and line numbers. Click any source to inspect syntax-highlighted code.',
      tag: 'Grounded Evidence',
    },
    {
      icon: Layers,
      title: 'Architecture Intelligence',
      desc: 'Identifies entry points, database integrations, authentication services, and cross-module communications automatically.',
      tag: 'System Mapping',
    },
    {
      icon: SearchCode,
      title: 'Structure-Aware AST Search',
      desc: 'Parses functions, classes, and methods via Tree-sitter. Discards character-split illusions in favor of true syntactic boundaries.',
      tag: 'Precision RAG',
    },
    {
      icon: MessageSquareCode,
      title: 'Multi-Turn Contextual Chat',
      desc: 'Ask follow-ups naturally. RepoMind preserves repo context and session boundaries without leaking user queries.',
      tag: 'Interactive Dialogue',
    },
    {
      icon: GitPullRequest,
      title: 'PR & Change Impact Analysis',
      desc: 'Assess downstream impact before editing a method or review pull requests with automated dependency verification.',
      tag: 'Change Intelligence',
    },
    {
      icon: ShieldCheck,
      title: 'Hardened Security Boundary',
      desc: 'Cloned repositories are strictly isolated in temporary sandboxes. Untrusted code is never executed under any condition.',
      tag: 'SSRF & Injection Defense',
    },
  ];

  return (
    <section id="features" className="w-full max-w-6xl py-12">
      <div className="mb-10 text-center">
        <span className="rounded-full border border-purple-500/30 bg-purple-500/10 px-3 py-1 text-xs font-semibold uppercase tracking-wider text-purple-400">
          Core Capabilities
        </span>
        <h2 className="mt-3 text-3xl font-extrabold tracking-tight text-white sm:text-4xl">
          Engineered for Real Developer Workflows
        </h2>
        <p className="mx-auto mt-3 max-w-2xl text-sm text-slate-400 sm:text-base">
          Far beyond a generic chatbot. RepoMind acts as a dedicated staff engineer who has read every line of code in the repository.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
        {capabilities.map((item) => {
          const Icon = item.icon;
          return (
            <div
              key={item.title}
              className="group rounded-2xl border border-slate-800 bg-slate-900/40 p-6 transition-all duration-300 hover:border-indigo-500/40 hover:bg-slate-900/80 hover:shadow-lg hover:shadow-indigo-950/20"
            >
              <div className="flex items-center justify-between">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-slate-800 bg-slate-800/80 text-indigo-400 group-hover:border-indigo-500/40 group-hover:bg-indigo-500/10 group-hover:text-indigo-300">
                  <Icon className="h-5 w-5" />
                </div>
                <span className="rounded-md bg-slate-800/60 px-2 py-0.5 text-[10px] font-medium text-slate-400">
                  {item.tag}
                </span>
              </div>

              <h3 className="mt-4 text-base font-bold text-white group-hover:text-indigo-300">
                {item.title}
              </h3>
              <p className="mt-2 text-xs leading-relaxed text-slate-400">
                {item.desc}
              </p>
            </div>
          );
        })}
      </div>
    </section>
  );
};
