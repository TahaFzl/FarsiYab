# FarsiYab website

Next.js 16 site in Persian (RTL, default) and English. It talks to the API in
[`services/api`](../../services/api/README.md); design docs are in [`docs/`](../../docs/).

## Run locally

The API must be running with indexed data (`uv run farsiyab serve` in `services/api`).

```bash
npm ci
npm run dev                     # http://localhost:3000 → redirects to /fa or /en
```

`FARSIYAB_API_URL` (default `http://127.0.0.1:8000`) is where server components
and the `/api/*` rewrite reach the API.

## Checks

```bash
npm run typecheck               # next typegen + tsc
npm run lint
npm run build
```

End-to-end tests (Playwright) need the site and the API running with Toronto
and Hamburg indexed:

```bash
npm run build && npm start &    # or npm run dev
npm run e2e                     # E2E_SCREENSHOTS=/some/dir to save screenshots
```

## Structure

| Path | What |
|---|---|
| `src/proxy.ts` | Redirects `/` to `/fa` or `/en` from `Accept-Language` |
| `src/app/[lang]/` | Pages: home (search form), `search`, `how-it-works`, `about`, `privacy` |
| `src/components/` | `SearchForm`, `ResultCard`, `LiveSearch` (SSE progress), `ReportButton` |
| `src/lib/api.ts` | API types and fetch helpers |
| `src/dictionaries/` | UI text in `fa.json` and `en.json` |
| `src/app/fonts/` | Vazirmatn (SIL Open Font License, see `Vazirmatn-OFL.txt`) |
