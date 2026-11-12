// frontend/src/components/States.tsx
import React from 'react';
import { AlertCircle, FolderOpen, RefreshCw } from 'lucide-react';

interface LoadingStateProps {
  message?: string;
  className?: string;
}

export const LoadingState: React.FC<LoadingStateProps> = ({
  message = 'Loading verified data...',
  className = '',
}) => {
  return (
    <div
      className={`py-12 flex flex-col items-center justify-center text-center ${className}`}
      aria-live="polite"
      aria-busy="true"
    >
      <div className="w-8 h-8 border-3 border-gov-200 border-t-gov-700 rounded-full animate-spin mb-3" />
      <p className="text-sm text-slate-600 font-medium">{message}</p>
    </div>
  );
};

interface EmptyStateProps {
  title?: string;
  description?: string;
  actionText?: string;
  onAction?: () => void;
  className?: string;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  title = 'No schemes found',
  description = 'No matching schemes could be retrieved for the current filter criteria.',
  actionText,
  onAction,
  className = '',
}) => {
  return (
    <div
      className={`border border-dashed border-slate-300 rounded-lg p-10 text-center bg-slate-50/50 max-w-lg mx-auto my-8 ${className}`}
    >
      <div className="w-10 h-10 mx-auto rounded-full bg-slate-100 flex items-center justify-center text-slate-400 mb-3">
        <FolderOpen className="w-5 h-5" />
      </div>
      <h3 className="text-sm font-semibold text-slate-800 mb-1">{title}</h3>
      <p className="text-xs text-slate-500 mb-4 leading-relaxed">{description}</p>
      {actionText && onAction && (
        <button
          type="button"
          onClick={onAction}
          className="inline-flex items-center text-xs font-semibold px-3 py-1.5 rounded bg-gov-700 text-white hover:bg-gov-800 transition-colors"
        >
          {actionText}
        </button>
      )}
    </div>
  );
};

interface ErrorStateProps {
  title?: string;
  message?: string;
  onRetry?: () => void;
  className?: string;
}

export const ErrorState: React.FC<ErrorStateProps> = ({
  title = 'Failed to load data',
  message = 'An unexpected error occurred while communicating with the service.',
  onRetry,
  className = '',
}) => {
  return (
    <div
      className={`border border-rose-200 bg-rose-50/50 rounded-lg p-6 max-w-lg mx-auto my-6 text-center ${className}`}
      role="alert"
    >
      <div className="w-10 h-10 mx-auto rounded-full bg-rose-100 flex items-center justify-center text-rose-600 mb-3">
        <AlertCircle className="w-5 h-5" />
      </div>
      <h3 className="text-sm font-semibold text-rose-900 mb-1">{title}</h3>
      <p className="text-xs text-rose-700 mb-4 leading-relaxed">{message}</p>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="inline-flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded bg-rose-600 text-white hover:bg-rose-700 transition-colors"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Retry Request
        </button>
      )}
    </div>
  );
};
