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
  ConversationListItem,
  ConversationDetail,
  ChatStreamRequest,
  StructuredAnswer,
  Citation,
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

  async createConversation(repositoryId: string, title?: string): Promise<ConversationDetail> {
    const res = await apiClient.post<ConversationDetail>(
      `/repositories/${repositoryId}/conversations`,
      { title }
    );
    return res.data;
  },

  async listConversations(repositoryId: string): Promise<ConversationListItem[]> {
    const res = await apiClient.get<ConversationListItem[]>(
      `/repositories/${repositoryId}/conversations`
    );
    return res.data;
  },

  async getConversation(repositoryId: string, conversationId: string): Promise<ConversationDetail> {
    const res = await apiClient.get<ConversationDetail>(
      `/repositories/${repositoryId}/conversations/${conversationId}`
    );
    return res.data;
  },

  async deleteConversation(repositoryId: string, conversationId: string): Promise<{ message: string }> {
    const res = await apiClient.delete<{ message: string }>(
      `/repositories/${repositoryId}/conversations/${conversationId}`
    );
    return res.data;
  },

  async chatSync(repositoryId: string, payload: ChatStreamRequest): Promise<StructuredAnswer> {
    const res = await apiClient.post<StructuredAnswer>(
      `/repositories/${repositoryId}/chat`,
      payload
    );
    return res.data;
  },

  async streamChat(
    repositoryId: string,
    payload: ChatStreamRequest,
    callbacks: {
      onRetrievalStarted?: (data: any) => void;
      onRetrievalCompleted?: (data: any) => void;
      onGenerationStarted?: (data: any) => void;
      onToken?: (token: string) => void;
      onCitation?: (citation: Citation) => void;
      onDone?: (answer: any) => void;
      onError?: (error: { error: string; error_type: string }) => void;
    },
    signal?: AbortSignal
  ): Promise<void> {
    const response = await fetch(`${API_BASE}/repositories/${repositoryId}/chat/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
      signal,
    });

    if (!response.ok) {
      let errorDetail = 'Failed to connect to chat stream';
      try {
        const errorJson = await response.json();
        errorDetail = errorJson.detail || errorDetail;
      } catch {
        // fallback
      }
      if (callbacks.onError) {
        callbacks.onError({ error: errorDetail, error_type: 'HttpError' });
      }
      return;
    }

    if (!response.body) {
      if (callbacks.onError) {
        callbacks.onError({ error: 'Response body is null', error_type: 'StreamError' });
      }
      return;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n\n');
      buffer = lines.pop() || '';

      for (const block of lines) {
        if (!block.trim()) continue;
        const eventMatch = block.match(/^event:\s*(.+)$/m);
        const dataMatch = block.match(/^data:\s*(.+)$/m);

        const eventType = eventMatch ? eventMatch[1].trim() : 'message';
        const dataStr = dataMatch ? dataMatch[1].trim() : '{}';

        try {
          const data = JSON.parse(dataStr);
          switch (eventType) {
            case 'retrieval_started':
              callbacks.onRetrievalStarted?.(data);
              break;
            case 'retrieval_completed':
              callbacks.onRetrievalCompleted?.(data);
              break;
            case 'generation_started':
              callbacks.onGenerationStarted?.(data);
              break;
            case 'token':
              callbacks.onToken?.(data.token || '');
              break;
            case 'citation':
              callbacks.onCitation?.(data.citation);
              break;
            case 'done':
              callbacks.onDone?.(data);
              break;
            case 'error':
              callbacks.onError?.(data);
              break;
          }
        } catch (e) {
          console.error('Failed to parse SSE event chunk:', e, block);
        }
      }
    }
  },
};
