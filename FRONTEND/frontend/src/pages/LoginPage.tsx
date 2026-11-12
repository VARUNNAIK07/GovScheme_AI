// frontend/src/pages/LoginPage.tsx
import React, { useState } from 'react';
import { Link, Navigate, useNavigate, useLocation } from 'react-router-dom';
import { ShieldCheck, AlertCircle } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import personas from '../mocks/personas.json';

// Persona shortcuts only work against the MSW mock API (no VITE_API_BASE set)
const MOCK_MODE = !import.meta.env.VITE_API_BASE;

export const LoginPage: React.FC = () => {
  const { login, isAuthenticated, isLoading } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [email, setEmail] = useState(MOCK_MODE ? 'ramesh.patel@example.com' : '');
  const [password, setPassword] = useState(MOCK_MODE ? 'secure_password_123' : '');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const from = (location.state as any)?.from?.pathname || '/library';

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);

    try {
      await login(email, password);
      navigate(from, { replace: true });
    } catch (err: any) {
      setError(err.message || 'Failed to authenticate. Please check your credentials.');
    } finally {
      setSubmitting(false);
    }
  };

  const fillPersona = (pEmail: string) => {
    setEmail(pEmail);
    setPassword('persona_pass_123');
    setError(null);
  };

  if (!isLoading && isAuthenticated && !submitting) {
    return <Navigate to="/library" replace />;
  }

  return (
    <div className="min-h-screen bg-slate-100 flex flex-col justify-center py-12 px-4 sm:px-6 lg:px-8">
      <div className="sm:mx-auto sm:w-full sm:max-w-md text-center">
        <div className="w-12 h-12 rounded bg-gov-800 text-white flex items-center justify-center mx-auto mb-3 shadow-xs">
          <ShieldCheck className="w-7 h-7 text-emerald-400" />
        </div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">
          GovScheme AI
        </h1>
        <p className="mt-1 text-sm text-slate-600">
          Access your verified government welfare portal
        </p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md">
        <div className="bg-white py-8 px-6 shadow-sm border border-slate-200 rounded-lg sm:px-10">
          {error && (
            <div className="mb-5 p-3 rounded-md bg-rose-50 border border-rose-200 flex items-start gap-2.5 text-xs text-rose-800" role="alert">
              <AlertCircle className="w-4 h-4 flex-shrink-0 text-rose-600 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          <form className="space-y-4" onSubmit={handleSubmit}>
            <div>
              <label htmlFor="email" className="block text-xs font-semibold text-slate-700">
                Email Address
              </label>
              <input
                id="email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="mt-1 block w-full px-3 py-2 bg-white border border-slate-300 rounded-md text-sm text-slate-900 focus:ring-2 focus:ring-gov-700 focus:border-gov-700"
                placeholder="citizen@gov.in"
              />
            </div>

            <div>
              <label htmlFor="password" className="block text-xs font-semibold text-slate-700">
                Password
              </label>
              <input
                id="password"
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="mt-1 block w-full px-3 py-2 bg-white border border-slate-300 rounded-md text-sm text-slate-900 focus:ring-2 focus:ring-gov-700 focus:border-gov-700"
              />
            </div>

            <button
              type="submit"
              disabled={submitting}
              className="w-full mt-2 flex justify-center py-2.5 px-4 border border-transparent rounded-md text-sm font-semibold text-white bg-gov-700 hover:bg-gov-800 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-gov-700 disabled:opacity-50 transition-colors cursor-pointer"
            >
              {submitting ? 'Authenticating...' : 'Sign In'}
            </button>
          </form>

          {/* Quick Persona Fillers for Evaluation (mock mode only) */}
          {MOCK_MODE && (
          <div className="mt-6 pt-5 border-t border-slate-200">
            <span className="block text-xs font-semibold text-slate-500 mb-2 uppercase tracking-wider text-center">
              Quick Test Personas
            </span>
            <div className="flex flex-col gap-1.5">
              {personas.map((p: any) => {
                const pEmail = `${p.name.toLowerCase().replace(/\s+/g, '.')}@example.com`;
                return (
                  <button
                    key={p.id}
                    type="button"
                    onClick={() => fillPersona(pEmail)}
                    className="text-left text-xs px-2.5 py-1.5 rounded border border-slate-200 hover:bg-slate-50 text-slate-700 transition-colors flex items-center justify-between"
                  >
                    <span className="font-medium text-gov-800">{p.name}</span>
                    <span className="text-[11px] text-slate-500 truncate max-w-[200px]">{p.description.split(' in ')[0]}</span>
                  </button>
                );
              })}
            </div>
          </div>
          )}

          <div className="mt-6 text-center text-xs text-slate-600">
            Don&apos;t have an account?{' '}
            <Link to="/register" className="font-semibold text-gov-700 hover:underline">
              Register as new citizen
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
};
