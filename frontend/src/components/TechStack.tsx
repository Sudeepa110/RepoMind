import React from 'react';

export const TechStack: React.FC = () => {
  const stack = [
    { name: 'React 19 & Vite', category: 'Frontend', desc: 'Type-safe reactive dashboard with Tailwind styling' },
    { name: 'FastAPI & Python', category: 'Backend Engine', desc: 'Asynchronous REST & SSE streaming server' },
    { name: 'Tree-sitter Grammars', category: 'AST Code Parsing', desc: 'Extracts exact functions, classes & imports' },
    { name: 'Sentence Transformers', category: 'Dense Embeddings', desc: 'Local all-MiniLM-L6-v2 vector generation' },
    { name: 'ChromaDB', category: 'Vector Storage', desc: 'Durable structure-aware code indexing' },
    { name: 'Google Gemini AI', category: 'Reasoning & Synthesis', desc: 'Zero-cost free-tier LLM intelligence' },
  ];

  return (
    <section id="tech-stack" className="w-full max-w-6xl py-12">
      <div className="mb-10 text-center">
        <span className="rounded-full border border-cyan-500/30 bg-cyan-500/10 px-3 py-1 text-xs font-semibold uppercase tracking-wider text-cyan-400">
          Zero-Cost Production Stack
        </span>
        <h2 className="mt-3 text-3xl font-extrabold tracking-tight text-white sm:text-4xl">
          Engineered for Modern Standards
        </h2>
        <p className="mx-auto mt-3 max-w-2xl text-sm text-slate-400 sm:text-base">
          Built with open-source tools and zero mandatory paid APIs. Fully reproducible on commodity developer laptops.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
        {stack.map((item) => (
          <div
            key={item.name}
            className="flex flex-col justify-between rounded-xl border border-slate-800 bg-slate-900/30 p-4 transition-all hover:border-slate-700 hover:bg-slate-900/70"
          >
            <div>
              <span className="text-[10px] font-mono text-cyan-400 uppercase">
                {item.category}
              </span>
              <h4 className="mt-1 text-sm font-bold text-white">{item.name}</h4>
            </div>
            <p className="mt-3 text-[11px] leading-snug text-slate-400">
              {item.desc}
            </p>
          </div>
        ))}
      </div>
    </section>
  );
};
