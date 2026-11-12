// frontend/src/api/client.ts

let inMemoryToken: string | null = localStorage.getItem('govscheme_token');

export const getAuthToken = (): string | null => {
  if (inMemoryToken) return inMemoryToken;
  const stored = localStorage.getItem('govscheme_token');
  if (stored) {
    inMemoryToken = stored;
  }
  return inMemoryToken;
};

export const setAuthToken = (token: string | null): void => {
  inMemoryToken = token;
  if (token) {
    localStorage.setItem('govscheme_token', token);
  } else {
    localStorage.removeItem('govscheme_token');
  }
};

export const getApiBaseUrl = (): string => {
  const envBase = import.meta.env.VITE_API_BASE;
  if (envBase && typeof envBase === 'string' && envBase.trim() !== '') {
    const base = envBase.replace(/\/+$/, '');
    return base.endsWith('/api') ? base.slice(0, -4) : base;
  }
  return '';
};

export interface ApiClientOptions extends RequestInit {
  requiresAuth?: boolean;
}

export class ApiError extends Error {
  code: string;
  details?: any;
  status: number;

  constructor(code: string, message: string, status: number = 400, details?: any) {
    super(message);
    this.name = 'ApiError';
    this.code = code;
    this.status = status;
    this.details = details;
  }
}

export async function apiClient<T>(
  endpoint: string,
  options: ApiClientOptions = {}
): Promise<T> {
  const { requiresAuth = true, headers = {}, ...customConfig } = options;
  const baseUrl = getApiBaseUrl();
  const url = `${baseUrl}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;

  const requestHeaders: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(headers as Record<string, string>),
  };

  if (requiresAuth) {
    const token = getAuthToken();
    if (token) {
      requestHeaders['Authorization'] = `Bearer ${token}`;
    }
  }

  const response = await fetch(url, {
    ...customConfig,
    headers: requestHeaders,
  });

  if (!response.ok) {
    let errorCode = 'UNKNOWN_ERROR';
    let errorMessage = `Request failed with status ${response.status}`;
    let details: any = undefined;

    try {
      const errorJson = await response.json();
      if (errorJson && errorJson.error) {
        errorCode = errorJson.error.code || errorCode;
        errorMessage = errorJson.error.message || errorMessage;
        details = errorJson.error.details;
      }
    } catch {
      // response was not JSON
    }

    if (response.status === 401 && requiresAuth) {
      setAuthToken(null);
    }

    throw new ApiError(errorCode, errorMessage, response.status, details);
  }

  // Check if response is empty (e.g. 204 No Content)
  if (response.status === 204) {
    return {} as T;
  }

  const contentType = response.headers.get('content-type');
  if (contentType && contentType.includes('application/pdf')) {
    return (await response.blob()) as unknown as T;
  }

  return response.json();
}
