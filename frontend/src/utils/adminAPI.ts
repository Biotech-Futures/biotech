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

export const adminDelete = <T>(path: string): Promise<T> =>
  adminRequest<T>(path, { method: 'DELETE' })

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
// Users
// ---------------------------------------------------------------------------

export interface AdminUser {
  id?: number | string
  user_id?: string
  first_name?: string | null
  last_name?: string | null
  email?: string | null
  username?: string | null
  role?: string | null
  status?: string | null
  is_active?: boolean
  [key: string]: unknown
}

export interface UserListParams {
  search?: string
  role?: string | string[]
  status?: string | string[]
  page?: number
  page_size?: number
  ordering?: string
}

export const fetchAdminUsers = (params: UserListParams = {}) =>
  adminGet<PaginatedResult<AdminUser>>(`/user/${buildAdminQuery(params)}`)

export const fetchAdminUser = (userId: string | number) =>
  adminGet<AdminUser>(`/user/${userId}/`)

export const fetchUserCountries = () =>
  adminGet<unknown[]>(`/user/countries/`)

export const fetchUserStates = () =>
  adminGet<unknown[]>(`/user/states/`)

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
