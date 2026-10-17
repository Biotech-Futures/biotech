import { apiErrorFromResponse } from './apiError'
import { buildSessionHeaders, ensureCsrfCookie } from './csrf'
import { formatShortDateTime } from './date'

export type SupervisedStudent = {
  id: number
  first_name: string
  last_name: string
  email: string
  country_id?: number | null
  country_name?: string
  state_id?: number | null
  state_name?: string
  /** "Active", "Pending" and so on. */
  account_status?: string
  /** From the signed form: null when there's none on the platform. */
  media_consent?: boolean | null
  school_name: string
  year_lvl: string
  interests: string[]
  pg_first_name: string
  pg_last_name: string
  pg_email: string | null
  parent_guardian_flag: boolean
  has_join_permission: boolean
  joinperm_response_id: string | null
  joinperm_granted_at: string | null
  group_id: number | null
  group_name: string | null
}

export type StudentRegistrationBucket =
  | 'pendingDetails'
  | 'pendingPermission'
  | 'fullyRegistered'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export const fullName = (first?: string | null, last?: string | null, fallback = '—') => {
  const name = [first, last]
    .map((part) => String(part || '').replace(/\s+/g, ' ').trim())
    .filter(Boolean)
    .join(' ')
  return name || fallback
}

// A guardian email is what makes a student pending permission: without one
// there's nobody to send the consent form to. Same rule as the backend's daily
// guardian details email (guardian_details.students_due). parent_guardian_flag
// can't be used, as every student is saved with it on.
export const classifyStudent = (student: SupervisedStudent): StudentRegistrationBucket => {
  if (student.has_join_permission) return 'fullyRegistered'
  if ((student.pg_email || '').trim()) return 'pendingPermission'
  return 'pendingDetails'
}

export const toStudentRow = (student: SupervisedStudent) => ({
  id: student.id,
  student: fullName(student.first_name, student.last_name, student.email),
  email: student.email,
  parentGuardian: fullName(student.pg_first_name, student.pg_last_name),
  pgEmail: student.pg_email || '',
  school: student.school_name,
  yearLevel: student.year_lvl,
  interests: student.interests,
  permissionGiven: student.has_join_permission
    ? formatShortDateTime(student.joinperm_granted_at) || 'Recorded'
    : '—',
  permissionGivenAt: student.joinperm_granted_at,
  groupId: student.group_id,
  groupName: student.group_name,
})

/** The guardians' drawn signatures for ``studentIds`` (each a PNG data URL,
 *  or null), fetched when their consent forms are opened: the roster leaves
 *  them out, as they're large. */
export async function fetchConsentSignatures(
  studentIds: number[],
): Promise<Record<string, string | null>> {
  if (!studentIds.length) return {}
  const query = new URLSearchParams({ ids: studentIds.join(',') })
  const response = await fetch(`${API_BASE_URL}/api/v1/users/supervised-students/signatures/?${query}`, {
    credentials: 'include',
    headers: buildSessionHeaders({ headers: { Accept: 'application/json' } }),
  })
  if (!response.ok) throw await apiErrorFromResponse(response)
  const body = await response.json()
  return body?.signatures ?? {}
}

/** ``rows`` with their guardians' signatures, for their consent forms. */
export async function withConsentSignatures<T extends { id: unknown }>(
  rows: T[],
): Promise<Array<T & { signature: string }>> {
  const ids = [...new Set(rows.map((row) => Number(row.id)).filter((id) => Number.isFinite(id) && id > 0))]
  const signatures = await fetchConsentSignatures(ids)
  return rows.map((row) => ({ ...row, signature: signatures[String(row.id)] || '' }))
}

export async function saveGuardianDetails(payload: {
  student_ids: number[]
  pg_first_name: string
  pg_last_name: string
  pg_email?: string
}): Promise<SupervisedStudent[]> {
  await ensureCsrfCookie(API_BASE_URL)
  const response = await fetch(`${API_BASE_URL}/api/v1/users/supervised-students/`, {
    method: 'PATCH',
    credentials: 'include',
    headers: buildSessionHeaders({
      includeCSRF: true,
      headers: { Accept: 'application/json' },
    }),
    body: JSON.stringify(payload),
  })
  if (!response.ok) {
    throw await apiErrorFromResponse(response)
  }
  return response.json()
}

export async function updateSupervisedStudentProfile(
  studentId: number,
  payload: {
    first_name: string
    last_name: string
    email: string
    school_name: string
    year_lvl: string
    interests?: string[]
    country_id?: number | null
    state_id?: number | null
  },
): Promise<SupervisedStudent> {
  await ensureCsrfCookie(API_BASE_URL)
  const response = await fetch(`${API_BASE_URL}/api/v1/users/supervised-students/${studentId}/`, {
    method: 'PATCH',
    credentials: 'include',
    headers: buildSessionHeaders({
      includeCSRF: true,
      headers: { Accept: 'application/json' },
    }),
    body: JSON.stringify(payload),
  })
  if (!response.ok) {
    throw await apiErrorFromResponse(response)
  }
  return response.json()
}

