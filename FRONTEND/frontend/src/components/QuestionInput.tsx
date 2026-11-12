// frontend/src/components/QuestionInput.tsx
import React from 'react';
import type { Question } from '../types/contracts';

interface QuestionInputProps {
  question: Question;
  value: any;
  onChange: (val: any) => void;
  disabled?: boolean;
  autoFocus?: boolean;
}

// Long option lists (e.g. 36 states) use a dropdown instead of a grid of radio buttons
const DROPDOWN_THRESHOLD = 10;

export const QuestionInput: React.FC<QuestionInputProps> = ({
  question,
  value,
  onChange,
  disabled = false,
  autoFocus = true,
}) => {
  const { type, options, field } = question;
  const label = (opt: string) => question.option_labels?.[opt] ?? opt.replace(/_/g, ' ');

  switch (type) {
    case 'number':
      return (
        <div className="space-y-1.5">
          <input
            id={field}
            type="number"
            value={value ?? ''}
            onChange={(e) => onChange(e.target.value === '' ? '' : Number(e.target.value))}
            disabled={disabled}
            placeholder="Enter numeric value"
            className="w-full max-w-md px-3.5 py-2.5 bg-white border border-slate-300 rounded-md text-sm text-slate-900 focus:ring-2 focus:ring-gov-700 focus:border-gov-700"
            autoFocus={autoFocus}
          />
        </div>
      );

    case 'single_choice':
      if (options.length > DROPDOWN_THRESHOLD) {
        return (
          <select
            id={field}
            value={value ?? ''}
            onChange={(e) => onChange(e.target.value === '' ? null : e.target.value)}
            disabled={disabled}
            className="w-full max-w-md px-3.5 py-2.5 bg-white border border-slate-300 rounded-md text-sm text-slate-900 focus:ring-2 focus:ring-gov-700 focus:border-gov-700"
          >
            <option value="">Select…</option>
            {options.map((opt) => (
              <option key={opt} value={opt}>
                {label(opt)}
              </option>
            ))}
          </select>
        );
      }
      return (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 max-w-xl">
          {options.map((opt) => {
            const isSelected = value === opt;
            return (
              <label
                key={opt}
                className={`flex items-center gap-3 p-3 rounded-md border text-sm font-medium cursor-pointer transition-colors ${
                  isSelected
                    ? 'border-gov-700 bg-gov-50/60 text-gov-900 ring-1 ring-gov-700'
                    : 'border-slate-200 bg-white text-slate-700 hover:bg-slate-50'
                } ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
              >
                <input
                  type="radio"
                  name={field}
                  value={opt}
                  checked={isSelected}
                  onChange={() => onChange(opt)}
                  disabled={disabled}
                  className="w-4 h-4 text-gov-700 border-slate-300 focus:ring-gov-700 cursor-pointer"
                />
                <span>{label(opt)}</span>
              </label>
            );
          })}
        </div>
      );

    case 'multi_choice': {
      const selectedList: string[] = Array.isArray(value) ? value : [];
      const handleToggle = (opt: string) => {
        if (selectedList.includes(opt)) {
          onChange(selectedList.filter((item) => item !== opt));
        } else {
          onChange([...selectedList, opt]);
        }
      };

      return (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 max-w-xl">
          {options.map((opt) => {
            const isSelected = selectedList.includes(opt);
            return (
              <label
                key={opt}
                className={`flex items-center gap-3 p-3 rounded-md border text-sm font-medium cursor-pointer transition-colors ${
                  isSelected
                    ? 'border-gov-700 bg-gov-50/60 text-gov-900 ring-1 ring-gov-700'
                    : 'border-slate-200 bg-white text-slate-700 hover:bg-slate-50'
                } ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
              >
                <input
                  type="checkbox"
                  value={opt}
                  checked={isSelected}
                  onChange={() => handleToggle(opt)}
                  disabled={disabled}
                  className="w-4 h-4 text-gov-700 border-slate-300 rounded focus:ring-gov-700 cursor-pointer"
                />
                <span>{label(opt)}</span>
              </label>
            );
          })}
        </div>
      );
    }

    case 'boolean':
      return (
        <div className="flex gap-4 max-w-md">
          {[
            { label: 'Yes', val: true },
            { label: 'No', val: false },
          ].map(({ label, val }) => {
            const isSelected = value === val;
            return (
              <label
                key={label}
                className={`flex-1 flex items-center justify-center gap-2 p-3.5 rounded-md border text-sm font-semibold cursor-pointer transition-colors ${
                  isSelected
                    ? 'border-gov-700 bg-gov-50/60 text-gov-900 ring-1 ring-gov-700'
                    : 'border-slate-200 bg-white text-slate-700 hover:bg-slate-50'
                } ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
              >
                <input
                  type="radio"
                  name={field}
                  checked={isSelected}
                  onChange={() => onChange(val)}
                  disabled={disabled}
                  className="w-4 h-4 text-gov-700 border-slate-300 focus:ring-gov-700 cursor-pointer"
                />
                <span>{label}</span>
              </label>
            );
          })}
        </div>
      );

    case 'text':
    default:
      return (
        <div className="space-y-1.5">
          <input
            id={field}
            type="text"
            value={value ?? ''}
            onChange={(e) => onChange(e.target.value)}
            disabled={disabled}
            placeholder="Type your answer"
            className="w-full max-w-md px-3.5 py-2.5 bg-white border border-slate-300 rounded-md text-sm text-slate-900 focus:ring-2 focus:ring-gov-700 focus:border-gov-700"
            autoFocus={autoFocus}
          />
        </div>
      );
  }
};
