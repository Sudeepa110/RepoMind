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
};
