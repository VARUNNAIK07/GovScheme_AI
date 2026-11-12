# Scoring and Eligibility Rules

## Deterministic Eligibility Status Order

Eligibility is evaluated deterministically in the following exact order:
1. **NOT_ELIGIBLE**: Any required rule fails, or any exclusion rule matches.
2. **ELIGIBLE**: Every rule passes.
3. **PARTIALLY_ELIGIBLE**: Some rules are unknown because the user profile is missing a field.
4. **NEEDS_VERIFICATION**: Any rule is manual or ambiguous (e.g. requires offline certificate or administrative committee discretion).
5. **NEEDS_VERIFICATION** (default): A scheme with no rules extracted yet ("Eligibility criteria not extracted yet").

## Match Score Formula (v1)

$$\text{match} = \operatorname{round}\big(100 \times (0.35P + 0.30E + 0.20N + 0.15B)\big)$$

| Component | Weight | Meaning | Calculation |
|---|---|---|---|
| **P** | 0.35 | Profile relevance | Matched beneficiary tags / total scheme tags (farmer, student, woman, sc, st, senior, disabled, rural, bpl) |
| **E** | 0.30 | Eligibility fit | ELIGIBLE: 1.0, PARTIALLY_ELIGIBLE: 0.6, NEEDS_VERIFICATION: 0.5, NOT_ELIGIBLE: 0.0 |
| **N** | 0.20 | Need relevance | Cosine similarity between embeddings of user needs text and scheme summary (0 if needs empty) |
| **B** | 0.15 | Benefit relevance | 1.0 if scheme sector is in user's sectors_of_interest, else 0 |

Ties are broken alphabetically by `scheme_id`.
In the UI, this number is labeled as **"relevance match"** (never "chance of approval").
