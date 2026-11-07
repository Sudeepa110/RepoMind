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

export type AppView = 'landing' | 'dashboard';
