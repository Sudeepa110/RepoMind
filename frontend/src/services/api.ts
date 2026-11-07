import axios from 'axios';
import type { HealthStatus, DemoRepository, ValidationResult } from '../types';

const API_BASE = '/api/v1';

const apiClient = axios.create({
  baseURL: API_BASE,
  timeout: 10000,
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
};
