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

export type AppView = 'landing' | 'dashboard' | 'evaluation';

export interface Citation {
  citation_id: string;
  file_path: string;
  start_line: number;
  end_line: number;
  symbol_name?: string;
  symbol_type?: string;
  source_excerpt?: string;
  retrieval_source: string;
  confidence: number;
  is_verified: boolean;
  reason?: string;
}

export interface ChatMessageItem {
  id: string;
  conversation_id: string;
  role: 'user' | 'assistant';
  content: string;
  citations: Citation[];
  retrieval_intents: string[];
  retrieval_sources: string[];
  confidence: number;
  insufficient_evidence: boolean;
  generation_model?: string;
  generation_latency_ms?: number;
  retrieval_latency_ms?: number;
  created_at: string;
}

export interface ConversationListItem {
  id: string;
  repository_id: string;
  title: string;
  message_count: number;
  created_at: string;
  updated_at: string;
}

export interface ConversationDetail {
  id: string;
  repository_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  messages: ChatMessageItem[];
}

export interface ChatStreamRequest {
  query: string;
  conversation_id?: string;
  top_k?: number;
  temperature?: number;
}

export interface StructuredAnswer {
  answer_id: string;
  conversation_id: string;
  repository_id: string;
  content: string;
  citations: Citation[];
  retrieval_intents: string[];
  retrieval_sources: string[];
  confidence: number;
  evidence_sufficiency: 'SUFFICIENT' | 'PARTIAL' | 'INSUFFICIENT' | 'NO_EVIDENCE';
  generation_model: string;
  generation_latency_ms: number;
  retrieval_latency_ms: number;
  warnings: string[];
}

// --- Phase 8 Intelligence Types ---

export type ImpactCategory = 'DIRECT' | 'INDIRECT' | 'STRUCTURAL' | 'POTENTIAL';

export interface AffectedEntity {
  symbol_id: string;
  name: string;
  type: string;
  file_path: string;
  start_line?: number;
  end_line?: number;
  category: ImpactCategory;
  relationship_path: string[];
  depth: number;
  confidence: number;
  resolution_status: string;
  code_snippet?: string;
}

export interface ImpactAnalysisRequest {
  target_symbol: string;
  file_path?: string;
  max_depth?: number;
}

export interface ImpactAnalysisResult {
  target_symbol: string;
  target_file?: string;
  direct_count: number;
  indirect_count: number;
  structural_count: number;
  potential_count: number;
  total_affected_symbols: number;
  total_affected_files: number;
  affected_files: string[];
  affected_entities: AffectedEntity[];
  risk_score: number;
  risk_level: string;
  explanation: string;
  citations: Citation[];
  limitations: string[];
}

export interface ExecutionFlowStep {
  step_index: number;
  symbol_name: string;
  symbol_type: string;
  file_path: string;
  start_line?: number;
  end_line?: number;
  caller_symbol?: string;
  depth: number;
  crosses_file: boolean;
  is_external: boolean;
  is_branch_point: boolean;
  confidence: number;
  resolution_status: string;
  code_snippet?: string;
}

export interface ExecutionFlowRequest {
  entry_point: string;
  file_path?: string;
  max_depth?: number;
  target_symbol?: string;
}

export interface ExecutionFlowResult {
  entry_point: string;
  target_symbol?: string;
  total_steps: number;
  cross_file_count: number;
  unresolved_calls: number;
  steps: ExecutionFlowStep[];
  involved_files: string[];
  explanation: string;
  citations: Citation[];
  limitations: string[];
}

export interface DependencyCouplingMetric {
  file_path: string;
  module_name: string;
  in_degree: number;
  out_degree: number;
  instability: number;
  is_tightly_coupled: boolean;
  direct_dependencies: string[];
  direct_dependents: string[];
  external_libraries: string[];
  layer: string;
}

export interface DependencyAnalysisResult {
  total_files: number;
  total_modules: number;
  average_instability: number;
  tightly_coupled_pairs: Array<{ module_a: string; module_b: string; nature: string }>;
  file_metrics: DependencyCouplingMetric[];
  external_libraries: string[];
  layer_distribution: Record<string, number>;
  summary: string;
  citations: Citation[];
}

export type BugSeverity = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW' | 'INFORMATIONAL';
export type BugCategory = 'ERROR_HANDLING' | 'NULL_SAFETY' | 'RESOURCE_LEAK' | 'TYPE_MISMATCH' | 'UNRESOLVED_CALL' | 'SECURITY_CONCERN' | 'CONCURRENCY';

export interface BugFinding {
  finding_id: string;
  title: string;
  category: BugCategory;
  severity: BugSeverity;
  affected_symbol: string;
  file_path: string;
  start_line: number;
  end_line: number;
  explanation: string;
  evidence: string;
  possible_failure_scenario: string;
  suggested_remediation: string;
  confidence: number;
}

export interface BugInvestigationRequest {
  target?: string;
  query?: string;
}

export interface BugInvestigationResult {
  target?: string;
  findings: BugFinding[];
  total_findings: number;
  critical_count: number;
  high_count: number;
  medium_count: number;
  low_count: number;
  explanation: string;
  citations: Citation[];
  limitations: string[];
}

