/**
 * @file adminAPI.ts
 * @description adminAPI.ts is the typed API client for the admin section of the
 * merged frontend. It wraps the Django admin API (mounted at /api/v1/admin/)
 * with helpers that follow the same conventions as the rest of the SPA
 * (see eventsAPI.ts / tasksAPI.ts): session cookies, CSRF for unsafe methods,
 * Browser Authorization header, and normalized ApiError responses.
 *
 * Scope: Foundation shared by every admin page (dashboard, users, groups,
 * matching, events, resources, announcements, mentors, tasks).
 */

import { buildSessionHeaders, ensureCsrfCookie } from './csrf'
import { apiErrorFromResponse } from './apiError'
import type { StudentImportRow } from './adminStudentCsv'
import type { MentorImportRow } from './adminMentorCsv'

export const ADMIN_API_BASE =
  (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000') + '/api/v1/admin'

// ---------------------------------------------------------------------------
// Transport
// ---------------------------------------------------------------------------

interface AdminRequestOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE'
  body?: unknown
  /** Raw FormData body (no JSON Content-Type, no stringify). */
  isFormData?: boolean
  /** Force a fresh CSRF token fetch for this request. */
  refreshCsrf?: boolean
}

export const ADMIN_UNAUTHORIZED = 'not_authenticated'

async function adminRequest<T>(path: string, options: AdminRequestOptions = {}): Promise<T> {
  const { method = 'GET', body, isFormData = false, refreshCsrf = false } = options
  const unsafe = method !== 'GET'

  if (unsafe) {
    // Force a fresh token fetch when the caller expects the session CSRF to
    // have rotated (e.g. right after login/logout).
    if (refreshCsrf) {
      const reset = await import('./csrf')
      reset.resetCsrfToken()
    }

    const csrfReady = await ensureCsrfCookie(
      import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
    )
    if (!csrfReady) {
      throw new Error('Could not initialize a secure session. Please refresh and try again.')
    }
  }

  const headers = buildSessionHeaders({
    includeCSRF: unsafe,
    isFormData,
    headers: { Accept: 'application/json' }
  })

  const token = localStorage.getItem('access_token')
  if (token) {
    headers.set('Authorization', `Bearer ${token}`)
  }

  const init: RequestInit = {
    method,
    credentials: 'include',
    headers
  }

  if (body !== undefined) {
    init.body = isFormData ? (body as BodyInit) : JSON.stringify(body)
  }

  const res = await fetch(`${ADMIN_API_BASE}${path}`, init)

  if (!res.ok) {
    throw await apiErrorFromResponse(res, 'Admin request failed')
  }

  if (res.status === 204 || res.headers.get('content-length') === '0') {
    return undefined as unknown as T
  }

  const text = await res.text()
  return (text ? JSON.parse(text) : null) as T
}

export const adminGet = <T>(path: string): Promise<T> =>
  adminRequest<T>(path)

export const adminPost = <T>(path: string, body?: unknown): Promise<T> =>
  adminRequest<T>(path, { method: 'POST', body })

export const adminPatch = <T>(path: string, body?: unknown): Promise<T> =>
  adminRequest<T>(path, { method: 'PATCH', body })

export const adminPut = <T>(path: string, body?: unknown): Promise<T> =>
  adminRequest<T>(path, { method: 'PUT', body })

export const adminDelete = <T>(path: string, body?: unknown): Promise<T> =>
  adminRequest<T>(path, { method: 'DELETE', body })

// ---------------------------------------------------------------------------
// Shared list helpers
// ---------------------------------------------------------------------------

export interface PaginatedResult<T> {
  count?: number
  next?: string | null
  previous?: string | null
  results?: T[]
}

/** Serialize query params, skipping empty values and joining arrays with ",". */
export const buildAdminQuery = <T extends object>(params: T): string => {
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null) continue
    if (typeof value === 'string' && !value.trim()) continue
    query.set(key, Array.isArray(value) ? value.join(',') : String(value))
  }
  const qs = query.toString()
  return qs ? `?${qs}` : ''
}

// ---------------------------------------------------------------------------
// Dashboard summary
// ---------------------------------------------------------------------------

export interface AdminSummary {
  active_users?: number
  invited_or_pending_users?: number
  suspended_or_deactivated_users?: number
  active_groups?: number
  groups_without_mentor?: number
  unassigned_match_recommendations?: number
  upcoming_events?: number
}

