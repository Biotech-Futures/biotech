import { apiErrorFromResponse } from './apiError'
import { buildSessionHeaders, ensureCsrfCookie } from './csrf'
import { formatShortDateTime } from './date'

export type SupervisedStudent = {
  id: number
  first_name: string
  last_name: string
  email: string
  country_name?: string
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
  signature?: string | null
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
  signature: student.signature || '',
  groupId: student.group_id,
  groupName: student.group_name,
})

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
    interests: string[]
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

export type SupervisedConsentLink = {
  studentId: number
  /** The consent link, or null when one couldn't be made (see msg). */
  link: string | null
  msg: string
}

/** Consent links for the students' guardians, to share by hand. A link
 *  already out is given again, so an emailed one keeps working. */
export async function fetchConsentLinks(studentIds: number[]): Promise<SupervisedConsentLink[]> {
  await ensureCsrfCookie(API_BASE_URL)
  const response = await fetch(`${API_BASE_URL}/api/v1/users/supervised-students/consent-links/`, {
    method: 'POST',
    credentials: 'include',
    headers: buildSessionHeaders({
      includeCSRF: true,
      headers: { Accept: 'application/json' },
    }),
    body: JSON.stringify({ student_ids: studentIds }),
  })
  const payload = (await response.json().catch(() => ({}))) as {
    links?: SupervisedConsentLink[]
    msg?: string
    error?: string
  }
  if (!response.ok) {
    throw new Error(payload.msg || payload.error || 'Consent links could not be made.')
  }
  return payload.links || []
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
