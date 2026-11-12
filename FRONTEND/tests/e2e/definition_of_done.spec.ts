// tests/e2e/definition_of_done.spec.ts
import { test, expect } from '@playwright/test';
import personas from '../../contracts/personas.json';

test.describe('GovScheme AI — Definition of Done Walkthrough', () => {
  const persona = personas[0]; // Ramesh Patel (Farmer in rural MP)

  test('walks through register, onboarding, library, scheme detail, citation viewer, comparison, and profile update', async ({
    page,
  }) => {
    // -------------------------------------------------------------------------
    // 1. Citizen Registration
    // -------------------------------------------------------------------------
    await page.goto('/register');
    await expect(page).toHaveTitle(/GovScheme AI/i);
    await expect(page.getByRole('heading', { name: /Citizen Registration/i })).toBeVisible();

    await page.getByLabel(/Full Name/i).fill(persona.name);
    await page.getByLabel(/Email Address/i).fill(`e2e.${Date.now()}@example.com`);
    await page.getByLabel(/Password/i).fill('TestPass123$');
    await page.getByRole('button', { name: /Continue to Onboarding/i }).click();

    // -------------------------------------------------------------------------
    // 2. Guided Onboarding Flow (one question per screen)
    // -------------------------------------------------------------------------
    await expect(page).toHaveURL(/\/onboarding/);
    await expect(page.getByRole('progressbar')).toBeVisible();

    // Question 1: Occupation
    await expect(page.getByText(/What is your primary occupation/i)).toBeVisible();
    await page.getByRole('radio', { name: /Agriculture, Farming/i }).check();
    await page.getByRole('button', { name: /Next Question/i }).click();

    // Question 2: State
    await expect(page.getByText(/Which state or union territory do you reside in/i)).toBeVisible();
    await page.locator('input[type="text"]').fill(persona.attributes.state || 'Madhya Pradesh');
    await page.getByRole('button', { name: /Next Question/i }).click();

    // Question 3: Land Holding Acres
    await expect(page.getByText(/cultivable agricultural land/i)).toBeVisible();
    await page.locator('input[type="number"]').fill(String(persona.attributes.land_holding_acres || 2.5));
    await page.getByRole('button', { name: /Next Question/i }).click();

    // Question 4: Annual Income
    await expect(page.getByText(/annual family income/i)).toBeVisible();
    await page.locator('input[type="number"]').fill(String(persona.attributes.annual_family_income_inr || 120000));
    await page.getByRole('button', { name: /Next Question/i }).click();

    // Question 5: Sectors of interest
    await expect(page.getByText(/Which welfare sectors/i)).toBeVisible();
    await page.getByRole('checkbox', { name: /agriculture/i }).check();
    await page.getByRole('button', { name: /Next Question/i }).click();

    // -------------------------------------------------------------------------
    // 3. Scheme Library
    // -------------------------------------------------------------------------
    await expect(page).toHaveURL(/\/library/);
    await expect(page.getByRole('heading', { name: /Your Scheme Library/i })).toBeVisible();

    // Verify "Recommended for you" (5 cards with "relevance match" and eligibility badge)
    await expect(page.getByRole('heading', { name: /Recommended for you/i })).toBeVisible();
    const relevanceLabels = page.getByText(/relevance match/i);
    await expect(relevanceLabels.first()).toBeVisible();

    // Verify "More in your sectors"
    await expect(page.getByRole('heading', { name: /More in your sectors/i })).toBeVisible();

    // -------------------------------------------------------------------------
    // 4. Scheme Detail Page
    // -------------------------------------------------------------------------
    // Click on PM-KISAN details link
    const viewDetailBtn = page.getByRole('link', { name: /View details & evidence/i }).first();
    await viewDetailBtn.click();

    await expect(page).toHaveURL(/\/schemes\//);
    await expect(page.getByRole('heading', { name: /Scheme Overview/i })).toBeVisible();
    await expect(page.getByRole('heading', { name: /Why This Scheme is Relevant to You/i })).toBeVisible();
    await expect(page.getByRole('heading', { name: /Deterministic Eligibility Checks/i })).toBeVisible();
    await expect(page.getByRole('heading', { name: /Benefits & Financial Entitlements/i })).toBeVisible();

    // Verify citation chips exist inline
    const citationChips = page.locator('.citation-chip');
    await expect(citationChips.first()).toBeVisible();

    // -------------------------------------------------------------------------
    // 5. Document Citation Viewer
    // -------------------------------------------------------------------------
    await citationChips.first().click();

    await expect(page).toHaveURL(/\/viewer\//);
    await expect(page.getByText(/Page 1 of/i)).toBeVisible();
    await expect(page.getByText(/Citation:/i)).toBeVisible();
    await expect(page.locator('canvas')).toBeVisible();

    // -------------------------------------------------------------------------
    // 6. Comparative Analysis Matrix
    // -------------------------------------------------------------------------
    await page.goto('/comparison');
    await expect(page.getByRole('heading', { name: /Scheme Comparison Matrix/i })).toBeVisible();
    await expect(page.getByRole('table')).toBeVisible();
    await expect(page.getByText(/Evaluation Criteria/i)).toBeVisible();
    await expect(page.getByRole('heading', { name: /AI Cross-Scheme Insights/i })).toBeVisible();

    // -------------------------------------------------------------------------
    // 7. Profile Edit & Refreshed Library
    // -------------------------------------------------------------------------
    await page.goto('/profile');
    await expect(page.getByRole('heading', { name: /Citizen Attributes & Preferences/i })).toBeVisible();

    // Change land holding or income
    const incomeInput = page.locator('#attr_income');
    await incomeInput.fill('150000');
    await page.getByRole('button', { name: /Save & Re-evaluate Library/i }).click();

    // Verify success banner and refreshed recommendations
    await expect(page.getByText(/Profile Successfully Updated!/i)).toBeVisible();
    await expect(page.getByRole('heading', { name: /Refreshed Recommendations/i })).toBeVisible();
  });
});