export interface AdminSummaryResponse {
  [key: string]: unknown
  active_users?: number
  invited_or_pending_users?: number
  suspended_or_deactivated_users?: number
  active_groups?: number
  groups_without_mentor?: number
  unassigned_match_recommendations?: number
  upcoming_events?: number
}

export const fetchAdminSummary = (): Promise<AdminSummaryResponse> =>
  adminGet<AdminSummaryResponse>('/summary/')

// ---------------------------------------------------------------------------
// Users & Supervisors
//
// Contract notes (matches apps/admin/):
// - List uses a custom envelope: `{ msg, data: { items, total, page, limit, hasMore } }`.
//   Pagination param is `limit` (not page_size) and sorting uses `sortBy`/`sortOrder`.
// - Role strings: "student" | "mentor" | "supervisor" | "admin". Supervisors are
//   just users filtered with `?role=supervisor`; there is no separate endpoint.
// - Single status toggle: PATCH .../status/ with `{ isActive: bool }`.
// - Bulk status: PATCH .../bulk-status/; bulk delete: POST .../bulk-delete/ (accepts
//   `force` + `selectAll` for delete-all-matching).
// ---------------------------------------------------------------------------

export interface AdminEnvelope<T> {
  msg: string
  data: T
}

export interface AdminUserCountry {
  id: number
  countryName: string
}

export interface AdminUserState {
  id: number
  stateName: string
  countryName?: string | null
}

export interface AdminUserSupervisee {
  name: string
  email: string
}

export interface AdminUser {
  id: number
  firstName: string | null
  lastName: string | null
  email: string | null
  role: string | null
  country: AdminUserCountry | null
  state: AdminUserState | null
  groupId: number | null
  groupName: string | null
  schoolName: string | null
  mentorBackground: string | null
  mentorInstitution: string | null
  mentorReason: string | null
  mentorMaxGroupCount: number | null
  yearLevel: number | null
  joinPermissionReceived: boolean
  interests: string[]
  isAdmin: boolean
  isActive: boolean
  hasLoggedIn: boolean
  lastLogin: string | null
  accountStatus: 'active' | 'deactivated'
  invitedAt: string | null
  activatedAt: string | null
  supervisorName: string | null
  supervisorEmail: string | null
  supervisees: AdminUserSupervisee[]
}

export interface UserListParams {
  page?: number
  limit?: number
  search?: string
  role?: string
  state?: string
  country?: string
  active?: string | boolean
  inGroup?: string
  sortBy?: string
  sortOrder?: 'asc' | 'desc'
}

export interface UserListData {
  items: AdminUser[]
  total: number
  page: number
  limit: number
  hasMore: boolean
}

/** Filters that mirror the list view — reused by bulk status/delete for select-all-matching. */
export interface UserListFilters {
  search?: string
  role?: string
  state?: string
  country?: string
  /** The list endpoint reads this as a parsed string; bulk status/delete expect a boolean. */
  active?: string | boolean
  inGroup?: string
}

export const fetchAdminUsers = (params: UserListParams = {}): Promise<UserListData> =>
  adminGet<AdminEnvelope<UserListData>>(`/user/${buildAdminQuery(params)}`).then((env) => env.data)

export const fetchAdminUser = (userId: string | number): Promise<AdminUser> =>
  adminGet<AdminEnvelope<AdminUser>>(`/user/${userId}/`).then((env) => env.data)

export type CreateUserPayload = Record<string, unknown> & {
  email: string
  firstName: string
  lastName: string
  role: string
}

export interface StudentImportSkippedRow {
  email: string
  reason: string
}

export interface StudentImportCoRegistrationGroup {
  name: string
  memberCount: number
}

export interface StudentImportCoRegistration {
  groupsCreated: StudentImportCoRegistrationGroup[]
  warnings: string[]
}

export interface StudentBulkImportData {
  created: AdminUser[]
  skipped: StudentImportSkippedRow[]
  coRegistration?: StudentImportCoRegistration
}

export interface StudentBulkImportResult {
  msg: string
  data: StudentBulkImportData
}

export interface MentorBulkImportData {
  created: AdminUser[]
  skipped: StudentImportSkippedRow[]
}

export interface MentorBulkImportResult {
  msg: string
  data: MentorBulkImportData
}

export const createAdminUser = (payload: CreateUserPayload) =>
  adminPost<AdminEnvelope<AdminUser>>('/user/', payload).then((env) => ({
    msg: env.msg,
    data: env.data
  }))

