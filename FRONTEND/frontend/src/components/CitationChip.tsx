// frontend/src/components/CitationChip.tsx
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { citationsApi } from '../api/endpoints';

interface CitationChipProps {
  citationId: string;
  index?: number;
}

export const CitationChip: React.FC<CitationChipProps> = ({ citationId, index }) => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);

  const handleClick = async (e: React.MouseEvent) => {
    e.stopPropagation();
    e.preventDefault();
    if (loading) return;

    setLoading(true);
    try {
      const target = await citationsApi.get(citationId);
      navigate(`/viewer/${encodeURIComponent(target.doc_id)}?page=${target.page}&citation_id=${encodeURIComponent(target.citation_id)}`);
    } catch {
      // Fallback if citation lookup fails: extract doc_id and page from chunk_id syntax if available
      // chunk_id = {doc_id}-p{page}-c{n}
      const parts = citationId.match(/^([a-f0-9]+)-p(\d+)/i);
      if (parts) {
        navigate(`/viewer/${parts[1]}?page=${parts[2]}&citation_id=${encodeURIComponent(citationId)}`);
      } else {
        navigate(`/viewer/sample?page=1&citation_id=${encodeURIComponent(citationId)}`);
      }
    } finally {
      setLoading(false);
    }
  };

  const label = index !== undefined ? `[${index}]` : `[ref]`;

  return (
    <button
      type="button"
      onClick={handleClick}
      disabled={loading}
      className="citation-chip inline-flex items-center text-xs font-semibold px-1 py-0.2 mx-0.5 rounded text-gov-800 bg-gov-100 hover:bg-gov-200 border border-gov-300 focus:outline-none focus:ring-1 focus:ring-gov-700"
      title={`Official source citation: ${citationId}. Click to view verified passage in document.`}
      aria-label={`Citation reference ${index ?? citationId}. Opens PDF evidence viewer.`}
    >
      {loading ? '...' : label}
    </button>
  );
};
