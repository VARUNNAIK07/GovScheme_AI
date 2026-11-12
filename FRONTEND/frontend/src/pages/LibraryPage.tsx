// frontend/src/pages/LibraryPage.tsx
import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Sparkles, Layers, SlidersHorizontal, Info } from 'lucide-react';
import { libraryApi } from '../api/endpoints';
import { SchemeCard } from '../components/SchemeCard';
import { LoadingState, EmptyState, ErrorState } from '../components/States';
import type { LibraryResult } from '../types/contracts';

export const LibraryPage: React.FC = () => {
  const [libraryData, setLibraryData] = useState<LibraryResult | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchLibrary = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await libraryApi.get();
      setLibraryData(data);
    } catch (err: any) {
      setError(err.message || 'Unable to retrieve your scheme library.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLibrary();
  }, []);

  if (loading) {
    return <LoadingState message="Evaluating your profile against official scheme guidelines..." />;
  }

  if (error || !libraryData) {
    return (
      <ErrorState
        title="Scheme Library Error"
        message={error || 'Could not load schemes.'}
        onRetry={fetchLibrary}
      />
    );
  }

  const { top, more, profile_version } = libraryData;
  const hasSchemes = top.length > 0 || more.length > 0;

  return (
    <div className="space-y-8">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-5 border-b border-slate-200">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">
              Your Scheme Library
            </h1>
            <span className="text-xs bg-slate-100 text-slate-600 px-2 py-0.5 rounded font-mono font-medium">
              v{profile_version}
            </span>
          </div>
          <p className="text-sm text-slate-600">
            Personalized public schemes matched deterministically with citation-backed criteria.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Link
            to="/profile"
            className="inline-flex items-center gap-2 px-3.5 py-2 text-xs font-semibold rounded-md border border-slate-300 bg-white text-slate-700 hover:bg-slate-50 transition-colors"
          >
            <SlidersHorizontal className="w-3.5 h-3.5 text-slate-500" />
            <span>Update Profile</span>
          </Link>
          <Link
            to="/comparison"
            className="inline-flex items-center gap-2 px-3.5 py-2 text-xs font-semibold rounded-md bg-gov-700 text-white hover:bg-gov-800 transition-colors"
          >
            <span>Compare Schemes</span>
          </Link>
        </div>
      </div>

      {/* Audit Banner */}
      <div className="bg-gov-50/70 border border-gov-200 rounded-md p-3.5 flex items-start gap-3 text-xs text-gov-900">
        <Info className="w-4 h-4 text-gov-600 flex-shrink-0 mt-0.5" />
        <p className="leading-relaxed">
          <strong>Relevance Match Notice:</strong> Percentages reflect mathematical alignment with your declared beneficiary tags, needs, and sectors using the published formula. They represent topical relevance, not an administrative grant approval.
        </p>
      </div>

      {!hasSchemes ? (
        <EmptyState
          title="No Matching Schemes"
          description="We could not find any active schemes matching your current profile attributes. Try updating your profile sectors or needs."
          actionText="Edit Profile"
          onAction={() => window.location.assign('/profile')}
        />
      ) : (
        <div className="space-y-10">
          {/* Section 1: Recommended for you (Top 5) */}
          <section aria-labelledby="recommended-heading">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-gov-700" />
                <h2 id="recommended-heading" className="text-lg font-bold text-slate-900">
                  Recommended for you
                </h2>
              </div>
              <span className="text-xs text-slate-500">
                {top.length} {top.length === 1 ? 'scheme' : 'schemes'} evaluated
              </span>
            </div>

            {top.length === 0 ? (
              <p className="text-xs text-slate-500 italic py-4">
                No high-priority recommendations available for this profile version.
              </p>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
                {top.map((card) => (
                  <SchemeCard
                    key={card.scheme_id}
                    card={card}
                    showMatchPercent={true}
                  />
                ))}
              </div>
            )}
          </section>

          {/* Section 2: More in your sectors (Up to 5) */}
          <section aria-labelledby="more-heading" className="pt-4 border-t border-slate-200">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <Layers className="w-4 h-4 text-slate-600" />
                <h2 id="more-heading" className="text-lg font-bold text-slate-900">
                  More in your sectors
                </h2>
              </div>
              <span className="text-xs text-slate-500">
                {more.length} {more.length === 1 ? 'scheme' : 'schemes'} in declared sectors
              </span>
            </div>

            {more.length === 0 ? (
              <p className="text-xs text-slate-500 italic py-4">
                No additional schemes found in your selected sectors.
              </p>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
                {more.map((card) => (
                  <SchemeCard
                    key={card.scheme_id}
                    card={card}
                    showMatchPercent={false}
                  />
                ))}
              </div>
            )}
          </section>
        </div>
      )}
    </div>
  );
};
