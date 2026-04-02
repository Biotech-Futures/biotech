# Admin Project - Full-Stack Monorepo

## Project Overview

A full-stack monorepo containing a Hono backend API and a React frontend application.

## Project Structure

```
admin/
├── package.json              # Root package with workspace scripts
├── pnpm-workspace.yaml       # Workspace configuration
├── pnpm-lock.yaml            # Lockfile
├── .husky/                   # Git hooks (pre-commit)
│   └── pre-commit
└── apps/
    ├── server/               # Backend API (Hono)
    │   ├── src/
    │   │   ├── index.ts           # Server entry point
    │   │   ├── middleware/        # HTTP middleware (CORS, etc.)
    │   │   ├── db/
    │   │   │   └── schema/        # Drizzle database schemas
    │   │   │       ├── auth.ts    # User, session, account tables
    │   │   │       └── chat.ts    # Messages, attachments tables
    │   │   ├── lib/
    │   │   │   ├── auth.ts        # Auth utilities
    │   │   │   └── db.ts          # Database connection
    │   │   ├── algorithm/         # Business algorithms
    │   │   └── module/            # Feature modules
    │   │       └── demo/          # Example module
    │   │           ├── route.ts   # HTTP routes
    │   │           ├── schema.ts  # Zod validation
    │   │           └── service.ts # Business logic
    │   ├── drizzle/               # Migration files
    │   └── CLAUDE.md              # Backend documentation
    └── web/                      # Frontend (React)
        ├── src/
        │   ├── routes/            # TanStack Router routes
        │   ├── components/
        │   │   ├── ui/            # shadcn/ui components
        │   │   └── layout/        # Layout components
        │   ├── lib/
        │   │   ├── utils.ts       # Utility functions
        │   │   └── myFetch.ts     # Axios instance
        │   ├── schema/            # Zod schemas for forms
        │   ├── type/              # API response types
        │   ├── query/             # TanStack Query hooks
        │   └── hooks/             # Custom React hooks
        └── CLAUDE.md              # Frontend documentation
```

## Common Commands

```bash
# Run both servers (from root)
pnpm dev:server    # Start backend on port 3003
pnpm dev:web       # Start frontend on port 3000

# Or run from respective directories
cd apps/server && pnpm dev
cd apps/web && pnpm dev
```

---

## Feature Implementation Procedure

When implementing a new feature, follow this step-by-step procedure:

### Step 1: Check Database Schema

**Before starting**, verify if the database can fulfill the requirement.

1. Read existing schemas in `apps/server/src/db/schema/`
2. Determine if existing tables can support the feature
3. If new tables/columns are needed:
   - Create or update schema file in `apps/server/src/db/schema/`
   - Run `pnpm drizzle-kit generate` to create migration
   - Run `pnpm drizzle-kit migrate` to apply migration

**Example check:**
```typescript
// Check apps/server/src/db/schema/auth.ts
// Tables: user, session, account, verification

// Check apps/server/src/db/schema/chat.ts
// Tables: messages, messageAttachments
```

---

### Step 2: Create Backend Files

Create files in `apps/server/src/module/<feature>/`:

#### 2.1 Create `schema.ts` - Zod Validation

Define input validation schemas:

```typescript
// apps/server/src/module/<feature>/schema.ts
import z from "zod";

export const createFeatureSchema = z.object({
  name: z.string().min(1).max(100),
  // ... other fields
});

export const updateFeatureSchema = z.object({
  id: z.string(),
  name: z.string().min(1).max(100).optional(),
});
```

#### 2.2 Create `service.ts` - Business Logic

Implement business logic functions. **All responses MUST follow this format:**

```typescript
// apps/server/src/module/<feature>/service.ts
import db from "@/lib/db";
import { createFeatureSchema } from "./schema.js";

export function queryFeature() {
  // Database queries here
  return {
    msg: "Feature data retrieved successfully",
    data: { /* result */ },
  };
}

export function createFeature(data: z.infer<typeof createFeatureSchema>) {
  // Insert to database
  return {
    msg: "Feature created successfully",
    data: { /* created record */ },
  };
}

export function updateFeature(id: string, data: UpdateInput) {
  // Update database
  return {
    msg: "Feature updated successfully",
    data: { /* updated record */ },
  };
}

export function deleteFeature(id: string) {
  // Delete from database
  return {
    msg: "Feature deleted successfully",
    data: null,
  };
}
```

#### 2.3 Create `route.ts` - HTTP Routes

Define Hono routes with validation:

```typescript
// apps/server/src/module/<feature>/route.ts
import { Hono } from "hono";
import { sValidator } from "@hono/standard-validator";
import { createFeatureSchema, updateFeatureSchema } from "./schema.js";
import { queryFeature, createFeature, updateFeature, deleteFeature } from "./service.js";

export const featureRoute = new Hono();

// GET - List/Query
featureRoute.get("/", (c) => {
  const res = queryFeature();
  return c.json(res);
});

// GET - Single item
featureRoute.get("/:id", (c) => {
  const id = c.req.param("id");
  const res = queryFeatureById(id);
  return c.json(res);
});

// POST - Create
featureRoute.post("/", sValidator("json", createFeatureSchema), (c) => {
  const data = c.req.valid("json");
  const res = createFeature(data);
  return c.json(res);
});

// PUT - Update
featureRoute.put("/:id", sValidator("json", updateFeatureSchema), (c) => {
  const id = c.req.param("id");
  const data = c.req.valid("json");
  const res = updateFeature(id, data);
  return c.json(res);
});

// DELETE
featureRoute.delete("/:id", (c) => {
  const id = c.req.param("id");
  const res = deleteFeature(id);
  return c.json(res);
});
```

#### 2.4 Register Route in `index.ts`

