import React, { useState } from 'react';
import {
  GitBranch,
  ArrowLeft,
  ExternalLink,
  ShieldCheck,
  FolderTree,
  MessageSquare,
  Sparkles,
  Layers,
  CheckCircle2,
  Clock,
} from 'lucide-react';
import type { ValidationResult } from '../types';

interface DashboardPreviewProps {
  repoUrl: string;
  validation: ValidationResult;
  onBack: () => void;
}

export const DashboardPreview: React.FC<DashboardPreviewProps> = ({
  repoUrl,
  validation,
  onBack,
}) => {
  const [activeTab, setActiveTab] = useState<'overview' | 'explorer' | 'chat'>('overview');

  const suggestedQuestions = [
    'Explain the overall architecture and data flow of this repository.',
    'Where is the main application entry point and how does it start?',
    'Which modules handle authentication and database connections?',
    'What external APIs and primary third-party dependencies are used?',
  ];

  return (
    <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
      {/* Top Navigation & Back Action */}
      <div className="mb-6 flex items-center justify-between">
        <button
          onClick={onBack}
          className="flex items-center space-x-2 rounded-lg border border-slate-800 bg-slate-900/60 px-3.5 py-1.5 text-xs font-medium text-slate-300 transition-colors hover:border-slate-700 hover:text-white"
        >
          <ArrowLeft className="h-4 w-4" />
          <span>Select Another Repository</span>
        </button>

        <div className="flex items-center space-x-2 text-xs text-slate-400">
          <span className="h-2 w-2 rounded-full bg-emerald-400" />
          <span>URL Validated & Public Access Confirmed</span>
        </div>
      </div>

      {/* Repository Main Header Card */}
      <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6 backdrop-blur-md">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <div className="flex items-center space-x-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                <GitBranch className="h-5 w-5" />
              </div>
              <div>
                <h1 className="text-2xl font-bold text-white">
                  {validation.owner} / <span className="text-indigo-400">{validation.repo}</span>
                </h1>
                <div className="flex items-center space-x-3 text-xs text-slate-400">
                  <a
                    href={repoUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center space-x-1 hover:text-indigo-300"
                  >
                    <span>{repoUrl}</span>
                    <ExternalLink className="h-3 w-3" />
                  </a>
                  <span>•</span>
                  <span className="rounded bg-emerald-500/10 px-2 py-0.5 font-medium text-emerald-400 border border-emerald-500/20">
                    Public Repository
                  </span>
                </div>
              </div>
            </div>
          </div>

          <div className="flex items-center space-x-3">
            <span className="flex items-center space-x-1.5 rounded-xl border border-slate-700 bg-slate-800/60 px-3 py-1.5 text-xs text-slate-300">
              <ShieldCheck className="h-4 w-4 text-emerald-400" />
              <span>Sandbox Isolated</span>
            </span>
          </div>
        </div>

        {/* Ingestion Pipeline Stages Status */}
        <div className="mt-6 border-t border-slate-800/80 pt-6">
          <div className="mb-2 flex items-center justify-between text-xs">
            <span className="font-semibold text-slate-300 uppercase tracking-wider">
              Ingestion Pipeline Status
            </span>
            <span className="text-indigo-400 font-mono">Phase 1: Validation Complete</span>
          </div>

          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/5 p-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-emerald-400">1. URL Validation</span>
                <CheckCircle2 className="h-4 w-4 text-emerald-400" />
              </div>
              <p className="mt-1 text-[11px] text-slate-400">Verified & Accessible</p>
            </div>

            <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-slate-300">2. Ingestion & Clone</span>
                <Clock className="h-4 w-4 text-slate-500" />
              </div>
              <p className="mt-1 text-[11px] text-slate-500">Phase 2 Target</p>
            </div>

            <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-slate-300">3. AST Code Parsing</span>
                <Clock className="h-4 w-4 text-slate-500" />
              </div>
              <p className="mt-1 text-[11px] text-slate-500">Phase 3 Target</p>
            </div>

            <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-slate-300">4. Vector Embeddings</span>
                <Clock className="h-4 w-4 text-slate-500" />
              </div>
              <p className="mt-1 text-[11px] text-slate-500">Phase 4 Target</p>
            </div>
          </div>
        </div>
      </div>

      {/* Dashboard Tabs */}
      <div className="mt-6 flex border-b border-slate-800 space-x-4">
        <button
          onClick={() => setActiveTab('overview')}
          className={`flex items-center space-x-2 border-b-2 px-3 py-2.5 text-sm font-medium transition-colors ${
            activeTab === 'overview'
              ? 'border-indigo-500 text-indigo-400'
              : 'border-transparent text-slate-400 hover:text-white'
          }`}
        >
          <Layers className="h-4 w-4" />
          <span>Overview</span>
        </button>

        <button
          onClick={() => setActiveTab('explorer')}
          className={`flex items-center space-x-2 border-b-2 px-3 py-2.5 text-sm font-medium transition-colors ${
            activeTab === 'explorer'
              ? 'border-indigo-500 text-indigo-400'
              : 'border-transparent text-slate-400 hover:text-white'
          }`}
        >
          <FolderTree className="h-4 w-4" />
          <span>Code Explorer</span>
        </button>

        <button
          onClick={() => setActiveTab('chat')}
          className={`flex items-center space-x-2 border-b-2 px-3 py-2.5 text-sm font-medium transition-colors ${
            activeTab === 'chat'
              ? 'border-indigo-500 text-indigo-400'
              : 'border-transparent text-slate-400 hover:text-white'
          }`}
        >
          <MessageSquare className="h-4 w-4" />
          <span>Interactive Chat</span>
        </button>
      </div>

      {/* Tab Panels */}
      <div className="mt-6">
        {activeTab === 'overview' && (
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
            {/* Left 2 Cols: Details */}
            <div className="space-y-6 lg:col-span-2">
              <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-6">
                <h3 className="text-base font-bold text-white">Repository Overview</h3>
                <p className="mt-2 text-sm text-slate-400">
                  Target repository validated successfully. The system has confirmed public accessibility without pulling untrusted code into the execution environment.
                </p>

                <div className="mt-4 grid grid-cols-2 gap-4 rounded-xl border border-slate-800 bg-slate-950/60 p-4 font-mono text-xs text-slate-300">
                  <div>
                    <span className="text-slate-500">Repository Owner:</span> {validation.owner}
                  </div>
                  <div>
                    <span className="text-slate-500">Repository Name:</span> {validation.repo}
                  </div>
                  <div>
                    <span className="text-slate-500">Target Host:</span> github.com
                  </div>
                  <div>
                    <span className="text-slate-500">Access Type:</span> Public Open Source
                  </div>
                </div>
              </div>

              {/* Sample Suggested Questions */}
              <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-6">
                <div className="flex items-center space-x-2">
                  <Sparkles className="h-4 w-4 text-indigo-400" />
                  <h3 className="text-base font-bold text-white">
                    Sample Grounded Questions for this Repo
                  </h3>
                </div>
                <p className="mt-1 text-xs text-slate-400">
                  Once indexing completes in Phase 2-4, RepoMind will answer these questions with clickable line citations:
                </p>

                <div className="mt-4 space-y-2">
                  {suggestedQuestions.map((q, idx) => (
                    <div
                      key={idx}
                      className="flex items-center justify-between rounded-xl border border-slate-800 bg-slate-900/60 p-3 text-xs text-slate-300 transition-colors hover:border-slate-700"
                    >
                      <span>{q}</span>
                      <span className="rounded bg-indigo-500/10 px-2 py-0.5 text-[10px] text-indigo-300">
                        RAG Query
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Right 1 Col: Security & Architecture Info */}
            <div className="space-y-6">
              <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-6">
                <h3 className="text-sm font-bold text-white uppercase tracking-wider">
                  Security Sandbox Policy
                </h3>
                <ul className="mt-4 space-y-3 text-xs text-slate-400">
                  <li className="flex items-start space-x-2">
                    <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-400" />
                    <span>Isolated temporary directories for file cloning</span>
                  </li>
                  <li className="flex items-start space-x-2">
                    <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-400" />
                    <span>Strict SSRF protection & domain validation</span>
                  </li>
                  <li className="flex items-start space-x-2">
                    <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-400" />
                    <span>Zero execution of cloned repository code</span>
                  </li>
                  <li className="flex items-start space-x-2">
                    <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-400" />
                    <span>Filters secret files, keys, and credentials</span>
                  </li>
                </ul>
              </div>

              <div className="rounded-2xl border border-indigo-500/20 bg-indigo-950/20 p-6">
                <h3 className="text-sm font-bold text-indigo-300 uppercase tracking-wider">
                  Phase 1 Milestone
                </h3>
                <p className="mt-2 text-xs leading-relaxed text-slate-300">
                  Phase 1 foundation is operational. Full-stack connectivity, GitHub URL validation, responsive dashboard layouts, and system health checks are live.
                </p>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'explorer' && (
          <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-12 text-center">
            <FolderTree className="mx-auto h-12 w-12 text-slate-600" />
            <h3 className="mt-4 text-base font-bold text-white">Code Explorer Module</h3>
            <p className="mx-auto mt-2 max-w-md text-xs text-slate-400">
              Directory trees, syntax-highlighted viewers, and AST symbol navigation activate upon repository cloning in Phase 2 & Phase 3.
            </p>
          </div>
        )}

        {activeTab === 'chat' && (
          <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-12 text-center">
            <MessageSquare className="mx-auto h-12 w-12 text-slate-600" />
            <h3 className="mt-4 text-base font-bold text-white">Grounded RAG Chat Interface</h3>
            <p className="mx-auto mt-2 max-w-md text-xs text-slate-400">
              Interactive conversation with traceable citations and Gemini synthesis activates in Phase 5 & Phase 6.
            </p>
          </div>
        )}
      </div>
    </div>
  );
};
