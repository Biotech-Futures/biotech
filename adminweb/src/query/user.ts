import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { myFetch } from "@/lib/myFetch";
import type {
  CsvUserRow,
  StatesResponse,
  ServerUser,
  UserAccount,
  UserFormValues,
  UserOverride,
  UserPaginatedResponse,
  UserRole,
} from "@/type/user";

const LOCAL_USERS_KEY = "admin.user.local-users";
const USER_OVERRIDES_KEY = "admin.user.overrides";

type CreateUserPayload = {
  firstName: string;
  lastName: string;
  email: string;
  role: UserRole;
  // Backend create resolves the state by name (add_users_by_role reads `state`).
  state?: string;
  // Country lets the backend get_or_create the state for registration-export imports.
  country?: string;
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
  // Backend update resolves the state by id (update_user reads `stateId`).
  stateId?: number | null;
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

type BulkStatusResult = {
  updatedIds: number[];
  unchangedIds: number[];
  notFoundIds: number[];
  skippedSelf: boolean;
};

// Filters mirror the list query so a "select all matching" bulk action targets
// exactly the rows the admin was viewing.
export type BulkStatusFilters = {
  search?: string;
  role?: UserRole;
  state?: string;
  active?: boolean;
};

export type BulkStatusVars =
  | { ids: string[]; isActive: boolean }
  | {
      selectAll: true;
      filters: BulkStatusFilters;
      excludeIds: string[];
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
  state?: string;
  active?: boolean;
  sortBy?: "name" | "email" | "role" | "state" | "status" | "createdAt";
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
  const { page = 1, limit = 100, search, role, state, active, sortBy, sortOrder } = params;

  return useQuery({
    queryKey: ["users", page, limit, search, role, state, active, sortBy, sortOrder],
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
          state,
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

export function useQueryStates() {
  return useQuery({
    queryKey: ["user-states"],
    queryFn: async (): Promise<StatesResponse> => {
      const res = await myFetch.get<StatesResponse>("/user/states");
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
        MutationResponse<{
          created: UserAccount[];
          skipped: { email: string; reason: string }[];
        }>
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

export function useBulkUpdateUserStatus() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (payload: BulkStatusVars) => {
      const body =
        "selectAll" in payload
          ? {
              selectAll: true,
              isActive: payload.isActive,
              filters: payload.filters,
              excludeIds: payload.excludeIds.map(Number),
            }
          : { userIds: payload.ids.map(Number), isActive: payload.isActive };

      const res = await myFetch.patch<MutationResponse<BulkStatusResult | null>>(
        "/user/bulk-status",
        body,
      );
      return res.data;
    },
    onSuccess: (_, payload) => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
      if (!("selectAll" in payload)) {
        for (const id of payload.ids) {
          queryClient.invalidateQueries({ queryKey: ["user", id] });
        }
      }
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

export type BulkDeleteResult = {
  deletedIds: number[];
  failedIds?: number[];
  notFoundIds: number[];
  skippedSelf: boolean;
  skippedAdmins?: number;
};

export type BulkDeleteVars =
  | { ids: string[] }
  | {
      selectAll: true;
      filters: BulkStatusFilters;
      excludeIds: string[];
      /** Count the admin reviewed; the server refuses if the live set grew past it. */
      expectedCount: number;
    };

/** Permanently delete users (hard delete) in one request — explicit ids or
 *  "select all matching" (resolved server-side from the same list filters). */
export function useBulkDeleteUsers() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (payload: BulkDeleteVars) => {
      const body =
        "selectAll" in payload
          ? {
              selectAll: true,
              filters: payload.filters,
              excludeIds: payload.excludeIds.map(Number),
              expectedCount: payload.expectedCount,
            }
          : { userIds: payload.ids.map(Number) };

      const res = await myFetch.post<MutationResponse<BulkDeleteResult | null>>(
        "/user/bulk-delete",
        body,
      );
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
      queryClient.invalidateQueries({ queryKey: ["students"] });
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
    state: user.state ?? null,
    groupId: user.groupId ?? null,
    groupName: user.groupName ?? null,
    age: user.age ?? user.yearLevel ?? null,
    schoolName: user.schoolName ?? null,
    mentorBackground: user.mentorBackground ?? null,
    mentorInstitution: user.mentorInstitution ?? null,
    mentorReason: user.mentorReason ?? null,
    mentorMaxGroupCount: user.mentorMaxGroupCount ?? null,
    interests: Array.isArray(user.interests) ? user.interests : [],
    isAdmin: Boolean(user.isAdmin),
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
    state: null,
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
    isAdmin: values.role === "admin",
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
      const state = normalizeState((row[headerIndex.state] ?? "").trim());
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
        state,
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

function normalizeState(state: string) {
  if (!state || state.toLowerCase() === "unassigned" || state.toLowerCase() === "none") {
    return null;
  }
  return state;
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

// ── Mentor registration-export import ──────────────────────────────────────────

export type MentorImportRow = {
  firstName: string;
  lastName: string;
  email: string;
  country: string;
  state: string;
  interests: string[];
  mentorReason: string;
  mentorInstitution: string;
  mentorBackground: string | null;
  mentorMaxGroupCount: number;
  /** Set when the raw Background value couldn't be mapped to the enum. */
  backgroundNote?: string;
};

export type ImportRowError = { rowNumber: number; email: string; reason: string };

/** Map the export's Background text to the MentorProfile enum; null = leave unset. */
function mapMentorBackground(raw: string): string | null {
  const v = raw.trim().toLowerCase();
  if (!v) return null;
  if (v === "industry") return "industry";
  if (v.includes("undergraduate")) return "undergraduate";
  if (v.includes("postgraduate")) return "postgraduate";
  if (v.includes("hdr")) return "hdr";
  return null; // "Academic" / anything unrecognised → leave background unset
}

function normalizeHeader(header: string): string {
  return header.trim().toLowerCase().replace(/\s+/g, " ");
}

// Registration-export header (space/case tolerant) → canonical key.
const MENTOR_HEADER_ALIASES: Record<string, string> = {
  "email address": "email",
  email: "email",
  "first name": "firstName",
  firstname: "firstName",
  surname: "lastName",
  "last name": "lastName",
  lastname: "lastName",
  country: "country",
  region: "region",
  state: "region",
  "mentor reason": "mentorReason",
  capacity: "capacity",
  "max group count": "capacity",
  "area(s) of interest": "interests",
  "areas of interest": "interests",
  interests: "interests",
  background: "background",
  "institution or company": "institution",
  institution: "institution",
};

/**
 * Parse a Mentors registration export. Never throws per-row: valid rows are
 * returned for import, invalid rows are collected with a human reason. Throws
 * only for a wrong/empty file (missing required columns) so the UI can show an
 * actionable "this doesn't look like a Mentors export" message.
 */
export function parseMentorCsv(text: string): {
  valid: MentorImportRow[];
  invalid: ImportRowError[];
} {
  const rows = parseCsvRows(text);
  if (!rows.length) {
    throw new Error("The CSV file is empty.");
  }

  const [headerRow, ...dataRows] = rows;
  const colIndex: Record<string, number> = {};
  headerRow.forEach((header, index) => {
    const canonical = MENTOR_HEADER_ALIASES[normalizeHeader(header)];
    if (canonical && colIndex[canonical] === undefined) {
      colIndex[canonical] = index;
    }
  });

  const required: Array<[string, string]> = [
    ["email", "Email Address"],
    ["firstName", "First Name"],
    ["lastName", "Surname"],
    ["country", "Country"],
    ["interests", "Area(s) of Interest"],
    ["mentorReason", "Mentor Reason"],
    ["institution", "Institution or Company"],
    ["capacity", "Capacity"],
  ];
  const missing = required
    .filter(([key]) => colIndex[key] === undefined)
    .map(([, label]) => label);
  if (missing.length) {
    throw new Error(
      `This doesn't look like a Mentors export — missing columns: ${missing.join(", ")}.`,
    );
  }

  const cell = (row: string[], key: string) =>
    colIndex[key] !== undefined ? (row[colIndex[key]] ?? "").trim() : "";

  const valid: MentorImportRow[] = [];
  const invalid: ImportRowError[] = [];

  dataRows
    .filter((row) => row.some((value) => value.trim()))
    .forEach((row, index) => {
      const rowNumber = index + 2; // account for the header row
      const email = cell(row, "email").toLowerCase();
      const firstName = cell(row, "firstName");
      const lastName = cell(row, "lastName");
      const country = cell(row, "country");
      const region = cell(row, "region");
      const interests = parseInterestList(cell(row, "interests"));
      const mentorReason = cell(row, "mentorReason");
      const institution = cell(row, "institution");
      const capacityRaw = cell(row, "capacity");
      const backgroundRaw = cell(row, "background");

      const state = country === "Australia" ? region : country;
      const capacity = Number(capacityRaw);

      const problems: string[] = [];
      if (!email) problems.push("missing email");
      else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email))
        problems.push("invalid email");
      if (!firstName || !lastName) problems.push("missing first or last name");
      if (!state) problems.push("missing country/region");
      if (!interests.length) problems.push("no interests");
      if (!mentorReason) problems.push("missing mentor reason");
      if (!institution) problems.push("missing institution");
      if (!capacityRaw || !Number.isFinite(capacity) || capacity <= 0)
        problems.push("invalid capacity");

      if (problems.length) {
        invalid.push({
          rowNumber,
          email: email || "(no email)",
          reason: problems.join(", "),
        });
        return;
      }

      const mentorBackground = mapMentorBackground(backgroundRaw);
      valid.push({
        firstName,
        lastName,
        email,
        country,
        state,
        interests,
        mentorReason,
        mentorInstitution: institution,
        mentorBackground,
        mentorMaxGroupCount: capacity,
        backgroundNote:
          backgroundRaw && !mentorBackground
            ? `background "${backgroundRaw}" not recognised — left unset`
            : undefined,
      });
    });

  return { valid, invalid };
}

// ── Student registration-export import ─────────────────────────────────────────

export type StudentImportRow = {
  firstName: string;
  lastName: string;
  email: string;
  country: string;
  state: string;
  schoolName: string;
  yearLevel: number;
  interests: string[];
  guardianFirstName: string;
  guardianLastName: string;
  guardianEmail: string;
  supervisorFirstName: string;
  supervisorLastName: string;
  supervisorEmail: string;
  joinpermResponseId: string;
  /** False when there's no approval ResponseID → import inactive. */
  active: boolean;
  /** Co-registration: friends sharing this land in one group, skipping auto-matching. */
  groupNumber?: string;
};

const STUDENT_HEADER_ALIASES: Record<string, string> = {
  "student email address": "email",
  "email address": "email",
  email: "email",
  "first name": "firstName",
  firstname: "firstName",
  surname: "lastName",
  "last name": "lastName",
  lastname: "lastName",
  "guardian first name": "guardianFirstName",
  "guardian surname": "guardianLastName",
  "guardian last name": "guardianLastName",
  "guardian email": "guardianEmail",
  "school name": "school",
  school: "school",
  schoolname: "school",
  "year level": "yearLevel",
  yearlevel: "yearLevel",
  "area(s) of interest": "interests",
  "areas of interest": "interests",
  interests: "interests",
  "supervisor first name": "supervisorFirstName",
  "supervisor surname": "supervisorLastName",
  "supervisor last name": "supervisorLastName",
  "supervisor email": "supervisorEmail",
  "parent/guardian approval responseid": "responseId",
  "approval responseid": "responseId",
  responseid: "responseId",
  country: "country",
  region: "region",
  state: "region",
  "group number": "groupNumber",
  "group no": "groupNumber",
  "group no.": "groupNumber",
  "group #": "groupNumber",
  "group id": "groupNumber",
  group: "groupNumber",
  groupnumber: "groupNumber",
};

/**
 * Parse a Students registration export. Supervisors are derived from the
 * student row. Never throws per-row (valid/invalid split); throws only for a
 * wrong/empty file so the UI can show a "missing columns" message.
 */
export function parseStudentCsv(text: string): {
  valid: StudentImportRow[];
  invalid: ImportRowError[];
} {
  const rows = parseCsvRows(text);
  if (!rows.length) {
    throw new Error("The CSV file is empty.");
  }

  const [headerRow, ...dataRows] = rows;
  const colIndex: Record<string, number> = {};
  headerRow.forEach((header, index) => {
    const canonical = STUDENT_HEADER_ALIASES[normalizeHeader(header)];
    if (canonical && colIndex[canonical] === undefined) {
      colIndex[canonical] = index;
    }
  });

  const required: Array<[string, string]> = [
    ["email", "Student email address"],
    ["firstName", "First Name"],
    ["lastName", "Surname"],
    ["country", "Country"],
    ["school", "School Name"],
    ["yearLevel", "Year Level"],
    ["interests", "Area(s) of Interest"],
  ];
  const missing = required
    .filter(([key]) => colIndex[key] === undefined)
    .map(([, label]) => label);
  if (missing.length) {
    throw new Error(
      `This doesn't look like a Students export — missing columns: ${missing.join(", ")}.`,
    );
  }

  const cell = (row: string[], key: string) =>
    colIndex[key] !== undefined ? (row[colIndex[key]] ?? "").trim() : "";

  const valid: StudentImportRow[] = [];
  const invalid: ImportRowError[] = [];

  dataRows
    .filter((row) => row.some((value) => value.trim()))
    .forEach((row, index) => {
      const rowNumber = index + 2;
      const email = cell(row, "email").toLowerCase();
      const firstName = cell(row, "firstName");
      const lastName = cell(row, "lastName");
      const country = cell(row, "country");
      const region = cell(row, "region");
      const schoolName = cell(row, "school");
      const yearLevelRaw = cell(row, "yearLevel");
      const interests = parseInterestList(cell(row, "interests"));
      const responseId = cell(row, "responseId");

      const state = country === "Australia" ? region : country;
      const yearLevel = Number(yearLevelRaw);

      const problems: string[] = [];
      if (!email) problems.push("missing email");
      else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email))
        problems.push("invalid email");
      if (!firstName || !lastName) problems.push("missing first or last name");
      if (!state) problems.push("missing country/region");
      if (!schoolName) problems.push("missing school");
      if (!yearLevelRaw || !Number.isInteger(yearLevel) || yearLevel < 9 || yearLevel > 12)
        problems.push("year level must be 9–12");
      if (!interests.length) problems.push("no interests");

      if (problems.length) {
        invalid.push({
          rowNumber,
          email: email || "(no email)",
          reason: problems.join(", "),
        });
        return;
      }

      valid.push({
        firstName,
        lastName,
        email,
        country,
        state,
        schoolName,
        yearLevel,
        interests,
        guardianFirstName: cell(row, "guardianFirstName"),
        guardianLastName: cell(row, "guardianLastName"),
        guardianEmail: cell(row, "guardianEmail").toLowerCase(),
        supervisorFirstName: cell(row, "supervisorFirstName"),
        supervisorLastName: cell(row, "supervisorLastName"),
        supervisorEmail: cell(row, "supervisorEmail").toLowerCase(),
        joinpermResponseId: responseId,
        active: responseId.length > 0,
        groupNumber: cell(row, "groupNumber") || undefined,
      });
    });

  return { valid, invalid };
}