export const importAdminStudents = (rows: StudentImportRow[]): Promise<StudentBulkImportResult> =>
  adminPost<AdminEnvelope<StudentBulkImportData>>('/user/bulk/', rows).then((env) => ({
    msg: env.msg,
    data: env.data
  }))

export const importAdminMentors = (rows: MentorImportRow[]): Promise<MentorBulkImportResult> => {
  const payload = rows.map((row) => ({
    firstName: row.firstName,
    lastName: row.lastName,
    email: row.email,
    role: 'mentor' as const,
    state: row.state,
    country: row.country,
    interests: row.interests,
    mentorReason: row.mentorReason,
    mentorInstitution: row.mentorInstitution,
    mentorBackground: row.mentorBackground ?? undefined,
    mentorMaxGroupCount: row.mentorMaxGroupCount,
    active: true
  }))

  return adminPost<AdminEnvelope<MentorBulkImportData>>('/user/bulk/', payload).then((env) => ({
    msg: env.msg,
    data: env.data
  }))
}

export const updateAdminUser = (userId: string | number, payload: Record<string, unknown>) =>
  adminPut<AdminEnvelope<AdminUser>>(`/user/${userId}/`, payload).then((env) => ({
    msg: env.msg,
    data: env.data
  }))

export const deleteAdminUser = (userId: string | number, force = false) =>
  adminDelete<AdminEnvelope<null>>(`/user/${userId}/`, force ? { force: true } : undefined).then(
    (env) => env.msg
  )

export const setAdminUserActive = (userId: string | number, isActive: boolean) =>
  adminPatch<AdminEnvelope<AdminUser>>(`/user/${userId}/status/`, { isActive }).then((env) => ({
    msg: env.msg,
    data: env.data
  }))

export interface BulkStatusPayload {
  isActive: boolean
  selectAll?: boolean
  filters?: UserListFilters
  excludeIds?: number[]
  userIds: number[]
}
export interface BulkStatusResult {
  msg: string
  data: {
    updatedIds: number[]
    unchangedIds: number[]
    notFoundIds: number[]
    skippedSelf: boolean
  }
}
export const bulkSetUsersActive = (payload: BulkStatusPayload): Promise<BulkStatusResult> =>
  adminPatch<AdminEnvelope<BulkStatusResult['data']>>('/user/bulk-status/', payload).then(
    (env) => ({ msg: env.msg, data: env.data })
  )

export interface BulkDeletePayload {
  userIds: number[]
  force?: boolean
  selectAll?: boolean
  filters?: UserListFilters
  excludeIds?: number[]
  expectedCount?: number | null
}
export interface BulkDeleteResult {
  msg: string
  data: {
    deletedIds: number[]
    failedIds: number[]
    notFoundIds: number[]
    skippedSelf: boolean
    skippedAdmins: number
  }
}
export const bulkDeleteUsers = (payload: BulkDeletePayload): Promise<BulkDeleteResult> =>
  adminPost<AdminEnvelope<BulkDeleteResult['data']>>('/user/bulk-delete/', payload).then(
    (env) => ({ msg: env.msg, data: env.data })
  )

/** Countries lookup. Pass `{ inUse: true }` to restrict to countries that actually
 *  have users — the lookup holds every country on earth, but only a fraction have
 *  rows worth filtering to. */
export const fetchAdminCountries = (
  options: { inUse?: boolean } = {}
): Promise<AdminUserCountry[]> =>
  adminGet<AdminEnvelope<AdminUserCountry[]>>(
    `/user/countries/${options.inUse ? buildAdminQuery({ inUse: true }) : ''}`
  ).then((env) => env.data)

export const fetchAdminStates = (): Promise<AdminUserState[]> =>
  adminGet<AdminEnvelope<AdminUserState[]>>('/user/states/').then((env) => env.data)

// ---------------------------------------------------------------------------
// Groups
// ---------------------------------------------------------------------------

export interface AdminGroup {
  id?: number | string
  group_id?: string
  name?: string | null
  member_count?: number
  has_mentor?: boolean
  [key: string]: unknown
}

export interface GroupListParams {
  search?: string
  page?: number
  page_size?: number
}

export const fetchAdminGroups = (params: GroupListParams = {}) =>
  adminGet<PaginatedResult<AdminGroup>>(`/group/${buildAdminQuery(params)}`)

