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
  adminIsGlobal?: boolean;
  schoolName?: string;
  supervisorSchoolName?: string;
  mentorBackground?: string | null;
  mentorInstitution?: string;
  mentorReason?: string;
  mentorMaxGroupCount?: number;
  yearLevel?: number;
  interests?: string[];
  supervisorEmail?: string;
  active?: boolean;
};

type UpdateUserPayload = {
  firstName?: string;
  lastName?: string;
  role?: UserRole;
  track?: UserTrack | null;
  adminTracks?: string[];
  adminIsGlobal?: boolean;
  schoolName?: string | null;
  supervisorSchoolName?: string | null;
  mentorBackground?: string | null;
  mentorInstitution?: string | null;
  mentorReason?: string | null;
  mentorMaxGroupCount?: number | null;
  yearLevel?: number | null;
  interests?: string[];
  supervisorEmail?: string;
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
  sortBy?: "name" | "email" | "role" | "track" | "status" | "createdAt";
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
    mutationFn: async (payload: CreateUserPayload[]) => {
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
    interests: Array.isArray(user.interests) ? user.interests : [],
    adminTracks: Array.isArray((user as any).adminTracks) ? (user as any).adminTracks : [],
    adminIsGlobal: Boolean((user as any).adminIsGlobal),
    createdAt:
      user.createdAt ?? user.invitedAt ?? user.activatedAt ?? new Date(0).toISOString(),
    updatedAt:
      user.updatedAt ?? user.activatedAt ?? user.invitedAt ?? new Date(0).toISOString(),
    active: Boolean(user.active ?? user.isActive),
    source: "server",
    supervisorName: (user as any).supervisorName ?? null,
    supervisorEmail: (user as any).supervisorEmail ?? null,
    supervisees: Array.isArray((user as any).supervisees) ? (user as any).supervisees : [],
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
    supervisorName: null,
    supervisorEmail: null,
    supervisees: [],
    adminTracks: values.role === "admin" ? values.adminTracks : [],
    adminIsGlobal: values.role === "admin" ? values.adminIsGlobal : false,
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

  const hasSplitNameHeaders =
    headerIndex.firstname !== undefined && headerIndex.lastname !== undefined;
  const hasNameHeader = headerIndex.name !== undefined;

  if (!hasSplitNameHeaders && !hasNameHeader) {
    throw new Error(
      "Missing CSV columns: provide either name, or both firstName and lastName.",
    );
  }

  const requiredHeaders = ["email", "role"];
  const missing = requiredHeaders.filter((header) => headerIndex[header] === undefined);
  if (missing.length) {
    throw new Error(`Missing CSV columns: ${missing.join(", ")}`);
  }

  return dataRows
    .filter((row) => row.some((cell) => cell.trim()))
    .map((row, rowIndex) => {
      const rawName = (row[headerIndex.name] ?? "").trim();
      const [parsedFirstName, parsedLastName] = splitFullName(rawName);
      const firstName = hasSplitNameHeaders
        ? (row[headerIndex.firstname] ?? "").trim()
        : parsedFirstName;
      const lastName = hasSplitNameHeaders
        ? (row[headerIndex.lastname] ?? "").trim()
        : parsedLastName;
      const roleValue = (row[headerIndex.role] ?? "").trim().toLowerCase();
      const role = normalizeRole(roleValue);
      const track = normalizeTrack((row[headerIndex.track] ?? "").trim());
      const adminTracksRaw = (row[headerIndex.admintracks] ?? "").trim();
      const adminIsGlobalRaw = (
        row[headerIndex.adminisglobal] ??
        row[headerIndex.globaladmin] ??
        row[headerIndex.isglobaladmin] ??
        ""
      ).trim();
      const statusRaw = (row[headerIndex.status] ?? "").trim().toLowerCase();
      const schoolName = (
        row[headerIndex.school] ??
        row[headerIndex.schoolname] ??
        ""
      ).trim();
      const yearLevelRaw =
        (row[headerIndex.yearlevel] ?? row[headerIndex.age] ?? "").trim();
      const interestsRaw = (row[headerIndex.interests] ?? "").trim();
      const supervisorEmailRaw = (row[headerIndex.supervisoremail] ?? "").trim();
      const mentorMaxGroupCountRaw =
        (row[headerIndex.maxgroupcount] ?? row[headerIndex.maxgroups] ?? "").trim();
      const mentorMaxGroupCount = mentorMaxGroupCountRaw
        ? Number(mentorMaxGroupCountRaw)
        : null;

      if (!firstName || !lastName) {
        throw new Error(
          `Row ${rowIndex + 2}: first and last name are required. Use either name, or firstName and lastName columns.`,
        );
      }

      const email = (row[headerIndex.email] ?? "").trim();
      if (!email) {
        throw new Error(`Row ${rowIndex + 2}: email is required.`);
      }

      return {
        id: `csv-${rowIndex + 1}`,
        firstName,
        lastName,
        email,
        role,
        track,
        adminTracks: parseTrackList(adminTracksRaw),
        adminIsGlobal: parseBoolean(adminIsGlobalRaw),
        schoolName,
        supervisorSchoolName:
          role === "supervisor"
            ? (
                row[headerIndex.supervisorschoolname] ??
                row[headerIndex.school] ??
                row[headerIndex.schoolname] ??
                ""
              ).trim()
            : "",
        mentorBackground: (row[headerIndex.background] ?? "").trim(),
        mentorInstitution: (
          row[headerIndex.mentorinstitution] ??
          row[headerIndex.institution] ??
          ""
        ).trim(),
        mentorReason: (row[headerIndex.mentorreason] ?? "").trim(),
        mentorMaxGroupCount: Number.isFinite(mentorMaxGroupCount)
          ? mentorMaxGroupCount
          : null,
        yearLevel: yearLevelRaw ? Number(yearLevelRaw) : null,
        interests: parseInterestList(interestsRaw),
        active: statusRaw ? statusRaw !== "inactive" : true,
        supervisorEmail: role === "student" ? supervisorEmailRaw : "",
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

function parseBoolean(input: string) {
  const normalized = input.trim().toLowerCase();
  return (
    normalized === "true" ||
    normalized === "yes" ||
    normalized === "y" ||
    normalized === "1"
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
