import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { myFetch } from "@/lib/myFetch";
import type {
  CsvUserRow,
  TracksResponse,
  ServerUser,
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
  firstName: string;
  lastName: string;
  email: string;
  role: UserRole;
  track?: UserTrack;
  adminTracks?: UserTrack[];
  schoolName?: string;
  supervisorSchoolName?: string;
  mentorBackground?: string | null;
  mentorInstitution?: string;
  mentorReason?: string;
  mentorMaxGroupCount?: number;
  yearLevel?: number;
  interests?: string[];
  joinPermissionReceived?: boolean;
  active?: boolean;
};

type UpdateUserPayload = {
  firstName?: string;
  lastName?: string;
  role?: UserRole;
  track?: UserTrack | null;
  adminTracks?: string[];
  schoolName?: string | null;
  supervisorSchoolName?: string | null;
  mentorBackground?: string | null;
  mentorInstitution?: string | null;
  mentorReason?: string | null;
  mentorMaxGroupCount?: number | null;
  yearLevel?: number | null;
  interests?: string[];
  joinPermissionReceived?: boolean;
};

type UpdateStatusPayload = {
  isActive: boolean;
};

type MutationResponse<T> = {
  msg: string;
  data: T;
};

interface QueryUsersParams {
  page?: number;
  limit?: number;
  search?: string;
  role?: UserRole;
  track?: UserTrack;
  active?: boolean;
  sortBy?: "name" | "createdAt";
  sortOrder?: "asc" | "desc";
}

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

export function useQueryUsers(params: QueryUsersParams = {}) {
  const { page = 1, limit = 100, search, role, track, active, sortBy, sortOrder } = params;

  return useQuery({
    queryKey: ["users", page, limit, search, role, track, active, sortBy, sortOrder],
    queryFn: async (): Promise<UserPaginatedResponse> => {
      const res = await myFetch.get<{
        msg: string;
        data?: {
          items?: Array<Partial<ServerUser> & {
            firstName?: string | null;
            lastName?: string | null;
            isActive?: boolean | null;
            invitedAt?: string | null;
            activatedAt?: string | null;
            schoolName?: string | null;
            mentorBackground?: string | null;
            mentorInstitution?: string | null;
            mentorReason?: string | null;
            mentorMaxGroupCount?: number | null;
            yearLevel?: number | null;
            joinPermissionReceived?: boolean | null;
          }>;
          total?: number;
          page?: number;
          limit?: number;
          hasMore?: boolean;
        };
      }>("/user", {
        params: {
          page,
          limit,
          search,
          role,
          track,
          active,
          sortBy,
          sortOrder,
        },
      });

      return {
        msg: res.data.msg,
        data: {
          items: (res.data.data?.items ?? []).map(normalizeServerUser),
          total: res.data.data?.total ?? 0,
          page: res.data.data?.page ?? 1,
          limit: res.data.data?.limit ?? 100,
          hasMore: res.data.data?.hasMore ?? false,
        },
      };
    },
  });
}

