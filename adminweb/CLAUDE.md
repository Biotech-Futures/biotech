# Web Project - React Frontend

## Project Overview

A React frontend application using TanStack Router for routing, TanStack Query for data fetching, and shadcn/ui for UI components. Runs on port 3000.

## Tech Stack

- **Framework**: React 19 with TypeScript
- **Routing**: TanStack Router (file-based routing)
- **Data Fetching**: Axios + TanStack Query
- **Tables**: TanStack Table + shadcn/ui table
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
│   │   ├── table.tsx        # shadcn table components
│   │   └── ...
│   ├── layout/              # Layout components
│   │   ├── app-sidebar.tsx
│   │   ├── Nav.tsx
│   │   └── NavUser.tsx
│   └── <feature>/           # Feature-specific components
│       ├── columns.tsx      # Table column definitions
│       ├── <Feature>Table.tsx  # Table with pagination
│       └── <Feature>Filters.tsx # Filter components
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

## Table Pattern (TanStack Table + shadcn/ui + Pagination)

For data tables, combine **@tanstack/react-table** with shadcn's table components and **TanStack Query pagination** for server-side search and pagination.

### Setup

```bash
# Add shadcn table component
pnpm dlx shadcn@latest add table
```

### Backend: Paginated API Endpoint

The backend must support pagination and search parameters:

```typescript
// Backend endpoint shape expected by the web app
export function queryUser(params: { page?: number; limit?: number; search?: string }) {
  const page = params.page ?? 1;
  const limit = params.limit ?? 10;
  const offset = (page - 1) * limit;

  // Query database with search and pagination
  const users = await db
    .select()
    .from(userTable)
    .where(params.search ? ilike(userTable.name, `%${params.search}%`) : undefined)
    .limit(limit)
    .offset(offset);

  const total = await db
    .select({ count: sql`count(*)` })
    .from(userTable)
    .where(params.search ? ilike(userTable.name, `%${params.search}%`) : undefined);

  return {
    msg: "Users retrieved successfully",
    data: {
      items: users,
      total: total[0].count,
      page,
      limit,
      hasMore: offset + users.length < total[0].count,
    },
  };
}

// Example HTTP route shape
userRoute.get("/", (c) => {
  const page = c.req.query("page") ?? "1";
  const limit = c.req.query("limit") ?? "10";
  const search = c.req.query("search") ?? "";
  const res = queryUser({ page: parseInt(page), limit: parseInt(limit), search });
  return c.json(res);
});
```

### Frontend: Paginated Query Hook

```typescript
// src/query/user.ts
import { myFetch } from "@/lib/myFetch";
import { useQuery } from "@tanstack/react-query";
import type { User, PaginatedResponse } from "@/type/user";

export function useQueryUsers(page: number = 1, search: string = "") {
  return useQuery({
    queryKey: ["users", page, search],
    queryFn: async (): Promise<PaginatedResponse<User>> => {
      const res = await myFetch.get<PaginatedResponse<User>>(
        `/user?page=${page}&limit=10&search=${encodeURIComponent(search)}`
      );
      return res.data;
    },
  });
}
```

### Frontend: Types

```typescript
// src/type/user.ts
export type User = {
  id: string;
  name: string;
  email: string;
  createdAt: string;
};

export type PaginatedResponse<T> = {
  msg: string;
  data: {
    items: T[];
    total: number;
    page: number;
    limit: number;
    hasMore: boolean;
  };
};
```

### Define Columns

```typescript
// src/components/user/columns.tsx
import type { ColumnDef } from "@tanstack/react-table";
import type { User } from "@/type/user";
import { ArrowUpDown, MoreHorizontal } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

export const columns: ColumnDef<User>[] = [
  {
    accessorKey: "name",
    header: ({ column }) => {
      return (
        <Button
          variant="ghost"
          onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}
        >
          Name
          <ArrowUpDown className="ml-2 size-4" />
        </Button>
      );
    },
  },
  {
    accessorKey: "email",
    header: "Email",
  },
  {
    accessorKey: "createdAt",
    header: "Created At",
    cell: ({ row }) => {
      return new Date(row.getValue("createdAt")).toLocaleDateString();
    },
  },
  {
    id: "actions",
    cell: ({ row }) => {
      const user = row.original;

      return (
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon">
              <MoreHorizontal className="size-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent>
            <DropdownMenuItem onClick={() => console.log("Edit", user.id)}>
              Edit
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => console.log("Delete", user.id)}>
              Delete
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      );
    },
  },
];
```

### Create Table with Pagination