export const fetchAdminGroup = (groupId: string | number) =>
  adminGet<AdminGroup>(`/group/${groupId}/`)

// ---------------------------------------------------------------------------
// Student group assignment
//
// The group list endpoint returns a custom envelope:
//   `{ msg, data: { items, total, page, limit, has_more } }` where each group
//   carries its full member array (`{ id, name, email, role, membershipId }`),
//   so the free-seat capacity rule can be computed client-side.
// ---------------------------------------------------------------------------

export interface AdminGroupMember {
  id: string
  name: string
  email: string
  /** "student" | "mentor" */
  role: string
  membershipId: number | null
}

export interface AdminGroupDetail {
  id: number
  name: string
  members: AdminGroupMember[]
  mentor: AdminGroupMember | null
  createdAt: string
  updatedAt: string
}

export interface AdminGroupListData {
  items: AdminGroupDetail[]
  total: number
  page: number
  limit: number
  has_more: boolean
}

export interface GroupListDetailParams {
  page?: number
  limit?: number
  searchName?: string
  searchGroup?: string
  mentorStatus?: string
  sortBy?: string
  sortOrder?: 'asc' | 'desc'
}

/** Full group payloads — used by the assign-student surfaces. */
export const fetchAdminGroupList = (params: GroupListDetailParams = {}) =>
  adminGet<AdminEnvelope<AdminGroupListData>>(`/group/${buildAdminQuery(params)}`).then(
    (env) => env.data
  )

export interface StudentAssignment {
  studentId: number
  groupId: number
}

/** Assign students to groups (POST /match/confirm/). Returns the count confirmed. */
export const confirmStudentAssignments = (assignments: StudentAssignment[]) =>
  adminPost<AdminEnvelope<{ assigned_count: number }>>('/match/confirm/', { assignments }).then(
    (env) => ({ msg: env.msg, assignedCount: env.data.assigned_count })
  )

/** Remove a student from their group (DELETE /group/{id}/members/{userId}/). */
export const removeGroupMember = (groupId: string | number, userId: string | number) =>
  adminDelete<AdminEnvelope<AdminGroupDetail | null>>(
    `/group/${groupId}/members/${userId}/`
  ).then((env) => env.msg)

// ---------------------------------------------------------------------------
// Events
// ---------------------------------------------------------------------------

export interface AdminEvent {
  id?: number | string
  event_id?: string
  event_name?: string | null
  start_datetime?: string | null
  ends_datetime?: string | null
  accepted_count?: number
  waitlist_count?: number
  [key: string]: unknown
}

export interface AdminEventListParams {
  search?: string
  ordering?: string
  page?: number
  page_size?: number
}

export const fetchAdminEvents = (params: AdminEventListParams = {}) =>
  adminGet<PaginatedResult<AdminEvent>>(`/event/${buildAdminQuery(params)}`)

export const fetchAdminEventMetaGroups = () => adminGet<unknown[]>('/event/meta/groups/')
export const fetchAdminEventMetaRoles = () => adminGet<unknown[]>('/event/meta/roles/')

// ---------------------------------------------------------------------------
// Resources
// ---------------------------------------------------------------------------

export interface AdminResource {
  id?: number | string
  resource_id?: number
  title?: string | null
  resource_type?: string | null
  [key: string]: unknown
}

export const fetchAdminResources = (params: Record<string, unknown> = {}) =>
  adminGet<PaginatedResult<AdminResource>>(`/resource/${buildAdminQuery(params)}`)

export const fetchResourceRoles = () => adminGet<unknown[]>('/resource/roles/')
export const fetchResourceTypes = () => adminGet<unknown[]>('/resource/types/')

// ---------------------------------------------------------------------------
// Announcements
// ---------------------------------------------------------------------------

export interface AdminAnnouncement {
  id?: number | string
  announcement_id?: number
  title?: string | null
  archived?: boolean
  [key: string]: unknown
}

export const fetchAdminAnnouncements = (params: Record<string, unknown> = {}) =>
  adminGet<PaginatedResult<AdminAnnouncement>>(`/announcement/${buildAdminQuery(params)}`)

export const fetchAnnouncementGroups = () => adminGet<unknown[]>('/announcement/groups/')
export const fetchAnnouncementRoles = () => adminGet<unknown[]>('/announcement/roles/')

// ---------------------------------------------------------------------------
// Mentors
// ---------------------------------------------------------------------------