```typescript
// apps/server/src/index.ts
import { featureRoute } from "./module/feature/route.js";

app
  .basePath("/api/v1")
  .route("feature", featureRoute)  // Add this line
  .route("demo", demoRoute);
```

---

### Step 3: Create Frontend Files

Create files in the correct folders in `apps/web/src/`:

#### 3.1 Create `schema/<feature>.ts` - Form Validation

```typescript
// apps/web/src/schema/feature.ts
import { z } from "zod";

export const createFeatureSchema = z.object({
  name: z.string().min(1).max(100, "Name must be less than 100 characters"),
});

export type CreateFeature = z.infer<typeof createFeatureSchema>;
```

#### 3.2 Create `type/<feature>.ts` - Response Types

```typescript
// apps/web/src/type/feature.ts
export type Feature = {
  id: string;
  name: string;
  createdAt: string;
};

export type ApiResponse<T> = {
  msg: string;
  data: T;
};
```

#### 3.3 Create `query/<feature>.ts` - TanStack Query Hooks

```typescript
// apps/web/src/query/feature.ts
import { myFetch } from "@/lib/myFetch";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { CreateFeature } from "@/schema/feature";
import type { Feature, ApiResponse } from "@/type/feature";

// GET - Query
export function useQueryFeature() {
  return useQuery({
    queryKey: ["feature"],
    queryFn: async () => {
      const res = await myFetch.get<ApiResponse<Feature[]>>("/feature");
      return res.data;
    },
  });
}

// GET - Single
export function useQueryFeatureById(id: string) {
  return useQuery({
    queryKey: ["feature", id],
    queryFn: async () => {
      const res = await myFetch.get<ApiResponse<Feature>>(`/feature/${id}`);
      return res.data;
    },
    enabled: !!id,
  });
}

// POST - Create
export function useCreateFeature() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: CreateFeature) => {
      const res = await myFetch.post<ApiResponse<Feature>>("/feature", data);
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["feature"] });
    },
  });
}

// PUT - Update
export function useUpdateFeature() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, data }: { id: string; data: Partial<CreateFeature> }) => {
      const res = await myFetch.put<ApiResponse<Feature>>(`/feature/${id}`, data);
      return res.data;
    },
    onSuccess: (_, { id }) => {
      queryClient.invalidateQueries({ queryKey: ["feature"] });
      queryClient.invalidateQueries({ queryKey: ["feature", id] });
    },
  });
}

// DELETE
export function useDeleteFeature() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      const res = await myFetch.delete<ApiResponse<null>>(`/feature/${id}`);
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["feature"] });
    },
  });
}
```

#### 3.4 Create `routes/_auth/<feature>.tsx` - Page Component

```typescript
// apps/web/src/routes/_auth/feature.tsx
import { createFileRoute } from "@tanstack/react-router";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useQueryFeature, useCreateFeature } from "@/query/feature";
import { useForm, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { createFeatureSchema, type CreateFeature } from "@/schema/feature";

export const Route = createFileRoute("/_auth/feature")({
  component: FeaturePage,
});

function FeaturePage() {
  const { data, isPending } = useQueryFeature();
  const { mutate, isPending: isCreating } = useCreateFeature();

  const { control, handleSubmit } = useForm<CreateFeature>({
    defaultValues: { name: "" },
    resolver: zodResolver(createFeatureSchema),
  });

  return (
    <div>
      <h1>Features</h1>

      {/* List */}
      {isPending ? (
        <div>Loading...</div>
      ) : (
        <ul>
          {data?.data?.map((item) => (
            <li key={item.id}>{item.name}</li>
          ))}
        </ul>
      )}

      {/* Create Form */}
      <form onSubmit={handleSubmit((data) => mutate(data))}>
        <Controller
          control={control}
          name="name"
          render={({ field }) => <Input {...field} placeholder="Name" />}
        />
        <Button type="submit" disabled={isCreating}>
          {isCreating ? "Creating..." : "Create"}
        </Button>
      </form>
    </div>
  );
}
```

#### 3.5 Add Navigation Link

Update `apps/web/src/components/layout/Nav.tsx`:

```typescript
import { /* existing icons */, FeatureIcon } from "lucide-react";

const NAV_ITEMS = [
  // ... existing items
  { title: "Feature", url: "/feature", icon: <FeatureIcon /> },
];
```

---

## File Creation Checklist

For each new feature, create:

**Backend (`apps/server/src/module/<feature>/`):**
- [ ] `schema.ts` - Zod validation schemas
- [ ] `service.ts` - Business logic with `{msg, data}` response
- [ ] `route.ts` - Hono routes with `sValidator`
- [ ] Register in `index.ts`

**Frontend (`apps/web/src/`):**
- [ ] `schema/<feature>.ts` - Form validation schema
- [ ] `type/<feature>.ts` - Response type definitions
- [ ] `query/<feature>.ts` - TanStack Query hooks
- [ ] `routes/_auth/<feature>.tsx` - Page component
- [ ] Add nav link in `Nav.tsx`

---

## Database Schema Reference

### Auth Tables (`auth.ts`)
- `user` - id, name, email, emailVerified, image, createdAt, updatedAt
- `session` - id, expiresAt, token, userId, ipAddress, userAgent
- `account` - id, accountId, providerId, userId, accessToken, refreshToken
- `verification` - id, identifier, value, expiresAt

### Chat Tables (`chat.ts`)
- `messages` - id, senderUserId, groupId, messageText, sentDatetime, deletedFlag
- `messageAttachments` - id, messageId, attachmentId, attachmentFilename

---

## API Response Format

All backend endpoints MUST return:

```typescript
{
  msg: string,    // Result message
  data: any,      // Response data (object, array, or null)
}
```