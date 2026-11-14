# Phase 10 gap decisions (prototype -> real frontend)

| Prototype feature | Decision | Reason |
|---|---|---|
| Vanilla single HTML file | Replaced | Spec requires Vite + React + TS strict |
| Mock `/api/ask` + SSE streaming | Dropped | No mocks, no streaming; one request, one response to `/api/v1/ask` |
| Chart.js and Google Fonts CDN | Dropped | Not in allowed deps; system font stack used |
| Landing, story chapters, Compare, Insights, Moon score | Dropped | Out of scope (single question/answer view); `moon_score` is not an API field |
| Hardcoded suggested questions | Adapted | Shown only with an "Example" label, or from `/meta` examples if provided |
| Space background, planet/flame/astronaut, animations, dark/light theme, cards, dossier grid, stamp | **Kept** | Visual identity preserved; `prefers-reduced-motion` honoured |
| Orange/red/purple/green | Kept by default; strict blue via `data-palette="blue"` | You asked to keep the look; both modes use icon + label + border style for states |
| `n/r` for missing values, real 0 stays 0 | Ported | `Val` component |
| Evidence/answer/plan/limitations/drawer/footer/toggle/error states | New | Required by spec |
| Button gradient | Slightly darkened | White text needed >= 4.5:1 contrast |
