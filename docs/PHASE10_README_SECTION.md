## Frontend (Phase 10)

React + TypeScript (strict) + Vite, plain CSS. Single screen: question, answer, plan, evidence.

```bash
cd frontend
npm install
npm run gen:api     # regenerates src/api/schema.d.ts from ../docs/openapi.json
npm run dev         # http://localhost:5173, proxies /api to http://localhost:8000
npm run typecheck && npm run lint && npm test
npm run build       # outputs frontend/dist
npm run contrast    # writes docs/PHASE10_CONTRAST.md (WCAG AA check)
```

Production: after `npm run build`, FastAPI serves `frontend/dist` (see `frontend_mount.py`):
`uvicorn main:app` then open http://localhost:8000. `/api/*` is never shadowed.

Wire format lives in one file, `frontend/src/api/normalize.ts`. If the API changes, edit only that file.

Palette: `index.html` has `data-palette="space"` (prototype colours). Set it to `"blue"` for the strict blue-only
palette. States are distinguished by icon + text label + border style in both.
