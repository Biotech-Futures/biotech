# Web Project - React Frontend

## Project Overview

A React frontend application using TanStack Router for routing, TanStack Query for data fetching, and shadcn/ui for UI components. Runs on port 3000.

## Tech Stack

- **Framework**: React 19 with TypeScript
- **Routing**: TanStack Router (file-based routing)
- **Data Fetching**: Axios + TanStack Query
- **UI Components**: shadcn/ui (Radix-based)
- **Styling**: Tailwind CSS v4
- **Icons**: Lucide React
- **Form Validation**: react-hook-form + Zod + @hookform/resolvers
- **State Management**: Zustand (for global state)

## Project Structure

```
src/
├── main.tsx                 # Application entry point
├── router.tsx               # Router configuration
├── routes/                  # File-based routes (TanStack Router)
│   ├── __root.tsx           # Root layout with providers
│   └── _auth/               # Authenticated routes
│       ├── route.tsx        # Auth layout
│       ├── demo.tsx         # Demo page
│       ├── group.tsx        # Group page
│       └── ...
├── components/
│   ├── ui/                  # shadcn/ui components
│   │   ├── button.tsx
│   │   ├── input.tsx
│   │   ├── sidebar.tsx
│   │   └── ...
│   └── layout/              # Layout components
│       ├── app-sidebar.tsx
│       ├── Nav.tsx
│       └── NavUser.tsx
├── lib/
│   ├── utils.ts             # Utility functions (cn, etc.)
│   └── myFetch.ts           # Axios instance configuration
├── hooks/
│   └── use-mobile.ts        # Custom hooks
├── schema/                  # Zod schemas for validation
│   └── demo.ts              # Example: createDemoSchema
├── type/                    # TypeScript type definitions
│   └── deme.ts              # Response types from API
├── query/                   # TanStack Query hooks
│   ├── index.ts             # Export barrel
│   └── demo.ts              # Query/mutation hooks
└── util/
    └── url.ts               # URL builder utility
```

## UI Components Guidelines

### Use shadcn/ui First

Always use existing shadcn/ui components before creating custom components.

```bash
# Add a new shadcn component
pnpm dlx shadcn@latest add <component-name>
```

Available components are in `src/components/ui/`. Import using:

```typescript
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Sidebar, SidebarContent, SidebarHeader } from "@/components/ui/sidebar";
```

### Icons - Use Lucide

All icons must come from `lucide-react`:

```typescript
import { UsersIcon, MailIcon, CalendarIcon, SettingsIcon } from "lucide-react";

// Usage in component
<UsersIcon className="size-4" />
<Button><SettingsIcon /> Settings</Button>
```

## Data Fetching Pattern

### Axios Configuration

Use the pre-configured axios instance from `myFetch.ts`:

```typescript
// src/lib/myFetch.ts
import axios from "axios";
import { buildUrl } from "@/util/url";

export const myFetch = axios.create({
  baseURL: buildUrl(
    import.meta.env.VITE_PUBLIC_API_URL || "http://localhost:3001",
    "api",
    "v1",
  ),
  withCredentials: true,
});
```

### TanStack Query Hooks

Create query hooks in `src/query/<feature>.ts`:

```typescript
// src/query/demo.ts
import { myFetch } from "@/lib/myFetch";
import { useMutation, useQuery } from "@tanstack/react-query";
import type { CreateDemo } from "@/schema/demo";
import type { Demo } from "@/type/demo";

// GET query
export function useQueryDemo() {
  return useQuery({
    queryKey: ["demo"],
    queryFn: async () => {
      return myFetch.get<{ msg: string; data: Demo }>("/demo");
    },
  });
}

// POST mutation
export function useCreateDemo() {
  return useMutation({
    mutationFn: async (data: CreateDemo) => {
      return myFetch.post<Demo>("/demo", data);
    },
    onSuccess: () => {
      // Handle success (e.g., invalidate queries)
    },
    onError: (error) => {
      // Handle error
    },
  });
}
```

## Form Validation Pattern

### Schema Definition

Define Zod schemas in `src/schema/<feature>.ts`:

```typescript
// src/schema/demo.ts
import { z } from "zod";

export const createDemoSchema = z.object({
  name: z.string().min(2).max(100),
  age: z.number().min(0).max(150),
});

// Infer TypeScript type from schema
export type CreateDemo = z.infer<typeof createDemoSchema>;
```

### Type Definitions

Define response types in `src/type/<feature>.ts`:

```typescript
// src/type/demo.ts
export type Demo = {
  name: string;
  age: number;
};

// API response wrapper type
export type ApiResponse<T> = {
  msg: string;
  data: T;
};
```

### Form Implementation

Use react-hook-form with zodResolver:

```typescript
import { useForm, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { createDemoSchema, type CreateDemo } from "@/schema/demo";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

function MyForm() {
  const { mutate, isPending } = useCreateDemo();

  const { control, handleSubmit } = useForm<CreateDemo>({
    defaultValues: {
      name: "",
      age: 0,
    },
    resolver: zodResolver(createDemoSchema),
  });

  return (
    <form onSubmit={handleSubmit((data) => mutate(data))}>
      <Controller
        control={control}
        name="name"
        render={({ field, fieldState }) => (
          <div>
            <Input {...field} />
            {fieldState.error && (
              <span className="text-destructive">{fieldState.error.message}</span>
            )}
          </div>
        )}
      />
      <Controller
        control={control}
        name="age"
        render={({ field }) => (
          <Input {...field} type="number" />
        )}
      />
      <Button type="submit" disabled={isPending}>
        {isPending ? "Submitting..." : "Submit"}
      </Button>
    </form>
  );
}
```

## Routing Pattern

TanStack Router uses file-based routing in `src/routes/`:

- `__root.tsx` - Root layout with global providers
- `_auth/` - Authentication-required routes (layout group)
- `_auth/route.tsx` - Auth layout with sidebar
- `_auth/demo.tsx` - `/demo` route component

```typescript
// src/routes/_auth/demo.tsx
import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/_auth/demo")({
  component: DemoPage,
});

function DemoPage() {
  // Page component logic
}
```

Navigation using Link:

```typescript
import { Link } from "@tanstack/react-router";

<Link to="/demo" activeProps={{ className: "bg-primary/10" }}>
  Demo
</Link>
```

## Common Commands

```bash
pnpm dev       # Start dev server on port 3000
pnpm build     # Build for production
pnpm preview   # Preview production build
pnpm test      # Run tests
```

## Adding New shadcn Components

```bash
pnpm dlx shadcn@latest add dialog
pnpm dlx shadcn@latest add select
pnpm dlx shadcn@latest add form
```

## Best Practices

1. **UI Components**: Always check `src/components/ui/` first - use existing shadcn components
2. **Icons**: Import from `lucide-react` only - no custom SVG icons
3. **Forms**: Use `react-hook-form` + `zodResolver` + Zod schema
4. **API Types**: Define schema first, infer types with `z.infer`, separate response types in `src/type/`
5. **Query Hooks**: Wrap all API calls in TanStack Query hooks in `src/query/`
6. **Styling**: Use Tailwind classes directly, or use `cn()` utility for conditional classes