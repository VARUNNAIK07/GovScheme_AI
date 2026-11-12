// frontend/src/api/endpoints.ts
import { apiClient, getApiBaseUrl } from './client';
import type {
  AuthResponse,
  MeResponse,
  OnboardingNextResponse,
  OnboardingAnswerRequest,
  OnboardingAnswerResponse,
  Profile,
  ProfileAttributes,
  ProfileUpdateResponse,
  LibraryResult,
  LibraryCard,
  SchemeDetailResponse,
  ComparisonRequest,
  ComparisonResponse,
  CitationTarget,
  Question,
  HealthResponse,
} from '../types/contracts';

export const authApi = {
  register: (data: { email: string; password: string; name: string }) =>
    apiClient<AuthResponse>('/api/auth/register', {
      method: 'POST',
      body: JSON.stringify(data),
      requiresAuth: false,
    }),

  login: (data: { email: string; password: string }) =>
    apiClient<AuthResponse>('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify(data),
      requiresAuth: false,
    }),

  me: () => apiClient<MeResponse>('/api/me'),
};

export const onboardingApi = {
  next: () => apiClient<OnboardingNextResponse>('/api/onboarding/next'),

  answer: (data: OnboardingAnswerRequest) =>
    apiClient<OnboardingAnswerResponse>('/api/onboarding/answer', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
};

export const profileApi = {
  get: () => apiClient<Profile>('/api/profile'),

  update: (attributes: Partial<ProfileAttributes>) =>
    apiClient<ProfileUpdateResponse>('/api/profile', {
      method: 'PUT',
      body: JSON.stringify({ attributes }),
    }),

  // Questions that apply to a draft profile (nothing saved): follow-ups appear/disappear as answers change
  questions: (attributes: Partial<ProfileAttributes>) =>
    apiClient<Question[]>('/api/profile/questions', {
      method: 'POST',
      body: JSON.stringify({ attributes }),
    }),
};

export const libraryApi = {
  get: () => apiClient<LibraryResult>('/api/library'),
};

export const schemesApi = {
  getDetail: (schemeId: string) =>
    apiClient<SchemeDetailResponse>(`/api/schemes/${encodeURIComponent(schemeId)}`),
};

export const comparisonApi = {
  getOptions: () => apiClient<LibraryCard[]>('/api/comparison/options'),

  compare: (schemeIds: string[]) => {
    const payload: ComparisonRequest = { scheme_ids: schemeIds };
    return apiClient<ComparisonResponse>('/api/comparison', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },
};

export const citationsApi = {
  get: (citationId: string) =>
    apiClient<CitationTarget>(`/api/citations/${encodeURIComponent(citationId)}`),

  getDocumentFileUrl: (docId: string) => {
    const base = getApiBaseUrl();
    return `${base}/api/documents/${encodeURIComponent(docId)}/file`;
  },
};

export const systemApi = {
  health: () =>
    apiClient<HealthResponse>('/api/health', {
      requiresAuth: false,
    }),

  refresh: (docId?: string) =>
    apiClient<{ changed_docs: string[]; affected_schemes: string[]; invalidated_runs: string[] }>(
      '/api/admin/refresh',
      {
        method: 'POST',
        body: JSON.stringify({ doc_id: docId }),
      }
    ),
};
