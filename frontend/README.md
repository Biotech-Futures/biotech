# BIOTech Futures Frontend

Vue 3 + Vite single-page application for the BIOTech Futures Mentoring Platform. It provides authenticated dashboards for students, mentors, supervisors, and administrators, including resource management, events, announcements, and admin tooling that integrates with the Django backend.

## Stack
- Vue 3 with the Composition API, Vite, and TypeScript
- Pinia for session-aware state management
- Vue Router for routing (SPA with login callback handling)
- Naive UI components and Font Awesome icons
- Vitest + Vue Test Utils for unit tests, Playwright for end-to-end coverage

## Prerequisites
- Node.js `^20.19.0` or `>=22.12.0` (see `package.json`)
- npm 10+ (bundled with Node)
- Running backend API (default `http://localhost:8000`) for authenticated features

## Getting Started
```bash
npm install          # install dependencies
npm run dev          # start Vite dev server on http://localhost:5173
```
The client expects a Django session cookie. Initiate login by requesting a magic link from the backend (`POST /services/send-login-code/`), follow the emailed link, and the Pinia store will hydrate the session.

To build or preview:
```bash
npm run build        # type-check + production build to dist/
npm run preview      # serve the production bundle locally
```

## Authentication Flow
1. User submits their email (frontend `LoginPage.vue` posts to `/services/send-login-code/`).
2. Backend emails an OTP/magic link. Visiting the link hits `/services/magic/`, creates a Django session, and redirects back to `#/auth/callback`.
3. The callback view calls `useAuthStore().fetchUserData()` (`GET /api/v1/users/me/`) to populate the local session and role context.
4. Session cookies + CSRF tokens are sent automatically (`credentials: 'include'` in `resourcesAPI.ts`).
If resources fail to load, confirm that the login flow completed and that the backend is returning the `csrftoken` cookie.

## Backend Integration
- API root: `http://localhost:8000` (update `API_BASE_URL` in `src/utils/resourcesAPI.ts` if the backend runs elsewhere).
- Primary endpoints currently consumed:
  - `GET /api/v1/users/me/` – hydrate logged-in user
  - `GET /resources/resource-files/` – list resources with pagination support
  - `POST /services/send-login-code/` and `/services/verify-login-code/` – magic link auth
- CORS/CSRF: the backend is configured for `http://localhost:5173`. If you change ports or domains, update Django’s `CORS_ALLOWED_ORIGINS` and `CSRF_TRUSTED_ORIGINS`.

## Scripts
- `npm run dev` – Vite development server with hot module reload
- `npm run build` – type-check + production build
- `npm run preview` – static preview of the production bundle
- `npm run test:unit` – Vitest unit tests (runs with jsdom)
- `npm run test:e2e` – Playwright tests. Run `npx playwright install` once to fetch browsers.
- `npm run lint` – ESLint with Vue + TypeScript rules (`--fix` enabled)
- `npm run format` – Prettier on `src/`

## Directory Reference
- `src/main.ts` – Vite entry, mounts the root app and Pinia store
- `src/App.vue` – shell layout, header/sidebar, notification drawer, auth gate
- `src/router/` – route definitions and per-route guards
- `src/stores/auth.ts` – session + role management, hydration helpers
- `src/views/` – page components (dashboard, groups, resources, events, admin, etc.)
- `src/utils/resourcesAPI.ts` – typed API client with CSRF/session handling
- `src/data/` – static fixtures for dashboard widgets
- `public/` – static assets served by Vite

## Testing & Quality
```bash
npm run test:unit        # unit tests (Vitest)
npm run test:e2e         # end-to-end tests (Playwright, requires running backend and dev server)
npm run lint             # ESLint
npm run format           # Prettier formatting check
```
Playwright tests assume the backend is reachable and that seeded test users exist. For CI, build before running E2E (`npm run build && npm run test:e2e`).

## Troubleshooting
- **Resources page shows “You must be logged in”** – ensure the magic link flow completed and cookies are stored; clear old cookies before retrying.
- **403/CSRF errors** – confirm the backend is issuing a `csrftoken` cookie and that CORS/CSRF origins include your frontend URL.
- **Stale data after deploy** – `useAuthStore().hydrate()` loads cached data from `localStorage`; call `logout` to clear persisted session info when switching users.
