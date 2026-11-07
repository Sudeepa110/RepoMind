import React from 'react';
import { GitBranch, Network, Database, BrainCircuit } from 'lucide-react';

export const HowItWorks: React.FC = () => {
  const steps = [
    {
      num: '01',
      icon: GitBranch,
      title: 'Secure Ingestion & Filtering',
      description:
        'Clones repository into isolated temporary storage. Strips binaries, lockfiles, node_modules, and secrets while retaining structural code.',
      accent: 'from-blue-500 to-cyan-500',
    },
    {
      num: '02',
      icon: Network,
      title: 'Tree-sitter AST Parsing',
      description:
        'Extracts syntax nodes: classes, functions, methods, imports, and docstrings with exact file paths and line ranges.',
      accent: 'from-indigo-500 to-purple-500',
    },
    {
      num: '03',
      icon: Database,
      title: 'Dense & Sparse Vectorization',
      description:
        'Generates embeddings locally using Sentence Transformers and stores structured code chunks in ChromaDB vector storage.',
      accent: 'from-purple-500 to-pink-500',
    },
    {
      num: '04',
      icon: BrainCircuit,
      title: 'Grounded RAG with Citations',
      description:
        'Performs hybrid retrieval and feeds verified repository evidence to Google Gemini. Never hallucinates non-existent files or methods.',
      accent: 'from-pink-500 to-rose-500',
    },
  ];

  return (
    <section id="how-it-works" className="w-full max-w-6xl py-12">
      <div className="mb-10 text-center">
        <span className="rounded-full border border-indigo-500/30 bg-indigo-500/10 px-3 py-1 text-xs font-semibold uppercase tracking-wider text-indigo-400">
          Architecture & Execution Flow
        </span>
        <h2 className="mt-3 text-3xl font-extrabold tracking-tight text-white sm:text-4xl">
          How RepoMind Understands Any Codebase
        </h2>
        <p className="mx-auto mt-3 max-w-2xl text-sm leading-relaxed text-slate-400 sm:text-base">
          A zero-cost-first RAG pipeline engineered for high precision, verifiable evidence, and deep structural awareness.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-4">
        {steps.map((step) => {
          const Icon = step.icon;
          return (
            <div
              key={step.num}
              className="relative rounded-2xl border border-slate-800 bg-slate-900/50 p-6 backdrop-blur-sm transition-all duration-300 hover:border-slate-700 hover:bg-slate-900/80 hover:shadow-xl hover:shadow-indigo-950/30"
            >
              <div className="flex items-center justify-between">
                <span className="font-mono text-2xl font-black text-slate-700">
                  {step.num}
                </span>
                <div
                  className={`flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br ${step.accent} p-0.5 shadow-md`}
                >
                  <div className="flex h-full w-full items-center justify-center rounded-[10px] bg-slate-950">
                    <Icon className="h-5 w-5 text-white" />
                  </div>
                </div>
              </div>

              <h3 className="mt-5 text-lg font-bold text-white">{step.title}</h3>
              <p className="mt-2 text-xs leading-relaxed text-slate-400">
                {step.description}
              </p>
            </div>
          );
        })}
      </div>
    </section>
  );
};
