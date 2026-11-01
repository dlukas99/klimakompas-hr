---
paths: ["frontend/**"]
---

# Frontend conventions (SPEC §22)

- TypeScript `strict`, no `any`; ESLint and Prettier; function components and hooks.
- TanStack Query for all fetching; API types from OpenAPI (`openapi-typescript`).
- Location and layer state live in the URL.
- All text in `src/i18n/hr.json`; numbers and dates through `Intl` with `hr-HR`.
- Accessible components (Radix/shadcn).
- MapLibre layers are declared in `features/map/layers.ts`; every layer has a legend and attribution
  from `/api/v1/sources`.
- Every new page gets an e2e scenario and an axe check.
