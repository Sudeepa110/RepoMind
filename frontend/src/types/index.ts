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

export type AppView = 'landing' | 'dashboard';
