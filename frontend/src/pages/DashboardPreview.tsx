import React, { useState, useEffect } from 'react';
import {
  GitBranch,
  ArrowLeft,
  ExternalLink,
  ShieldCheck,
  FolderTree,
  Folder,
  FileCode,
  MessageSquare,
  Sparkles,
  Layers,
  CheckCircle2,
  Clock,
  AlertTriangle,
  Loader2,
  FileText,
} from 'lucide-react';
import { api } from '../services/api';
import type {
  ValidationResult,
  RepositoryDetail,
  IndexingStatus,
  TreeNode,
  FileContent,
} from '../types';

interface DashboardPreviewProps {
  repoUrl: string;
  validation: ValidationResult;
  onBack: () => void;
}

const LANGUAGE_COLORS: Record<string, string> = {
  Python: 'bg-blue-500',
  TypeScript: 'bg-indigo-500',
  JavaScript: 'bg-yellow-400',
  Go: 'bg-cyan-500',
  Java: 'bg-red-500',
  C: 'bg-slate-400',
  'C++': 'bg-pink-500',
  Rust: 'bg-orange-500',
  HTML: 'bg-amber-500',
  CSS: 'bg-purple-500',
  Markdown: 'bg-emerald-500',
  JSON: 'bg-teal-500',
  YAML: 'bg-lime-500',
};

