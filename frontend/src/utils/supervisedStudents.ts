import { apiErrorFromResponse } from './apiError'
import { buildSessionHeaders, ensureCsrfCookie } from './csrf'

export type SupervisedStudent = {
  id: number
  first_name: string
  last_name: string
  email: string
  school_name: string
  year_lvl: string
  interests: string[]
  pg_first_name: string
  pg_last_name: string
  pg_email: string | null
  parent_guardian_flag: boolean
  has_join_permission: boolean
  joinperm_response_id: string | null
  group_id: number | null
  group_name: string | null
}

export type StudentRegistrationBucket =
  | 'pendingDetails'
  | 'pendingPermission'
  | 'fullyRegistered'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export const fullName = (first?: string | null, last?: string | null, fallback = '—') => {
  const name = `${first || ''} ${last || ''}`.trim()
  return name || fallback
}

export const classifyStudent = (student: SupervisedStudent): StudentRegistrationBucket => {
  if (student.has_join_permission) return 'fullyRegistered'
  if (student.parent_guardian_flag) return 'pendingPermission'
  return 'pendingDetails'
}

export const registrationLabel = (student: SupervisedStudent) => {
  const bucket = classifyStudent(student)
  if (bucket === 'fullyRegistered') return 'Fully registered with parent/guardian permission'
  if (bucket === 'pendingPermission') return 'Pending parent/guardian permission'
  return 'Pending parent/guardian details'
}

export const initials = (first?: string | null, last?: string | null, fallback = '—') => {
  const letters = `${(first || '').trim().charAt(0)}${(last || '').trim().charAt(0)}`.toUpperCase()
  return letters || fallback.charAt(0).toUpperCase() || '?'
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
  joinpermResponseId: student.joinperm_response_id || '',
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

export async function fetchSupervisedStudent(
  id: number,
  headers: HeadersInit,
): Promise<SupervisedStudent | null> {
  const students = await fetchSupervisedStudents(headers)
  return students.find((student) => student.id === id) ?? null
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
