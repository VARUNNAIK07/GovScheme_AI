// frontend/src/pages/ComparisonPage.tsx
import React, { useState, useEffect } from 'react';
import { GitCompare, Lightbulb, AlertCircle } from 'lucide-react';
import { comparisonApi } from '../api/endpoints';
import { SchemeCard } from '../components/SchemeCard';
import { ComparisonTable } from '../components/ComparisonTable';
import { CitedText } from '../components/CitedText';
import { LoadingState, EmptyState, ErrorState } from '../components/States';
import type { LibraryCard, ComparisonResponse } from '../types/contracts';

export const ComparisonPage: React.FC = () => {
  const [options, setOptions] = useState<LibraryCard[]>([]);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [comparisonResult, setComparisonResult] = useState<ComparisonResponse | null>(null);

  const [loadingOptions, setLoadingOptions] = useState<boolean>(true);
  const [comparing, setComparing] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // 1. Fetch available options (top 5 schemes)
  const fetchOptions = async () => {
    setLoadingOptions(true);
    setError(null);
    try {
      const cards = await comparisonApi.getOptions();
      setOptions(cards);
      // Preselect first 2-3 cards if available
      const initial = cards.slice(0, Math.min(3, cards.length)).map((c) => c.scheme_id);
      setSelectedIds(initial);

      // Auto-run comparison if 2+ options available
      if (initial.length >= 2) {
        runComparison(initial);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to load schemes for comparison.');
    } finally {
      setLoadingOptions(false);
    }
  };

  useEffect(() => {
    fetchOptions();
  }, []);

  // 2. Run comparison API call
  const runComparison = async (ids: string[]) => {
    if (ids.length < 2 || ids.length > 5) return;
    setComparing(true);
    setError(null);
    try {
      const result = await comparisonApi.compare(ids);
      setComparisonResult(result);
    } catch (err: any) {
      setError(err.message || 'Comparison request failed.');
    } finally {
      setComparing(false);
    }
  };

  const handleToggle = (schemeId: string) => {
    setSelectedIds((prev) => {
      const exists = prev.includes(schemeId);
      if (exists) {
        return prev.filter((id) => id !== schemeId);
      } else {
        if (prev.length >= 5) {
          return prev; // cap at 5
        }
        return [...prev, schemeId];
      }
    });
  };

  if (loadingOptions) {
    return <LoadingState message="Loading scheme options for comparative evaluation..." />;
  }

  const isValidCount = selectedIds.length >= 2 && selectedIds.length <= 5;

  // Build lookup mapping of schemeId -> schemeName
  const schemeNameMap = options.reduce<Record<string, string>>((acc, curr) => {
    acc[curr.scheme_id] = curr.name;
    return acc;
  }, {});

  return (
    <div className="space-y-8">
      {/* Page Header */}
      <div className="pb-5 border-b border-slate-200">
        <h1 className="text-2xl font-bold tracking-tight text-slate-900 mb-1">
          Scheme Comparison Matrix
        </h1>
        <p className="text-sm text-slate-600">
          Compare 2 to 5 high-relevance schemes side by side across verified criteria and cited evidence.
        </p>
      </div>

      {/* Top 5 Scheme Selection Area */}
      <section aria-labelledby="selection-heading">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
          <div>
            <h2 id="selection-heading" className="text-sm font-bold text-slate-900 uppercase tracking-wider">
              Top Recommended Schemes
            </h2>
            <p className="text-xs text-slate-500">
              Select 2 to 5 schemes to compare. Currently selected: {selectedIds.length}
            </p>
          </div>

          <button
            type="button"
            onClick={() => runComparison(selectedIds)}
            disabled={!isValidCount || comparing}
            className={`inline-flex items-center gap-2 px-4 py-2 rounded-md text-xs font-semibold text-white transition-colors cursor-pointer ${
              isValidCount && !comparing
                ? 'bg-gov-700 hover:bg-gov-800'
                : 'bg-slate-300 text-slate-500 cursor-not-allowed'
            }`}
          >
            <GitCompare className="w-4 h-4" />
            <span>{comparing ? 'Evaluating...' : 'Run Comparative Matrix'}</span>
          </button>
        </div>

        {options.length === 0 ? (
          <EmptyState
            title="No Candidates Found"
            description="No top scheme cards available for comparison."
          />
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {options.map((card) => {
              const isSelected = selectedIds.includes(card.scheme_id);
              return (
                <SchemeCard
                  key={card.scheme_id}
                  card={card}
                  showMatchPercent={true}
                  selectable={true}
                  selected={isSelected}
                  onSelectToggle={handleToggle}
                />
              );
            })}
          </div>
        )}
      </section>

      {/* Validation banner if selection count invalid */}
      {!isValidCount && (
        <div className="p-3 bg-amber-50 border border-amber-200 rounded-md flex items-center gap-2 text-xs text-amber-800">
          <AlertCircle className="w-4 h-4 text-amber-600 flex-shrink-0" />
          <span>Please select at least 2 and at most 5 schemes to generate the comparison matrix.</span>
        </div>
      )}

      {/* Comparison Loading / Error / Content */}
      {comparing && (
        <LoadingState message="Generating structured comparison matrix and factual insights..." />
      )}

      {error && (
        <ErrorState
          title="Comparison Failed"
          message={error}
          onRetry={() => runComparison(selectedIds)}
        />
      )}

      {comparisonResult && !comparing && (
        <div className="space-y-8 pt-4 border-t border-slate-200">
          {/* Matrix Section */}
          <section aria-labelledby="matrix-heading">
            <h2 id="matrix-heading" className="text-lg font-bold text-slate-900 mb-3">
              Comparative Analysis Matrix
            </h2>
            <ComparisonTable
              matrix={comparisonResult.matrix}
              schemeNames={schemeNameMap}
            />
          </section>

          {/* Insights List */}
          <section
            aria-labelledby="insights-heading"
            className="bg-white border border-slate-200 rounded-lg p-6 shadow-xs"
          >
            <div className="flex items-center gap-2 mb-3">
              <Lightbulb className="w-4 h-4 text-amber-600" />
              <h2 id="insights-heading" className="text-base font-bold text-slate-900">
                AI Cross-Scheme Insights & Synergy Notes
              </h2>
            </div>
            <p className="text-xs text-slate-500 mb-4">
              Synthesized by the comparison agent grounded strictly in official source citations.
            </p>
            <CitedText sentences={comparisonResult.insights.insights} />
          </section>
        </div>
      )}
    </div>
  );
};
