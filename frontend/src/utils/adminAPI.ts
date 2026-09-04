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
// Group management (create / rename / delete / messages)
// ---------------------------------------------------------------------------

/** Preview of the name create_group() would auto-generate. Reserves nothing —
 *  the number is only allocated at insert time. */
export const fetchNextGroupName = (): Promise<string> =>
  adminGet<AdminEnvelope<{ name: string }>>('/group/next-name/').then((env) => env.data.name)

/** Create a group. Omit `name` to let the backend allocate the next BTF number. */
export const createGroup = (name?: string) =>
  adminPost<AdminEnvelope<AdminGroupDetail | null>>('/group/', { name }).then((env) => ({
    msg: env.msg,
    data: env.data
  }))

/** Rename a group. Duplicate active names are rejected by the backend. */
export const updateGroup = (groupId: string | number, name: string) =>
  adminPut<AdminEnvelope<AdminGroupDetail | null>>(`/group/${groupId}/`, { name }).then((env) => ({
    msg: env.msg,
    data: env.data
  }))

/** Permanently delete one group (hard delete; cascades chat history, memberships,
 *  event targets, announcement audiences, tasks, match recommendations). Fails if a
 *  hosted workshop still references it — use bulkDeleteGroups with force for that. */
export const deleteGroup = (groupId: string | number) =>
  adminDelete<AdminEnvelope<{ id: string } | null>>(`/group/${groupId}/`).then((env) => env.msg)

export type GroupBulkDeleteVars =
  | { groupIds: (string | number)[]; force?: boolean }
  | {
      selectAll: true
      filters?: GroupListDetailParams
      excludeIds?: (string | number)[]
      /** Count the admin reviewed; the server refuses if the live set grew past it. */
      expectedCount?: number
      force?: boolean
      /** Max groups to delete this call; the response reports `remaining`. */
      limit?: number
    }

export interface GroupBulkDeleteResult {
  deletedIds: number[]
  failedIds: number[]
  notFoundIds: number[]
  /** Only present for the selectAll path — matching groups not attempted this
   *  call. The caller loops (raising `excludeIds`) until this is 0. */
  remaining?: number
}

/** Permanently delete groups in one request — explicit ids or "select all
 *  matching" (resolved server-side from the same list filters). force=true also
 *  purges the hosted workshops that PROTECT a group. */
export const bulkDeleteGroups = (payload: GroupBulkDeleteVars) =>
  adminPost<AdminEnvelope<GroupBulkDeleteResult | null>>('/group/bulk-delete/', payload).then(
    (env) => ({ msg: env.msg, data: env.data })
  )

export interface AdminGroupMessageAttachment {
  id: number
  filename: string
  mime_type: string
  size: number
  download_url: string
}

export interface AdminGroupMessage {
  id: string
  group_id: string
  sender: { id: string; name: string; email: string; role: string | null }
  message_type: string
  text: string
  attachments: AdminGroupMessageAttachment[]
  gif: { gif_url: string; preview_url: string; title: string } | null
  sent_at: string
  edited_at: string | null
}

export interface AdminGroupMessagesData {
  items: AdminGroupMessage[]
  total: number
  page: number
  limit: number
  has_more: boolean
}

export const fetchGroupMessages = (
  groupId: string | number,
  params: { page?: number; limit?: number } = {}
): Promise<AdminGroupMessagesData> =>
  adminGet<AdminEnvelope<AdminGroupMessagesData>>(
    `/group/${groupId}/messages/${buildAdminQuery(params)}`
  ).then((env) => env.data)

