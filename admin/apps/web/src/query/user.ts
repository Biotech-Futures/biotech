import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { myFetch } from "@/lib/myFetch";
import type {
  CsvUserRow,
  UserAccount,
  UserFormValues,
  UserOverride,
  UserPaginatedResponse,
  UserTrack,
  UserRole,
} from "@/type/user";

const LOCAL_USERS_KEY = "admin.user.local-users";
const USER_OVERRIDES_KEY = "admin.user.overrides";

type CreateUserPayload = {
  name: string;
  email: string;
  role: UserRole;
  track?: UserTrack;
  active?: boolean;
};

type UpdateUserPayload = {
  name?: string;
  email: string;
  role?: UserRole;
  track?: UserTrack | null;
  active?: boolean;
};

type MutationResponse<T> = {
  msg: string;
  data: T;
};

function readStorage<T>(key: string, fallback: T): T {
  try {
    const raw = window.localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

function writeStorage<T>(key: string, value: T) {
  window.localStorage.setItem(key, JSON.stringify(value));
}

export function useQueryUsers() {
  return useQuery({
    queryKey: ["users"],
    queryFn: async (): Promise<UserPaginatedResponse> => {
      const res = await myFetch.get<UserPaginatedResponse>("/user", {
        params: {
          page: 1,
          limit: 100,
        },
      });
      return res.data;
    },
  });
}

export function useCreateUser() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (payload: CreateUserPayload) => {
      const res = await myFetch.post<MutationResponse<UserAccount | null>>(
        "/user",
        payload,
      );
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
    },
  });
}

export function useBulkCreateUsers() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (payload: { users: CreateUserPayload[] }) => {
      const res = await myFetch.post<
        MutationResponse<{ created: UserAccount[]; skipped: string[] }>
      >("/user/bulk", payload);
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
    },
  });
}

export function useUpdateUser() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (payload: { id: string; updates: UpdateUserPayload }) => {
      const res = await myFetch.put<MutationResponse<UserAccount | null>>(
        `/user/${payload.id}`,
        payload.updates,
      );
      return res.data;
    },
    onSuccess: (_, { id }) => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
      queryClient.invalidateQueries({ queryKey: ["user", id] });
    },
  });
}

export function loadLocalUsers() {
  return readStorage<UserAccount[]>(LOCAL_USERS_KEY, []);
}

export function saveLocalUsers(users: UserAccount[]) {
  writeStorage(LOCAL_USERS_KEY, users);
}

export function loadUserOverrides() {
  return readStorage<Record<string, UserOverride>>(USER_OVERRIDES_KEY, {});
}

export function saveUserOverrides(overrides: Record<string, UserOverride>) {
  writeStorage(USER_OVERRIDES_KEY, overrides);
}

export function normalizeServerUser(user: UserAccount): UserAccount {
  return {
    ...user,
    source: "server",
  };
}

export function makeLocalUser(values: UserFormValues): UserAccount {
  const timestamp = new Date().toISOString();
  return {
    id: `local-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    name: values.name.trim(),
    email: values.email.trim(),
    role: values.role,
    track: values.track,
    groupId: null,
    groupName: null,
    age: values.role === "student" ? 16 : null,
    interests: values.role === "student" ? ["biology"] : [],
    createdAt: timestamp,
    updatedAt: timestamp,
    active: values.active,
    source: "local",
  };
}

export function mergeUsers(
  serverUsers: ServerUser[] | undefined,
  localUsers: UserAccount[],
  overrides: Record<string, UserOverride>,
) {
  const normalized = (serverUsers ?? []).map(normalizeServerUser);

  return [...normalized, ...localUsers].map((user) => {
    const override = overrides[user.id];
    if (!override) return user;
    return {
      ...user,
      ...override,
      updatedAt: override.updatedAt ?? user.updatedAt,
    };
  });
}

export function parseCsvUsers(text: string) {
  const rows = parseCsvRows(text);
  if (!rows.length) {
    throw new Error("The CSV file is empty.");
  }

  const [headerRow, ...dataRows] = rows;
  const headers = headerRow.map((header) => header.trim().toLowerCase());
  const headerIndex = Object.fromEntries(
    headers.map((header, index) => [header, index]),
  );

  const requiredHeaders = ["name", "email", "role"];
  const missing = requiredHeaders.filter((header) => headerIndex[header] === undefined);
  if (missing.length) {
    throw new Error(`Missing CSV columns: ${missing.join(", ")}`);
  }

  return dataRows
    .filter((row) => row.some((cell) => cell.trim()))
    .map((row, rowIndex) => {
      const roleValue = (row[headerIndex.role] ?? "").trim().toLowerCase();
      const role = normalizeRole(roleValue);
      const track = normalizeTrack((row[headerIndex.track] ?? "").trim().toLowerCase());
      const statusRaw = (row[headerIndex.status] ?? "").trim().toLowerCase();

      return {
        id: `csv-${rowIndex + 1}`,
        name: (row[headerIndex.name] ?? "").trim(),
        email: (row[headerIndex.email] ?? "").trim(),
        role,
        track,
        active: statusRaw ? statusRaw !== "inactive" : true,
      } satisfies CsvUserRow;
    });
}

function normalizeRole(role: string) {
  if (role === "student" || role === "mentor" || role === "admin" || role === "supervisor") {
    return role;
  }

  throw new Error(`Unsupported role "${role}". Use student, mentor, supervisor, or admin.`);
}

function normalizeTrack(track: string) {
  if (!track || track === "unassigned" || track === "none") {
    return null;
  }
  if (track === "frontend" || track === "backend" || track === "fullstack" || track === "data") {
    return track;
  }

  throw new Error(`Unsupported track "${track}". Use frontend, backend, fullstack, or data.`);
}

function parseCsvRows(text: string) {
  const rows: string[][] = [];
  let currentRow: string[] = [];
  let currentCell = "";
  let insideQuotes = false;

  for (let i = 0; i < text.length; i += 1) {
    const char = text[i];
    const nextChar = text[i + 1];

    if (char === '"') {
      if (insideQuotes && nextChar === '"') {
        currentCell += '"';
        i += 1;
      } else {
        insideQuotes = !insideQuotes;
      }
      continue;
    }

    if (char === "," && !insideQuotes) {
      currentRow.push(currentCell);
      currentCell = "";
      continue;
    }

    if ((char === "\n" || char === "\r") && !insideQuotes) {
      if (char === "\r" && nextChar === "\n") {
        i += 1;
      }
      currentRow.push(currentCell);
      rows.push(currentRow);
      currentRow = [];
      currentCell = "";
      continue;
    }

    currentCell += char;
  }

  if (currentCell.length || currentRow.length) {
    currentRow.push(currentCell);
    rows.push(currentRow);
  }

  return rows;
}