export interface RiskFactorBreakdown {
  factor_name: string;
  points: number;
  reason: string;
}

export interface RiskAssessmentRequest {
  target_symbol: string;
  file_path?: string;
}

export interface RiskAssessmentResult {
  target_symbol: string;
  target_file?: string;
  risk_score: number;
  risk_level: string;
  blast_radius_files: number;
  direct_dependents: number;
  indirect_dependents: number;
  is_public_api: boolean;
  is_core_model: boolean;
  formula_breakdown: RiskFactorBreakdown[];
  summary: string;
  citations: Citation[];
  formula_explanation: string;
}

export type TestType = 'UNIT' | 'INTEGRATION' | 'REGRESSION' | 'E2E';

export interface TestRecommendation {
  recommendation_id: string;
  category: TestType;
  target_symbol: string;
  file_path: string;
  reason: string;
  suggested_assertions: string[];
  existing_test_reference?: string;
  priority: string;
}

export interface TestRecommendationsRequest {
  target_symbol: string;
  file_path?: string;
}

export interface TestRecommendationsResult {
  target_symbol: string;
  existing_tests_found: string[];
  recommendations: TestRecommendation[];
  total_recommendations: number;
  summary: string;
  citations: Citation[];
}

export interface DocumentationRequest {
  target: string;
  file_path?: string;
  doc_type?: string;
}

export interface DocumentationResult {
  target_name: string;
  target_type: string;
  file_path: string;
  markdown_documentation: string;
  citations: Citation[];
}

// ==========================================
// Phase 9: Evaluation & Benchmarking Types
// ==========================================

export interface RetrievalStrategyMetrics {
  precision_at_1: number;
  precision_at_3: number;
  precision_at_5: number;
  recall_at_3: number;
  recall_at_5: number;
  mrr: number;
  ndcg_at_5: number;
  file_accuracy: number;
  symbol_accuracy: number;
  mean_latency_ms: number;
  latency_p50_ms: number;
  latency_p95_ms: number;
  total_queries?: number;
}

export interface RetrievalComparisonSummary {
  [repoId: string]: {
    vector_only: RetrievalStrategyMetrics;
    keyword_only: RetrievalStrategyMetrics;
    graph_only: RetrievalStrategyMetrics;
    hybrid: RetrievalStrategyMetrics;
  };
}

export interface GroundingMetrics {
  citation_validity: number;
  citation_coverage: number;
  abstention_accuracy: number;
  injection_defense_success_rate: number;
}

export interface KnowledgeGraphBenchmark {
  total_nodes_extracted: number;
  ground_truth_nodes: number;
  node_precision: number;
  node_recall: number;
  total_edges_extracted: number;
  ground_truth_edges: number;
  edge_precision: number;
  edge_recall: number;
  confirmed_edges: number;
  unresolved_edges: number;
}

export interface ImpactAnalysisBenchmark {
  direct_precision: number;
  direct_recall: number;
  false_positive_rate: number;
  false_negative_rate: number;
  file_blast_radius_accuracy: number;
}

export interface BugInvestigationBenchmark {
  precision: number;
  recall: number;
  f1_score: number;
  false_positive_rate: number;
  false_negative_rate: number;
}

export interface GraphAndIntelligenceBenchmark {
  knowledge_graph: KnowledgeGraphBenchmark;
  change_impact_analysis: ImpactAnalysisBenchmark;
  bug_investigation: BugInvestigationBenchmark;
  test_recommendations: {
    category_coverage: number;
    has_suggested_assertions: boolean;
  };
}

export interface HardwareEnvironment {
  platform: string;
  cpu_architecture: string;
  cpu_cores_logical: number;
  cpu_cores_physical: number;
  ram_total_gb: number;
  ram_available_gb: number;
  gpu_detected: string;
  pytorch_device: string;
}

export interface QueryLatencyPercentiles {
  cold_start_latency_ms: number;
  warm_start_p50_ms: number;
  warm_start_p95_ms: number;
  warm_start_p99_ms: number;
  total_measured_queries: number;
}

export interface StageMetric {
  duration_ms: number;
  memory_before_mb: number;
  memory_after_mb: number;
  memory_delta_mb: number;
}

export interface EvaluationSummary {
  status: string;
  metadata: {
    timestamp?: string;
    phase: string;
    hardware: HardwareEnvironment;
    total_queries_evaluated: number;
  };
  retrieval_strategy_comparison: RetrievalComparisonSummary;
  grounding_and_citations: GroundingMetrics;
  graph_and_intelligence: GraphAndIntelligenceBenchmark;
  system_latency_profiling: {
    hardware_environment: HardwareEnvironment;
    query_latency_percentiles: QueryLatencyPercentiles;
    stages: Record<string, StageMetric>;
  };
}

export interface SystemProfile {
  hardware_environment: HardwareEnvironment;
  current_rss_mb: number;
  query_latency_percentiles: QueryLatencyPercentiles;
  pipeline_stages: Record<string, StageMetric>;
  indexing_breakdown: Record<string, any>;
}



