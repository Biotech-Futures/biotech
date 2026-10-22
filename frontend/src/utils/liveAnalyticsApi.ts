const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

type ApiEnvelope<T> = { data?: T; msg?: string }

export type AdminUser = {
  id: number
  firstName: string
  lastName: string
  email: string
  role: string | null
  country: { id?: number; countryName?: string } | null
  state: { id?: number; stateName?: string } | null
  groupId: string | number | null
  groupName: string | null
  schoolName: string | null
  mentorBackground: string | null
  mentorInstitution: string | null
  mentorReason: string | null
  mentorMaxGroupCount: number | null
  yearLevel: number | null
  joinPermissionReceived: boolean
  guardianEmail: string | null
  interests: string[]
  isAdmin: boolean
  isActive: boolean
  hasLoggedIn: boolean
  lastLogin: string | null
  accountStatus: string
  invitedAt: string | null
  activatedAt: string | null
  createdAt?: string | null
  supervisorName: string | null
  supervisorEmail: string | null
}

export type AdminGroup = {
  id: string
  name: string
  members: Array<{ id: string; name: string; email: string; role: string; membershipId: number }>
  mentor: { id: string; name: string; email: string; role: string; membershipId: number } | null
  mentors?: Array<{ id: string; name: string; email: string; role: string; membershipId: number }>
  createdAt: string
  updatedAt: string
}

export type AdminMentor = {
  mentorId: number
  firstName: string
  lastName: string
  name: string
  email: string
  isActive: boolean
  // User.account_status ("active" once the account is activated). Optional
  // while older backends that only send isActive are still deployed.
  accountStatus?: string | null
  hasLoggedIn: boolean
  lastLogin: string | null
  institution: string | null
  countryName: string | null
  maxGroupCount: number
  currentAssignedCount: number
  remainingCapacity: number
  interests: string[]
  lastMessageAt: string | null
}

export type GroupActivityResponse = {
  mentor_activity_by_day?: Array<{ mentor_id: number; date: string; messages: number; logins: number }>
  messages_by_group: Array<{ group_id: number; group_name: string; message_count: number }>
  messages_by_user: Array<{ user_id: number; name: string; message_count: number }>
  messages_by_day: Array<{ date: string; message_count: number }>
  messages_by_group_by_day: Array<{ date: string; group_id: number; group_name: string; message_count: number }>
  messages_by_user_by_group_by_day?: Array<{
    date: string
    user_id: number
    name: string
    group_id: number
    group_name: string
    message_count: number
  }>
  mentor_count: number
  student_count: number
  students_per_mentor: number | null
  average_group_size_by_year?: Array<{
    year: number
    group_count: number
    student_memberships: number
    average_group_size: number
  }>
  group_summary_by_year?: Array<{
    year: number
    group_count: number
    groups_with_mentor: number
    groups_without_mentor: number
    mentor_count: number
    student_count: number
    students_per_mentor: number | null
    group_size_distribution?: Array<{ student_count: number; group_count: number }>
    small_groups?: number
    full_groups?: number
    over_capacity_groups?: number
    active_groups?: number
    inactive_groups?: number
    not_started_groups?: number
  }>
  query_range: { start: string | null; end: string | null }
}

export type LoginActivityCount = {
  students: number
  mentors: number
  supervisors: number
  total: number
}

export type LoginActivityResponse = {
  by_day: Array<LoginActivityCount & { date: string }>
  by_year: Array<LoginActivityCount & { year: number }>
  active_users: { daily: number; weekly: number; monthly: number }
  active_user_comparison?: {
    daily: { current: number; previous: number }
    weekly: { current: number; previous: number }
    monthly: { current: number; previous: number }
  }
  latest_activity_date: string | null
  query_range: { start: string | null; end: string | null }
}

export type ResourceAnalyticsResponse = {
  total_clicks: number
  unique_users: number
  active_resources: number
  clicks_by_day: Array<{ date: string; click_count: number }>
  top_resources: Array<{ resource_id: number; resource_name: string; click_count: number; unique_users: number }>
  // Optional until every backend sends per-resource daily usage.
  clicks_by_resource_by_day?: Array<{
    date: string
    resource_id: number
    resource_name: string
    click_count: number
    unique_users: number
  }>
  clicks_by_category: Array<{ category_id: number | null; category_name: string | null; click_count: number }>
  query_range: { start: string | null; end: string | null }
}