export const DashboardPreview: React.FC<DashboardPreviewProps> = ({
  repoUrl,
  validation,
  onBack,
}) => {
  const [activeTab, setActiveTab] = useState<'overview' | 'explorer' | 'chat'>('overview');
  const [status, setStatus] = useState<IndexingStatus | null>(null);
  const [details, setDetails] = useState<RepositoryDetail | null>(null);
  const [tree, setTree] = useState<TreeNode | null>(null);
  const [selectedFilePath, setSelectedFilePath] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<FileContent | null>(null);
  const [fileLoading, setFileLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Initialize analysis on load
  useEffect(() => {
    let isMounted = true;
    let pollInterval: any = null;

    const startAnalysis = async () => {
      try {
        const initRes = await api.analyzeRepository(repoUrl);
        const repoId = initRes.repository_id;

        // Poll status until complete or failed
        const checkStatus = async () => {
          try {
            const st = await api.getRepositoryStatus(repoId);
            if (!isMounted) return;
            setStatus(st);

            if (st.status === 'completed') {
              clearInterval(pollInterval);
              // Fetch details & tree
              const [det, tr] = await Promise.all([
                api.getRepositoryDetails(repoId),
                api.getRepositoryTree(repoId),
              ]);
              if (isMounted) {
                setDetails(det);
                setTree(tr);
              }
            } else if (st.status === 'failed') {
              clearInterval(pollInterval);
              setError(st.error_message || 'Indexing job failed.');
            }
          } catch (pollErr: any) {
            console.error('Polling error:', pollErr);
          }
        };

        await checkStatus();
        pollInterval = setInterval(checkStatus, 1500);
      } catch (err: any) {
        if (isMounted) {
          setError(err.response?.data?.detail || err.message || 'Failed to start repository analysis.');
        }
      }
    };

    startAnalysis();

    return () => {
      isMounted = false;
      if (pollInterval) clearInterval(pollInterval);
    };
  }, [repoUrl]);

  // Load file content when a file is selected in the tree
  useEffect(() => {
    if (!selectedFilePath || !details) return;

    let isMounted = true;
    setFileLoading(true);

    api
      .getRepositoryFile(details.id, selectedFilePath)
      .then((data) => {
        if (isMounted) {
          setSelectedFile(data);
          setFileLoading(false);
        }
      })
      .catch((err) => {
        if (isMounted) {
          console.error('File load error:', err);
          setSelectedFile(null);
          setFileLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [selectedFilePath, details]);

  // Recursive Tree Component
  const renderTreeNodes = (nodes: TreeNode[] | undefined, depth = 0) => {
    if (!nodes) return null;

    return nodes.map((node) => {
      const isFile = node.type === 'file';
      const isSelected = selectedFilePath === node.path;

      if (isFile) {
        return (
          <div
            key={node.path}
            onClick={() => setSelectedFilePath(node.path)}
            style={{ paddingLeft: `${depth * 14 + 10}px` }}
            className={`flex cursor-pointer items-center justify-between py-1.5 pr-3 text-xs transition-colors ${
              isSelected
                ? 'bg-indigo-500/20 text-indigo-300 font-semibold'
                : 'text-slate-400 hover:bg-slate-800/40 hover:text-white'
            }`}
          >
            <div className="flex items-center space-x-2 truncate">
              <FileCode className="h-3.5 w-3.5 shrink-0 text-slate-500" />
              <span className="truncate">{node.name}</span>
            </div>
            {node.line_count !== undefined && (
              <span className="font-mono text-[10px] text-slate-500">
                {node.line_count}L
              </span>
            )}
          </div>
        );
      }

      // Directory
      return (
        <div key={node.path || node.name}>
          <div
            style={{ paddingLeft: `${depth * 14 + 10}px` }}
            className="flex items-center space-x-2 py-1.5 text-xs font-semibold text-slate-300"
          >
            <Folder className="h-3.5 w-3.5 text-indigo-400/80" />
            <span className="truncate">{node.name}</span>
          </div>
          {node.children && renderTreeNodes(node.children, depth + 1)}
        </div>
      );
    });
  };

  const isCompleted = status?.status === 'completed';
  const isFailed = status?.status === 'failed';

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
          <span className={`h-2 w-2 rounded-full ${isCompleted ? 'bg-emerald-400' : isFailed ? 'bg-rose-400' : 'bg-indigo-400 animate-ping'}`} />
          <span>{status?.current_stage || 'Initializing Ingestion...'}</span>
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
                  {details?.default_branch && (
                    <>
                      <span>•</span>
                      <span className="font-mono text-slate-400">
                        branch: {details.default_branch}
                      </span>
                    </>
                  )}
                  {details?.commit_hash && (
                    <>
                      <span>•</span>
                      <span className="font-mono text-slate-500 text-[11px]">
                        commit: {details.commit_hash.slice(0, 7)}
                      </span>
                    </>
                  )}
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

        {/* Live Progress Bar if Ingesting */}
        {!isCompleted && !isFailed && (
          <div className="mt-6 border-t border-slate-800/80 pt-6">
            <div className="mb-2 flex items-center justify-between text-xs">
              <div className="flex items-center space-x-2 text-indigo-400 font-medium">
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                <span>{status?.current_stage || 'Cloning and analyzing repository...'}</span>
              </div>
              <span className="font-mono text-slate-300">{status?.progress_pct || 0}%</span>
            </div>
            <div className="h-2 w-full overflow-hidden rounded-full bg-slate-800">
              <div
                className="h-full bg-gradient-to-r from-indigo-500 via-purple-500 to-pink-500 transition-all duration-500"
                style={{ width: `${status?.progress_pct || 5}%` }}
              />
            </div>
          </div>
        )}

        {/* Error Alert */}
        {error && (
          <div className="mt-6 flex items-center space-x-3 rounded-xl border border-rose-500/30 bg-rose-500/10 p-4 text-xs text-rose-300">
            <AlertTriangle className="h-5 w-5 shrink-0 text-rose-400" />
            <div>
              <p className="font-semibold text-rose-200">Repository Ingestion Error</p>
              <p className="mt-0.5 text-rose-300/90">{error}</p>
            </div>
          </div>
        )}

        {/* Ingestion Pipeline Stages Status */}
        <div className="mt-6 border-t border-slate-800/80 pt-6">
          <div className="mb-2 flex items-center justify-between text-xs">
            <span className="font-semibold text-slate-300 uppercase tracking-wider">
              Ingestion Pipeline Status
            </span>
            <span className="text-indigo-400 font-mono">
              {isCompleted ? 'Phase 2: Ingestion & Filtering Complete' : 'Executing Phase 2'}
            </span>
          </div>

          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/5 p-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-emerald-400">1. URL Validation</span>
                <CheckCircle2 className="h-4 w-4 text-emerald-400" />
              </div>
              <p className="mt-1 text-[11px] text-slate-400">Verified & Accessible</p>
            </div>

            <div className={`rounded-xl border p-3 ${isCompleted ? 'border-emerald-500/30 bg-emerald-500/5' : 'border-indigo-500/30 bg-indigo-500/5'}`}>
              <div className="flex items-center justify-between">
                <span className={`text-xs font-semibold ${isCompleted ? 'text-emerald-400' : 'text-indigo-300'}`}>
                  2. Shallow Clone
                </span>
                {isCompleted ? <CheckCircle2 className="h-4 w-4 text-emerald-400" /> : <Loader2 className="h-4 w-4 animate-spin text-indigo-400" />}
              </div>
              <p className="mt-1 text-[11px] text-slate-400">
                {isCompleted ? 'Isolated (depth=1)' : 'In Progress'}
              </p>
            </div>

            <div className={`rounded-xl border p-3 ${isCompleted ? 'border-emerald-500/30 bg-emerald-500/5' : 'border-slate-800 bg-slate-900/40'}`}>
              <div className="flex items-center justify-between">
                <span className={`text-xs font-semibold ${isCompleted ? 'text-emerald-400' : 'text-slate-300'}`}>
                  3. File Filtering
                </span>
                {isCompleted ? <CheckCircle2 className="h-4 w-4 text-emerald-400" /> : <Clock className="h-4 w-4 text-slate-500" />}
              </div>
              <p className="mt-1 text-[11px] text-slate-400">
                {isCompleted ? 'Binaries & Secrets Stripped' : 'Pending'}
              </p>
            </div>

            <div className={`rounded-xl border p-3 ${isCompleted ? 'border-emerald-500/30 bg-emerald-500/5' : 'border-slate-800 bg-slate-900/40'}`}>
              <div className="flex items-center justify-between">
                <span className={`text-xs font-semibold ${isCompleted ? 'text-emerald-400' : 'text-slate-300'}`}>
                  4. Static Analysis
                </span>
                {isCompleted ? <CheckCircle2 className="h-4 w-4 text-emerald-400" /> : <Clock className="h-4 w-4 text-slate-500" />}
              </div>
              <p className="mt-1 text-[11px] text-slate-400">
                {isCompleted ? `${details?.file_count || 0} Files Cataloged` : 'Pending'}
              </p>
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
          <span>Grounded RAG Chat</span>
        </button>
      </div>

      {/* Tab Panels */}
      <div className="mt-6">
        {activeTab === 'overview' && (
          <div className="space-y-6">
            {/* Quick Stats Grid */}
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
              <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
                <span className="text-[11px] text-slate-500 uppercase tracking-wider font-semibold">Indexed Files</span>
                <p className="mt-1 text-2xl font-bold text-white">{details?.file_count || 0}</p>
                <span className="text-[11px] text-slate-400">Excluding binaries & secrets</span>
              </div>

              <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
                <span className="text-[11px] text-slate-500 uppercase tracking-wider font-semibold">Primary Language</span>
                <p className="mt-1 text-2xl font-bold text-indigo-400">{details?.primary_language || 'Detecting...'}</p>
                <span className="text-[11px] text-slate-400">By total line volume</span>
              </div>

              <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
                <span className="text-[11px] text-slate-500 uppercase tracking-wider font-semibold">Configuration Manifests</span>
                <p className="mt-1 text-2xl font-bold text-emerald-400">{details?.manifest_files.length || 0}</p>
                <span className="text-[11px] text-slate-400">Dependencies & build configs</span>
              </div>

              <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
                <span className="text-[11px] text-slate-500 uppercase tracking-wider font-semibold">Entry Points</span>
                <p className="mt-1 text-2xl font-bold text-purple-400">{details?.entry_points.length || 0}</p>
                <span className="text-[11px] text-slate-400">Application bootstrap candidates</span>
              </div>
            </div>

            {/* Language Distribution Breakdown Bar */}
            {details && details.languages.length > 0 && (
              <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-6">
                <h3 className="text-sm font-bold text-white uppercase tracking-wider">
                  Language Distribution
                </h3>

                {/* Progress bar */}
                <div className="mt-4 flex h-3 w-full overflow-hidden rounded-full bg-slate-800">
                  {details.languages.map((lang) => (
                    <div
                      key={lang.name}
                      style={{ width: `${lang.percentage}%` }}
                      className={`${LANGUAGE_COLORS[lang.name] || 'bg-slate-500'}`}
                      title={`${lang.name}: ${lang.percentage}% (${lang.line_count} lines)`}
                    />
                  ))}
                </div>

                {/* Legend */}
                <div className="mt-4 flex flex-wrap gap-3">
                  {details.languages.map((lang) => (
                    <div key={lang.name} className="flex items-center space-x-2 text-xs">
                      <span className={`h-2.5 w-2.5 rounded-full ${LANGUAGE_COLORS[lang.name] || 'bg-slate-500'}`} />
                      <span className="font-medium text-slate-300">{lang.name}</span>
                      <span className="font-mono text-slate-500">{lang.percentage}%</span>
                      <span className="text-slate-600">({lang.file_count} files)</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Manifests & Entry Points */}
            <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
              <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-6">
                <h3 className="text-sm font-bold text-white uppercase tracking-wider">
                  Identified Dependency Manifests
                </h3>
                <div className="mt-3 space-y-2">
                  {details?.manifest_files && details.manifest_files.length > 0 ? (
                    details.manifest_files.map((mf) => (
                      <div
                        key={mf}
                        onClick={() => {
                          setSelectedFilePath(mf);
                          setActiveTab('explorer');
                        }}
                        className="flex cursor-pointer items-center justify-between rounded-xl border border-slate-800 bg-slate-950/60 p-2.5 text-xs text-slate-300 hover:border-indigo-500/40 hover:text-indigo-300"
                      >
                        <span className="font-mono">{mf}</span>
                        <span className="rounded bg-indigo-500/10 px-2 py-0.5 text-[10px] text-indigo-400">
                          Inspect
                        </span>
                      </div>
                    ))
                  ) : (
                    <p className="text-xs text-slate-500">No standard manifests identified.</p>
                  )}
                </div>
              </div>

              <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-6">
                <h3 className="text-sm font-bold text-white uppercase tracking-wider">
                  Entry Point Candidates
                </h3>
                <div className="mt-3 space-y-2">
                  {details?.entry_points && details.entry_points.length > 0 ? (
                    details.entry_points.map((ep) => (
                      <div
                        key={ep}
                        onClick={() => {
                          setSelectedFilePath(ep);
                          setActiveTab('explorer');
                        }}
                        className="flex cursor-pointer items-center justify-between rounded-xl border border-slate-800 bg-slate-950/60 p-2.5 text-xs text-slate-300 hover:border-purple-500/40 hover:text-purple-300"
                      >
                        <span className="font-mono">{ep}</span>
                        <span className="rounded bg-purple-500/10 px-2 py-0.5 text-[10px] text-purple-400">
                          Inspect
                        </span>
                      </div>
                    ))
                  ) : (
                    <p className="text-xs text-slate-500">No standard entry points identified.</p>
                  )}
                </div>
              </div>
            </div>

            {/* Extracted README */}
            {details?.readme_content && (
              <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-6">
                <div className="flex items-center space-x-2 border-b border-slate-800 pb-3">
                  <FileText className="h-4 w-4 text-indigo-400" />
                  <h3 className="text-sm font-bold text-white uppercase tracking-wider">
                    Extracted Repository README
                  </h3>
                </div>
                <div className="mt-4 max-h-96 overflow-y-auto rounded-xl border border-slate-800 bg-slate-950/80 p-4 font-mono text-xs text-slate-300 leading-relaxed whitespace-pre-wrap">
                  {details.readme_content}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Code Explorer Tab */}
        {activeTab === 'explorer' && (
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
            {/* Left 4 Cols: Directory Tree */}
            <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-4 lg:col-span-4 max-h-[700px] overflow-y-auto">
              <div className="mb-3 flex items-center justify-between border-b border-slate-800/80 pb-2">
                <span className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
                  Directory Tree
                </span>
                <span className="text-[10px] text-slate-500 font-mono">
                  {details?.file_count || 0} Files
                </span>
              </div>
              <div className="divide-y divide-slate-800/30">
                {tree ? renderTreeNodes(tree.children) : <p className="text-xs text-slate-500">Loading directory tree...</p>}
              </div>
            </div>

            {/* Right 8 Cols: File Viewer */}
            <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-4 lg:col-span-8 flex flex-col min-h-[500px]">
              {selectedFilePath ? (
                <div>
                  <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                    <div>
                      <h4 className="font-mono text-sm font-bold text-white">
                        {selectedFilePath}
                      </h4>
                      <p className="text-xs text-slate-500">
                        {selectedFile?.language} • {selectedFile?.line_count} lines •{' '}
                        {selectedFile ? Math.round(selectedFile.size_bytes / 1024) : 0} KB
                      </p>
                    </div>
                    <span className="rounded bg-indigo-500/10 px-2 py-0.5 text-xs text-indigo-400 font-medium">
                      Sanitized Source
                    </span>
                  </div>

                  <div className="mt-4 max-h-[600px] overflow-y-auto rounded-xl border border-slate-800 bg-slate-950 p-4 font-mono text-xs text-slate-300">
                    {fileLoading ? (
                      <div className="flex items-center space-x-2 text-slate-400 py-12 justify-center">
                        <Loader2 className="h-4 w-4 animate-spin" />
                        <span>Loading file contents...</span>
                      </div>
                    ) : selectedFile ? (
                      <div className="table w-full">
                        {selectedFile.content.split('\n').map((line, idx) => (
                          <div key={idx} className="table-row hover:bg-slate-900/60">
                            <span className="table-cell select-none pr-4 text-right text-slate-600 font-mono text-[11px] w-12">
                              {idx + 1}
                            </span>
                            <span className="table-cell whitespace-pre font-mono text-slate-200">
                              {line || ' '}
                            </span>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-slate-500">Could not read file.</p>
                    )}
                  </div>
                </div>
              ) : (
                <div className="flex flex-1 flex-col items-center justify-center py-24 text-center">
                  <FileCode className="h-12 w-12 text-slate-700" />
                  <h4 className="mt-3 text-sm font-bold text-white">No File Selected</h4>
                  <p className="mt-1 text-xs text-slate-500 max-w-xs">
                    Click any file in the directory tree on the left to inspect its sanitized syntax and line numbering.
                  </p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Chat Tab Preview */}
        {activeTab === 'chat' && (
          <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-8 text-center">
            <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
              <Sparkles className="h-7 w-7" />
            </div>
            <h3 className="mt-4 text-xl font-bold text-white">Grounded RAG Chat Engine</h3>
            <p className="mx-auto mt-2 max-w-lg text-sm text-slate-400">
              Repository ingestion and file filtering are complete. The next phases will parse AST syntax nodes via Tree-sitter, vectorize into ChromaDB, construct the NetworkX Knowledge Graph, and activate grounded chat with clickable line citations.
            </p>

            <div className="mt-8 mx-auto max-w-xl text-left rounded-xl border border-slate-800 bg-slate-950/60 p-4">
              <span className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
                Ready for Phase 3:
              </span>
              <ul className="mt-2 space-y-1.5 text-xs text-slate-400">
                <li>• Parse functions, classes & methods via Tree-sitter</li>
                <li>• Extract static call relationships & inheritance</li>
                <li>• Generate dense MiniLM embeddings</li>
              </ul>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