/** Soft-delete a message from a group. */
export const removeGroupMessage = (groupId: string | number, messageId: string | number) =>
  adminDelete<AdminEnvelope<{ id: string; group_id: string } | null>>(
    `/group/${groupId}/messages/${messageId}/`
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

export interface EventTargetGroupItem {
  id: number
  groupName: string
}

export interface EventTargetRoleItem {
  id: number
  roleName: string
}

export interface AdminEventTargetsData {
  groupIds: number[]
  roleIds: number[]
}

export interface AdminEventRsvpItem {
  id: number
  eventId: number
  userId: number
  rsvpStatus: 'pending' | 'accepted' | 'tentative' | 'declined' | 'waitlisted'
  respondedAt: string | null
}

export interface AdminEventDetail {
  id: number
  eventName: string
  description: string | null
  startDatetime: string
  endsDatetime: string
  location: string | null
  deletedFlag: boolean
  deletedDatetime: string | null
  eventImage: string | null
  eventFormat: 'in_person' | 'virtual' | 'hybrid'
  eventTimezone: string
  hostUserId: number | null
  hostName: string | null
  hostEmail: string | null
  locationLink: string | null
}

export interface CreateAdminEventPayload {
  eventName: string
  description?: string | null
  location?: string | null
  locationLink?: string | null
  eventFormat?: 'in_person' | 'virtual' | 'hybrid'
  eventTimezone?: string
  hostUserId?: number | null
  startAt: string
  endsAt: string
  eventImage?: string | null
  targetGroupIds?: number[]
  targetRoleIds?: number[]
}

export interface UpdateAdminEventPayload {
  eventName?: string
  description?: string | null
  location?: string | null
  locationLink?: string | null
  eventFormat?: 'in_person' | 'virtual' | 'hybrid'
  eventTimezone?: string
  hostUserId?: number | null
  startAt?: string
  endsAt?: string
  eventImage?: string | null
  targetGroupIds?: number[]
  targetRoleIds?: number[]
}

export interface AdminEventListParams {
  search?: string
  ordering?: string
  page?: number
  page_size?: number
}

export const fetchAdminEvents = (params: AdminEventListParams = {}) =>
  adminGet<PaginatedResult<AdminEvent>>(`/event/${buildAdminQuery(params)}`)

export const fetchAdminEvent = (id: number | string) =>
  adminGet<AdminEnvelope<AdminEventDetail>>(`/event/${id}/`).then((env) => env.data)

export const createAdminEvent = (payload: CreateAdminEventPayload) =>
  adminPost<AdminEnvelope<AdminEventDetail>>('/event/', payload).then((env) => env.data)

export const updateAdminEvent = (id: number | string, payload: UpdateAdminEventPayload) =>
  adminPut<AdminEnvelope<AdminEventDetail>>(`/event/${id}/`, payload).then((env) => env.data)

export const deleteAdminEvent = (id: number | string) =>
  adminDelete<AdminEnvelope<AdminEventDetail>>(`/event/${id}/`).then((env) => env.data)

export const uploadAdminEventImage = (id: number | string, file: File) => {
  const formData = new FormData()
  formData.append('image', file)
  return adminRequest<AdminEnvelope<AdminEventDetail>>(`/event/${id}/upload-image/`, {
    method: 'POST',
    body: formData,
    isFormData: true
  }).then((env) => env.data)
}

export const fetchAdminEventRsvps = (id: number | string) =>
  adminGet<AdminEnvelope<AdminEventRsvpItem[]>>(`/event/${id}/rsvp/`).then((env) => env.data || [])

export const fetchAdminEventTargets = (id: number | string) =>
  adminGet<AdminEnvelope<AdminEventTargetsData>>(`/event/${id}/targets/`).then((env) => env.data)

export const fetchAdminEventMetaGroups = () =>
  adminGet<AdminEnvelope<EventTargetGroupItem[]>>('/event/meta/groups/').then((env) => env.data || [])

export const fetchAdminEventMetaRoles = () =>
  adminGet<AdminEnvelope<EventTargetRoleItem[]>>('/event/meta/roles/').then((env) => env.data || [])


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

export interface AdminResourceRoleItem {
  id: number
  slug: string
  type_name: string
}

export interface AdminResourceTypeOption {
  value: string
  label: string
}

export interface AdminResourceDetail {
  id: number
  resource_name: string
  resource_description: string | null
  resource_kind: 'file' | 'attachment' | 'page' | string
  resource_type: string | null
  resource_type_id: number | null
  visibility_scope: 'global' | 'role_based' | string
  uploaded_at: string
  deleted_at: string | null
  file_name: string | null
  file_mime_type: string | null
  file_size: number | null
  content_html?: string | null
  storage_key?: string | null
  labels?: Array<{ id: number; name: string }>
  audiences?: Array<{
    id: number
    role_id: number | null
    role?: { id: number; slug: string; type_name: string }
  }>
  uploader?: {
    id: number | string
    first_name: string
    last_name: string
    email: string
  }
}

export interface CreateAdminResourcePayload {
  resource_name: string
  resource_description: string
  resource_kind: 'file' | 'attachment' | 'page'
  visibility_scope: 'global' | 'role_based'
  role_ids?: number[]
  resource_type_id?: number | null
  resource_type?: string | null
  label_names?: string[]
  content_html?: string
  group_id?: number | null
}

export interface UpdateAdminResourcePayload {
  resource_name?: string
  resource_description?: string | null
  visibility_scope?: 'global' | 'role_based'
  role_ids?: number[]
  resource_type_id?: number | null
  resource_type?: string | null
  label_names?: string[]
  content_html?: string | null
}

export const fetchAdminResources = (params: Record<string, unknown> = {}) =>
  adminGet<PaginatedResult<AdminResource>>(`/resource/${buildAdminQuery(params)}`)

export const fetchAdminResource = (id: number | string) =>
  adminGet<AdminEnvelope<AdminResourceDetail>>(`/resource/${id}/`).then((env) => env.data)

export const createAdminResource = (payload: CreateAdminResourcePayload) =>
  adminPost<AdminEnvelope<AdminResourceDetail>>('/resource/', payload).then((env) => env.data)

export const uploadAdminResource = (formData: FormData) =>
  adminRequest<AdminEnvelope<AdminResourceDetail>>('/resource/upload/', {
    method: 'POST',
    body: formData,
    isFormData: true
  }).then((env) => env.data)

export const updateAdminResource = (id: number | string, payload: UpdateAdminResourcePayload) =>
  adminPut<AdminEnvelope<AdminResourceDetail>>(`/resource/${id}/`, payload).then((env) => env.data)

export const deleteAdminResource = (id: number | string) =>
  adminDelete<AdminEnvelope<null>>(`/resource/${id}/`).then((env) => env.data)

export const replaceAdminResourceFile = (id: number | string, file: File) => {
  const formData = new FormData()
  formData.append('file', file)
  return adminRequest<AdminEnvelope<AdminResourceDetail>>(`/resource/${id}/upload/`, {
    method: 'POST',
    body: formData,
    isFormData: true
  }).then((env) => env.data)
}

export const fetchAdminResourceRoles = () =>
  adminGet<AdminEnvelope<AdminResourceRoleItem[]>>('/resource/roles/').then((env) => env.data || [])

export const fetchAdminResourceTypes = () =>
  adminGet<AdminEnvelope<AdminResourceTypeOption[]>>('/resource/types/').then((env) => env.data || [])

export const downloadAdminResourceFile = async (id: number | string, fileName?: string) => {
  const url = `${ADMIN_API_BASE}/resource/${id}/download/`
  const res = await fetch(url, {
    method: 'GET',
    credentials: 'include'
  })
  if (!res.ok) {
    throw new Error(`Failed to download resource: ${res.statusText}`)
  }
  const blob = await res.blob()
  const blobUrl = window.URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = blobUrl
  a.download = fileName || 'download'
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  window.URL.revokeObjectURL(blobUrl)
}

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
  id?: number | string
  task_id?: number
  title?: string | null
  is_active?: boolean
  [key: string]: unknown
}

export const fetchAdminTasks = (params: Record<string, unknown> = {}) =>
  adminGet<PaginatedResult<AdminTask>>(`/task/${buildAdminQuery(params)}`)

export const fetchTaskRoleRecipients = () =>
  adminGet<unknown[]>(`/task/role-recipients/`)

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

export interface MentorReplacePayload {
  membershipId: number
  groupId: number
  newMentorUserId: number
}

/** Swap one group's mentor for another (POST /mentor-match/replace/). Rejects
 *  if the new mentor is already at capacity. */
export const replaceMentor = (payload: MentorReplacePayload) =>
  adminPost<AdminEnvelope<{ replaced: number }>>('/mentor-match/replace/', payload).then(
    (env) => ({ msg: env.msg, replaced: env.data.replaced })
  )

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