```typescript
// src/components/user/UserTable.tsx
import type { ColumnDef } from "@tanstack/react-table";
import {
  flexRender,
  getCoreRowModel,
  useReactTable,
  getSortedRowModel,
} from "@tanstack/react-table";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import type { User } from "@/type/user";
import { ChevronLeftIcon, ChevronRightIcon } from "lucide-react";

interface UserTableProps {
  columns: ColumnDef<User>[];
  data: User[];
  page: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  isPending?: boolean;
}

export function UserTable({
  columns,
  data,
  page,
  totalPages,
  onPageChange,
  isPending,
}: UserTableProps) {
  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  return (
    <div className="space-y-4">
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            {table.getHeaderGroups().map((headerGroup) => (
              <TableRow key={headerGroup.id}>
                {headerGroup.headers.map((header) => (
                  <TableHead key={header.id}>
                    {header.isPlaceholder
                      ? null
                      : flexRender(
                          header.column.columnDef.header,
                          header.getContext()
                        )}
                  </TableHead>
                ))}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {isPending ? (
              <TableRow>
                <TableCell colSpan={columns.length} className="h-24 text-center">
                  Loading...
                </TableCell>
              </TableRow>
            ) : table.getRowModel().rows?.length ? (
              table.getRowModel().rows.map((row) => (
                <TableRow key={row.id}>
                  {row.getVisibleCells().map((cell) => (
                    <TableCell key={cell.id}>
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell colSpan={columns.length} className="h-24 text-center">
                  No results.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      {/* Pagination Controls */}
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          Page {page} of {totalPages}
        </p>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => onPageChange(page - 1)}
            disabled={page <= 1 || isPending}
          >
            <ChevronLeftIcon className="size-4" />
            Previous
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => onPageChange(page + 1)}
            disabled={page >= totalPages || isPending}
          >
            Next
            <ChevronRightIcon className="size-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}
```

### Search Input with Debounce

```typescript
// src/components/ui/search-input.tsx
import { Input } from "@/components/ui/input";
import { useState, useEffect, useRef, useCallback } from "react";

interface SearchInputProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  debounceMs?: number;
}

export function SearchInput({
  value,
  onChange,
  placeholder = "Search...",
  debounceMs = 300,
}: SearchInputProps) {
  const [localValue, setLocalValue] = useState(value);
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);

  const debouncedOnChange = useCallback((newValue: string) => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }
    timeoutRef.current = setTimeout(() => {
      onChange(newValue);
    }, debounceMs);
  }, [onChange, debounceMs]);

  useEffect(() => {
    setLocalValue(value);
  }, [value]);

  useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, []);

  return (
    <Input
      placeholder={placeholder}
      value={localValue}
      onChange={(e) => {
        setLocalValue(e.target.value);
        debouncedOnChange(e.target.value);
      }}
      className="max-w-sm"
    />
  );
}
```

### Use in Page Component

```typescript
// src/routes/_auth/user.tsx
import { createFileRoute } from "@tanstack/react-router";
import { useState, useEffect } from "react";
import { UserTable } from "@/components/user/UserTable";
import { columns } from "@/components/user/columns";
import { SearchInput } from "@/components/ui/search-input";
import { useQueryUsers } from "@/query/user";

export const Route = createFileRoute("/_auth/user")({
  component: UserPage,
});

function UserPage() {
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);

  const { data, isPending } = useQueryUsers(page, search);

  // Reset to page 1 when search changes
  useEffect(() => {
    setPage(1);
  }, [search]);

  const users = data?.data.items ?? [];
  const totalPages = Math.ceil((data?.data.total ?? 0) / (data?.data.limit ?? 10));

  return (
    <div className="p-4 space-y-4">
      <h1 className="text-2xl font-bold">Users</h1>
      <SearchInput
        value={search}
        onChange={setSearch}
        placeholder="Search users..."
      />
      <UserTable
        columns={columns}
        data={users}
        page={page}
        totalPages={totalPages}
        onPageChange={setPage}
        isPending={isPending}
      />
    </div>
  );
}
```

### Table Features

- **Pagination**: Previous/Next buttons with page display
- **Server-side Search**: Debounced search triggers API call
- **Sorting**: Click column headers to sort (client-side for loaded data)
- **Actions**: Dropdown menu for row actions

## Data Fetching Pattern

### Axios Configuration

Use the pre-configured axios instance from `myFetch.ts`:

```typescript
// src/lib/myFetch.ts
import axios from "axios";
import { buildUrl } from "@/util/url";

export const myFetch = axios.create({
  baseURL: buildUrl(
    import.meta.env.VITE_PUBLIC_API_URL || "http://localhost:3003",
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
pnpm dlx shadcn@latest add table   # For data tables
pnpm dlx shadcn@latest add dropdown-menu  # For table row actions
```

## Best Practices

1. **UI Components**: Always check `src/components/ui/` first - use existing shadcn components
2. **Icons**: Import from `lucide-react` only - no custom SVG icons
3. **Forms**: Use `react-hook-form` + `zodResolver` + Zod schema
4. **Tables**: Use `@tanstack/react-table` + `useQuery` with pagination + shadcn table + debounced search
5. **API Types**: Define schema first, infer types with `z.infer`, separate response types in `src/type/`
6. **Query Hooks**: Wrap all API calls in TanStack Query hooks in `src/query/`
7. **Styling**: Use Tailwind classes directly, or use `cn()` utility for conditional classes
