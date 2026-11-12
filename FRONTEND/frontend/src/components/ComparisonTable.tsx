// frontend/src/components/ComparisonTable.tsx
import React from 'react';
import { CitationChip } from './CitationChip';
import type { ComparisonMatrix } from '../types/contracts';

interface ComparisonTableProps {
  matrix: ComparisonMatrix;
  schemeNames?: Record<string, string>;
}

const FIELD_LABELS: Record<string, string> = {
  target_group: 'Target Beneficiaries',
  eligibility_status: 'Eligibility Assessment',
  benefits: 'Key Benefits',
  max_benefit_inr: 'Max Financial Benefit',
  documents: 'Required Documentation',
  application_process: 'Application Modalities',
  limitations: 'Exclusions & Limits',
};

export const ComparisonTable: React.FC<ComparisonTableProps> = ({ matrix, schemeNames = {} }) => {
  const { scheme_ids, fields, cells } = matrix;

  const formatFieldName = (f: string) => FIELD_LABELS[f] || f.replace(/_/g, ' ');

  return (
    <div className="overflow-x-auto border border-slate-200 rounded-lg shadow-sm bg-white">
      <table className="w-full border-collapse text-left text-xs">
        <thead>
          <tr className="bg-slate-50 border-b border-slate-200">
            <th className="py-3 px-4 font-semibold text-slate-700 w-44 sticky left-0 bg-slate-50 z-10 border-r border-slate-200">
              Evaluation Criteria
            </th>
            {scheme_ids.map((id) => (
              <th key={id} className="py-3 px-4 font-semibold text-gov-900 border-r border-slate-200 min-w-[220px]">
                {schemeNames[id] || id.toUpperCase()}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {fields.map((field, fIdx) => (
            <tr key={field} className={fIdx % 2 === 0 ? 'bg-white' : 'bg-slate-50/40'}>
              <td className="py-3 px-4 font-medium text-slate-800 sticky left-0 bg-inherit z-10 border-r border-slate-200">
                {formatFieldName(field)}
              </td>
              {scheme_ids.map((id) => {
                const cell = cells[id]?.[field];
                const value = cell?.value;
                const citations = cell?.citation_ids || [];

                return (
                  <td key={`${id}-${field}`} className="py-3 px-4 text-slate-700 leading-relaxed border-r border-slate-200 align-top">
                    {value === null || value === undefined ? (
                      <span className="text-slate-400 italic">
                        Not stated in the source document
                      </span>
                    ) : (
                      <div>
                        <span>{value}</span>
                        {citations.length > 0 && (
                          <span className="inline-block ml-1">
                            {citations.map((cid, cIdx) => (
                              <CitationChip key={`${cid}-${cIdx}`} citationId={cid} index={cIdx + 1} />
                            ))}
                          </span>
                        )}
                      </div>
                    )}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};