export type EmailMailboxAnalytics = {
  email: string
  quota_limit: number
  totals: { attempted: number; delivered: number; failed: number; delivery_runs: number }
  hourly: Array<{ hour: string; attempted: number; delivered: number; failed: number }>
  daily: Array<{ date: string; attempted: number; delivered: number; failed: number }>
}

export type EmailRoleStatus = {
  role: 'Student' | 'Mentor' | 'Supervisor'
  attempted: number
  delivered: number
  opened: number | null
  failed: number
  tracked_deliveries: number
}

export type EmailRoleAttribution = {
  basis: 'current_single_role_audience'
  available: boolean
  complete: boolean
  tracked_delivery_runs: number
  unattributed_delivery_runs: number
  tracked_attempted: number
  unattributed_attempted: number
  tracked_delivered: number
  unattributed_delivered: number
  tracked_failed: number
  unattributed_failed: number
}

export type EmailDeliveryAnalyticsResponse = {
  snapshot_at: string | null
  mailboxes: EmailMailboxAnalytics[]
  // Legacy single-mailbox fields are kept optional for compatibility with older backends.
  mailbox?: string
  quota_limit?: number
  totals: { attempted: number; delivered: number; failed: number; delivery_runs: number }
  hourly: Array<{ hour: string; attempted: number; delivered: number; failed: number }>
  daily: Array<{ date: string; attempted: number; delivered: number; failed: number }>
  // Optional while older backend/frontend branches converge. The UI must
  // render an explicit unavailable state when these fields are absent.
  status_by_role?: EmailRoleStatus[]
  role_attribution?: EmailRoleAttribution
  recent_deliveries: Array<{
    id: number
    announcement_id: number
    title: string
    started_at: string
    completed_at?: string | null
    status: 'success' | 'partial' | 'failed'
    recipient_count: number
    success_count: number
    failure_count: number
    initiated_by_name: string
    initiated_by_email: string
  }>
  // Every email type (system emails, announcements, digests, bulk sends).
  // Optional while older backends only send announcement deliveries.
  recent_sends?: Array<Omit<EmailSend, 'id' | 'status'> & {
    // An announcement send still going has no id yet: delivery_id names its
    // announcement delivery row and its status is 'sending'.
    id: number | null
    delivery_id?: number
    status: EmailSend['status'] | 'sending'
    // Recipients kept for the send; 0 for sends made before they were recorded.
    recipients_recorded?: number
  }>
}

// One finished send of any email type.
export type EmailSend = {
  id: number
  email_type: string
  email_type_label: string
  title: string | null
  announcement_id: number | null
  source_mailbox: string
  started_at: string
  status: 'success' | 'partial' | 'failed'
  attempted: number
  delivered: number
  failed: number
  initiated_by_name: string
  initiated_by_email: string
}

export type EmailRecipient = {
  email: string
  user_id: number | null
  name: string
  status: 'delivered' | 'failed'
  reason: string
}

export type EmailSendToRecipient = EmailSend & {
  recipient: EmailRecipient
}

export type AdminResource = {
  resource_id?: number
  id?: number
  resource_name: string
  resource_type?: string | null
  audiences?: Array<{ role?: { slug?: string | null; role_name?: string | null } | null }>
}

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    cache: 'no-store',
    method: 'GET',
    credentials: 'include',
    headers: { Accept: 'application/json' },
  })

  if (!response.ok) {
    const body = await response.text()
    throw new Error(body || `Analytics request failed (${response.status})`)
  }

  return (await response.json()) as T
}

export async function fetchAllUsers(): Promise<AdminUser[]> {
  const items: AdminUser[] = []
  let page = 1
  const limit = 500

  while (true) {
    const body = await getJson<ApiEnvelope<{ items: AdminUser[]; hasMore: boolean }>>(
      `/api/v1/admin/user/?page=${page}&limit=${limit}&sortBy=createdAt&sortOrder=asc`,
    )
    const batch = body.data?.items ?? []
    items.push(...batch)
    if (!body.data?.hasMore || !batch.length) break
    page += 1
  }

  return items
}

