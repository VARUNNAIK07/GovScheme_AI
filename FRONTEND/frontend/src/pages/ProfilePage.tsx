// frontend/src/pages/ProfilePage.tsx
// The form is built from the backend's questioning agent (POST /api/profile/questions), so the
// follow-up questions and the options offered change as the user edits their answers.
import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Save, UserCircle2, CheckCircle2, AlertCircle } from 'lucide-react';
import { profileApi } from '../api/endpoints';
import { useAuth } from '../context/AuthContext';
import { QuestionInput } from '../components/QuestionInput';
import { SchemeCard } from '../components/SchemeCard';
import { LoadingState, ErrorState } from '../components/States';
import type { ProfileAttributes, LibraryResult, Question } from '../types/contracts';

const isEmpty = (v: unknown) => v === null || v === undefined || v === '' || (Array.isArray(v) && v.length === 0);

export const ProfilePage: React.FC = () => {
  const navigate = useNavigate();
  const { profileComplete, refreshMe } = useAuth();

  const [attributes, setAttributes] = useState<ProfileAttributes | null>(null);
  const [questions, setQuestions] = useState<Question[]>([]);
  const [profileVersion, setProfileVersion] = useState<number>(1);
  const [refreshedLibrary, setRefreshedLibrary] = useState<LibraryResult | null>(null);

  const [loading, setLoading] = useState<boolean>(true);
  const [saving, setSaving] = useState<boolean>(false);
  const [savedSuccess, setSavedSuccess] = useState<boolean>(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const requestSeq = useRef(0);

  const loadQuestions = async (draft: ProfileAttributes) => {
    const seq = ++requestSeq.current;
    const qs = await profileApi.questions(draft);
    if (seq === requestSeq.current) setQuestions(qs); // ignore out-of-order responses
  };

  const fetchProfile = async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const p = await profileApi.get();
      setAttributes(p.attributes);
      setProfileVersion(p.version);
      await loadQuestions(p.attributes);
    } catch (err: any) {
      setLoadError(err.message || 'Failed to load your profile.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProfile();
  }, []);

  const handleChange = (field: string, value: unknown) => {
    if (!attributes) return;
    const normalised = value === '' ? null : value;
    const draft = { ...attributes, [field]: normalised } as ProfileAttributes;
    setAttributes(draft);
    setSavedSuccess(false);
    loadQuestions(draft).catch(() => undefined); // the question list just stays as it was
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!attributes) return;
    setSaving(true);
    setSaveError(null);
    setSavedSuccess(false);

    // Send only the questions that apply; hidden follow-ups are cleared by the backend.
    const payload: Partial<ProfileAttributes> = { district: attributes.district };
    for (const q of questions) {
      (payload as any)[q.field] = (attributes as any)[q.field];
    }

    try {
      const res = await profileApi.update(payload);
      setAttributes(res.profile.attributes);
      setProfileVersion(res.profile.version);
      setRefreshedLibrary(res.library);
      setSavedSuccess(true);
      await loadQuestions(res.profile.attributes);
      if (res.profile.complete && !profileComplete) {
        await refreshMe(); // unlocks the rest of the app
      }
    } catch (err: any) {
      setSaveError(err.message || 'Failed to update your profile.');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <LoadingState message="Loading your profile..." />;
  }

  if (loadError || !attributes) {
    return <ErrorState title="Profile Error" message={loadError || 'Profile not found.'} onRetry={fetchProfile} />;
  }

  const unanswered = questions.filter((q) => isEmpty((attributes as any)[q.field])).length;

  return (
    <div className="space-y-8 max-w-4xl">
      {/* Header */}
      <div className="pb-4 border-b border-slate-200">
        <div className="flex flex-wrap items-center gap-2 mb-1">
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">Your Profile</h1>
          <span className="text-xs bg-slate-100 text-slate-700 px-2.5 py-0.5 rounded font-mono font-medium">
            Version v{profileVersion}
          </span>
        </div>
        <p className="text-sm text-slate-600">
          Questions adapt to your answers. Saving re-checks eligibility and refreshes your scheme list.
        </p>
      </div>

      {!profileComplete && (
        <div className="p-4 bg-amber-50 border border-amber-300 rounded-lg text-xs text-amber-900" role="status">
          Your profile is not complete yet ({unanswered} question{unanswered === 1 ? '' : 's'} left). Answer all
          questions and save to see your schemes.
        </div>
      )}

      {saveError && (
        <div className="p-3 rounded-md bg-rose-50 border border-rose-200 text-xs text-rose-800 flex items-center gap-2" role="alert">
          <AlertCircle className="w-4 h-4 text-rose-600" />
          <span>{saveError}</span>
        </div>
      )}

      {savedSuccess && (
        <div className="p-4 bg-emerald-50 border border-emerald-300 rounded-lg flex items-start gap-3 text-emerald-900 text-xs" role="status">
          <CheckCircle2 className="w-5 h-5 text-emerald-600 flex-shrink-0" />
          <div>
            <p className="font-bold text-emerald-950">Profile updated</p>
            <p className="text-emerald-800">Eligibility has been re-checked. Your refreshed schemes are below.</p>
          </div>
        </div>
      )}

      {/* Dynamic form */}
      <form onSubmit={handleSubmit} className="bg-white border border-slate-200 rounded-lg p-6 sm:p-8 space-y-6 shadow-xs">
        {questions.map((q) => (
          <div key={q.question_id} className="pb-5 border-b border-slate-100 last:border-b-0">
            <label htmlFor={q.field} className="block text-sm font-semibold text-slate-800 mb-2">
              {q.text}
            </label>
            <QuestionInput
              question={q}
              value={(attributes as any)[q.field]}
              onChange={(v) => handleChange(q.field, v)}
              disabled={saving}
              autoFocus={false}
            />
          </div>
        ))}

        <div>
          <label htmlFor="attr_district" className="block text-sm font-semibold text-slate-800 mb-2">
            District (optional)
          </label>
          <input
            id="attr_district"
            type="text"
            value={attributes.district ?? ''}
            onChange={(e) => handleChange('district', e.target.value)}
            disabled={saving}
            className="w-full max-w-md px-3.5 py-2.5 bg-white border border-slate-300 rounded-md text-sm text-slate-900 focus:ring-2 focus:ring-gov-700 focus:border-gov-700"
          />
        </div>

        <div className="pt-4 border-t border-slate-200 flex justify-end">
          <button
            type="submit"
            disabled={saving}
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-md text-sm font-semibold text-white bg-gov-700 hover:bg-gov-800 disabled:opacity-50 transition-colors cursor-pointer"
          >
            <Save className="w-4 h-4" />
            <span>{saving ? 'Re-checking eligibility...' : 'Save & refresh my schemes'}</span>
          </button>
        </div>
      </form>

      {/* Refreshed library */}
      {refreshedLibrary && (
        <section className="space-y-6 pt-6 border-t border-slate-200">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <UserCircle2 className="w-5 h-5 text-gov-700" />
              <h2 className="text-xl font-bold text-slate-900">
                Refreshed Recommendations (v{refreshedLibrary.profile_version})
              </h2>
            </div>
            <button
              type="button"
              onClick={() => navigate('/library')}
              className="text-xs font-semibold text-gov-700 hover:underline"
            >
              Open library &rarr;
            </button>
          </div>

          <div>
            <h3 className="text-sm font-bold text-slate-800 uppercase tracking-wider mb-3">
              Recommended For You ({refreshedLibrary.top.length})
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
              {refreshedLibrary.top.map((card) => (
                <SchemeCard key={card.scheme_id} card={card} showMatchPercent={true} />
              ))}
            </div>
          </div>

          {refreshedLibrary.more.length > 0 && (
            <div className="pt-4 border-t border-slate-200">
              <h3 className="text-sm font-bold text-slate-800 uppercase tracking-wider mb-3">
                More In Your Sectors ({refreshedLibrary.more.length})
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
                {refreshedLibrary.more.map((card) => (
                  <SchemeCard key={card.scheme_id} card={card} showMatchPercent={false} />
                ))}
              </div>
            </div>
          )}
        </section>
      )}
    </div>
  );
};
