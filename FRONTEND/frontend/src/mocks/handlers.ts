// frontend/src/mocks/handlers.ts
import { http, HttpResponse } from 'msw';
import profileFixture from './fixtures/profile.json';
import questionFixture from './fixtures/question.json';
import libraryFixture from './fixtures/library.json';
import schemeDetailFixture from './fixtures/scheme_detail.json';
import comparisonFixture from './fixtures/comparison.json';
import citationFixture from './fixtures/citation.json';
import type { Question, Profile } from '../types/contracts';
import { SECTOR_LABELS } from '../types/contracts';

// In-memory mock database state for MSW
let currentUser = {
  user_id: 'usr_ramesh_42',
  email: 'ramesh.patel@example.com',
  name: 'Ramesh Patel',
};

let currentProfile: Profile = JSON.parse(JSON.stringify(profileFixture));

// Dynamic question bank for realistic onboarding walkthrough
const ONBOARDING_QUESTIONS: Question[] = [
  {
    question_id: 'q_occupation',
    field: 'occupation',
    text: 'What is your primary occupation or livelihood source?',
    type: 'single_choice',
    options: ['farmer', 'student', 'salaried', 'self_employed', 'unemployed', 'retired', 'homemaker', 'other'],
    option_labels: { farmer: 'Farmer / cultivator', student: 'Student', salaried: 'Salaried employee', self_employed: 'Self-employed / small business', unemployed: 'Looking for work', retired: 'Retired', homemaker: 'Homemaker', other: 'Other' },
    progress: 0.2,
  },
  {
    question_id: 'q_state',
    field: 'state',
    text: 'Which state or union territory do you reside in?',
    type: 'single_choice',
    options: ['IN-MP', 'IN-BR', 'IN-UP', 'IN-MH', 'IN-RJ', 'IN-KA', 'IN-TN', 'IN-WB'],
    option_labels: { 'IN-MP': 'Madhya Pradesh', 'IN-BR': 'Bihar', 'IN-UP': 'Uttar Pradesh', 'IN-MH': 'Maharashtra', 'IN-RJ': 'Rajasthan', 'IN-KA': 'Karnataka', 'IN-TN': 'Tamil Nadu', 'IN-WB': 'West Bengal' },
    progress: 0.4,
  },
  {
    question_id: 'q_land_holding',
    field: 'land_holding_acres',
    text: questionFixture.text,
    type: questionFixture.type as any,
    options: questionFixture.options,
    progress: 0.6,
  },
  {
    question_id: 'q_annual_income',
    field: 'annual_family_income_inr',
    text: 'What is your total estimated annual family income in Indian Rupees (INR)?',
    type: 'number',
    options: [],
    progress: 0.8,
  },
  {
    question_id: 'q_sectors',
    field: 'sectors_of_interest',
    text: 'Which welfare sectors are you seeking support for?',
    type: 'multi_choice',
    options: Object.keys(SECTOR_LABELS),
    option_labels: SECTOR_LABELS,
    progress: 1.0,
  },
];

let onboardingStepIndex = 0;
let isProfileComplete = false;

