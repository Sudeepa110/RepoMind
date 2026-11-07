import React, { useState, useEffect } from 'react';
import {
  Search,
  ArrowRight,
  ShieldCheck,
  AlertTriangle,
  CheckCircle2,
  Loader2,
  Lock,
} from 'lucide-react';
import { api } from '../services/api';
import type { ValidationResult } from '../types';

interface UrlInputFormProps {
  initialUrl?: string;
  onAnalysisStart: (repoUrl: string, validation: ValidationResult) => void;
}

export const UrlInputForm: React.FC<UrlInputFormProps> = ({
  initialUrl = '',
  onAnalysisStart,
}) => {
  const [url, setUrl] = useState(initialUrl);
  const [isValidating, setIsValidating] = useState(false);
  const [validationResult, setValidationResult] = useState<ValidationResult | null>(null);
  const [clientError, setClientError] = useState<string | null>(null);

  useEffect(() => {
    if (initialUrl) {
      setUrl(initialUrl);
      setClientError(null);
      setValidationResult(null);
    }
  }, [initialUrl]);

  // Client-side quick validation on change
  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setUrl(val);
    setValidationResult(null);

    if (!val.trim()) {
      setClientError(null);
      return;
    }

    if (!val.startsWith('http://') && !val.startsWith('https://')) {
      setClientError('URL must begin with https://');
      return;
    }

    if (val.startsWith('http://')) {
      setClientError('Only secure HTTPS URLs are allowed.');
      return;
    }

    if (!val.includes('github.com')) {
      setClientError('Repository URL must be from github.com.');
      return;
    }

    setClientError(null);
  };

  const handleValidateAndAnalyze = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    const cleanUrl = url.trim();

    if (!cleanUrl) {
      setClientError('Please enter a GitHub repository URL.');
      return;
    }

    setIsValidating(true);
    setClientError(null);

    try {
      const res = await api.validateRepository(cleanUrl);
      setValidationResult(res);

      if (res.is_valid && res.is_accessible) {
        onAnalysisStart(res.normalized_url || cleanUrl, res);
      }
    } catch (err: any) {
      setValidationResult({
        is_valid: false,
        is_accessible: false,
        message:
          err.response?.data?.message ||
          'Unable to reach RepoMind backend service. Please check connection.',
      });
    } finally {
      setIsValidating(false);
    }
  };

  return (
    <div className="w-full max-w-3xl">
      <form onSubmit={handleValidateAndAnalyze} className="relative">
        <div className="relative flex items-center rounded-2xl border border-slate-700/80 bg-slate-900/90 p-2 shadow-2xl shadow-indigo-950/40 backdrop-blur-xl transition-all focus-within:border-indigo-500 focus-within:ring-2 focus-within:ring-indigo-500/20">
          <div className="flex pl-3 text-slate-400">
            <Search className="h-5 w-5" />
          </div>

          <input
            type="text"
            value={url}
            onChange={handleInputChange}
            placeholder="Paste public GitHub URL (e.g. https://github.com/fastapi/fastapi)"
            className="w-full bg-transparent px-4 py-3 text-sm text-white placeholder-slate-500 outline-none sm:text-base"
            disabled={isValidating}
          />

          <button
            type="submit"
            disabled={isValidating || !url.trim()}
            className="flex items-center space-x-2 rounded-xl bg-gradient-to-r from-indigo-500 to-purple-600 px-5 py-3 text-sm font-semibold text-white shadow-lg shadow-indigo-500/25 transition-all hover:from-indigo-600 hover:to-purple-700 hover:shadow-indigo-500/40 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isValidating ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                <span>Verifying...</span>
              </>
            ) : (
              <>
                <span>Analyze Repo</span>
                <ArrowRight className="h-4 w-4" />
              </>
            )}
          </button>
        </div>
      </form>

      {/* Validation Feedback & Alerts */}
      <div className="mt-3 space-y-2">
        {clientError && (
          <div className="flex items-center space-x-2 rounded-xl border border-amber-500/30 bg-amber-500/10 px-3.5 py-2 text-xs text-amber-300">
            <AlertTriangle className="h-4 w-4 shrink-0 text-amber-400" />
            <span>{clientError}</span>
          </div>
        )}

        {validationResult && !validationResult.is_valid && (
          <div className="flex items-center space-x-2 rounded-xl border border-rose-500/30 bg-rose-500/10 px-3.5 py-2 text-xs text-rose-300">
            <AlertTriangle className="h-4 w-4 shrink-0 text-rose-400" />
            <span>{validationResult.message || 'Invalid repository URL format.'}</span>
          </div>
        )}

        {validationResult && validationResult.is_valid && !validationResult.is_accessible && (
          <div className="flex items-center space-x-2 rounded-xl border border-rose-500/30 bg-rose-500/10 px-3.5 py-2 text-xs text-rose-300">
            <Lock className="h-4 w-4 shrink-0 text-rose-400" />
            <span>{validationResult.message || 'Repository not accessible or private.'}</span>
          </div>
        )}

        {validationResult && validationResult.is_valid && validationResult.is_accessible && (
          <div className="flex items-center space-x-2 rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-3.5 py-2 text-xs text-emerald-300">
            <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-400" />
            <span>
              Verified public repository:{' '}
              <span className="font-semibold">{validationResult.owner}/{validationResult.repo}</span>.
              Ready for intelligent parsing.
            </span>
          </div>
        )}

        {/* Security Assurance Tag */}
        <div className="flex items-center justify-center space-x-4 pt-1 text-[11px] text-slate-500">
          <span className="flex items-center space-x-1">
            <ShieldCheck className="h-3.5 w-3.5 text-indigo-400" />
            <span>Public Repos Only</span>
          </span>
          <span>•</span>
          <span>Zero Execution Sandbox</span>
          <span>•</span>
          <span>No Login Required</span>
        </div>
      </div>
    </div>
  );
};
