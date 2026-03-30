# Server Project - Hono API Backend

## Project Overview

This is a Hono-based backend API server using Node.js with TypeScript. The server runs on port 3001 and provides RESTful API endpoints.

## Tech Stack

- **Framework**: Hono (lightweight web framework)
- **Runtime**: Node.js with TypeScript
- **Validation**: Zod v4 with @hono/standard-validator
- **Database**: PostgreSQL with Drizzle ORM
- **Auth**: better-auth with Drizzle adapter
- **Testing**: Vitest

## Project Structure

```
src/
├── index.ts              # Application entry point, server setup
├── middleware/
│   └── myCors.ts         # CORS configuration
├── db/
│   └── schema/           # Drizzle database schemas
│       ├── auth.ts       # Auth-related schema
│       └── chat.ts       # Chat-related schema
├── lib/
│   ├── auth.ts           # Authentication utilities
│   └── db.ts             # Database connection
├── algorithm/
│   ├── student.ts        # Student matching algorithm
│   └── tutor.ts          # Tutor matching algorithm
└── module/               # Feature modules (each module contains:)
    ├── demo/             # Example module
    │   ├── route.ts       # HTTP route definitions
    │   ├── schema.ts      # Zod validation schemas
    │   └── service.ts     # Business logic
    ├── match/            # Matching feature module
    └── group/            # Group feature module
```

## Module Pattern

Each feature module follows a consistent 3-file pattern:

### `route.ts` - HTTP Route Definitions

Defines Hono routes and maps HTTP requests to service functions.

- Creates a new Hono instance for the module
- Uses `sValidator` for request validation
- Delegates business logic to service functions
- Returns JSON responses

```typescript
import { Hono } from "hono";
import { sValidator } from "@hono/standard-validator";
import { createDemoSchema } from "./schema.js";
import { createDemo, queryDemo } from "./service.js";

export const demoRoute = new Hono();

demoRoute.get("/", (c) => {
  const data = queryDemo();
  return c.json(data);
});

demoRoute.post("/", sValidator("json", createDemoSchema), (c) => {
  const data = c.req.valid("json");
  const res = createDemo(data);
  return c.json(res);
});
```

### `schema.ts` - Zod Validation Schemas

Defines Zod schemas for request validation.

- Exports Zod schemas for each endpoint's input
- Used by `sValidator` in route.ts

```typescript
import z from "zod";

export const createDemoSchema = z.object({
  name: z.string(),
  age: z.number(),
});
```

### `service.ts` - Business Logic

Contains the core business logic and data operations.

- Pure functions that handle business logic
- Returns data in standard API response format

```typescript
export function queryDemo() {
  return {
    msg: "Demo data retrieved successfully",
    data: { name: "demo", age: 18 },
  };
}

export function createDemo(data: { name: string; age: number }) {
  return {
    msg: "Demo created successfully",
    data,
  };
}
```

## API Response Format

All API endpoints **MUST** return responses in this standard format:

```typescript
{
  msg: string,    // Message describing the result
  data: any,      // Response data (object, array, or null)
  ...             // Additional optional fields (e.g., status, error)
}
```

Examples:

```typescript
// Success response
{ msg: "Demo created successfully", data: { id: 1, name: "test" } }

// Error response
{ msg: "Validation failed", data: null, error: "Invalid input" }
```

## Common Commands

```bash
pnpm dev       # Start development server with hot reload
pnpm build     # Build TypeScript to dist/
pnpm start     # Run production build
pnpm test      # Run tests with Vitest
```

## API Base Path

All API routes are prefixed with `/api/v1`

Current routes:

- `GET /` - Health check
- `/api/v1/demo` - Demo endpoints
- `/api/v1/match` - Match endpoints
- `/api/v1/group` - Group endpoints