export type SupervisedEmailKind = 'guardian_details' | 'guardian_consent'

export type SupervisedEmailResult = {
  sent: number
  failed: number
  skipped: number
  msg: string
  messages: string[]
}

export async function sendSupervisedEmails(
  studentIds: number[],
  kind: SupervisedEmailKind,
): Promise<SupervisedEmailResult> {
  await ensureCsrfCookie(API_BASE_URL)
  const response = await fetch(`${API_BASE_URL}/api/v1/users/supervised-students/email/`, {
    method: 'POST',
    credentials: 'include',
    headers: buildSessionHeaders({
      includeCSRF: true,
      headers: { Accept: 'application/json' },
    }),
    body: JSON.stringify({ student_ids: studentIds, kind }),
  })
  const payload = (await response.json().catch(() => ({}))) as Partial<SupervisedEmailResult> & {
    error?: string
    msg?: string
  }
  if (!response.ok) {
    throw new Error(payload.msg || payload.error || 'Emails could not be sent.')
  }
  return {
    sent: payload.sent ?? 0,
    failed: payload.failed ?? 0,
    skipped: payload.skipped ?? 0,
    msg: payload.msg || 'Emails sent.',
    messages: payload.messages || [],
  }
}

export type SupervisedStudentLink = {
  studentId: number
  /** The link, or null when one couldn't be made (see msg). */
  link: string | null
  msg: string
}

/** Consent links for the students' guardians, to share by hand. A link
 *  already out is given again, so an emailed one keeps working. */
export const fetchConsentLinks = (studentIds: number[]) => fetchStudentLinks('consent-links', studentIds)

/** Links to a public form for each student's guardian name and email. */
export const fetchDetailsLinks = (studentIds: number[]) => fetchStudentLinks('details-links', studentIds)

async function fetchStudentLinks(
  kind: 'consent-links' | 'details-links',
  studentIds: number[],
): Promise<SupervisedStudentLink[]> {
  await ensureCsrfCookie(API_BASE_URL)
  const response = await fetch(`${API_BASE_URL}/api/v1/users/supervised-students/${kind}/`, {
    method: 'POST',
    credentials: 'include',
    headers: buildSessionHeaders({
      includeCSRF: true,
      headers: { Accept: 'application/json' },
    }),
    body: JSON.stringify({ student_ids: studentIds }),
  })
  const payload = (await response.json().catch(() => ({}))) as {
    links?: SupervisedStudentLink[]
    msg?: string
    error?: string
  }
  if (!response.ok) {
    throw new Error(payload.msg || payload.error || 'Links could not be made.')
  }
  return payload.links || []
}

/** A sheet row that would set a student's guardian. */
export type GuardianUploadEntry = {
  row: number
  student_id: number
  student_name: string
  guardian_first_name: string
  guardian_last_name: string
  guardian_email: string
}

/** What Upload Guardian Details found in a sheet, as Upload marks reports. */
export type GuardianUploadResult = {
  checks: {
    missing_headers: string[]
    header_order: string
    unknown_students: { row: number; email: string }[]
    bad_rows: { row: number; reason: string }[]
    consented: { row: number; email: string }[]
  }
  creates: GuardianUploadEntry[]
  updates: GuardianUploadEntry[]
  unchanged: GuardianUploadEntry[]
  summary: { creates: number; updates: number; unchanged: number; errors: number }
  saved?: number
}

/** Preview (``dryRun``) or save a sheet of guardian details. */
export async function uploadGuardianDetails(file: File, dryRun: boolean): Promise<GuardianUploadResult> {
  await ensureCsrfCookie(API_BASE_URL)
  const form = new FormData()
  form.append('file', file)
  form.append('dry_run', dryRun ? 'true' : 'false')
  const response = await fetch(`${API_BASE_URL}/api/v1/users/supervised-students/guardian-upload/`, {
    method: 'POST',
    credentials: 'include',
    headers: buildSessionHeaders({ includeCSRF: true, isFormData: true, headers: { Accept: 'application/json' } }),
    body: form,
  })
  if (!response.ok) {
    throw await apiErrorFromResponse(response)
  }
  return response.json()
}

/** What the student panel's Edit offers: countries, regions and interests. */
export type StudentEditOptions = {
  countries: { id: number; country_name: string }[]
  regions: { id: number; country_id: number; state_name: string }[]
  interests: string[]
}

export async function fetchStudentEditOptions(): Promise<StudentEditOptions> {
  const response = await fetch(`${API_BASE_URL}/api/v1/users/supervised-students/options/`, {
    credentials: 'include',
    headers: buildSessionHeaders({ headers: { Accept: 'application/json' } }),
  })
  if (!response.ok) throw await apiErrorFromResponse(response)
  return response.json()
}

export async function fetchSupervisedStudents(headers: HeadersInit): Promise<SupervisedStudent[]> {
  const response = await fetch(`${API_BASE_URL}/api/v1/users/supervised-students/`, {
    method: 'GET',
    credentials: 'include',
    headers,
  })
  if (!response.ok) {
    throw await apiErrorFromResponse(response)
  }
  return response.json()
}
