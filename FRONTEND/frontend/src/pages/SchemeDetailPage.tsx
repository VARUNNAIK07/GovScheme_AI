// frontend/src/pages/SchemeDetailPage.tsx
import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  ExternalLink,
  FileText,
  CheckCircle2,
  XCircle,
  HelpCircle,
  AlertTriangle,
  ArrowLeft,
  Calendar,
  Building,
  Tag,
} from 'lucide-react';
import { schemesApi } from '../api/endpoints';
import { EligibilityBadge } from '../components/EligibilityBadge';
import { CitedText } from '../components/CitedText';
import { CitationChip } from '../components/CitationChip';
import { LoadingState, ErrorState } from '../components/States';
import type { SchemeDetailResponse, RuleCheckResult } from '../types/contracts';
import { sectorLabel } from '../types/contracts';

export const SchemeDetailPage: React.FC = () => {
  const { scheme_id } = useParams<{ scheme_id: string }>();
  const [data, setData] = useState<SchemeDetailResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchDetail = async () => {
    if (!scheme_id) return;
    setLoading(true);
    setError(null);
    try {
      const response = await schemesApi.getDetail(scheme_id);
      setData(response);
    } catch (err: any) {
      setError(err.message || 'Unable to retrieve scheme details.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDetail();
  }, [scheme_id]);

  if (loading) {
    return <LoadingState message="Fetching scheme guidelines and citation evidence..." />;
  }

  if (error || !data) {
    return (
      <ErrorState
        title="Scheme Detail Not Found"
        message={error || 'Could not find details for this scheme.'}
        onRetry={fetchDetail}
      />
    );
  }

  const { scheme, eligibility, summary, evidence } = data;

  const renderRuleCheckIcon = (result: RuleCheckResult) => {
    switch (result) {
      case 'pass':
        return <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />;
      case 'fail':
        return <XCircle className="w-4 h-4 text-rose-600 flex-shrink-0" />;
      case 'unknown':
        return <HelpCircle className="w-4 h-4 text-amber-600 flex-shrink-0" />;
      case 'ambiguous':
      default:
        return <AlertTriangle className="w-4 h-4 text-sky-600 flex-shrink-0" />;
    }
  };

  return (
    <div className="space-y-8 max-w-5xl">
      {/* Back Link */}
      <div>
        <Link
          to="/library"
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-gov-700 hover:text-gov-900 transition-colors"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Back to Library</span>
        </Link>
      </div>

      {/* Hero Scheme Header */}
      <div className="bg-white border border-slate-200 rounded-lg p-6 sm:p-8 shadow-xs">
        <div className="flex flex-wrap items-center gap-2 mb-3">
          <span className="text-xs uppercase font-bold tracking-wider text-slate-500 bg-slate-100 px-2.5 py-1 rounded">
            {sectorLabel(scheme.sector)}
          </span>
          <span className="text-xs font-semibold text-gov-800 bg-gov-50 px-2.5 py-1 rounded capitalize">
            {scheme.level} Scheme
          </span>
          <EligibilityBadge status={eligibility.status} />
          {scheme.facts_status && (
            <span className="text-xs font-medium text-slate-500 bg-slate-50 border border-slate-200 px-2 py-0.5 rounded">
              Status: {scheme.facts_status}
            </span>
          )}
        </div>

        <h1 className="text-2xl sm:text-3xl font-bold text-slate-900 tracking-tight mb-2">
          {scheme.name}
        </h1>

        <div className="flex flex-wrap items-center gap-y-2 gap-x-6 text-xs text-slate-500 pt-2 border-t border-slate-100 mt-4">
          <div className="flex items-center gap-1.5">
            <Building className="w-3.5 h-3.5 text-slate-400" />
            <span>{scheme.department || 'Not stated in the source document'}</span>
          </div>
          {scheme.max_benefit_inr !== null && (
            <div className="flex items-center gap-1.5 font-semibold text-emerald-800">
              <Tag className="w-3.5 h-3.5 text-emerald-600" />
              <span>Max Financial Benefit: ₹{scheme.max_benefit_inr.toLocaleString('en-IN')}</span>
            </div>
          )}
          <div className="flex items-center gap-1.5">
            <Calendar className="w-3.5 h-3.5 text-slate-400" />
            <span>Verified: {scheme.last_checked || 'Not stated in the source document'}</span>
          </div>
        </div>
      </div>

      {/* Main Sections Grid */}
      <div className="space-y-6">
        {/* Section 1: Overview */}
        <section className="bg-white border border-slate-200 rounded-lg p-6">
          <h2 className="text-base font-bold text-slate-900 mb-3 flex items-center gap-2">
            <span>Scheme Overview</span>
          </h2>
          <CitedText sentences={summary.overview} />
        </section>

        {/* Section 2: Why it is relevant */}
        <section className="bg-white border border-slate-200 rounded-lg p-6">
          <h2 className="text-base font-bold text-slate-900 mb-3 flex items-center gap-2">
            <span>Why This Scheme is Relevant to You</span>
          </h2>
          <CitedText sentences={summary.relevance} />
        </section>

        {/* Section 3: Eligibility Checks */}
        <section className="bg-white border border-slate-200 rounded-lg p-6">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 mb-4">
            <div>
              <h2 className="text-base font-bold text-slate-900">
                Deterministic Eligibility Checks
              </h2>
              <p className="text-xs text-slate-500">
                Evaluated against the frozen criteria rules extracted from official scheme gazettes.
              </p>
            </div>
            <EligibilityBadge status={eligibility.status} />
          </div>

          <div className="mb-4">
            <CitedText sentences={summary.eligibility} />
          </div>

          {/* Detailed rule breakdown */}
          <div className="mt-4 border border-slate-200 rounded-md overflow-hidden">
            <div className="bg-slate-50 px-4 py-2 border-b border-slate-200 text-xs font-semibold text-slate-700">
              Rule Verification Breakdown
            </div>
            <ul className="divide-y divide-slate-100 text-xs">
              {eligibility.checks.length === 0 ? (
                <li className="p-4 text-slate-500 italic">
                  Not stated in the source document
                </li>
              ) : (
                eligibility.checks.map((chk, idx) => (
                  <li key={chk.rule_id || idx} className="p-3.5 flex items-start justify-between gap-3 bg-white">
                    <div className="flex items-start gap-2.5">
                      <div className="mt-0.5">{renderRuleCheckIcon(chk.result)}</div>
                      <div>
                        <span className="font-semibold capitalize text-slate-900 mr-2">
                          {chk.result}:
                        </span>
                        <span className="text-slate-700">{chk.reason}</span>
                      </div>
                    </div>
                    {chk.citation_id && (
                      <div className="flex-shrink-0">
                        <CitationChip citationId={chk.citation_id} />
                      </div>
                    )}
                  </li>
                ))
              )}
            </ul>
          </div>

          {eligibility.missing_fields && eligibility.missing_fields.length > 0 && (
            <div className="mt-3 p-3 bg-amber-50 border border-amber-200 rounded text-xs text-amber-900">
              <strong>Missing Profile Attributes:</strong> {eligibility.missing_fields.join(', ')}.
              Please update your profile to resolve partial status.
            </div>
          )}
        </section>

        {/* Section 4: Benefits */}
        <section className="bg-white border border-slate-200 rounded-lg p-6">
          <h2 className="text-base font-bold text-slate-900 mb-3">
            Benefits & Financial Entitlements
          </h2>
          <CitedText sentences={summary.benefits} />

          {scheme.benefits && scheme.benefits.length > 0 && (
            <ul className="mt-4 list-disc list-inside space-y-1.5 text-xs text-slate-700 pl-2">
              {scheme.benefits.map((b, i) => (
                <li key={i}>{b}</li>
              ))}
            </ul>
          )}
        </section>

        {/* Section 5: Documents Required */}
        <section className="bg-white border border-slate-200 rounded-lg p-6">
          <h2 className="text-base font-bold text-slate-900 mb-3">
            Documents Required for Application
          </h2>
          <CitedText sentences={summary.documents} />

          {scheme.documents_required && scheme.documents_required.length > 0 ? (
            <ul className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
              {scheme.documents_required.map((doc, i) => (
                <li key={i} className="flex items-center gap-2 p-2 rounded bg-slate-50 border border-slate-200 text-slate-800">
                  <FileText className="w-3.5 h-3.5 text-gov-700 flex-shrink-0" />
                  <span>{doc}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-3 text-xs text-slate-500 italic">Not stated in the source document</p>
          )}
        </section>

        {/* Section 6: Application Steps */}
        <section className="bg-white border border-slate-200 rounded-lg p-6">
          <h2 className="text-base font-bold text-slate-900 mb-3">
            Application Steps & Procedure
          </h2>
          <CitedText sentences={summary.application} />

          {scheme.application_steps && scheme.application_steps.length > 0 ? (
            <ol className="mt-4 space-y-2.5 text-xs text-slate-800">
              {scheme.application_steps.map((step, i) => (
                <li key={i} className="flex items-start gap-3 p-2.5 rounded bg-slate-50 border border-slate-200">
                  <span className="w-5 h-5 rounded-full bg-gov-700 text-white font-bold flex items-center justify-center text-[10px] flex-shrink-0 mt-0.5">
                    {i + 1}
                  </span>
                  <span className="leading-relaxed">{step}</span>
                </li>
              ))}
            </ol>
          ) : (
            <p className="mt-3 text-xs text-slate-500 italic">Not stated in the source document</p>
          )}
        </section>

        {/* Section 7: Official Portals & Evidence Files */}
        <section className="bg-white border border-slate-200 rounded-lg p-6">
          <h2 className="text-base font-bold text-slate-900 mb-4">
            Official Government Portals & Sources
          </h2>
          <div className="flex flex-wrap gap-3">
            {scheme.official_url ? (
              <a
                href={scheme.official_url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-semibold rounded border border-slate-300 bg-white hover:bg-slate-50 text-slate-800 transition-colors"
              >
                <span>Official Scheme Portal</span>
                <ExternalLink className="w-3.5 h-3.5 text-slate-500" />
              </a>
            ) : (
              <span className="text-xs text-slate-500 italic">Official portal: Not stated in the source document</span>
            )}

            {scheme.application_url && (
              <a
                href={scheme.application_url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-semibold rounded bg-gov-700 hover:bg-gov-800 text-white transition-colors"
              >
                <span>Direct Application Link</span>
                <ExternalLink className="w-3.5 h-3.5 text-white" />
              </a>
            )}

            {evidence && evidence.length > 0 && (
              <Link
                to={`/viewer/${evidence[0].doc_id}?page=${evidence[0].page}&citation_id=${evidence[0].citation_id}`}
                className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-semibold rounded border border-gov-300 bg-gov-50 text-gov-800 hover:bg-gov-100 transition-colors"
              >
                <FileText className="w-3.5 h-3.5 text-gov-700" />
                <span>Open Source PDF Document</span>
              </Link>
            )}
          </div>
        </section>
      </div>
    </div>
  );
};