export interface AdminMentor {
  id?: number | string
  mentor_id?: number
  name?: string | null
  is_active?: boolean
  [key: string]: unknown
}

export const fetchAdminMentors = (params: Record<string, unknown> = {}) =>
  adminGet<PaginatedResult<AdminMentor>>(`/mentor/${buildAdminQuery(params)}`)

/** Full mentor profile rows used by the People → Mentors tab (GET /mentor/). */
export interface AdminMentorAvailability {
  weekday: number
  startTime: string
  endTime: string
}

export interface AdminMentorCertificate {
  certificateTypeName: string
  certificateNumber: string | null
  issuedBy: string | null
  issuedAt: string
  expiresAt: string | null
  fileUrl: string | null
  /** Backend maps this from MentorCertificate.verified — a boolean despite the "At". */
  verifiedAt: boolean | string | null
}

export interface AdminMentorDetail {
  mentorId: number
  firstName: string | null
  lastName: string | null
  name: string
  email: string | null
  isActive: boolean
  institution: string | null
  countryName: string | null
  maxGroupCount: number
  currentAssignedCount: number
  remainingCapacity: number
  interests: string[]
  lastMessageAt: string | null
  hasLoggedIn?: boolean
  lastLogin?: string | null
  availability: AdminMentorAvailability[]
  certificates: AdminMentorCertificate[]
}

export const fetchAdminMentorDetails = () =>
  adminGet<AdminEnvelope<AdminMentorDetail[]>>('/mentor/').then((env) => env.data)

/** Toggle a mentor's account status (PATCH /mentor/{mentorId}/active/). */
export const setAdminMentorActive = (mentorId: number, isActive: boolean) =>
  adminPatch<AdminEnvelope<{ mentorId: number; isActive: boolean }>>(
    `/mentor/${mentorId}/active/`,
    { isActive }
  ).then((env) => env.data)

// ---------------------------------------------------------------------------
// Tasks
// ---------------------------------------------------------------------------

export interface AdminTask {
  id: number
  name: string
  description: string
  due_date: string | null
  status: AdminTaskStatus
  completed: boolean
  parent: number | null
  task_type: AdminTaskType
  group: number | null
  assigned_user: number | null
  created_by: AdminTaskUserMini | null
  creator_role: string
  deleted_at: string | null
  created_at: string
  updated_at: string
}

export type AdminTaskStatus = 'todo' | 'in_progress' | 'done' | 'blocked'
export type AdminTaskType = 'group' | 'individual'
export type AdminTaskSortBy = 'completed' | 'name' | 'type' | 'target' | 'status' | 'due' | 'createdAt'

export interface AdminTaskUserMini {
  id: number
  name: string | null
}

export interface AdminTaskListParams {
  page?: number
  limit?: number
  task_type?: AdminTaskType | ''
  sortBy?: AdminTaskSortBy
  sortOrder?: 'asc' | 'desc'
}

export interface AdminTaskListData {
  items: AdminTask[]
  total: number
  page: number
  limit: number
  has_more: boolean
}

export interface CreateAdminTaskPayload {
  name: string
  description?: string
  due_date?: string | null
  status?: AdminTaskStatus
  parent?: number | null
  task_type: AdminTaskType
  group?: number | null
  assigned_user?: number | null
  assigned_role?: string | null
}

export interface UpdateAdminTaskPayload {
  name?: string
  description?: string
  due_date?: string | null
  status?: AdminTaskStatus
  parent?: number | null
}

export interface AdminTaskFanoutResult {
  created_count: number
  assigned_role: string
}

export interface AdminTaskRoleRecipientsData {
  role: string
  count: number
}

export type AdminTaskMutationResult<T = AdminTask | AdminTaskFanoutResult | null> = AdminEnvelope<T>

export const fetchAdminTasks = (params: AdminTaskListParams = {}): Promise<AdminTaskListData> =>
  adminGet<AdminEnvelope<AdminTaskListData>>(`/task/${buildAdminQuery(params)}`).then(
    (env) => env.data
  )

export const createAdminTask = (
  payload: CreateAdminTaskPayload
): Promise<AdminTaskMutationResult<AdminTask | AdminTaskFanoutResult | null>> =>
  adminPost<AdminTaskMutationResult<AdminTask | AdminTaskFanoutResult | null>>('/task/', payload)

export const updateAdminTask = (
  taskId: number | string,
  payload: UpdateAdminTaskPayload
): Promise<AdminTaskMutationResult<AdminTask | null>> =>
  adminPatch<AdminTaskMutationResult<AdminTask | null>>(`/task/${taskId}/`, payload)