export function useQueryTracks() {
  return useQuery({
    queryKey: ["user-tracks"],
    queryFn: async (): Promise<TracksResponse> => {
      const res = await myFetch.get<TracksResponse>("/user/tracks");
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

export function useUpdateUserStatus() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (payload: { id: string; updates: UpdateStatusPayload }) => {
      const res = await myFetch.patch<MutationResponse<UserAccount | null>>(
        `/user/${payload.id}/status`,
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

export function useDeleteUser() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (id: string) => {
      const res = await myFetch.delete<MutationResponse<null>>(`/user/${id}`);
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
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

export function normalizeServerUser(
  user: Partial<ServerUser> & {
    firstName?: string | null;
    lastName?: string | null;
    isActive?: boolean | null;
    invitedAt?: string | null;
    activatedAt?: string | null;
    schoolName?: string | null;
    yearLevel?: number | null;
    joinPermissionReceived?: boolean | null;
  },
): UserAccount {
  const resolvedFirstName = (user.firstName ?? "").trim();
  const resolvedLastName = (user.lastName ?? "").trim();
  const fallbackName = (user.name ?? "").trim();
  const name =
    `${resolvedFirstName} ${resolvedLastName}`.trim() || fallbackName;
  const [fallbackFirstName, fallbackLastName] = splitFullName(fallbackName);

  return {
    id: String(user.id ?? ""),
    name,
    firstName: resolvedFirstName || fallbackFirstName,
    lastName: resolvedLastName || fallbackLastName,
    email: user.email ?? "",
    role: (user.role ?? "") as UserRole,
    track: user.track ?? null,
    groupId: user.groupId ?? null,
    groupName: user.groupName ?? null,
    age: user.age ?? user.yearLevel ?? null,
    schoolName: user.schoolName ?? null,
    mentorBackground: user.mentorBackground ?? null,
    mentorInstitution: user.mentorInstitution ?? null,
    mentorReason: user.mentorReason ?? null,
    mentorMaxGroupCount: user.mentorMaxGroupCount ?? null,
    joinPermissionReceived: Boolean(user.joinPermissionReceived),
    interests: Array.isArray(user.interests) ? user.interests : [],
    adminTracks: Array.isArray((user as any).adminTracks) ? (user as any).adminTracks : [],
    createdAt:
      user.createdAt ?? user.invitedAt ?? user.activatedAt ?? new Date(0).toISOString(),
    updatedAt:
      user.updatedAt ?? user.activatedAt ?? user.invitedAt ?? new Date(0).toISOString(),
    active: Boolean(user.active ?? user.isActive),
    source: "server",
  };
}

export function makeLocalUser(values: UserFormValues): UserAccount {
  const timestamp = new Date().toISOString();
  const name = `${values.firstName} ${values.lastName}`.trim();
  return {
    id: `local-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    name,
    firstName: values.firstName.trim(),
    lastName: values.lastName.trim(),
    email: values.email.trim(),
    role: values.role,
    track: values.track,
    groupId: null,
    groupName: null,
    age: values.role === "student" ? values.yearLevel : null,
    schoolName:
      values.role === "student"
        ? values.schoolName || null
        : values.role === "supervisor"
          ? values.supervisorSchoolName || null
          : null,
    mentorBackground:
      values.role === "mentor" ? values.mentorBackground || null : null,
    mentorInstitution:
      values.role === "mentor" ? values.mentorInstitution || null : null,
    mentorReason: values.role === "mentor" ? values.mentorReason || null : null,
    mentorMaxGroupCount:
      values.role === "mentor" ? values.mentorMaxGroupCount : null,
    joinPermissionReceived:
      values.role === "student" ? values.joinPermissionReceived : false,
    adminTracks: values.role === "admin" ? values.adminTracks : [],
    interests:
      values.role === "student" || values.role === "mentor"
        ? values.interests
        : [],
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

  const requiredHeaders = ["firstname", "lastname", "email", "role"];
  const missing = requiredHeaders.filter((header) => headerIndex[header] === undefined);
  if (missing.length) {
    throw new Error(`Missing CSV columns: ${missing.join(", ")}`);
  }

  return dataRows
    .filter((row) => row.some((cell) => cell.trim()))
    .map((row, rowIndex) => {
      const roleValue = (row[headerIndex.role] ?? "").trim().toLowerCase();
      const role = normalizeRole(roleValue);
      const track = normalizeTrack((row[headerIndex.track] ?? "").trim());
      const adminTracksRaw = (row[headerIndex.admintracks] ?? "").trim();
      const statusRaw = (row[headerIndex.status] ?? "").trim().toLowerCase();
      const schoolName = (row[headerIndex.school] ?? "").trim();
      const yearLevelRaw =
        (row[headerIndex.yearlevel] ?? row[headerIndex.age] ?? "").trim();
      const interestsRaw = (row[headerIndex.interests] ?? "").trim();
      const mentorMaxGroupCountRaw =
        (row[headerIndex.maxgroupcount] ?? row[headerIndex.maxgroups] ?? "").trim();
      const mentorMaxGroupCount = mentorMaxGroupCountRaw
        ? Number(mentorMaxGroupCountRaw)
        : null;

      return {
        id: `csv-${rowIndex + 1}`,
        firstName: (row[headerIndex.firstname] ?? "").trim(),
        lastName: (row[headerIndex.lastname] ?? "").trim(),
        email: (row[headerIndex.email] ?? "").trim(),
        role,
        track,
        adminTracks: parseTrackList(adminTracksRaw),
        schoolName,
        supervisorSchoolName: role === "supervisor" ? schoolName : "",
        mentorBackground: (row[headerIndex.background] ?? "").trim(),
        mentorInstitution: (row[headerIndex.institution] ?? "").trim(),
        mentorReason: (row[headerIndex.mentorreason] ?? "").trim(),
        mentorMaxGroupCount: Number.isFinite(mentorMaxGroupCount)
          ? mentorMaxGroupCount
          : null,
        yearLevel: yearLevelRaw ? Number(yearLevelRaw) : null,
        interests: parseInterestList(interestsRaw),
        joinPermissionReceived: false,
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
  return track;
}

export function parseInterestList(input: string) {
  return Array.from(
    new Set(
      input
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean),
    ),
  );
}

function parseTrackList(input: string) {
  return Array.from(
    new Set(
      input
        .split(/[|;,]/)
        .map((item) => item.trim())
        .filter(Boolean),
    ),
  );
}

function splitFullName(name: string): [string, string] {
  const trimmed = name.trim();
  if (!trimmed) {
    return ["", ""];
  }

  const parts = trimmed.split(/\s+/);
  const firstName = parts.shift() ?? "";
  return [firstName, parts.join(" ")];
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
