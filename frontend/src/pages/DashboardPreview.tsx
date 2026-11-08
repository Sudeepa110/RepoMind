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
  Search,
  Database,
  Code2,
  RefreshCw,
  Filter,
  Network,
  Share2,
  Waypoints,
  Activity,
  ArrowUpRight,
  Zap,
} from 'lucide-react';
import { api } from '../services/api';
import type {
  ValidationResult,
  RepositoryDetail,
  IndexingStatus,
  TreeNode,
  FileContent,
  SearchChunkResult,
  VectorIndexStatus,
  GraphStatus,
  GraphNodeItem,
  CallersResponse,
  CalleesResponse,
  ImpactAnalysisResponse,
  SubgraphResponse,
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

const EXAMPLE_QUERIES = [
  'authentication and password verification',
  'database connection and session management',
  'HTTP API routing and request handlers',
  'configuration loading and environment settings',
  'error handling and exception responses',
];

export const DashboardPreview: React.FC<DashboardPreviewProps> = ({
  repoUrl,
  validation,
  onBack,
}) => {
  const [activeTab, setActiveTab] = useState<'overview' | 'explorer' | 'search' | 'graph' | 'chat'>('overview');
  const [status, setStatus] = useState<IndexingStatus | null>(null);
  const [details, setDetails] = useState<RepositoryDetail | null>(null);
  const [tree, setTree] = useState<TreeNode | null>(null);
  const [selectedFilePath, setSelectedFilePath] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<FileContent | null>(null);
  const [fileLoading, setFileLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Search state
  const [searchQuery, setSearchQuery] = useState('');
  const [searchTopK, setSearchTopK] = useState(5);
  const [searchLangFilter, setSearchLangFilter] = useState('');
  const [searchTypeFilter, setSearchTypeFilter] = useState('');
  const [searchResults, setSearchResults] = useState<SearchChunkResult[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchExecuted, setSearchExecuted] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [vectorStats, setVectorStats] = useState<VectorIndexStatus | null>(null);
  const [reindexing, setReindexing] = useState(false);

  // Knowledge Graph State
  const [graphStatus, setGraphStatus] = useState<GraphStatus | null>(null);
  const [graphLoading, setGraphLoading] = useState(false);
  const [graphError, setGraphError] = useState<string | null>(null);
  const [graphViewMode, setGraphViewMode] = useState<'subgraph' | 'hierarchy' | 'impact' | 'nodes'>('subgraph');
  const [graphSearchQuery, setGraphSearchQuery] = useState('');
  const [selectedGraphNode, setSelectedGraphNode] = useState<GraphNodeItem | null>(null);
  const [subgraphData, setSubgraphData] = useState<SubgraphResponse | null>(null);
  const [callersData, setCallersData] = useState<CallersResponse | null>(null);
  const [calleesData, setCalleesData] = useState<CalleesResponse | null>(null);
  const [impactData, setImpactData] = useState<ImpactAnalysisResponse | null>(null);
  const [graphNodesList, setGraphNodesList] = useState<GraphNodeItem[]>([]);
  const [graphNodeTypeFilter, setGraphNodeTypeFilter] = useState('');
  const [hierarchySymbol, setHierarchySymbol] = useState('');
  const [impactTarget, setImpactTarget] = useState('');

  // Initialize analysis on load
  useEffect(() => {
    let isMounted = true;
    let pollInterval: any = null;

    const startAnalysis = async () => {
      try {
        const initRes = await api.analyzeRepository(repoUrl);
        const repoId = initRes.repository_id;

        const checkStatus = async () => {
          try {
            const st = await api.getRepositoryStatus(repoId);
            if (!isMounted) return;
            setStatus(st);

            if (st.status === 'completed') {
              clearInterval(pollInterval);
              const [det, tr, vs] = await Promise.all([
                api.getRepositoryDetails(repoId),
                api.getRepositoryTree(repoId),
                api.getVectorIndexStatus(repoId).catch(() => null),
              ]);
              if (isMounted) {
                setDetails(det);
                setTree(tr);
                if (vs) setVectorStats(vs);
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

  // Fetch vector store stats when switching to search tab
  useEffect(() => {
    if (activeTab === 'search' && details?.id) {
      api.getVectorIndexStatus(details.id)
        .then(setVectorStats)
        .catch((e) => console.debug('Could not load vector stats:', e));
    }
  }, [activeTab, details]);

  // Execute Semantic Code Search
  const handleSearch = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!searchQuery.trim() || !details?.id) return;

    setSearchLoading(true);
    setSearchError(null);
    setSearchExecuted(true);

    try {
      const res = await api.searchRepository(details.id, {
        query: searchQuery.trim(),
        top_k: searchTopK,
        language: searchLangFilter || undefined,
        symbol_type: searchTypeFilter || undefined,
      });
      setSearchResults(res.results);
    } catch (err: any) {
      console.error('Search failed:', err);
      setSearchError(err.response?.data?.detail || err.message || 'Failed to execute semantic search.');
      setSearchResults([]);
    } finally {
      setSearchLoading(false);
    }
  };

  // Trigger manual vector re-indexing
  const handleReindex = async () => {
    if (!details?.id || reindexing) return;
    setReindexing(true);
    try {
      await api.triggerReindex(details.id, true);
      // Refresh status after trigger
      const st = await api.getRepositoryStatus(details.id);
      setStatus(st);
      const vs = await api.getVectorIndexStatus(details.id);
      setVectorStats(vs);
    } catch (err: any) {
      console.error('Re-index failed:', err);
    } finally {
      setReindexing(false);
    }
  };

  // Fetch Knowledge Graph data when switching to graph tab
  const loadGraphData = async (repoId: string, query?: string) => {
    setGraphLoading(true);
    setGraphError(null);
    try {
      const [st, nodesRes] = await Promise.all([
        api.getGraphStatus(repoId),
        api.getGraphNodes(repoId, { query, limit: 100 }),
      ]);
      setGraphStatus(st);
      setGraphNodesList(nodesRes.nodes);

      // Select candidate node for ego subgraph view
      const candidate =
        nodesRes.nodes.find((n) => n.type === 'Function' || n.type === 'Method' || n.type === 'Class') ||
        nodesRes.nodes.find((n) => n.type === 'File') ||
        nodesRes.nodes[0];

      if (candidate) {
        setSelectedGraphNode(candidate);
        setHierarchySymbol(candidate.name);
        setImpactTarget(candidate.name);
        try {
          const sub = await api.getSubgraph(repoId, candidate.id, 1, 35);
          setSubgraphData(sub);
        } catch (e) {
          console.debug('Subgraph error:', e);
        }
      }
    } catch (err: any) {
      console.error('Error loading graph data:', err);
      setGraphError(err.response?.data?.detail || err.message || 'Failed to load repository knowledge graph.');
    } finally {
      setGraphLoading(false);
    }
  };

  useEffect(() => {
    if (activeTab === 'graph' && details?.id) {
      loadGraphData(details.id);
    }
  }, [activeTab, details]);

  const handleSelectNode = async (node: GraphNodeItem) => {
    setSelectedGraphNode(node);
    setHierarchySymbol(node.name);
    setImpactTarget(node.name);
    if (!details?.id) return;
    try {
      const sub = await api.getSubgraph(details.id, node.id, 1, 35);
      setSubgraphData(sub);
    } catch (err) {
      console.debug('Error fetching subgraph:', err);
    }
  };

  const handleQueryCallersCallees = async (symbol: string) => {
    if (!details?.id || !symbol.trim()) return;
    setGraphLoading(true);
    try {
      const [callers, callees] = await Promise.all([
        api.getCallers(details.id, symbol.trim()),
        api.getCallees(details.id, symbol.trim()),
      ]);
      setCallersData(callers);
      setCalleesData(callees);
    } catch (err: any) {
      console.error('Error querying callers/callees:', err);
    } finally {
      setGraphLoading(false);
    }
  };

  const handleQueryImpact = async (target: string) => {
    if (!details?.id || !target.trim()) return;
    setGraphLoading(true);
    try {
      const imp = await api.getImpactAnalysis(details.id, target.trim(), 2);
      setImpactData(imp);
    } catch (err: any) {
      console.error('Error querying impact analysis:', err);
    } finally {
      setGraphLoading(false);
    }
  };

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
                <span>{status?.current_stage || 'Cloning and vector indexing repository...'}</span>
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
              <p className="font-semibold text-rose-200">Repository Processing Error</p>
              <p className="mt-0.5 text-rose-300/90">{error}</p>
            </div>
          </div>
        )}

        {/* Ingestion & Vector Pipeline Stages Status */}
        <div className="mt-6 border-t border-slate-800/80 pt-6">
          <div className="mb-2 flex items-center justify-between text-xs">
            <span className="font-semibold text-slate-300 uppercase tracking-wider">
              Architecture Pipeline (Phases 1-4)
            </span>
            <span className="text-indigo-400 font-mono">
              {isCompleted ? 'Phase 4: Structure-Aware Vector RAG Ready' : 'Processing Pipeline...'}
            </span>
          </div>

          <div className="grid grid-cols-2 gap-3 sm:grid-cols-6">
            <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/5 p-2.5">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-semibold text-emerald-400">1. URL Check</span>
                <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
              </div>
              <p className="mt-1 text-[10px] text-slate-400">Validated</p>
            </div>

            <div className={`rounded-xl border p-2.5 ${isCompleted ? 'border-emerald-500/30 bg-emerald-500/5' : 'border-indigo-500/30 bg-indigo-500/5'}`}>
              <div className="flex items-center justify-between">
                <span className={`text-[11px] font-semibold ${isCompleted ? 'text-emerald-400' : 'text-indigo-300'}`}>
                  2. Clone
                </span>
                {isCompleted ? <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" /> : <Loader2 className="h-3.5 w-3.5 animate-spin text-indigo-400" />}
              </div>
              <p className="mt-1 text-[10px] text-slate-400">
                {isCompleted ? 'Shallow (depth=1)' : 'Cloning'}
              </p>
            </div>

            <div className={`rounded-xl border p-2.5 ${isCompleted ? 'border-emerald-500/30 bg-emerald-500/5' : 'border-slate-800 bg-slate-900/40'}`}>
              <div className="flex items-center justify-between">
                <span className={`text-[11px] font-semibold ${isCompleted ? 'text-emerald-400' : 'text-slate-300'}`}>
                  3. Filter
                </span>
                {isCompleted ? <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" /> : <Clock className="h-3.5 w-3.5 text-slate-500" />}
              </div>
              <p className="mt-1 text-[10px] text-slate-400">
                {isCompleted ? 'Cleaned' : 'Pending'}
              </p>
            </div>

            <div className={`rounded-xl border p-2.5 ${isCompleted ? 'border-emerald-500/30 bg-emerald-500/5' : 'border-slate-800 bg-slate-900/40'}`}>
              <div className="flex items-center justify-between">
                <span className={`text-[11px] font-semibold ${isCompleted ? 'text-emerald-400' : 'text-slate-300'}`}>
                  4. Tree-sitter
                </span>
                {isCompleted ? <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" /> : <Clock className="h-3.5 w-3.5 text-slate-500" />}
              </div>
              <p className="mt-1 text-[10px] text-slate-400">
                {isCompleted ? 'AST Symbols' : 'Pending'}
              </p>
            </div>

            <div className={`rounded-xl border p-2.5 ${isCompleted ? 'border-emerald-500/30 bg-emerald-500/5' : 'border-slate-800 bg-slate-900/40'}`}>
              <div className="flex items-center justify-between">
                <span className={`text-[11px] font-semibold ${isCompleted ? 'text-emerald-400' : 'text-slate-300'}`}>
                  5. Chunking
                </span>
                {isCompleted ? <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" /> : <Clock className="h-3.5 w-3.5 text-slate-500" />}
              </div>
              <p className="mt-1 text-[10px] text-slate-400">
                {isCompleted ? 'Structure-Aware' : 'Pending'}
              </p>
            </div>

            <div className={`rounded-xl border p-2.5 ${isCompleted ? 'border-emerald-500/30 bg-emerald-500/5' : 'border-slate-800 bg-slate-900/40'}`}>
              <div className="flex items-center justify-between">
                <span className={`text-[11px] font-semibold ${isCompleted ? 'text-emerald-400' : 'text-slate-300'}`}>
                  6. ChromaDB
                </span>
                {isCompleted ? <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" /> : <Clock className="h-3.5 w-3.5 text-slate-500" />}
              </div>
              <p className="mt-1 text-[10px] text-slate-400">
                {vectorStats ? `${vectorStats.total_chunks} Chunks` : 'Vector RAG'}
              </p>
            </div>

            <div className={`rounded-xl border p-2.5 ${isCompleted ? 'border-emerald-500/30 bg-emerald-500/5' : 'border-slate-800 bg-slate-900/40'}`}>
              <div className="flex items-center justify-between">
                <span className={`text-[11px] font-semibold ${isCompleted ? 'text-emerald-400' : 'text-slate-300'}`}>
                  7. NetworkX
                </span>
                {isCompleted ? <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" /> : <Clock className="h-3.5 w-3.5 text-slate-500" />}
              </div>
              <p className="mt-1 text-[10px] text-slate-400">
                {graphStatus ? `${graphStatus.total_nodes} Nodes` : 'GraphRAG'}
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
          onClick={() => setActiveTab('search')}
          className={`flex items-center space-x-2 border-b-2 px-3 py-2.5 text-sm font-medium transition-colors ${
            activeTab === 'search'
              ? 'border-indigo-500 text-indigo-400'
              : 'border-transparent text-slate-400 hover:text-white'
          }`}
        >
          <Search className="h-4 w-4" />
          <span>Semantic Vector Search</span>
          {vectorStats && vectorStats.total_chunks > 0 && (
            <span className="rounded-full bg-indigo-500/20 px-2 py-0.5 text-[10px] font-mono text-indigo-300">
              {vectorStats.total_chunks}
            </span>
          )}
        </button>

        <button
          onClick={() => setActiveTab('graph')}
          className={`flex items-center space-x-2 border-b-2 px-3 py-2.5 text-sm font-medium transition-colors ${
            activeTab === 'graph'
              ? 'border-indigo-500 text-indigo-400'
              : 'border-transparent text-slate-400 hover:text-white'
          }`}
        >
          <Network className="h-4 w-4" />
          <span>Knowledge Graph</span>
          {graphStatus && graphStatus.total_nodes > 0 && (
            <span className="rounded-full bg-purple-500/20 px-2 py-0.5 text-[10px] font-mono text-purple-300">
              {graphStatus.total_nodes}
            </span>
          )}
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
        {/* OVERVIEW TAB */}
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
                <span className="text-[11px] text-slate-500 uppercase tracking-wider font-semibold">Vector Chunks</span>
                <p className="mt-1 text-2xl font-bold text-emerald-400">{vectorStats?.total_chunks || 0}</p>
                <span className="text-[11px] text-slate-400">Indexed in ChromaDB</span>
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

                <div className="mt-4 flex flex-wrap gap-3">
                  {details.languages.map((lang) => (
                    <div key={lang.name} className="flex items-center space-x-2 text-xs">
                      <span className={`h-2.5 w-2.5 rounded-full ${LANGUAGE_COLORS[lang.name] || 'bg-slate-500'}`} />
                      <span className="text-slate-300 font-medium">{lang.name}</span>
                      <span className="text-slate-500 font-mono">({lang.percentage}%)</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

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

        {/* CODE EXPLORER TAB */}
        {activeTab === 'explorer' && (
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
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

        {/* SEMANTIC VECTOR SEARCH TAB (PHASE 4) */}
        {activeTab === 'search' && (
          <div className="space-y-6">
            {/* Search Input Bar & Filter Bar */}
            <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6 backdrop-blur-md">
              <form onSubmit={handleSearch} className="space-y-4">
                <div className="relative flex items-center">
                  <Search className="absolute left-4 h-5 w-5 text-slate-400" />
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Search code semantics (e.g. 'JWT token verification' or 'database session pool')..."
                    className="w-full rounded-xl border border-slate-700 bg-slate-950/80 py-3.5 pl-12 pr-28 text-sm text-white placeholder-slate-500 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                  />
                  <button
                    type="submit"
                    disabled={searchLoading || !searchQuery.trim()}
                    className="absolute right-2 flex items-center space-x-1.5 rounded-lg bg-indigo-600 px-4 py-2 text-xs font-semibold text-white transition-colors hover:bg-indigo-500 disabled:opacity-50"
                  >
                    {searchLoading ? (
                      <>
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        <span>Searching...</span>
                      </>
                    ) : (
                      <span>Search</span>
                    )}
                  </button>
                </div>

                {/* Filters Row */}
                <div className="flex flex-wrap items-center gap-3 text-xs">
                  <div className="flex items-center space-x-1.5 text-slate-400">
                    <Filter className="h-3.5 w-3.5 text-indigo-400" />
                    <span>Filters:</span>
                  </div>

                  {/* Language filter */}
                  <select
                    value={searchLangFilter}
                    onChange={(e) => setSearchLangFilter(e.target.value)}
                    className="rounded-lg border border-slate-800 bg-slate-950 px-2.5 py-1.5 text-slate-300 focus:border-indigo-500 focus:outline-none"
                  >
                    <option value="">All Languages</option>
                    {details?.languages.map((l) => (
                      <option key={l.name} value={l.name}>{l.name}</option>
                    ))}
                  </select>

                  {/* Symbol Type filter */}
                  <select
                    value={searchTypeFilter}
                    onChange={(e) => setSearchTypeFilter(e.target.value)}
                    className="rounded-lg border border-slate-800 bg-slate-950 px-2.5 py-1.5 text-slate-300 focus:border-indigo-500 focus:outline-none"
                  >
                    <option value="">All Symbol Types</option>
                    <option value="FUNCTION">Functions</option>
                    <option value="METHOD">Methods</option>
                    <option value="CLASS">Classes</option>
                    <option value="INTERFACE">Interfaces</option>
                    <option value="DOC">Documentation</option>
                    <option value="CONFIG">Configuration</option>
                  </select>

                  {/* Top K selector */}
                  <div className="flex items-center space-x-1.5">
                    <span className="text-slate-500">Top Results:</span>
                    <select
                      value={searchTopK}
                      onChange={(e) => setSearchTopK(Number(e.target.value))}
                      className="rounded-lg border border-slate-800 bg-slate-950 px-2.5 py-1.5 text-slate-300 focus:border-indigo-500 focus:outline-none"
                    >
                      <option value={3}>3</option>
                      <option value={5}>5</option>
                      <option value={10}>10</option>
                      <option value={20}>20</option>
                    </select>
                  </div>
                </div>

                {/* Example Quick-Pick Queries */}
                <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-slate-800/60">
                  <span className="text-[11px] text-slate-500">Try searching:</span>
                  {EXAMPLE_QUERIES.map((q) => (
                    <button
                      key={q}
                      type="button"
                      onClick={() => {
                        setSearchQuery(q);
                      }}
                      className="rounded-full border border-slate-800 bg-slate-950/60 px-2.5 py-1 text-[11px] text-slate-400 hover:border-indigo-500/40 hover:text-indigo-300"
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </form>
            </div>

            {/* ChromaDB Vector Store Diagnostic Card */}
            {vectorStats && (
              <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 rounded-xl border border-slate-800 bg-slate-900/40 p-4 text-xs">
                <div className="flex items-center space-x-3">
                  <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                    <Database className="h-4 w-4" />
                  </div>
                  <div>
                    <div className="flex items-center space-x-2">
                      <span className="font-semibold text-white">ChromaDB Persistent Collection:</span>
                      <span className="font-mono text-indigo-300">{vectorStats.collection_name}</span>
                    </div>
                    <p className="text-slate-400 mt-0.5">
                      {vectorStats.total_chunks} structure-aware chunks indexed • Model: sentence-transformers/all-MiniLM-L6-v2 (384-dim)
                    </p>
                  </div>
                </div>

                <button
                  type="button"
                  onClick={handleReindex}
                  disabled={reindexing}
                  className="flex items-center space-x-1.5 rounded-lg border border-slate-700 bg-slate-800/80 px-3 py-1.5 text-xs text-slate-300 hover:bg-slate-700 hover:text-white transition-colors disabled:opacity-50"
                >
                  <RefreshCw className={`h-3.5 w-3.5 ${reindexing ? 'animate-spin' : ''}`} />
                  <span>{reindexing ? 'Re-indexing...' : 'Re-index Vectors'}</span>
                </button>
              </div>
            )}

            {/* Search Results Section */}
            {searchLoading && (
              <div className="flex flex-col items-center justify-center py-16 text-center text-slate-400">
                <Loader2 className="h-8 w-8 animate-spin text-indigo-400" />
                <p className="mt-3 text-sm font-semibold text-white">Generating Dense Vector Embeddings...</p>
                <p className="mt-1 text-xs text-slate-500">Querying ChromaDB cosine similarity index</p>
              </div>
            )}

            {searchError && (
              <div className="flex items-center space-x-3 rounded-xl border border-rose-500/30 bg-rose-500/10 p-4 text-xs text-rose-300">
                <AlertTriangle className="h-5 w-5 shrink-0 text-rose-400" />
                <p>{searchError}</p>
              </div>
            )}

            {!searchLoading && searchExecuted && searchResults.length === 0 && !searchError && (
              <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-12 text-center text-slate-400">
                <Code2 className="mx-auto h-10 w-10 text-slate-600" />
                <h4 className="mt-3 text-sm font-bold text-white">No Matching Code Chunks</h4>
                <p className="mt-1 text-xs text-slate-500">
                  Try broadening your search query or removing language/symbol filters.
                </p>
              </div>
            )}

            {!searchLoading && searchResults.length > 0 && (
              <div className="space-y-4">
                <div className="flex items-center justify-between text-xs text-slate-400">
                  <span>Found {searchResults.length} relevant code chunks:</span>
                  <span className="font-mono text-[11px] text-slate-500">Ranked by Cosine Similarity</span>
                </div>

                {searchResults.map((res, idx) => {
                  const matchPct = Math.round(res.similarity_score * 100);
                  return (
                    <div
                      key={res.chunk_id || idx}
                      className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 transition-all hover:border-slate-700"
                    >
                      {/* Top Header of Result */}
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-800/80 pb-3">
                        <div className="flex items-center space-x-2">
                          <span className="flex h-6 w-6 items-center justify-center rounded-full bg-slate-800 font-mono text-xs font-bold text-indigo-400">
                            #{idx + 1}
                          </span>
                          <span className="font-mono text-xs font-semibold text-white">
                            {res.file_path}
                          </span>
                          <span className="font-mono text-[11px] text-indigo-400 bg-indigo-500/10 border border-indigo-500/20 px-2 py-0.5 rounded">
                            L{res.start_line}-L{res.end_line}
                          </span>
                        </div>

                        <div className="flex items-center space-x-2">
                          {res.symbol_type && (
                            <span className="rounded bg-purple-500/10 border border-purple-500/20 px-2 py-0.5 text-[10px] font-semibold text-purple-300">
                              {res.symbol_type}
                            </span>
                          )}
                          <span className="rounded bg-slate-800 px-2 py-0.5 text-[10px] font-mono text-slate-400">
                            {res.language}
                          </span>
                          <div className="flex items-center space-x-1 rounded bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 text-[10px] font-semibold text-emerald-400">
                            <span>{matchPct}% match</span>
                          </div>
                        </div>
                      </div>

                      {/* Symbol signature or docstring if available */}
                      {(res.symbol_name || res.docstring) && (
                        <div className="mt-2.5 flex flex-wrap items-center gap-2 text-xs">
                          {res.symbol_name && (
                            <span className="font-mono text-xs text-indigo-300">
                              symbol: <span className="font-bold">{res.symbol_name}</span>
                            </span>
                          )}
                          {res.docstring && (
                            <span className="text-[11px] text-slate-400 truncate max-w-lg italic">
                              "{res.docstring}"
                            </span>
                          )}
                        </div>
                      )}

                      {/* Code Snippet Box with Syntax Table */}
                      <div className="mt-3 max-h-64 overflow-y-auto rounded-lg border border-slate-950 bg-slate-950/90 p-3 font-mono text-xs text-slate-200">
                        <div className="table w-full">
                          {res.source_code.split('\n').map((line, lIdx) => (
                            <div key={lIdx} className="table-row hover:bg-slate-900/50">
                              <span className="table-cell select-none pr-3 text-right text-slate-600 font-mono text-[10px] w-10">
                                {res.start_line + lIdx}
                              </span>
                              <span className="table-cell whitespace-pre font-mono text-slate-300 text-[11px]">
                                {line || ' '}
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>

                      {/* Action to view in explorer */}
                      <div className="mt-3 flex justify-end">
                        <button
                          type="button"
                          onClick={() => {
                            setSelectedFilePath(res.file_path);
                            setActiveTab('explorer');
                          }}
                          className="flex items-center space-x-1.5 text-xs text-indigo-400 hover:text-indigo-300 transition-colors"
                        >
                          <span>Open in Code Explorer</span>
                          <ExternalLink className="h-3 w-3" />
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* KNOWLEDGE GRAPH TAB */}
        {activeTab === 'graph' && (
          <div className="space-y-6">
            {/* Graph Diagnostic & Summary Bar */}
            <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div className="flex items-center space-x-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-purple-500/10 border border-purple-500/20 text-purple-400">
                    <Network className="h-5 w-5" />
                  </div>
                  <div>
                    <h3 className="text-base font-bold text-white">Repository Knowledge Graph</h3>
                    <p className="text-xs text-slate-400">
                      NetworkX directed graph representing code entities, containment, calls, and dependencies
                    </p>
                  </div>
                </div>

                {graphStatus && (
                  <div className="flex flex-wrap items-center gap-2 text-xs">
                    <div className="rounded-lg border border-slate-800 bg-slate-950/60 px-3 py-1.5 font-mono text-slate-300">
                      <span className="text-slate-500">Nodes: </span>
                      <span className="font-bold text-purple-400">{graphStatus.total_nodes}</span>
                    </div>
                    <div className="rounded-lg border border-slate-800 bg-slate-950/60 px-3 py-1.5 font-mono text-slate-300">
                      <span className="text-slate-500">Edges: </span>
                      <span className="font-bold text-indigo-400">{graphStatus.total_edges}</span>
                    </div>
                    <div className="rounded-lg border border-slate-800 bg-slate-950/60 px-3 py-1.5 font-mono text-slate-300">
                      <span className="text-slate-500">Density: </span>
                      <span className="font-bold text-emerald-400">{graphStatus.graph_density}</span>
                    </div>
                    <div className="rounded-lg border border-emerald-500/20 bg-emerald-500/10 px-3 py-1.5 font-mono text-[11px] text-emerald-400">
                      ✓ NetworkX Persisted
                    </div>
                  </div>
                )}
              </div>

              {/* Sub-view Navigation */}
              <div className="mt-5 flex flex-wrap border-t border-slate-800/80 pt-4 gap-2">
                <button
                  type="button"
                  onClick={() => setGraphViewMode('subgraph')}
                  className={`flex items-center space-x-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                    graphViewMode === 'subgraph'
                      ? 'bg-purple-600 text-white'
                      : 'bg-slate-800/60 text-slate-400 hover:bg-slate-800 hover:text-white'
                  }`}
                >
                  <Share2 className="h-3.5 w-3.5" />
                  <span>Ego Subgraph</span>
                </button>

                <button
                  type="button"
                  onClick={() => {
                    setGraphViewMode('hierarchy');
                    if (selectedGraphNode?.name) {
                      handleQueryCallersCallees(selectedGraphNode.name);
                    }
                  }}
                  className={`flex items-center space-x-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                    graphViewMode === 'hierarchy'
                      ? 'bg-purple-600 text-white'
                      : 'bg-slate-800/60 text-slate-400 hover:bg-slate-800 hover:text-white'
                  }`}
                >
                  <Waypoints className="h-3.5 w-3.5" />
                  <span>Call Hierarchy</span>
                </button>

                <button
                  type="button"
                  onClick={() => {
                    setGraphViewMode('impact');
                    if (selectedGraphNode?.name) {
                      handleQueryImpact(selectedGraphNode.name);
                    }
                  }}
                  className={`flex items-center space-x-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                    graphViewMode === 'impact'
                      ? 'bg-purple-600 text-white'
                      : 'bg-slate-800/60 text-slate-400 hover:bg-slate-800 hover:text-white'
                  }`}
                >
                  <Zap className="h-3.5 w-3.5" />
                  <span>Impact Analysis</span>
                </button>

                <button
                  type="button"
                  onClick={() => setGraphViewMode('nodes')}
                  className={`flex items-center space-x-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                    graphViewMode === 'nodes'
                      ? 'bg-purple-600 text-white'
                      : 'bg-slate-800/60 text-slate-400 hover:bg-slate-800 hover:text-white'
                  }`}
                >
                  <FolderTree className="h-3.5 w-3.5" />
                  <span>All Code Entities</span>
                </button>
              </div>
            </div>

            {/* Error or Loading Banner */}
            {graphLoading && (
              <div className="flex items-center justify-center py-12 text-center text-slate-400">
                <Loader2 className="h-7 w-7 animate-spin text-purple-400" />
                <span className="ml-3 text-sm text-slate-300">Querying Knowledge Graph...</span>
              </div>
            )}

            {graphError && (
              <div className="flex items-center space-x-3 rounded-xl border border-rose-500/30 bg-rose-500/10 p-4 text-xs text-rose-300">
                <AlertTriangle className="h-5 w-5 shrink-0 text-rose-400" />
                <p>{graphError}</p>
              </div>
            )}

            {/* SUB-VIEW 1: EGO SUBGRAPH VISUALIZER */}
            {graphViewMode === 'subgraph' && !graphLoading && (
              <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
                {/* Visual Canvas Area */}
                <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-4 lg:col-span-8">
                  <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                    <div className="flex items-center space-x-2">
                      <Activity className="h-4 w-4 text-purple-400" />
                      <span className="text-xs font-semibold text-white">Interactive Subgraph Canvas</span>
                    </div>
                    {subgraphData && (
                      <span className="font-mono text-[11px] text-slate-400">
                        {subgraphData.node_count} nodes, {subgraphData.edge_count} relationships
                      </span>
                    )}
                  </div>

                  {/* SVG Graph Canvas */}
                  <div className="relative mt-4 flex items-center justify-center overflow-hidden rounded-xl border border-slate-950 bg-slate-950/80 p-4 h-[420px]">
                    {subgraphData && subgraphData.nodes.length > 0 ? (
                      <svg className="h-full w-full" viewBox="0 0 800 450">
                        <defs>
                          <marker
                            id="arrowhead"
                            markerWidth="8"
                            markerHeight="6"
                            refX="7"
                            refY="3"
                            orient="auto"
                          >
                            <polygon points="0 0, 8 3, 0 6" fill="#818cf8" />
                          </marker>
                        </defs>

                        {/* Draw connection edges */}
                        {(() => {
                          const cx = 400;
                          const cy = 225;
                          const neighbors = subgraphData.nodes.filter(
                            (n) => n.id !== subgraphData.center_node_id
                          );
                          const total = neighbors.length;
                          const radius = 160;

                          return neighbors.map((node, idx) => {
                            const angle = (2 * Math.PI * idx) / (total || 1);
                            const nx = cx + radius * Math.cos(angle);
                            const ny = cy + radius * Math.sin(angle);

                            // Find relationship type
                            const edge = subgraphData.edges.find(
                              (e) =>
                                (e.source_id === subgraphData.center_node_id && e.target_id === node.id) ||
                                (e.target_id === subgraphData.center_node_id && e.source_id === node.id)
                            );
                            const rel = edge ? edge.relationship : 'RELATED';

                            return (
                              <g key={`edge-${node.id}`}>
                                <line
                                  x1={cx}
                                  y1={cy}
                                  x2={nx}
                                  y2={ny}
                                  stroke="#334155"
                                  strokeWidth="1.5"
                                  markerEnd="url(#arrowhead)"
                                />
                                <text
                                  x={(cx + nx) / 2}
                                  y={(cy + ny) / 2 - 4}
                                  fill="#94a3b8"
                                  fontSize="9"
                                  textAnchor="middle"
                                  fontFamily="monospace"
                                >
                                  {rel}
                                </text>
                              </g>
                            );
                          });
                        })()}

                        {/* Draw neighbor nodes */}
                        {(() => {
                          const cx = 400;
                          const cy = 225;
                          const neighbors = subgraphData.nodes.filter(
                            (n) => n.id !== subgraphData.center_node_id
                          );
                          const total = neighbors.length;
                          const radius = 160;

                          return neighbors.map((node, idx) => {
                            const angle = (2 * Math.PI * idx) / (total || 1);
                            const nx = cx + radius * Math.cos(angle);
                            const ny = cy + radius * Math.sin(angle);

                            let nodeColor = '#3b82f6';
                            if (node.type === 'Class') nodeColor = '#10b981';
                            if (node.type === 'Function' || node.type === 'Method') nodeColor = '#f59e0b';
                            if (node.type === 'Interface') nodeColor = '#06b6d4';
                            if (node.type === 'Repository') nodeColor = '#a855f7';

                            return (
                              <g
                                key={`node-${node.id}`}
                                className="cursor-pointer transition-transform hover:scale-110"
                                onClick={() => handleSelectNode(node)}
                              >
                                <circle cx={nx} cy={ny} r="18" fill="#1e293b" stroke={nodeColor} strokeWidth="2" />
                                <text
                                  x={nx}
                                  y={ny + 28}
                                  fill="#cbd5e1"
                                  fontSize="10"
                                  textAnchor="middle"
                                  fontFamily="monospace"
                                  className="font-medium"
                                >
                                  {node.name.length > 14 ? node.name.substring(0, 12) + '..' : node.name}
                                </text>
                                <text
                                  x={nx}
                                  y={ny + 38}
                                  fill="#64748b"
                                  fontSize="8"
                                  textAnchor="middle"
                                >
                                  {node.type}
                                </text>
                              </g>
                            );
                          });
                        })()}

                        {/* Center focus node */}
                        {(() => {
                          const centerNode = subgraphData.nodes.find(
                            (n) => n.id === subgraphData.center_node_id
                          );
                          return (
                            <g className="cursor-default">
                              <circle cx="400" cy="225" r="28" fill="#581c87" stroke="#c084fc" strokeWidth="3" />
                              <circle cx="400" cy="225" r="34" fill="none" stroke="#c084fc" strokeWidth="1" strokeDasharray="3 3" />
                              <text
                                x="400"
                                y="230"
                                fill="#ffffff"
                                fontSize="11"
                                textAnchor="middle"
                                fontWeight="bold"
                                fontFamily="monospace"
                              >
                                {centerNode ? centerNode.name.substring(0, 10) : 'Center'}
                              </text>
                              <text
                                x="400"
                                y="272"
                                fill="#e9d5ff"
                                fontSize="10"
                                textAnchor="middle"
                                fontWeight="bold"
                              >
                                {centerNode?.type || 'Focus'}
                              </text>
                            </g>
                          );
                        })()}
                      </svg>
                    ) : (
                      <div className="text-center text-slate-500">
                        <Share2 className="mx-auto h-8 w-8 text-slate-600" />
                        <p className="mt-2 text-xs">No graph nodes selected. Choose an entity from the list.</p>
                      </div>
                    )}
                  </div>

                  {/* Quick Select Chips */}
                  <div className="mt-3">
                    <span className="text-[11px] font-semibold text-slate-400">Quick Focus Entity:</span>
                    <div className="mt-1.5 flex flex-wrap gap-1.5 max-h-24 overflow-y-auto">
                      {graphNodesList.slice(0, 15).map((node) => (
                        <button
                          key={node.id}
                          type="button"
                          onClick={() => handleSelectNode(node)}
                          className={`rounded-md px-2 py-1 text-[11px] font-mono transition-colors ${
                            selectedGraphNode?.id === node.id
                              ? 'bg-purple-600 text-white'
                              : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
                          }`}
                        >
                          {node.name} ({node.type})
                        </button>
                      ))}
                    </div>
                  </div>
                </div>

                {/* Node Inspector Drawer */}
                <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-5 lg:col-span-4 space-y-4">
                  <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                    <span className="text-xs font-semibold text-white">Entity Inspector</span>
                    {selectedGraphNode && (
                      <span className="rounded bg-purple-500/10 border border-purple-500/20 px-2 py-0.5 text-[10px] font-bold text-purple-300">
                        {selectedGraphNode.type}
                      </span>
                    )}
                  </div>

                  {selectedGraphNode ? (
                    <div className="space-y-3.5 text-xs">
                      <div>
                        <span className="text-[10px] uppercase font-bold text-slate-500 tracking-wider">
                          Name & Identifier
                        </span>
                        <p className="mt-1 font-mono text-sm font-bold text-white break-all">
                          {selectedGraphNode.name}
                        </p>
                        <p className="font-mono text-[10px] text-slate-500 break-all">
                          {selectedGraphNode.id}
                        </p>
                      </div>

                      {selectedGraphNode.file_path && (
                        <div>
                          <span className="text-[10px] uppercase font-bold text-slate-500 tracking-wider">
                            Source Location
                          </span>
                          <p className="mt-1 font-mono text-slate-300">
                            {selectedGraphNode.file_path}
                          </p>
                          {selectedGraphNode.start_line && (
                            <span className="inline-block mt-1 rounded bg-slate-800 px-2 py-0.5 font-mono text-[10px] text-indigo-300">
                              Lines {selectedGraphNode.start_line} - {selectedGraphNode.end_line}
                            </span>
                          )}
                        </div>
                      )}

                      {selectedGraphNode.properties?.signature && (
                        <div>
                          <span className="text-[10px] uppercase font-bold text-slate-500 tracking-wider">
                            Signature
                          </span>
                          <div className="mt-1 rounded bg-slate-950 p-2 font-mono text-[11px] text-amber-300">
                            {selectedGraphNode.properties.signature}
                          </div>
                        </div>
                      )}

                      {selectedGraphNode.properties?.docstring && (
                        <div>
                          <span className="text-[10px] uppercase font-bold text-slate-500 tracking-wider">
                            Docstring
                          </span>
                          <p className="mt-1 rounded bg-slate-950/70 p-2 text-slate-300 italic text-[11px]">
                            "{selectedGraphNode.properties.docstring}"
                          </p>
                        </div>
                      )}

                      {/* Action buttons */}
                      <div className="border-t border-slate-800 pt-3 flex flex-col gap-2">
                        {selectedGraphNode.file_path && (
                          <button
                            type="button"
                            onClick={() => {
                              if (selectedGraphNode.file_path) {
                                setSelectedFilePath(selectedGraphNode.file_path);
                                setActiveTab('explorer');
                              }
                            }}
                            className="flex items-center justify-center space-x-1.5 rounded-lg bg-indigo-600/20 border border-indigo-500/30 px-3 py-2 text-xs font-medium text-indigo-300 hover:bg-indigo-600/30 transition-colors"
                          >
                            <span>Open in Code Explorer</span>
                            <ExternalLink className="h-3 w-3" />
                          </button>
                        )}

                        <button
                          type="button"
                          onClick={() => {
                            setGraphViewMode('hierarchy');
                            handleQueryCallersCallees(selectedGraphNode.name);
                          }}
                          className="flex items-center justify-center space-x-1.5 rounded-lg bg-slate-800 px-3 py-2 text-xs font-medium text-slate-300 hover:bg-slate-700 transition-colors"
                        >
                          <Waypoints className="h-3 w-3" />
                          <span>View Call Hierarchy</span>
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="py-8 text-center text-slate-500 text-xs">
                      Select a node in the graph to view properties and relationships.
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* SUB-VIEW 2: CALL HIERARCHY (CALLERS & CALLEES) */}
            {graphViewMode === 'hierarchy' && !graphLoading && (
              <div className="space-y-6">
                {/* Search Bar for Call Hierarchy */}
                <div className="flex flex-col sm:flex-row items-center gap-3 rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
                  <div className="relative flex-1 w-full">
                    <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
                    <input
                      type="text"
                      placeholder="Enter function or method name (e.g. authenticate, verify_password)..."
                      value={hierarchySymbol}
                      onChange={(e) => setHierarchySymbol(e.target.value)}
                      onKeyDown={(e) => e.key === 'Enter' && handleQueryCallersCallees(hierarchySymbol)}
                      className="w-full rounded-xl border border-slate-800 bg-slate-950 py-2 pl-9 pr-3 text-xs text-white placeholder-slate-500 focus:border-purple-500 focus:outline-none"
                    />
                  </div>
                  <button
                    type="button"
                    onClick={() => handleQueryCallersCallees(hierarchySymbol)}
                    className="w-full sm:w-auto rounded-xl bg-purple-600 px-4 py-2 text-xs font-semibold text-white hover:bg-purple-500 transition-colors"
                  >
                    Analyze Hierarchy
                  </button>
                </div>

                {/* Two Column Callers & Callees Grid */}
                <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
                  {/* Incoming Callers */}
                  <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-5 space-y-4">
                    <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                      <div className="flex items-center space-x-2">
                        <ArrowUpRight className="h-4 w-4 text-emerald-400" />
                        <span className="text-xs font-bold text-white">Incoming Callers (Who calls this?)</span>
                      </div>
                      {callersData && (
                        <span className="rounded-full bg-emerald-500/20 px-2 py-0.5 text-[10px] font-mono font-bold text-emerald-300">
                          {callersData.total_callers}
                        </span>
                      )}
                    </div>

                    {callersData && callersData.callers.length > 0 ? (
                      <div className="space-y-2.5 max-h-[420px] overflow-y-auto">
                        {callersData.callers.map((c, i) => (
                          <div key={i} className="rounded-xl border border-slate-800 bg-slate-950/60 p-3 text-xs">
                            <div className="flex items-center justify-between">
                              <span className="font-mono font-bold text-purple-300">{c.caller_name}</span>
                              <span className="rounded bg-slate-800 px-2 py-0.5 font-mono text-[10px] text-slate-400">
                                {c.call_count} call{c.call_count > 1 ? 's' : ''}
                              </span>
                            </div>
                            <div className="mt-1 flex items-center justify-between text-[11px] text-slate-400">
                              <span className="font-mono">{c.file_path}</span>
                              {c.start_line && (
                                <span className="text-indigo-400">Line {c.start_line}</span>
                              )}
                            </div>
                            {c.invocation_lines.length > 0 && (
                              <p className="mt-1 text-[10px] text-slate-500 font-mono">
                                Invocations at line(s): {c.invocation_lines.join(', ')}
                              </p>
                            )}
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="py-8 text-center text-slate-500 text-xs">
                        No incoming callers found for this symbol.
                      </div>
                    )}
                  </div>

                  {/* Outgoing Callees */}
                  <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-5 space-y-4">
                    <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                      <div className="flex items-center space-x-2">
                        <Waypoints className="h-4 w-4 text-indigo-400" />
                        <span className="text-xs font-bold text-white">Outgoing Callees (What does this call?)</span>
                      </div>
                      {calleesData && (
                        <span className="rounded-full bg-indigo-500/20 px-2 py-0.5 text-[10px] font-mono font-bold text-indigo-300">
                          {calleesData.total_callees}
                        </span>
                      )}
                    </div>

                    {calleesData && calleesData.callees.length > 0 ? (
                      <div className="space-y-2.5 max-h-[420px] overflow-y-auto">
                        {calleesData.callees.map((c, i) => (
                          <div key={i} className="rounded-xl border border-slate-800 bg-slate-950/60 p-3 text-xs">
                            <div className="flex items-center justify-between">
                              <span className="font-mono font-bold text-indigo-300">{c.callee_name}</span>
                              <span className="rounded bg-indigo-500/10 border border-indigo-500/20 px-2 py-0.5 text-[10px] text-indigo-300">
                                {Math.round(c.confidence * 100)}% conf
                              </span>
                            </div>
                            {c.file_path && (
                              <div className="mt-1 flex items-center justify-between text-[11px] text-slate-400">
                                <span className="font-mono">{c.file_path}</span>
                                {c.start_line && <span className="text-indigo-400">Line {c.start_line}</span>}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="py-8 text-center text-slate-500 text-xs">
                        No outgoing callees found for this symbol.
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* SUB-VIEW 3: IMPACT ANALYSIS (BLAST RADIUS) */}
            {graphViewMode === 'impact' && !graphLoading && (
              <div className="space-y-6">
                <div className="flex flex-col sm:flex-row items-center gap-3 rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
                  <div className="relative flex-1 w-full">
                    <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
                    <input
                      type="text"
                      placeholder="Enter symbol or file to assess modification blast radius..."
                      value={impactTarget}
                      onChange={(e) => setImpactTarget(e.target.value)}
                      onKeyDown={(e) => e.key === 'Enter' && handleQueryImpact(impactTarget)}
                      className="w-full rounded-xl border border-slate-800 bg-slate-950 py-2 pl-9 pr-3 text-xs text-white placeholder-slate-500 focus:border-purple-500 focus:outline-none"
                    />
                  </div>
                  <button
                    type="button"
                    onClick={() => handleQueryImpact(impactTarget)}
                    className="w-full sm:w-auto rounded-xl bg-purple-600 px-4 py-2 text-xs font-semibold text-white hover:bg-purple-500 transition-colors"
                  >
                    Calculate Blast Radius
                  </button>
                </div>

                {impactData && (
                  <div className="space-y-6">
                    {/* Blast Radius Metrics Grid */}
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                      <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
                        <span className="text-xs text-slate-400">Impacted Symbols</span>
                        <p className="mt-1 text-2xl font-bold text-amber-400">{impactData.total_impacted_symbols}</p>
                      </div>
                      <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
                        <span className="text-xs text-slate-400">Affected Files</span>
                        <p className="mt-1 text-2xl font-bold text-purple-400">{impactData.total_affected_files}</p>
                      </div>
                      <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
                        <span className="text-xs text-slate-400">Traversal Depth</span>
                        <p className="mt-1 text-2xl font-bold text-indigo-400">{impactData.depth} Hops</p>
                      </div>
                    </div>

                    {/* Affected Files List */}
                    <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-5">
                      <h4 className="text-xs font-bold text-white uppercase tracking-wider">
                        Files Requiring Testing / Review ({impactData.affected_files.length})
                      </h4>
                      <div className="mt-3 flex flex-wrap gap-2">
                        {impactData.affected_files.map((file, idx) => (
                          <div
                            key={idx}
                            onClick={() => {
                              setSelectedFilePath(file);
                              setActiveTab('explorer');
                            }}
                            className="cursor-pointer rounded-lg border border-slate-800 bg-slate-950 px-3 py-1.5 font-mono text-xs text-slate-300 hover:border-purple-500/50 hover:text-white transition-colors"
                          >
                            {file}
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Direct Callers Impacted */}
                    {impactData.direct_callers.length > 0 && (
                      <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-5">
                        <h4 className="text-xs font-bold text-white uppercase tracking-wider">
                          Direct Callers Impacted ({impactData.direct_callers.length})
                        </h4>
                        <div className="mt-3 grid grid-cols-1 sm:grid-cols-2 gap-3">
                          {impactData.direct_callers.map((c, idx) => (
                            <div key={idx} className="rounded-xl border border-slate-800 bg-slate-950 p-3 text-xs">
                              <span className="font-mono font-bold text-purple-300">{c.name}</span>
                              <p className="mt-1 text-[11px] text-slate-400 font-mono">{c.file_path} (Line {c.line})</p>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* SUB-VIEW 4: ALL CODE ENTITIES */}
            {graphViewMode === 'nodes' && !graphLoading && (
              <div className="space-y-4">
                <div className="flex flex-col sm:flex-row items-center gap-3">
                  <div className="relative flex-1 w-full">
                    <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
                    <input
                      type="text"
                      placeholder="Filter entities by name..."
                      value={graphSearchQuery}
                      onChange={(e) => {
                        setGraphSearchQuery(e.target.value);
                        if (details?.id) loadGraphData(details.id, e.target.value);
                      }}
                      className="w-full rounded-xl border border-slate-800 bg-slate-950 py-2 pl-9 pr-3 text-xs text-white placeholder-slate-500 focus:border-purple-500 focus:outline-none"
                    />
                  </div>

                  <select
                    value={graphNodeTypeFilter}
                    onChange={(e) => setGraphNodeTypeFilter(e.target.value)}
                    className="w-full sm:w-auto rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-xs text-slate-300 focus:border-purple-500 focus:outline-none"
                  >
                    <option value="">All Entity Types</option>
                    <option value="Function">Functions</option>
                    <option value="Method">Methods</option>
                    <option value="Class">Classes</option>
                    <option value="Interface">Interfaces</option>
                    <option value="File">Files</option>
                    <option value="Directory">Directories</option>
                    <option value="Module">Modules</option>
                  </select>
                </div>

                <div className="rounded-2xl border border-slate-800 bg-slate-900/40 overflow-hidden">
                  <table className="w-full text-left text-xs text-slate-300">
                    <thead className="border-b border-slate-800 bg-slate-950/50 text-[10px] uppercase font-bold text-slate-500">
                      <tr>
                        <th className="px-4 py-3">Entity</th>
                        <th className="px-4 py-3">Type</th>
                        <th className="px-4 py-3">File Location</th>
                        <th className="px-4 py-3">Action</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/60">
                      {graphNodesList
                        .filter((n) => !graphNodeTypeFilter || n.type === graphNodeTypeFilter)
                        .map((node) => (
                          <tr key={node.id} className="hover:bg-slate-800/30 transition-colors">
                            <td className="px-4 py-3 font-mono font-bold text-white">
                              {node.name}
                            </td>
                            <td className="px-4 py-3">
                              <span className="rounded bg-purple-500/10 border border-purple-500/20 px-2 py-0.5 text-[10px] font-semibold text-purple-300">
                                {node.type}
                              </span>
                            </td>
                            <td className="px-4 py-3 font-mono text-[11px] text-slate-400">
                              {node.file_path ? `${node.file_path}${node.start_line ? `:${node.start_line}` : ''}` : '-'}
                            </td>
                            <td className="px-4 py-3">
                              <button
                                type="button"
                                onClick={() => {
                                  handleSelectNode(node);
                                  setGraphViewMode('subgraph');
                                }}
                                className="text-purple-400 hover:text-purple-300 font-medium transition-colors"
                              >
                                View in Graph
                              </button>
                            </td>
                          </tr>
                        ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}

        {/* CHAT TAB PREVIEW */}
        {activeTab === 'chat' && (
          <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-8 text-center">
            <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
              <Sparkles className="h-7 w-7" />
            </div>
            <h3 className="mt-4 text-xl font-bold text-white">Grounded RAG Chat Engine</h3>
            <p className="mx-auto mt-2 max-w-lg text-sm text-slate-400">
              Repository ingestion, Tree-sitter AST parsing, ChromaDB vector representations, and NetworkX Knowledge Graph construction are complete. You can now execute semantic code search and inspect graph relationships above. The upcoming phases will fuse both pipelines and connect Gemini for interactive grounded chat with file/line citations.
            </p>

            <div className="mt-8 mx-auto max-w-xl text-left rounded-xl border border-slate-800 bg-slate-950/60 p-4">
              <span className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
                Phase Progress:
              </span>
              <ul className="mt-2 space-y-1.5 text-xs text-slate-400">
                <li className="text-emerald-400">✓ Phase 1: Foundation Architecture</li>
                <li className="text-emerald-400">✓ Phase 2: Ingestion & File Filtering</li>
                <li className="text-emerald-400">✓ Phase 3: Tree-sitter Code Understanding</li>
                <li className="text-emerald-400">✓ Phase 4: Structure-Aware Vector RAG & ChromaDB Persistent Storage</li>
                <li className="text-emerald-400">✓ Phase 5: Knowledge Graph Construction & Persistence (NetworkX)</li>
                <li className="text-slate-500">⏳ Phase 6: GraphRAG & Traversal Retrieval (Call graphs, Dependencies, Scopes)</li>
                <li className="text-slate-500">⏳ Phase 7: Unified Hybrid Vector + Graph Retrieval & Gemini Chat</li>
              </ul>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