export const deleteAdminTask = (taskId: number | string): Promise<void> =>
  adminDelete<void>(`/task/${taskId}/`)

export const toggleAdminTask = (
  taskId: number | string,
  completed: boolean
): Promise<AdminTaskMutationResult<AdminTask | null>> =>
  adminPost<AdminTaskMutationResult<AdminTask | null>>(`/task/${taskId}/toggle/`, { completed })

export const fetchTaskRoleRecipients = (
  role: string
): Promise<AdminTaskMutationResult<AdminTaskRoleRecipientsData | null>> =>
  adminGet<AdminTaskMutationResult<AdminTaskRoleRecipientsData | null>>(
    `/task/role-recipients/${buildAdminQuery({ role })}`
  )

// ---------------------------------------------------------------------------
// Matching / mentor-match
// ---------------------------------------------------------------------------

export const fetchMatchSuggestions = (params: Record<string, unknown> = {}) =>
  adminGet<PaginatedResult<unknown>>(`/match/student-suggestions/${buildAdminQuery(params)}`)

export const fetchMentorMatchMentors = (params: Record<string, unknown> = {}) =>
  adminGet<PaginatedResult<unknown>>(`/mentor-match/mentors/${buildAdminQuery(params)}`)

export const fetchMentorMatchGroups = (params: Record<string, unknown> = {}) =>
  adminGet<PaginatedResult<unknown>>(`/mentor-match/groups/${buildAdminQuery(params)}`)

export const fetchMentorMatchMatchedGroups = (params: Record<string, unknown> = {}) =>
  adminGet<PaginatedResult<unknown>>(`/mentor-match/matched-groups/${buildAdminQuery(params)}`)

// --- Typed mentor-match surfaces (Replace Inactive Mentors) -----------------

export interface MentorListItem {
  mentorId: number
  name: string
  countryName: string | null
  institution: string | null
  interests: string[]
  maxGroupCount: number
  currentAssignedCount: number
  remainingCapacity: number
}

/** Flat mentor list (GET /mentor-match/mentors/) — the fallback pool for replacements. */
export const fetchMentorMatchMentorList = () =>
  adminGet<AdminEnvelope<MentorListItem[]>>('/mentor-match/mentors/').then((env) => env.data)

export interface MatchedGroupMentor {
  mentorId: number
  name: string
  isActive: boolean
  countryName: string | null
  institution: string | null
}

export interface MatchedGroupStudent {
  name: string
  hasLoggedIn: boolean
  interests: string[]
}

export interface MatchedGroup {
  membershipId: number
  groupId: number
  groupName: string
  countryName: string | null
  studentCount: number
  students: MatchedGroupStudent[]
  mentor: MatchedGroupMentor
}

/** Confirmed mentor assignments (GET /mentor-match/matched-groups/). */
export const fetchMatchedGroups = () =>
  adminGet<AdminEnvelope<MatchedGroup[]>>('/mentor-match/matched-groups/').then(
    (env) => env.data
  )

export interface MentorAssignment {
  groupId: number
  mentorUserId: number
}

export const confirmMentorAssignments = (assignments: MentorAssignment[]) =>
  adminPost<AdminEnvelope<{ confirmedCount: number }>>('/mentor-match/confirm/', {
    assignments
  }).then((env) => ({ msg: env.msg, confirmedCount: env.data.confirmedCount }))

export const unassignMentors = (groupIds: number[]) =>
  adminPost<AdminEnvelope<{ unassignedCount: number }>>('/mentor-match/unassign/', {
    groupIds
  }).then((env) => ({ msg: env.msg, unassignedCount: env.data.unassignedCount }))

export interface MentorReplaceSuggestion {
  mentorUserId: number
  name: string
  institution: string | null
  remainingCapacity: number
  atCapacity: boolean
  score: number
  reason: string
}

export interface MentorReplaceSuggestionsData {
  groupId: number
  groupName: string
  suggestions: MentorReplaceSuggestion[]
}

/** Scored replacement mentors for one group (GET /mentor-match/replace-suggestions/). */
export const fetchMentorReplaceSuggestions = (groupId: number) =>
  adminGet<AdminEnvelope<MentorReplaceSuggestionsData>>(
    `/mentor-match/replace-suggestions/?groupId=${groupId}`
  ).then((env) => env.data)
