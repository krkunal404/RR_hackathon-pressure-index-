# Pressure Index: frontend

**Live:** https://pressure-index-latest.onrender.com

React + TypeScript + Vite, with Tailwind CSS v4, shadcn-style UI primitives, Recharts, Framer Motion, Lucide icons, TanStack Table and TanStack Query, and React Router.

```bash
npm install
npm run dev        # http://localhost:5173 (proxies /api to the FastAPI server on :8000)
npm run build      # outputs dist/, which the FastAPI server also serves at /
npm test           # Vitest + React Testing Library
npm run test:e2e   # Playwright (starts its own API server on :8010)
npm run lint       # ESLint
```

The pages live in `src/pages`:
- Overview
- Rankings
- PlayerDetail
- Explorer
- PressureLab
- Competitions
- Methodology
- Validation

The API client and its types are in `src/lib/api.ts`. See `../README.md` for the full project.
