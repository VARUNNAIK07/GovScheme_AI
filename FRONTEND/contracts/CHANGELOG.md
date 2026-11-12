# Contracts Changelog

All contract changes are append-only. No field may be deleted or renamed during development.

## [2026-10-12] - Hour 0
- Frozen base schemas and types established for multi-agent shared state architecture.
- Pydantic models in `contracts/schemas.py`, TypeScript interfaces in `contracts/types.ts`.
- Core entities: `ProfileAttributes`, `Profile`, `Scheme`, `EligibilityRule`, `DocumentMeta`, `Evidence`, `CitedSentence`, `Question`, `Candidate`, `RuleCheck`, `EligibilityResult`, `ScoreResult`, `LibraryCard`, `LibraryResult`, `ComparisonMatrix`, `SchemeSummary`, `ComparisonInsights`, `CitationTarget`.
- Defined REST endpoints under `/api`.
