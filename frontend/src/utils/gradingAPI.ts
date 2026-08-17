import { apiErrorFromResponse } from './apiError'
import { buildSessionHeaders, ensureCsrfCookie } from './csrf'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export interface CriterionMark {
  name: string
  max_mark: string
  mark: string
  comment: string
}

export interface ComponentBlock {
  code: string
  name: string
  submitted: boolean
  criteria: CriterionMark[]
}

export interface MyGradesPayload {
  group: { id: number; group_name: string }
  year: number
  components: ComponentBlock[]
}

// GET /api/v1/grading/release/ — surfaces released_at so the UI can decide
// whether to render the Results tab. Kept public-ish (any authenticated user
// can hit it if it becomes needed) but the current backend limits it to
// is_staff. Front-of-house code should treat 403 here as "not released yet".
export interface ReleaseStatus {
  released_at: string | null
  released_by: string | null
}

async function requestJson<T>(pathOrUrl: string, options: RequestInit = {}): Promise<T> {
  const method = String(options.method || 'GET').toUpperCase()
  const isFormData = options.body instanceof FormData
  const includeCSRF = !['GET', 'HEAD', 'OPTIONS'].includes(method)

  if (includeCSRF) {
    const csrfReady = await ensureCsrfCookie(API_BASE_URL)
    if (!csrfReady) {
      throw new Error('Could not initialize a secure session. Please refresh and try again.')
    }
  }

  const url = pathOrUrl.startsWith('http') ? pathOrUrl : `${API_BASE_URL}${pathOrUrl}`
  const response = await fetch(url, {
    credentials: 'include',
    ...options,
    headers: buildSessionHeaders({
      includeCSRF,
      isFormData,
      headers: {
        Accept: 'application/json',
        ...(options.headers || {})
      }
    })
  })

  if (!response.ok) {
    throw await apiErrorFromResponse(response)
  }

  const text = await response.text()
  return (text ? JSON.parse(text) : null) as T
}

export function fetchMyGrades(): Promise<MyGradesPayload> {
  return requestJson<MyGradesPayload>('/api/v1/grading/me/grades/')
}

// Fetch bytes for the summary/certificate docx and trigger a browser download.
// Rendered server-side via docxtpl (see backend/apps/grading/services/docx.py).
async function downloadDocx(path: string, filename: string) {
  const csrfReady = await ensureCsrfCookie(API_BASE_URL)
  if (!csrfReady) throw new Error('Could not initialize a secure session.')
  const response = await fetch(`${API_BASE_URL}${path}`, {
    credentials: 'include',
    headers: buildSessionHeaders({ includeCSRF: false, isFormData: false, headers: { Accept: '*/*' } }),
  })
  if (!response.ok) throw await apiErrorFromResponse(response)
  const blob = await response.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

export function downloadMySummary(groupName: string) {
  return downloadDocx('/api/v1/grading/me/summary/', `marks-summary-${groupName}.docx`)
}

export function downloadMyCertificate(groupName: string) {
  return downloadDocx('/api/v1/grading/me/certificate/', `certificate-${groupName}.docx`)
}
