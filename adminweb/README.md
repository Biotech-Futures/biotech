# Admin Web

Standalone React admin UI built with Vite, TanStack Router, TanStack Query, shadcn/ui, and Tailwind CSS.

## Getting Started

```bash
pnpm install
pnpm dev
```

The local dev server runs on http://localhost:3000.

## Environment

Create `.env` in this directory when you need to point the app at a local API.

```env
VITE_PUBLIC_API_URL=http://localhost:8000
```

## Commands

```bash
pnpm dev
pnpm build
pnpm typecheck
pnpm test
pnpm preview
```

## Source Layout

```text
src/
├── components/
├── fetch/
├── hooks/
├── lib/
├── provider/
├── query/
├── routes/
├── schema/
├── type/
└── util/
```
