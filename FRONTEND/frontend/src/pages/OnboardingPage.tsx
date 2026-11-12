// frontend/src/pages/OnboardingPage.tsx
import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { ShieldCheck, AlertCircle, ArrowRight } from 'lucide-react';
import { onboardingApi } from '../api/endpoints';
import { QuestionInput } from '../components/QuestionInput';
import { LoadingState, ErrorState } from '../components/States';
import { useAuth } from '../context/AuthContext';
import type { Question } from '../types/contracts';

export const OnboardingPage: React.FC = () => {
  const navigate = useNavigate();
  const { refreshMe } = useAuth();

  const [question, setQuestion] = useState<Question | null>(null);
  const [currentValue, setCurrentValue] = useState<any>('');
  const [errors, setErrors] = useState<string[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [fetchError, setFetchError] = useState<string | null>(null);

  const fetchNextQuestion = async () => {
    setLoading(true);
    setFetchError(null);
    try {
      const res = await onboardingApi.next();
      if (res.done || !res.question) {
        await refreshMe();
        navigate('/library', { replace: true });
        return;
      }
      setQuestion(res.question);
      // Initialize default value based on type
      if (res.question.type === 'multi_choice') {
        setCurrentValue([]);
      } else if (res.question.type === 'boolean') {
        setCurrentValue(null);
      } else {
        setCurrentValue('');
      }
      setErrors([]);
    } catch (err: any) {
      setFetchError(err.message || 'Could not load onboarding questions.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchNextQuestion();
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!question) return;

    setSubmitting(true);
    setErrors([]);

    try {
      const res = await onboardingApi.answer({
        field: question.field,
        value: currentValue,
      });

      if (!res.ok) {
        setErrors(res.errors.length > 0 ? res.errors : ['Invalid response. Please check input.']);
        return;
      }

      if (res.done) {
        await refreshMe();
        navigate('/library', { replace: true });
      } else if (res.question) {
        setQuestion(res.question);
        if (res.question.type === 'multi_choice') {
          setCurrentValue([]);
        } else if (res.question.type === 'boolean') {
          setCurrentValue(null);
        } else {
          setCurrentValue('');
        }
      } else {
        await fetchNextQuestion();
      }
    } catch (err: any) {
      setErrors([err.message || 'Failed to submit response. Please try again.']);
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
        <LoadingState message="Loading your eligibility questionnaire..." />
      </div>
    );
  }

  if (fetchError || !question) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
        <ErrorState
          title="Questionnaire Error"
          message={fetchError || 'No active onboarding questions found.'}
          onRetry={fetchNextQuestion}
        />
      </div>
    );
  }

  const progressPercent = Math.min(100, Math.max(0, Math.round(question.progress * 100)));

  return (
    <div className="min-h-screen bg-slate-100 flex flex-col justify-center py-12 px-4 sm:px-6 lg:px-8">
      {/* Questionnaire Card */}
      <div className="sm:mx-auto sm:w-full sm:max-w-2xl">
        <div className="bg-white shadow-sm border border-slate-200 rounded-lg overflow-hidden">
          {/* Header & Progress Bar */}
          <div className="px-6 py-4 bg-gov-900 text-white flex items-center justify-between">
            <div className="flex items-center gap-2">
              <ShieldCheck className="w-5 h-5 text-emerald-400" />
              <span className="font-semibold text-sm">Citizen Profile Onboarding</span>
            </div>
            <span className="text-xs text-gov-200 tabular-nums">
              {progressPercent}% Complete
            </span>
          </div>

          <div
            className="w-full bg-gov-950 h-1.5"
            role="progressbar"
            aria-valuenow={progressPercent}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label="Onboarding progress"
          >
            <div
              className="bg-emerald-500 h-1.5 transition-all duration-300 ease-out"
              style={{ width: `${progressPercent}%` }}
            />
          </div>

          {/* Form Content */}
          <div className="p-6 sm:p-8">
            <div className="mb-6">
              <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider block mb-1">
                Field: {question.field.replace(/_/g, ' ')}
              </span>
              <h2 className="text-xl font-bold text-slate-900 leading-snug">
                {question.text}
              </h2>
            </div>

            {/* Inline validation errors */}
            {errors.length > 0 && (
              <div
                className="mb-5 p-3 rounded-md bg-rose-50 border border-rose-200 space-y-1 text-xs text-rose-800"
                role="alert"
              >
                <div className="flex items-center gap-1.5 font-semibold text-rose-900">
                  <AlertCircle className="w-4 h-4 text-rose-600" />
                  <span>Validation Warning</span>
                </div>
                {errors.map((err, i) => (
                  <p key={i} className="pl-5.5">{err}</p>
                ))}
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-6">
              <QuestionInput
                question={question}
                value={currentValue}
                onChange={setCurrentValue}
                disabled={submitting}
              />

              <div className="pt-4 border-t border-slate-200 flex items-center justify-between">
                <span className="text-xs text-slate-600">
                  Step advances automatically upon verification
                </span>
                <button
                  type="submit"
                  disabled={submitting}
                  className="inline-flex items-center gap-2 px-5 py-2.5 rounded-md text-sm font-semibold text-white bg-gov-700 hover:bg-gov-800 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-gov-700 disabled:opacity-50 transition-colors cursor-pointer"
                >
                  <span>{submitting ? 'Verifying...' : 'Next Question'}</span>
                  <ArrowRight className="w-4 h-4" />
                </button>
              </div>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
};
