import axios from 'axios';
import type {
  HealthStatus,
  DemoRepository,
  ValidationResult,
  RepositoryDetail,
  IndexingStatus,
  TreeNode,
  FileContent,
  SearchResponse,
  VectorIndexStatus,
  GraphStatus,
  GraphNodeItem,
  GraphEdgeItem,
  CallersResponse,
  CalleesResponse,
  ImpactAnalysisResponse,
  SubgraphResponse,
  HybridSearchRequest,
  HybridRetrievalResponse,
  QueryAnalysisResult,
} from '../types';

const API_BASE = '/api/v1';

const apiClient = axios.create({
  baseURL: API_BASE,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const api = {
  async getHealth(): Promise<HealthStatus> {
    const res = await apiClient.get<HealthStatus>('/health');
    return res.data;
  },

  async getDemos(): Promise<DemoRepository[]> {
    const res = await apiClient.get<DemoRepository[]>('/repositories/demos');
    return res.data;
  },

  async validateRepository(url: string): Promise<ValidationResult> {
    const res = await apiClient.post<ValidationResult>('/repositories/validate', { url });
    return res.data;
  },

  async analyzeRepository(url: string, forceReindex: boolean = false): Promise<{ repository_id: string; job_id: string; status: string; message: string }> {
    const res = await apiClient.post('/repositories/analyze', {
      url,
      force_reindex: forceReindex,
    });
    return res.data;
  },

  async getRepositoryStatus(repositoryId: string): Promise<IndexingStatus> {
    const res = await apiClient.get<IndexingStatus>(`/repositories/${repositoryId}/status`);
    return res.data;
  },

  async getRepositoryDetails(repositoryId: string): Promise<RepositoryDetail> {
    const res = await apiClient.get<RepositoryDetail>(`/repositories/${repositoryId}`);
    return res.data;
  },

  async getRepositoryTree(repositoryId: string): Promise<TreeNode> {
    const res = await apiClient.get<TreeNode>(`/repositories/${repositoryId}/tree`);
    return res.data;
  },

  async getRepositoryFile(repositoryId: string, path: string): Promise<FileContent> {
    const res = await apiClient.get<FileContent>(`/repositories/${repositoryId}/file`, {
      params: { path },
    });
    return res.data;
  },

  async searchRepository(
    repositoryId: string,
    params: {
      query: string;
      top_k?: number;
      language?: string;
      file_path?: string;
      symbol_type?: string;
    }
  ): Promise<SearchResponse> {
    const res = await apiClient.post<SearchResponse>(`/repositories/${repositoryId}/search`, params);
    return res.data;
  },

  async getVectorIndexStatus(repositoryId: string): Promise<VectorIndexStatus> {
    const res = await apiClient.get<VectorIndexStatus>(`/repositories/${repositoryId}/index/status`);
    return res.data;
  },

  async triggerReindex(repositoryId: string, forceReindex: boolean = true): Promise<{ repository_id: string; job_id: string; status: string; message: string }> {
    const res = await apiClient.post(`/repositories/${repositoryId}/index`, null, {
      params: { force_reindex: forceReindex },
    });
    return res.data;
  },

  async getGraphStatus(repositoryId: string): Promise<GraphStatus> {
    const res = await apiClient.get<GraphStatus>(`/repositories/${repositoryId}/graph/status`);
    return res.data;
  },

  async getGraphNodes(
    repositoryId: string,
    params?: {
      node_type?: string;
      file_path?: string;
      query?: string;
      limit?: number;
      offset?: number;
    }
  ): Promise<{ repository_id: string; total: number; limit: number; offset: number; nodes: GraphNodeItem[] }> {
    const res = await apiClient.get(`/repositories/${repositoryId}/graph/nodes`, { params });
    return res.data;
  },

  async getGraphEdges(
    repositoryId: string,
    params?: {
      relationship?: string;
      source_id?: string;
      target_id?: string;
      limit?: number;
      offset?: number;
    }
  ): Promise<{ repository_id: string; total: number; limit: number; offset: number; edges: GraphEdgeItem[] }> {
    const res = await apiClient.get(`/repositories/${repositoryId}/graph/edges`, { params });
    return res.data;
  },

  async getCallers(repositoryId: string, symbol: string): Promise<CallersResponse> {
    const res = await apiClient.get<CallersResponse>(`/repositories/${repositoryId}/graph/callers`, {
      params: { symbol },
    });
    return res.data;
  },

  async getCallees(repositoryId: string, symbol: string): Promise<CalleesResponse> {
    const res = await apiClient.get<CalleesResponse>(`/repositories/${repositoryId}/graph/callees`, {
      params: { symbol },
    });
    return res.data;
  },

  async getImpactAnalysis(repositoryId: string, target: string, depth: number = 2): Promise<ImpactAnalysisResponse> {
    const res = await apiClient.get<ImpactAnalysisResponse>(`/repositories/${repositoryId}/graph/impact`, {
      params: { target, depth },
    });
    return res.data;
  },

  async getSubgraph(
    repositoryId: string,
    centerNodeId: string,
    radius: number = 1,
    maxNodes: number = 50
  ): Promise<SubgraphResponse> {
    const res = await apiClient.get<SubgraphResponse>(`/repositories/${repositoryId}/graph/subgraph`, {
      params: { center_node_id: centerNodeId, radius, max_nodes: maxNodes },
    });
    return res.data;
  },

  async hybridSearch(
    repositoryId: string,
    payload: HybridSearchRequest
  ): Promise<HybridRetrievalResponse> {
    const res = await apiClient.post<HybridRetrievalResponse>(
      `/repositories/${repositoryId}/hybrid-search`,
      payload
    );
    return res.data;
  },

  async analyzeQuery(
    repositoryId: string,
    query: string
  ): Promise<QueryAnalysisResult> {
    const res = await apiClient.post<QueryAnalysisResult>(
      `/repositories/${repositoryId}/analyze-query`,
      { query }
    );
    return res.data;
  },
};
