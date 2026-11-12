// frontend/src/components/EligibilityBadge.tsx
import React from 'react';
import type { EligibilityStatus } from '../types/contracts';

interface EligibilityBadgeProps {
  status: EligibilityStatus | string;
  size?: 'sm' | 'md';
}

export const EligibilityBadge: React.FC<EligibilityBadgeProps> = ({ status, size = 'md' }) => {
  const getBadgeConfig = () => {
    switch (status) {
      case 'ELIGIBLE':
        return {
          label: 'Eligible',
          bg: 'bg-emerald-50 text-emerald-800 border-emerald-300',
          dot: 'bg-emerald-600',
        };
      case 'PARTIALLY_ELIGIBLE':
        return {
          label: 'Partially Eligible',
          bg: 'bg-amber-50 text-amber-900 border-amber-300',
          dot: 'bg-amber-600',
        };
      case 'NEEDS_VERIFICATION':
        return {
          label: 'Needs Verification',
          bg: 'bg-sky-50 text-sky-900 border-sky-300',
          dot: 'bg-sky-600',
        };
      case 'NOT_ELIGIBLE':
        return {
          label: 'Not Eligible',
          bg: 'bg-rose-50 text-rose-800 border-rose-300',
          dot: 'bg-rose-600',
        };
      default:
        return {
          label: status,
          bg: 'bg-slate-100 text-slate-700 border-slate-300',
          dot: 'bg-slate-500',
        };
    }
  };

  const config = getBadgeConfig();
  const sizeClasses = size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-xs tracking-wide';

  return (
    <span
      className={`inline-flex items-center gap-1.5 font-medium rounded border ${config.bg} ${sizeClasses}`}
      role="status"
    >
      <span className={`w-1.5 h-1.5 rounded-full ${config.dot}`} aria-hidden="true" />
      {config.label}
    </span>
  );
};
