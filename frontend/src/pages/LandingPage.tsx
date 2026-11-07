import React from 'react';
import { Zap } from 'lucide-react';
import { UrlInputForm } from '../components/UrlInputForm';
import { DemoCards } from '../components/DemoCards';
import { HowItWorks } from '../components/HowItWorks';
import { Features } from '../components/Features';
import { TechStack } from '../components/TechStack';
import type { DemoRepository, ValidationResult } from '../types';

interface LandingPageProps {
  demos: DemoRepository[];
  onAnalysisStart: (repoUrl: string, validation: ValidationResult) => void;
  selectedUrl: string;
  setSelectedUrl: (url: string) => void;
}

export const LandingPage: React.FC<LandingPageProps> = ({
  demos,
  onAnalysisStart,
  selectedUrl,
  setSelectedUrl,
}) => {
  return (
    <div className="flex flex-col items-center px-4 py-8 sm:px-6 lg:px-8">
      {/* Hero Section */}
      <section className="flex w-full max-w-5xl flex-col items-center pt-8 pb-14 text-center">
        {/* Release Pill */}
        <div className="inline-flex items-center space-x-2 rounded-full border border-indigo-500/30 bg-indigo-500/10 px-3.5 py-1.5 text-xs font-medium text-indigo-300 shadow-inner">
          <Zap className="h-3.5 w-3.5 text-indigo-400" />
          <span>RepoMind v0.1 • Zero-Cost Grounded RAG Platform</span>
        </div>

        {/* Hero Title */}
        <h1 className="mt-6 text-4xl font-extrabold tracking-tight text-white sm:text-6xl sm:leading-[1.15]">
          Understand Any GitHub Codebase{' '}
          <span className="bg-gradient-to-r from-indigo-400 via-purple-400 to-pink-400 bg-clip-text text-transparent">
            Without Reading Thousands of Lines
          </span>
        </h1>

        {/* Subtitle */}
        <p className="mx-auto mt-6 max-w-2xl text-base leading-relaxed text-slate-400 sm:text-lg">
          Paste any public GitHub repository URL. RepoMind extracts AST syntax nodes, builds semantic code embeddings, and provides verified technical answers backed by exact source file citations.
        </p>

        {/* URL Input Form */}
        <div className="mt-8 flex w-full justify-center">
          <UrlInputForm
            initialUrl={selectedUrl}
            onAnalysisStart={onAnalysisStart}
          />
        </div>

        {/* Curated Demo Cards */}
        <div className="mt-14 w-full flex justify-center">
          <DemoCards
            demos={demos}
            onSelectDemo={(url) => {
              setSelectedUrl(url);
              window.scrollTo({ top: 0, behavior: 'smooth' });
            }}
          />
        </div>
      </section>

      {/* Execution Flow & Architecture */}
      <HowItWorks />

      {/* Capabilities */}
      <Features />

      {/* Tech Stack */}
      <TechStack />
    </div>
  );
};
