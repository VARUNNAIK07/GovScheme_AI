// frontend/src/components/CitedText.tsx
import React from 'react';
import { CitationChip } from './CitationChip';
import type { CitedSentence } from '../types/contracts';

interface CitedTextProps {
  sentences?: CitedSentence[] | null;
  emptyFallback?: string;
  className?: string;
}

export const CitedText: React.FC<CitedTextProps> = ({
  sentences,
  emptyFallback = 'Not stated in the source document',
  className = '',
}) => {
  if (!sentences || sentences.length === 0) {
    return (
      <p className={`text-slate-500 italic text-sm ${className}`}>
        {emptyFallback}
      </p>
    );
  }

  // Running citation index across the sentences in this block
  let citationCounter = 1;

  return (
    <div className={`space-y-2 text-slate-800 leading-relaxed ${className}`}>
      {sentences.map((item, sIndex) => {
        const sentenceCitations = item.citation_ids || [];
        return (
          <span key={sIndex} className="inline mr-1">
            <span>{item.text}</span>
            {sentenceCitations.map((cid, cIndex) => (
              <CitationChip
                key={`${cid}-${cIndex}`}
                citationId={cid}
                index={citationCounter++}
              />
            ))}
            {' '}
          </span>
        );
      })}
    </div>
  );
};
