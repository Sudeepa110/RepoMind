import React, { useState } from 'react';
import {
  Zap,
  Activity,
  GitBranch,
  FileCode,
  CheckCircle2,
  AlertCircle,
  Copy,
  Check,
  Loader2,
  Search,
  BookOpen,
  Bug,
  Shield,
  Layers,
  ExternalLink,
} from 'lucide-react';
import { api } from '../services/api';
import type {
  ImpactAnalysisResult,
  ExecutionFlowResult,
  DependencyAnalysisResult,
  BugInvestigationResult,
  RiskAssessmentResult,
  TestRecommendationsResult,
  DocumentationResult,
} from '../types';

interface IntelligenceWorkspaceProps {
  repositoryId: string;
  onNavigateToFile?: (filePath: string, line?: number) => void;
}

export const IntelligenceWorkspace: React.FC<IntelligenceWorkspaceProps> = ({
  repositoryId,
  onNavigateToFile,
}) => {
  const [subTool, setSubTool] = useState<
    'impact' | 'flow' | 'dependencies' | 'bugs' | 'risk' | 'tests' | 'docs'
  >('impact');

  // Input states
  const [targetSymbol, setTargetSymbol] = useState('');
  const [filePath, setFilePath] = useState('');
  const [maxDepth, setMaxDepth] = useState(3);
  const [bugQuery, setBugQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copiedText, setCopiedText] = useState(false);

  // Result states
  const [impactResult, setImpactResult] = useState<ImpactAnalysisResult | null>(null);
  const [flowResult, setFlowResult] = useState<ExecutionFlowResult | null>(null);
  const [depResult, setDepResult] = useState<DependencyAnalysisResult | null>(null);
  const [bugResult, setBugResult] = useState<BugInvestigationResult | null>(null);
  const [riskResult, setRiskResult] = useState<RiskAssessmentResult | null>(null);
  const [testResult, setTestResult] = useState<TestRecommendationsResult | null>(null);
  const [docResult, setDocResult] = useState<DocumentationResult | null>(null);

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedText(true);
    setTimeout(() => setCopiedText(false), 2000);
  };

  // Handlers for each intelligence action
  const handleRunImpact = async () => {
    if (!targetSymbol.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.analyzeImpact(repositoryId, {
        target_symbol: targetSymbol.trim(),
        file_path: filePath.trim() || undefined,
        max_depth: maxDepth,
      });
      setImpactResult(res);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err.message || 'Failed to analyze impact.');
    } finally {
      setLoading(false);
    }
  };

  const handleRunFlow = async () => {
    if (!targetSymbol.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.traceExecutionFlow(repositoryId, {
        entry_point: targetSymbol.trim(),
        file_path: filePath.trim() || undefined,
        max_depth: maxDepth,
      });
      setFlowResult(res);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err.message || 'Failed to trace flow.');
    } finally {
      setLoading(false);
    }
  };

  const handleRunDependencies = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.analyzeDependencies(repositoryId);
      setDepResult(res);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err.message || 'Failed to analyze dependencies.');
    } finally {
      setLoading(false);
    }
  };

  const handleRunBugs = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.investigateBugs(repositoryId, {
        target: targetSymbol.trim() || undefined,
        query: bugQuery.trim() || undefined,
      });
      setBugResult(res);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err.message || 'Failed to investigate bugs.');
    } finally {
      setLoading(false);
    }
  };

  const handleRunRisk = async () => {
    if (!targetSymbol.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.assessRisk(repositoryId, {
        target_symbol: targetSymbol.trim(),
        file_path: filePath.trim() || undefined,
      });
      setRiskResult(res);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err.message || 'Failed to assess risk.');
    } finally {
      setLoading(false);
    }
  };

  const handleRunTests = async () => {
    if (!targetSymbol.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.recommendTests(repositoryId, {
        target_symbol: targetSymbol.trim(),
        file_path: filePath.trim() || undefined,
      });
      setTestResult(res);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err.message || 'Failed to generate test plan.');
    } finally {
      setLoading(false);
    }
  };

  const handleRunDocs = async () => {
    if (!targetSymbol.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.generateDocumentation(repositoryId, {
        target: targetSymbol.trim(),
        file_path: filePath.trim() || undefined,
      });
      setDocResult(res);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err.message || 'Failed to generate documentation.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header Banner */}
      <div className="rounded-2xl border border-indigo-500/20 bg-gradient-to-r from-indigo-950/40 via-purple-950/20 to-slate-900/60 p-6 backdrop-blur-md">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center space-x-2">
              <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-indigo-500/20 text-indigo-400">
                <Zap className="h-4 w-4" />
              </span>
              <h2 className="text-xl font-bold text-white">Repository Intelligence Engine</h2>
              <span className="rounded-full bg-indigo-500/20 px-2.5 py-0.5 text-[10px] font-mono text-indigo-300 border border-indigo-500/30">
                Phase 8
              </span>
            </div>
            <p className="mt-1 text-xs text-slate-400">
              Multi-file change impact analysis, cross-file execution tracing, architectural coupling, bug root-cause investigation, and deterministic risk assessment.
            </p>
          </div>
        </div>

        {/* Sub-Tool Navigation Pills */}
        <div className="mt-6 flex flex-wrap gap-2 border-t border-slate-800/80 pt-4">
          {[
            { id: 'impact', label: 'Impact Analysis', icon: GitBranch },
            { id: 'flow', label: 'Execution Flow', icon: Activity },
            { id: 'dependencies', label: 'Coupling & Layers', icon: Layers },
            { id: 'bugs', label: 'Bug Investigation', icon: Bug },
            { id: 'risk', label: 'Risk Assessment', icon: Shield },
            { id: 'tests', label: 'Test Recommendations', icon: CheckCircle2 },
            { id: 'docs', label: 'Technical Docs', icon: BookOpen },
          ].map((item) => {
            const Icon = item.icon;
            const active = subTool === item.id;
            return (
              <button
                key={item.id}
                onClick={() => {
                  setSubTool(item.id as any);
                  setError(null);
                }}
                className={`flex items-center space-x-2 rounded-xl px-3.5 py-2 text-xs font-medium transition-all ${
                  active
                    ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/20 font-semibold'
                    : 'bg-slate-800/60 text-slate-400 hover:bg-slate-800 hover:text-white'
                }`}
              >
                <Icon className="h-3.5 w-3.5" />
                <span>{item.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Input Controls Bar */}
      <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-4 backdrop-blur-md">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3 items-end">
          {subTool !== 'dependencies' && (
            <div className="md:col-span-2">
              <label className="block text-[11px] font-medium text-slate-400 mb-1">
                {subTool === 'flow' ? 'Entry Point Function / Handler' : 'Target Symbol (Function, Class, Method)'}
              </label>
              <input
                type="text"
                value={targetSymbol}
                onChange={(e) => setTargetSymbol(e.target.value)}
                placeholder="e.g. verify_password, authenticate_user, Router, main"
                className="w-full rounded-xl border border-slate-800 bg-slate-950/80 px-3.5 py-2 text-xs text-white placeholder-slate-500 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              />
            </div>
          )}

          {subTool !== 'dependencies' && (
            <div>
              <label className="block text-[11px] font-medium text-slate-400 mb-1">
                File Path (Optional)
              </label>
              <input
                type="text"
                value={filePath}
                onChange={(e) => setFilePath(e.target.value)}
                placeholder="e.g. backend/app/auth.py"
                className="w-full rounded-xl border border-slate-800 bg-slate-950/80 px-3.5 py-2 text-xs text-white placeholder-slate-500 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              />
            </div>
          )}

          {(subTool === 'impact' || subTool === 'flow') && (
            <div>
              <label className="block text-[11px] font-medium text-slate-400 mb-1">
                Max Traversal Depth: {maxDepth}
              </label>
              <input
                type="range"
                min="1"
                max="8"
                value={maxDepth}
                onChange={(e) => setMaxDepth(parseInt(e.target.value, 10))}
                className="w-full h-2 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-indigo-500"
              />
            </div>
          )}

          {subTool === 'bugs' && (
            <div className="md:col-span-3">
              <label className="block text-[11px] font-medium text-slate-400 mb-1">
                Bug Query / Error Scenario (Optional)
              </label>
              <input
                type="text"
                value={bugQuery}
                onChange={(e) => setBugQuery(e.target.value)}
                placeholder="e.g. Unhandled None return, missing exception handling in database query"
                className="w-full rounded-xl border border-slate-800 bg-slate-950/80 px-3.5 py-2 text-xs text-white placeholder-slate-500 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              />
            </div>
          )}

          <div className="flex items-center space-x-2">
            <button
              onClick={() => {
                if (subTool === 'impact') handleRunImpact();
                if (subTool === 'flow') handleRunFlow();
                if (subTool === 'dependencies') handleRunDependencies();
                if (subTool === 'bugs') handleRunBugs();
                if (subTool === 'risk') handleRunRisk();
                if (subTool === 'tests') handleRunTests();
                if (subTool === 'docs') handleRunDocs();
              }}
              disabled={loading}
              className="flex-1 flex items-center justify-center space-x-2 rounded-xl bg-indigo-600 px-4 py-2.5 text-xs font-semibold text-white shadow-lg shadow-indigo-600/20 hover:bg-indigo-500 transition-colors disabled:opacity-50"
            >
              {loading ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  <span>Analyzing...</span>
                </>
              ) : (
                <>
                  <Search className="h-3.5 w-3.5" />
                  <span>Execute Analysis</span>
                </>
              )}
            </button>
          </div>
        </div>

        {error && (
          <div className="mt-4 flex items-center space-x-2 rounded-xl border border-rose-500/30 bg-rose-500/10 p-3 text-xs text-rose-300">
            <AlertCircle className="h-4 w-4 shrink-0 text-rose-400" />
            <span>{error}</span>
          </div>
        )}
      </div>

      {/* --- SUB-VIEW 1: IMPACT ANALYSIS --- */}
      {subTool === 'impact' && impactResult && (
        <div className="space-y-6">
          {/* Quick Metrics */}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
              <span className="text-[10px] uppercase font-semibold text-slate-500">Risk Level</span>
              <p className={`mt-1 text-xl font-bold ${
                impactResult.risk_level === 'CRITICAL' ? 'text-rose-400' :
                impactResult.risk_level === 'HIGH' ? 'text-amber-400' :
                impactResult.risk_level === 'MEDIUM' ? 'text-yellow-400' : 'text-emerald-400'
              }`}>
                {impactResult.risk_level} ({impactResult.risk_score.toFixed(0)}/100)
              </p>
            </div>
            <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
              <span className="text-[10px] uppercase font-semibold text-slate-500">Direct Callers</span>
              <p className="mt-1 text-xl font-bold text-white">{impactResult.direct_count}</p>
            </div>
            <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
              <span className="text-[10px] uppercase font-semibold text-slate-500">Indirect Propagation</span>
              <p className="mt-1 text-xl font-bold text-indigo-400">{impactResult.indirect_count}</p>
            </div>
            <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
              <span className="text-[10px] uppercase font-semibold text-slate-500">Structural Scope</span>
              <p className="mt-1 text-xl font-bold text-purple-400">{impactResult.structural_count}</p>
            </div>
            <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
              <span className="text-[10px] uppercase font-semibold text-slate-500">Affected Files</span>
              <p className="mt-1 text-xl font-bold text-emerald-400">{impactResult.total_affected_files}</p>
            </div>
          </div>

          {/* Explanation Text */}
          <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold text-white">Grounded Impact Assessment</h3>
              <button
                onClick={() => handleCopy(impactResult.explanation)}
                className="flex items-center space-x-1 text-xs text-slate-400 hover:text-white"
              >
                {copiedText ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
                <span>{copiedText ? 'Copied' : 'Copy'}</span>
              </button>
            </div>
            <div className="prose prose-invert prose-xs max-w-none font-mono text-xs text-slate-300 whitespace-pre-wrap leading-relaxed">
              {impactResult.explanation}
            </div>
          </div>

          {/* Affected Entities List */}
          <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-6">
            <h3 className="text-sm font-semibold text-white mb-4">
              Affected Code Entities ({impactResult.affected_entities.length})
            </h3>
            <div className="space-y-2">
              {impactResult.affected_entities.map((entity, idx) => (
                <div
                  key={idx}
                  className="flex flex-col sm:flex-row sm:items-center justify-between p-3 rounded-xl border border-slate-800/80 bg-slate-950/40 hover:border-slate-700 transition-colors gap-2"
                >
                  <div className="flex items-center space-x-3">
                    <span className={`px-2 py-0.5 rounded text-[10px] font-semibold ${
                      entity.category === 'DIRECT' ? 'bg-rose-500/10 text-rose-400 border border-rose-500/20' :
                      entity.category === 'INDIRECT' ? 'bg-indigo-500/10 text-indigo-400 border border-indigo-500/20' :
                      entity.category === 'STRUCTURAL' ? 'bg-purple-500/10 text-purple-400 border border-purple-500/20' :
                      'bg-slate-800 text-slate-400'
                    }`}>
                      {entity.category}
                    </span>
                    <div>
                      <span className="font-mono text-xs font-semibold text-white">{entity.name}</span>
                      <span className="ml-2 text-[10px] text-slate-500 font-mono">({entity.type})</span>
                      {entity.relationship_path.length > 0 && (
                        <p className="text-[11px] text-slate-400 mt-0.5">
                          Path: {entity.relationship_path.join(' -> ')}
                        </p>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center space-x-3">
                    <button
                      onClick={() => onNavigateToFile?.(entity.file_path, entity.start_line)}
                      className="flex items-center space-x-1 font-mono text-xs text-indigo-400 hover:text-indigo-300"
                    >
                      <FileCode className="h-3.5 w-3.5" />
                      <span>{entity.file_path}:{entity.start_line || 1}</span>
                      <ExternalLink className="h-3 w-3" />
                    </button>
                    <span className="text-[10px] text-slate-500">depth {entity.depth}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* --- SUB-VIEW 2: EXECUTION FLOW --- */}
      {subTool === 'flow' && flowResult && (
        <div className="space-y-6">
          <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-6">
            <h3 className="text-sm font-semibold text-white mb-4">
              Static Call Sequence ({flowResult.total_steps} Steps, {flowResult.cross_file_count} Cross-File Jumps)
            </h3>
            <div className="space-y-3">
              {flowResult.steps.map((step) => (
                <div
                  key={step.step_index}
                  className="flex items-start space-x-4 p-3.5 rounded-xl border border-slate-800/80 bg-slate-950/40"
                >
                  <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-indigo-500/20 text-xs font-bold text-indigo-400">
                    {step.step_index}
                  </span>
                  <div className="flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-mono text-xs font-semibold text-white">{step.symbol_name}</span>
                      <span className="text-[10px] text-slate-500">({step.symbol_type})</span>
                      {step.crosses_file && (
                        <span className="rounded bg-amber-500/10 px-1.5 py-0.5 text-[9px] font-semibold text-amber-400 border border-amber-500/20">
                          Cross-File
                        </span>
                      )}
                      {step.is_external && (
                        <span className="rounded bg-slate-800 px-1.5 py-0.5 text-[9px] text-slate-400">
                          External Lib
                        </span>
                      )}
                      {step.is_branch_point && (
                        <span className="rounded bg-indigo-500/10 px-1.5 py-0.5 text-[9px] text-indigo-400 border border-indigo-500/20">
                          Branch Point
                        </span>
                      )}
                    </div>
                    {step.caller_symbol && (
                      <p className="mt-1 text-[11px] text-slate-400">
                        Called by: <span className="font-mono text-slate-300">{step.caller_symbol}</span>
                      </p>
                    )}
                  </div>
                  {step.file_path && (
                    <button
                      onClick={() => onNavigateToFile?.(step.file_path, step.start_line)}
                      className="flex items-center space-x-1 font-mono text-[11px] text-indigo-400 hover:text-indigo-300 shrink-0"
                    >
                      <FileCode className="h-3.5 w-3.5" />
                      <span>{step.file_path}:{step.start_line || 1}</span>
                    </button>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* --- SUB-VIEW 3: DEPENDENCIES & COUPLING --- */}
      {subTool === 'dependencies' && depResult && (
        <div className="space-y-6">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
              <span className="text-[10px] uppercase font-semibold text-slate-500">Total Files</span>
              <p className="mt-1 text-2xl font-bold text-white">{depResult.total_files}</p>
            </div>
            <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
              <span className="text-[10px] uppercase font-semibold text-slate-500">Avg Martin Instability</span>
              <p className="mt-1 text-2xl font-bold text-indigo-400">{depResult.average_instability.toFixed(2)}</p>
            </div>
            <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
              <span className="text-[10px] uppercase font-semibold text-slate-500">Tightly Coupled Pairs</span>
              <p className="mt-1 text-2xl font-bold text-amber-400">{depResult.tightly_coupled_pairs.length}</p>
            </div>
            <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
              <span className="text-[10px] uppercase font-semibold text-slate-500">External Packages</span>
              <p className="mt-1 text-2xl font-bold text-emerald-400">{depResult.external_libraries.length}</p>
            </div>
          </div>

          {/* Module Coupling Table */}
          <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-6 overflow-x-auto">
            <h3 className="text-sm font-semibold text-white mb-4">File Coupling & Instability Index</h3>
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-slate-800 text-[11px] text-slate-400">
                  <th className="pb-3 font-semibold">Module / File</th>
                  <th className="pb-3 font-semibold">Layer</th>
                  <th className="pb-3 font-semibold">In-Degree</th>
                  <th className="pb-3 font-semibold">Out-Degree</th>
                  <th className="pb-3 font-semibold">Instability (I)</th>
                  <th className="pb-3 font-semibold">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 font-mono">
                {depResult.file_metrics.map((m, idx) => (
                  <tr key={idx} className="hover:bg-slate-800/30">
                    <td className="py-2.5 text-white">{m.file_path}</td>
                    <td className="py-2.5 text-indigo-400">{m.layer}</td>
                    <td className="py-2.5 text-emerald-400">{m.in_degree}</td>
                    <td className="py-2.5 text-amber-400">{m.out_degree}</td>
                    <td className="py-2.5 text-slate-300">{m.instability.toFixed(2)}</td>
                    <td className="py-2.5">
                      {m.is_tightly_coupled ? (
                        <span className="rounded bg-rose-500/10 px-1.5 py-0.5 text-[10px] font-semibold text-rose-400 border border-rose-500/20">
                          Tightly Coupled
                        </span>
                      ) : (
                        <span className="rounded bg-slate-800 px-1.5 py-0.5 text-[10px] text-slate-400">
                          Normal
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* --- SUB-VIEW 4: BUG INVESTIGATION --- */}
      {subTool === 'bugs' && bugResult && (
        <div className="space-y-6">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="rounded-xl border border-rose-500/30 bg-rose-500/5 p-4">
              <span className="text-[10px] uppercase font-semibold text-rose-400">Critical Issues</span>
              <p className="mt-1 text-2xl font-bold text-rose-400">{bugResult.critical_count}</p>
            </div>
            <div className="rounded-xl border border-amber-500/30 bg-amber-500/5 p-4">
              <span className="text-[10px] uppercase font-semibold text-amber-400">High Severity</span>
              <p className="mt-1 text-2xl font-bold text-amber-400">{bugResult.high_count}</p>
            </div>
            <div className="rounded-xl border border-yellow-500/30 bg-yellow-500/5 p-4">
              <span className="text-[10px] uppercase font-semibold text-yellow-400">Medium Severity</span>
              <p className="mt-1 text-2xl font-bold text-yellow-400">{bugResult.medium_count}</p>
            </div>
            <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
              <span className="text-[10px] uppercase font-semibold text-slate-400">Low / Info</span>
              <p className="mt-1 text-2xl font-bold text-slate-300">{bugResult.low_count}</p>
            </div>
          </div>

          <div className="space-y-4">
            {bugResult.findings.map((f) => (
              <div
                key={f.finding_id}
                className="rounded-2xl border border-slate-800 bg-slate-900/40 p-6 space-y-3"
              >
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <div className="flex items-center space-x-2">
                    <span className={`px-2 py-0.5 rounded text-[10px] font-semibold ${
                      f.severity === 'CRITICAL' ? 'bg-rose-500/20 text-rose-300 border border-rose-500/30' :
                      f.severity === 'HIGH' ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30' :
                      'bg-indigo-500/20 text-indigo-300 border border-indigo-500/30'
                    }`}>
                      {f.severity}
                    </span>
                    <h4 className="text-sm font-semibold text-white">{f.title}</h4>
                    <span className="text-[11px] text-slate-500 font-mono">({f.finding_id})</span>
                  </div>
                  <button
                    onClick={() => onNavigateToFile?.(f.file_path, f.start_line)}
                    className="flex items-center space-x-1 font-mono text-xs text-indigo-400 hover:text-indigo-300"
                  >
                    <FileCode className="h-3.5 w-3.5" />
                    <span>{f.file_path}:{f.start_line}-{f.end_line}</span>
                  </button>
                </div>

                <p className="text-xs text-slate-300">{f.explanation}</p>
                <div className="rounded-xl bg-slate-950/60 p-3 text-[11px] font-mono text-rose-300/90 border border-rose-500/10">
                  <span className="text-slate-400 font-sans font-medium">Failure Scenario: </span>
                  {f.possible_failure_scenario}
                </div>
                <div className="rounded-xl bg-slate-950/60 p-3 text-[11px] font-mono text-emerald-300/90 border border-emerald-500/10">
                  <span className="text-slate-400 font-sans font-medium">Suggested Remediation: </span>
                  {f.suggested_remediation}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* --- SUB-VIEW 5: RISK ASSESSMENT --- */}
      {subTool === 'risk' && riskResult && (
        <div className="space-y-6">
          <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-6 space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <span className="text-[11px] uppercase tracking-wider font-semibold text-slate-500">
                  Risk Level
                </span>
                <h3 className={`text-2xl font-bold mt-1 ${
                  riskResult.risk_level === 'CRITICAL' ? 'text-rose-400' :
                  riskResult.risk_level === 'HIGH' ? 'text-amber-400' :
                  riskResult.risk_level === 'MEDIUM' ? 'text-yellow-400' : 'text-emerald-400'
                }`}>
                  {riskResult.risk_level} ({riskResult.risk_score.toFixed(1)} / 100)
                </h3>
              </div>
              <div className="text-right">
                <span className="text-xs text-slate-400 font-mono">
                  Blast Radius: {riskResult.blast_radius_files} File(s)
                </span>
              </div>
            </div>

            <p className="text-xs text-slate-300">{riskResult.summary}</p>
            <p className="text-[11px] font-mono text-slate-500">{riskResult.formula_explanation}</p>

            <div className="border-t border-slate-800/80 pt-4 space-y-2">
              <h4 className="text-xs font-semibold text-slate-400 mb-2">Formula Factors Breakdown</h4>
              {riskResult.formula_breakdown.map((factor, idx) => (
                <div
                  key={idx}
                  className="flex items-center justify-between p-2.5 rounded-xl bg-slate-950/40 border border-slate-800/60 text-xs"
                >
                  <span className="font-medium text-white">{factor.factor_name}</span>
                  <div className="flex items-center space-x-3">
                    <span className="text-slate-400 text-[11px]">{factor.reason}</span>
                    <span className="font-mono font-bold text-indigo-400">+{factor.points} pts</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* --- SUB-VIEW 6: TEST RECOMMENDATIONS --- */}
      {subTool === 'tests' && testResult && (
        <div className="space-y-6">
          <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-6 space-y-4">
            <h3 className="text-sm font-semibold text-white">
              Recommended Test Scenarios for `{testResult.target_symbol}` ({testResult.total_recommendations})
            </h3>
            <div className="space-y-3">
              {testResult.recommendations.map((rec) => (
                <div
                  key={rec.recommendation_id}
                  className="p-4 rounded-xl border border-slate-800/80 bg-slate-950/40 space-y-2"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-2">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-semibold ${
                        rec.category === 'UNIT' ? 'bg-indigo-500/20 text-indigo-300' :
                        rec.category === 'INTEGRATION' ? 'bg-purple-500/20 text-purple-300' :
                        'bg-amber-500/20 text-amber-300'
                      }`}>
                        {rec.category}
                      </span>
                      <span className="font-mono text-xs font-semibold text-white">{rec.target_symbol}</span>
                      <span className="text-[10px] text-slate-500 font-mono">({rec.priority} Priority)</span>
                    </div>
                    <span className="text-xs font-mono text-slate-400">{rec.file_path}</span>
                  </div>
                  <p className="text-xs text-slate-300">{rec.reason}</p>
                  <div className="rounded-lg bg-slate-900/60 p-3 space-y-1">
                    <span className="text-[10px] uppercase font-semibold text-slate-500">Suggested Assertions:</span>
                    {rec.suggested_assertions.map((a, i) => (
                      <p key={i} className="text-xs font-mono text-slate-400">• {a}</p>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* --- SUB-VIEW 7: TECHNICAL DOCUMENTATION --- */}
      {subTool === 'docs' && docResult && (
        <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-6 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-semibold text-white">Technical Specification</h3>
              <p className="text-xs text-slate-400 font-mono mt-0.5">{docResult.file_path}</p>
            </div>
            <button
              onClick={() => handleCopy(docResult.markdown_documentation)}
              className="flex items-center space-x-1.5 rounded-xl border border-slate-700 bg-slate-800 px-3 py-1.5 text-xs text-slate-300 hover:text-white"
            >
              {copiedText ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
              <span>{copiedText ? 'Copied' : 'Copy Markdown'}</span>
            </button>
          </div>
          <div className="prose prose-invert prose-xs max-w-none font-mono text-xs text-slate-300 whitespace-pre-wrap leading-relaxed border-t border-slate-800/80 pt-4">
            {docResult.markdown_documentation}
          </div>
        </div>
      )}
    </div>
  );
};
