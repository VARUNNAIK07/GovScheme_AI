// frontend/src/components/SchemeCard.tsx
import React from 'react';
import { Link } from 'react-router-dom';
import { EligibilityBadge } from './EligibilityBadge';
import type { LibraryCard } from '../types/contracts';
import { sectorLabel } from '../types/contracts';

interface SchemeCardProps {
  card: LibraryCard;
  showMatchPercent?: boolean;
  selectable?: boolean;
  selected?: boolean;
  onSelectToggle?: (schemeId: string) => void;
}

export const SchemeCard: React.FC<SchemeCardProps> = ({
  card,
  showMatchPercent = true,
  selectable = false,
  selected = false,
  onSelectToggle,
}) => {
  return (
    <div
      className={`border rounded-lg p-5 bg-white transition-shadow hover:shadow-md flex flex-col justify-between ${
        selected ? 'border-gov-600 ring-1 ring-gov-600 bg-gov-50/20' : 'border-slate-200'
      }`}
    >
      <div>
        {/* Header row: Sector and Checkbox or Relevance */}
        <div className="flex items-start justify-between gap-3 mb-2.5">
          <div className="flex items-center gap-2">
            {selectable && (
              <input
                type="checkbox"
                checked={selected}
                onChange={() => onSelectToggle && onSelectToggle(card.scheme_id)}
                className="w-4 h-4 text-gov-700 rounded border-slate-300 focus:ring-gov-600 cursor-pointer"
                aria-label={`Select ${card.name} for comparison`}
              />
            )}
            <span className="text-xs uppercase font-semibold tracking-wider text-slate-500 bg-slate-100 px-2 py-0.5 rounded">
              {sectorLabel(card.sector)}
            </span>
          </div>

          {showMatchPercent && card.match_percent !== null && card.match_percent !== undefined && (
            <div className="text-right">
              <span className="text-lg font-bold text-gov-800 tabular-nums">
                {card.match_percent}%
              </span>
              <span className="block text-[11px] text-slate-500 font-medium">
                relevance match
              </span>
            </div>
          )}
        </div>

        {/* Scheme Name */}
        <h3 className="text-base font-semibold text-slate-900 leading-snug mb-1">
          <Link
            to={`/schemes/${encodeURIComponent(card.scheme_id)}`}
            className="hover:text-gov-700 hover:underline"
          >
            {card.name}
          </Link>
        </h3>

        {/* Department */}
        <p className="text-xs text-slate-500 mb-3 line-clamp-1">
          {card.department}
        </p>

        {/* Eligibility Status & Reason */}
        <div className="pt-2 border-t border-slate-100 mb-4">
          <div className="mb-1.5">
            <EligibilityBadge status={card.eligibility_status} size="sm" />
          </div>
          <p className="text-xs text-slate-600 leading-relaxed line-clamp-2">
            {card.eligibility_reason}
          </p>
        </div>
      </div>

      {/* Action Footer */}
      <div className="pt-2 flex items-center justify-between text-xs font-medium">
        <Link
          to={`/schemes/${encodeURIComponent(card.scheme_id)}`}
          className="text-gov-700 hover:text-gov-900 hover:underline font-semibold flex items-center gap-1"
        >
          View details & evidence &rarr;
        </Link>
      </div>
    </div>
  );
};
