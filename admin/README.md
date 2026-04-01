# Admin - Full-Stack Application

A full-stack monorepo containing a Hono backend API server and a React frontend application.

## Quick Start

```bash
# 1. Install dependencies
pnpm install

# 2. Set up environment files
# Backend: apps/server/.env
DATABASE_URL=postgresql://user:password@host:port/database

# Frontend: apps/web/.env
VITE_PUBLIC_API_URL=http://localhost:3001

# 3. Set up database (if needed)
cd apps/server
pnpm drizzle-kit generate
pnpm drizzle-kit migrate

# 4. Start the application
# From root directory:
pnpm dev:server   # Backend on port 3001
pnpm dev:web      # Frontend on port 3000
```

**Access:**
- Frontend: http://localhost:3000
- Backend API: http://localhost:3001/api/v1

---

## Tech Stack

### Backend (Server)
- **Framework**: Hono
- **Database**: PostgreSQL with Drizzle ORM
- **Auth**: better-auth
- **Validation**: Zod

### Frontend (Web)
- **Framework**: React 19 with TypeScript
- **Routing**: TanStack Router
- **Data Fetching**: Axios + TanStack Query
- **UI Components**: shadcn/ui
- **Styling**: Tailwind CSS v4
- **Icons**: Lucide React
- **Form Validation**: react-hook-form + Zod

---

## Project Structure

```
admin/
├── apps/
│   ├── server/          # Backend API (port 3001)
│   │   ├── src/
│   │   │   ├── index.ts         # Server entry point
│   │   │   ├── db/schema/       # Database schemas
│   │   │   ├── lib/             # Utilities (auth, db)
│   │   │   ├── middleware/      # HTTP middleware
│   │   │   └── module/          # Feature modules
│   │   ├── drizzle/             # Migration files
│   │   └── package.json
│   │
│   └── web/             # Frontend (port 3000)
│   │   ├── src/
│   │   │   ├── routes/          # Page routes
│   │   │   ├── components/
│   │   │   │   ├── ui/          # shadcn components
│   │   │   │   └── layout/      # Layout components
│   │   │   ├── lib/             # Utilities
│   │   │   ├── schema/          # Form validation schemas
│   │   │   ├── type/            # Type definitions
│   │   │   └── query/           # TanStack Query hooks
│   │   └── package.json
│   │
├── package.json
├── pnpm-workspace.yaml
└── pnpm-lock.yaml
```

---

## Getting Started

### Prerequisites

- Node.js 18+
- pnpm 8+
- PostgreSQL database

### Installation

```bash
pnpm install
```

### Environment Setup

**Backend (`apps/server/.env`):**
```env
DATABASE_URL=postgresql://user:password@host:port/database
```

**Frontend (`apps/web/.env`):**
```env
VITE_PUBLIC_API_URL=http://localhost:3001
```

### Database Setup

```bash
cd apps/server
pnpm drizzle-kit generate
pnpm drizzle-kit migrate
```

### Running the Application

```bash
# From root
pnpm dev:server   # Backend (port 3001)
pnpm dev:web      # Frontend (port 3000)

# Or from app directories
cd apps/server && pnpm dev
cd apps/web && pnpm dev
```

---

## Development Workflow

### Adding a New Feature

1. **Check Database** - Verify if existing schemas can fulfill the requirement
2. **Create Backend Files** - Add module in `apps/server/src/module/<feature>/`
3. **Create Frontend Files** - Add schema, type, query, and page in `apps/web/src/`

### Backend Module Structure

```
apps/server/src/module/<feature>/
├── route.ts    # HTTP routes
├── schema.ts   # Zod validation
└── service.ts  # Business logic
```

### Frontend File Structure

```
apps/web/src/
├── schema/<feature>.ts         # Form validation
├── type/<feature>.ts           # Response types
├── query/<feature>.ts          # TanStack Query hooks
└── routes/_auth/<feature>.tsx  # Page component
```

---

## Building for Production

```bash
cd apps/server && pnpm build
cd apps/web && pnpm build
cd apps/web && pnpm preview
```

---

## Testing

```bash
cd apps/server && pnpm test
cd apps/web && pnpm test
```

---

## Available Routes

| Frontend | Backend API |
|----------|-------------|
| `/demo` | `/api/v1/demo` |
| `/group` | `/api/v1/group` |
| `/match` | `/api/v1/match` |
| `/user` | `/api/v1/user` |
| `/email` | `/api/v1/email` |
| `/event` | `/api/v1/event` |
| `/matching` | `/api/v1/matching` |

---

## Documentation

- Backend: `apps/server/CLAUDE.md`
- Frontend: `apps/web/CLAUDE.md`
- Feature guide: `CLAUDE.md`