export const handlers = [
  // POST /api/auth/register
  http.post('*/api/auth/register', async ({ request }) => {
    const body = (await request.json()) as any;
    if (!body.email || !body.password || !body.name) {
      return HttpResponse.json(
        { error: { code: 'VALIDATION_ERROR', message: 'Name, email, and password are required.' } },
        { status: 400 }
      );
    }

    currentUser = {
      user_id: `usr_${Date.now()}`,
      email: body.email,
      name: body.name,
    };
    onboardingStepIndex = 0;
    isProfileComplete = false;

    return HttpResponse.json({
      token: `mock_jwt_${Date.now()}`,
      user: currentUser,
    });
  }),

  // POST /api/auth/login
  http.post('*/api/auth/login', async ({ request }) => {
    const body = (await request.json()) as any;
    if (!body.email || !body.password) {
      return HttpResponse.json(
        { error: { code: 'INVALID_CREDENTIALS', message: 'Invalid email or password.' } },
        { status: 400 }
      );
    }

    currentUser = {
      user_id: 'usr_ramesh_42',
      email: body.email,
      name: body.email.includes('ramesh') ? 'Ramesh Patel' : 'Verified Citizen',
    };

    return HttpResponse.json({
      token: `mock_jwt_${Date.now()}`,
      user: currentUser,
    });
  }),

  // GET /api/me
  http.get('*/api/me', () => {
    return HttpResponse.json({
      user: currentUser,
      profile_complete: isProfileComplete,
      profile_version: currentProfile.version,
    });
  }),

  // GET /api/onboarding/next
  http.get('*/api/onboarding/next', () => {
    if (onboardingStepIndex >= ONBOARDING_QUESTIONS.length || isProfileComplete) {
      return HttpResponse.json({
        done: true,
        question: null,
      });
    }

    return HttpResponse.json({
      done: false,
      question: ONBOARDING_QUESTIONS[onboardingStepIndex],
    });
  }),

  // POST /api/onboarding/answer
  http.post('*/api/onboarding/answer', async ({ request }) => {
    const body = (await request.json()) as any;
    const { field, value } = body;

    // Field-level validation
    const errors: string[] = [];
    if (value === undefined || value === null || value === '') {
      errors.push(`${field} cannot be empty.`);
      return HttpResponse.json({
        ok: false,
        errors,
        done: false,
        question: ONBOARDING_QUESTIONS[onboardingStepIndex],
      });
    }

    if (field === 'land_holding_acres' && (Number(value) < 0 || Number(value) > 1000)) {
      errors.push('Land holding must be a valid acreage between 0 and 1000.');
      return HttpResponse.json({
        ok: false,
        errors,
        done: false,
        question: ONBOARDING_QUESTIONS[onboardingStepIndex],
      });
    }

    // Save answer to attributes
    (currentProfile.attributes as any)[field] = value;
    onboardingStepIndex++;

    const isDone = onboardingStepIndex >= ONBOARDING_QUESTIONS.length;
    if (isDone) {
      isProfileComplete = true;
      currentProfile.complete = true;
      currentProfile.version++;
    }

    return HttpResponse.json({
      ok: true,
      errors: [],
      done: isDone,
      question: isDone ? null : ONBOARDING_QUESTIONS[onboardingStepIndex],
    });
  }),

  // GET /api/profile
  http.get('*/api/profile', () => {
    return HttpResponse.json(currentProfile);
  }),

  // PUT /api/profile
  http.put('*/api/profile', async ({ request }) => {
    const body = (await request.json()) as any;
    if (body.attributes) {
      currentProfile.attributes = {
        ...currentProfile.attributes,
        ...body.attributes,
      };
      currentProfile.version += 1;
    }

    return HttpResponse.json({
      profile: currentProfile,
      library: libraryFixture,
    });
  }),

  // POST /api/profile/questions (mock: land question only for farmers)
  http.post('*/api/profile/questions', async ({ request }) => {
    const body = (await request.json()) as any;
    const occupation = body.attributes?.occupation;
    return HttpResponse.json(
      ONBOARDING_QUESTIONS.filter((q) => q.field !== 'land_holding_acres' || occupation === 'farmer')
    );
  }),

  // GET /api/library
  http.get('*/api/library', () => {
    return HttpResponse.json(libraryFixture);
  }),

  // GET /api/schemes/:id
  http.get('*/api/schemes/:scheme_id', ({ params }) => {
    const { scheme_id } = params;
    // Return fixture data, ensuring scheme_id matches
    const detail = JSON.parse(JSON.stringify(schemeDetailFixture));
    if (scheme_id && scheme_id !== 'pm-kisan') {
      detail.scheme.scheme_id = scheme_id as string;
      detail.scheme.name = (scheme_id as string).toUpperCase().replace(/-/g, ' ');
    }
    return HttpResponse.json(detail);
  }),

  // GET /api/comparison/options
  http.get('*/api/comparison/options', () => {
    return HttpResponse.json(libraryFixture.top);
  }),

  // POST /api/comparison
  http.post('*/api/comparison', async ({ request }) => {
    const body = (await request.json()) as any;
    const schemeIds = body.scheme_ids || [];

    if (!Array.isArray(schemeIds) || schemeIds.length < 2 || schemeIds.length > 5) {
      return HttpResponse.json(
        { error: { code: 'INVALID_SCHEME_COUNT', message: 'You must select between 2 and 5 schemes to compare.' } },
        { status: 400 }
      );
    }

    return HttpResponse.json(comparisonFixture);
  }),

  // GET /api/citations/:id
  http.get('*/api/citations/:citation_id', ({ params }) => {
    const { citation_id } = params;
    const citation = JSON.parse(JSON.stringify(citationFixture));
    citation.citation_id = citation_id as string;
    return HttpResponse.json(citation);
  }),

  // GET /api/documents/:doc_id/file
  http.get('*/api/documents/:doc_id/file', async () => {
    try {
      const response = await fetch('/sample.pdf');
      const arrayBuffer = await response.arrayBuffer();
      return new HttpResponse(arrayBuffer, {
        headers: {
          'Content-Type': 'application/pdf',
        },
      });
    } catch {
      return new HttpResponse(null, { status: 404 });
    }
  }),

  // GET /api/health
  http.get('*/api/health', () => {
    return HttpResponse.json({
      postgres: 'ok',
      qdrant: 'ok',
      llm: 'ok',
    });
  }),
];
