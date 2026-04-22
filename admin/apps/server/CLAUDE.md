# Server Project - Hono API Backend

## Project Overview

Backend API built with Hono + TypeScript, using Drizzle ORM with PostgreSQL and better-auth.

## Tech Stack

- Framework: Hono
- Runtime: Node.js + TypeScript
- Database: PostgreSQL + Drizzle ORM
- Auth: better-auth + Drizzle adapter
- Validation: Zod v4 + `@hono/standard-validator`
- Tests: Vitest

## Project Structure

```txt
src/
├── index.ts                  # App entry, routes, middleware wiring
├── lib/
│   ├── db.ts                 # Drizzle DB client
│   └── auth.ts               # better-auth setup
├── schema/
│   ├── index.ts              # Barrel export for schema
│   ├── db.ts                 # Public schema tables
│   └── admin.ts              # Admin schema tables (pgSchema("admin"))
├── module/
│   └── <feature>/
│       ├── route.ts          # Hono routes
│       ├── schema.ts         # Zod request/response contracts
│       └── service.ts        # Business logic + DB access
└── middleware/
    ├── auth.ts
    └── myCors.ts
```

## Database Schema Rules

When referencing database schema in docs/code, use `src/schema`.

- Canonical schema files:
  - `src/schema/db.ts`
  - `src/schema/admin.ts`
  - `src/schema/index.ts`
- Do not reference `src/db/schema/*` in new docs or new code.
- Prefer importing from `@/schema/index.js` (or `@/schema/db.js` / `@/schema/admin.js` when you need explicit scope).

Example:

```ts
import db from "@/lib/db.js";
import { users, tracks } from "@/schema/index.js";
```

## Current Schema Surface

`src/schema/db.ts` contains the core public tables, including:

- identity/auth support: `verification`, `users`, `userSession`, `userRoleAssignment`, `roles`
- matching/grouping: `groups`, `groupMembership`, `matchRun`
- profile domain: `studentProfile`, `mentorProfile`, `supervisorProfile`, `mentorAvailability`
- reference domain: `countries`, `countryStates`, `tracks`, `areasOfInterest`, `certificateType`
- join/link tables: `studentInterest`, `mentorInterest`, `mentorCertificate`
- content/comms: `announcements`, `announcementAudience`, `resources`, `resourceAudience`, `events`, `eventRsvp`, `messages`, `alert`, `auditLog`

`src/schema/admin.ts` contains admin-auth tables under `admin` schema:

- `adminUser`
- `adminSession`
- `adminAccount`
- `adminVerification`
- `matchRun`

## Drizzle Configuration

- Push config: `drizzle.config.ts` (admin schema only)
- Pull config: `drizzle.pull.config.ts` (public + admin)
- Schema entry: `./src/schema/index.ts`
- Push schema filter: `admin`
- Pull schema filter: `public`, `admin`
- Migration output: `./src/new/drizzle`

## Module Pattern

Each feature module should follow:

1. `schema.ts`: Zod input/output contracts.
2. `service.ts`: DB queries and business logic (no HTTP concerns).
3. `route.ts`: Route definitions and validation wiring.

## API Conventions

- Base API prefix: `/api/v1`
- Auth routes: `/api/auth/*`
- Protected routes use `authRequirement` middleware.
- Prefer consistent JSON responses:

```ts
{ msg: string, data: unknown }
```

## Common Commands

```bash
pnpm dev       # Run dev server (tsx watch)
pnpm build     # TypeScript build
pnpm start     # Run dist build
pnpm test      # Vitest watch
pnpm test:run  # Vitest single run
pnpm db:pull   # Pull public + admin from database into Drizzle artifacts
pnpm db:push   # Push admin schema changes only
```