export async function fetchAllGroups(): Promise<AdminGroup[]> {
  const items: AdminGroup[] = []
  let page = 1
  const limit = 500

  while (true) {
    const body = await getJson<ApiEnvelope<{ items: AdminGroup[]; has_more: boolean }>>(
      `/api/v1/admin/group/?page=${page}&limit=${limit}&sortBy=name&sortOrder=asc`,
    )
    const batch = body.data?.items ?? []
    items.push(...batch)
    if (!body.data?.has_more || !batch.length) break
    page += 1
  }

  return items
}

export async function fetchMentors(): Promise<AdminMentor[]> {
  const body = await getJson<ApiEnvelope<AdminMentor[]>>('/api/v1/admin/mentor/')
  return body.data ?? []
}

export async function fetchGroupActivity(start?: string, end?: string): Promise<GroupActivityResponse> {
  const params = new URLSearchParams()
  if (start) params.set('start', start)
  if (end) params.set('end', end)
  const query = params.toString()
  const body = await getJson<ApiEnvelope<GroupActivityResponse>>(
    `/api/v1/admin/analytics/group-activity/${query ? `?${query}` : ''}`,
  )
  if (!body.data) throw new Error('Group activity analytics returned no data.')
  return body.data
}

export async function fetchLoginActivity(start?: string, end?: string): Promise<LoginActivityResponse> {
  const params = new URLSearchParams()
  if (start) params.set('start', start)
  if (end) params.set('end', end)
  const query = params.toString()
  const body = await getJson<ApiEnvelope<LoginActivityResponse>>(
    `/api/v1/admin/analytics/login-activity/${query ? `?${query}` : ''}`,
  )
  if (!body.data) throw new Error('Login activity analytics returned no data.')
  return body.data
}

export async function fetchResourceAnalytics(start?: string, end?: string): Promise<ResourceAnalyticsResponse> {
  const params = new URLSearchParams()
  if (start) params.set('start', start)
  if (end) params.set('end', end)
  const query = params.toString()
  const body = await getJson<ApiEnvelope<ResourceAnalyticsResponse>>(
    `/api/v1/admin/analytics/resources/${query ? `?${query}` : ''}`,
  )
  if (!body.data) throw new Error('Resource analytics returned no data.')
  return body.data
}

export async function fetchEmailDeliveryAnalytics(): Promise<EmailDeliveryAnalyticsResponse> {
  const body = await getJson<ApiEnvelope<EmailDeliveryAnalyticsResponse>>('/api/v1/admin/analytics/email/')
  if (!body.data) throw new Error('Email analytics returned no data.')
  return body.data
}

/** Emails sent to recipients whose address or name matches ``query``. */
export async function searchEmailsToRecipient(query: string): Promise<EmailSendToRecipient[]> {
  const params = new URLSearchParams({ recipient: query })
  const body = await getJson<ApiEnvelope<EmailSendToRecipient[]>>(
    `/api/v1/admin/analytics/email/recipients/?${params}`,
  )
  return body.data ?? []
}

/** Download one send's recipient list as CSV. */
export async function downloadEmailRecipientsCsv(sendId: number): Promise<string> {
  const response = await fetch(
    `${API_BASE_URL}/api/v1/admin/analytics/email/sends/${sendId}/recipients/export/`,
    { credentials: 'include' },
  )
  if (!response.ok) throw new Error(`The recipient list could not be downloaded (${response.status}).`)
  const candidate = /filename="?([^";]+)"?/i.exec(response.headers.get('Content-Disposition') ?? '')?.[1]
  const filename = candidate && /^[a-z0-9][a-z0-9._-]*\.csv$/i.test(candidate)
    ? candidate
    : `biotech-email-recipients-send-${sendId}.csv`
  const url = window.URL.createObjectURL(await response.blob())
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.URL.revokeObjectURL(url)
  return filename
}

export async function fetchAllResources(): Promise<AdminResource[]> {
  const items: AdminResource[] = []
  let page = 1
  const limit = 500

  while (true) {
    const body = await getJson<ApiEnvelope<{ items: AdminResource[]; hasMore: boolean }>>(
      `/api/v1/admin/resource/?page=${page}&limit=${limit}`,
    )
    const batch = body.data?.items ?? []
    items.push(...batch)
    if (!body.data?.hasMore || !batch.length) break
    page += 1
  }

  return items
}

export { API_BASE_URL }
