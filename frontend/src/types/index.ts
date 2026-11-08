export interface HealthStatus {
  status: string;
  version: string;
  environment: string;
  gpu_available: boolean;
  gpu_name: string | null;
  gemini_configured: boolean;
  timestamp: string;
  system_info: {
    python_version: string;
    platform: string;
    processor: string;
  };
}

export interface DemoRepository {
  name: string;
  owner: string;
  url: string;
  description: string;
  category: string;
  language: string;
  stars: string;
}

export interface ValidationResult {
  is_valid: boolean;
  owner?: string;
  repo?: string;
  normalized_url?: string;
  is_accessible: boolean;
  message?: string;
}

export interface LanguageStat {
  name: string;
  file_count: number;
  line_count: number;
  byte_count: number;
  percentage: number;
}

export interface RepositoryDetail {
  id: string;
  owner: string;
  name: string;
  url: string;
  default_branch: string;
  description?: string;
  primary_language?: string;
  languages: LanguageStat[];
  file_count: number;
  total_size_bytes: number;
  commit_hash?: string;
  status: string;
  manifest_files: string[];
  entry_points: string[];
  readme_content?: string;
  error_message?: string;
}

export interface IndexingStatus {
  repository_id: string;
  job_id: string;
  status: 'queued' | 'processing' | 'completed' | 'failed';
  current_stage: string;
  progress_pct: number;
  error_message?: string;
}

export interface TreeNode {
  name: string;
  path: string;
  type: 'file' | 'directory';
  size: number;
  language?: string;
  line_count?: number;
  children?: TreeNode[];
}

export interface FileContent {
  relative_path: string;
  language: string;
  size_bytes: number;
  line_count: number;
  content: string;
}

export interface SearchChunkResult {
  chunk_id: string;
  repository_id: string;
  file_path: string;
  symbol_id?: string;
  symbol_name?: string;
  symbol_type?: string;
  language: string;
  start_line: number;
  end_line: number;
  source_code: string;
  signature?: string;
  docstring?: string;
  context_header?: string;
  similarity_score: number;
  distance: number;
  part_index: number;
  total_parts: number;
}

export interface SearchResponse {
  query: string;
  repository_id: string;
  total_results: number;
  results: SearchChunkResult[];
}

export interface VectorIndexStatus {
  repository_id: string;
  collection_name: string;
  total_chunks: number;
  language_breakdown: Record<string, number>;
  symbol_type_breakdown: Record<string, number>;
  status: string;
  persist_directory: string;
}

export interface GraphStatus {
  repository_id: string;
  total_nodes: number;
  total_edges: number;
  graph_density: number;
  is_persisted: boolean;
  node_types: Record<string, number>;
  relationship_types: Record<string, number>;
  confirmed_edges: number;
  inferred_edges: number;
}

export interface GraphNodeItem {
  id: string;
  repository_id: string;
  type: string;
  name: string;
  qualified_name?: string;
  file_path?: string;
  start_line?: number;
  end_line?: number;
  language?: string;
  commit_hash?: string;
  symbol_id?: string;
  content_hash?: string;
  properties?: Record<string, any>;
}

export interface GraphEdgeItem {
  source_id: string;
  target_id: string;
  relationship: string;
  repository_id: string;
  is_confirmed: boolean;
  confidence: number;
  resolution_status: string;
  properties?: Record<string, any>;
}

export interface CallerItem {
  caller_id: string;
  caller_name: string;
  caller_type: string;
  file_path: string;
  start_line?: number;
  invocation_lines: number[];
  call_count: number;
  confidence: number;
  is_confirmed: boolean;
  resolution_status: string;
}

export interface CallersResponse {
  repository_id: string;
  target_id?: string;
  target_symbol: string;
  target_type?: string;
  file_path?: string;
  line?: number;
  found: boolean;
  total_callers: number;
  callers: CallerItem[];
  error?: string;
}

export interface CalleeItem {
  callee_id: string;
  callee_name: string;
  callee_type: string;
  file_path: string;
  start_line?: number;
  invocation_lines: number[];
  call_count: number;
  confidence: number;
  is_confirmed: boolean;
  resolution_status: string;
}

export interface CalleesResponse {
  repository_id: string;
  source_id?: string;
  source_symbol: string;
  source_type?: string;
  file_path?: string;
  line?: number;
  found: boolean;
  total_callees: number;
  callees: CalleeItem[];
  error?: string;
}

export interface ImpactItem {
  node_id: string;
  name: string;
  type: string;
  file_path?: string;
  line?: number;
  confidence: number;
}

export interface ImpactAnalysisResponse {
  repository_id: string;
  target_node_id: string;
  target_name?: string;
  target_type?: string;
  depth: number;
  found: boolean;
  total_impacted_symbols: number;
  total_affected_files: number;
  affected_files: string[];
  direct_callers: ImpactItem[];
  direct_dependents: ImpactItem[];
  inheriting_classes: ImpactItem[];
  all_impacted_node_ids: string[];
  error?: string;
}

export interface SubgraphResponse {
  center_node_id: string;
  radius: number;
  node_count: number;
  edge_count: number;
  nodes: GraphNodeItem[];
  edges: GraphEdgeItem[];
}

export interface QueryAnalysisResult {
  original_query: string;
  intents: string[];
  extracted_symbols: string[];
  extracted_file_paths: string[];
  confidence: number;
  recommended_strategies: string[];
  intent_reasons: Record<string, string>;
}

export interface UnifiedSearchResult {
  chunk_id: string;
  repository_id: string;
  file_path: string;
  symbol_id?: string;
  symbol_name?: string;
  symbol_type?: string;
  language: string;
  start_line: number;
  end_line: number;
  source_code: string;
  signature?: string;
  docstring?: string;
  context_header?: string;
  retrieval_source: string;
  sources: string[];
  original_score: number;
  normalized_score: number;
  rrf_score: number;
  confidence: number;
  resolution_status?: string;
  properties?: Record<string, any>;
}

export interface GraphEvidence {
  relationship_type: string;
  source_node_id: string;
  source_name: string;
  target_node_id: string;
  target_name: string;
  confidence: number;
  is_confirmed: boolean;
  call_count: number;
  lines: number[];
  file_path?: string;
  description?: string;
}

export interface AssembledContext {
  summary: string;
  total_code_chunks: number;
  total_graph_relationships: number;
  sources_used: string[];
  formatted_context: string;
  citations: Array<{
    rank: number;
    file_path: string;
    start_line: number;
    end_line: number;
    symbol_name?: string;
    symbol_type?: string;
    sources: string[];
    rrf_score: number;
  }>;
}

export interface HybridSearchRequest {
  query: string;
  top_k?: number;
  include_vector?: boolean;
  include_graph?: boolean;
  include_keyword?: boolean;
  language?: string;
  file_path?: string;
  symbol_type?: string;
  rrf_k?: number;
}

export interface HybridRetrievalResponse {
  query: string;
  repository_id: string;
  intents: string[];
  strategies_used: string[];
  total_results: number;
  results: UnifiedSearchResult[];
  graph_evidence: GraphEvidence[];
  assembled_context: AssembledContext;
  execution_times: Record<string, number>;
  warnings: string[];
  diagnostics: Record<string, any>;
}

export type AppView = 'landing' | 'dashboard';
