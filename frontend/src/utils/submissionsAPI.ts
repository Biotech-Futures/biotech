import { apiErrorFromResponse } from './apiError'
import { buildSessionHeaders, ensureCsrfCookie } from './csrf'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

/** The three fixed attachment slots on a competition entry. */
export type SubmissionSlot = 'poster' | 'report' | 'prototype'

/** File details as stored by the backend, or null when nothing is attached. */
export interface StoredFile {
  storage_key: string
  name: string | null
  mime: string | null
  size: number | null
}

export interface SubmissionDeadline {
  closes_at: string | null
  is_extended: boolean
  is_open: boolean
}

export interface SubmissionRecord {
  answers: Record<string, string>
  poster: StoredFile | null
  report: StoredFile | null
  prototype: StoredFile | null
  prototype_url: string
  submitted_at: string | null
  is_submitted: boolean
  is_late: boolean
  updated_at: string
}

/** A question the form should render. Defined in the database, not here. */
export interface SubmissionQuestion {
  key: string
  prompt: string
  help_text: string
  is_required: boolean
  max_length: number | null
}

export interface SubmissionDetail {
  group: { id: number; name: string }
  deadline: SubmissionDeadline
  questions: SubmissionQuestion[]
  /** Upload ceiling in bytes, set by the server. */
  max_file_size: number
  /** null until the team saves something for the first time. */
  submission: SubmissionRecord | null
}

export interface SubmissionWriteResult {
  deadline: SubmissionDeadline
  submission: SubmissionRecord
}

export interface SaveDraftPayload {
  answers?: Record<string, string>
  prototype_url?: string
}

async function requestJson<T>(path: string, options: RequestInit = {}): Promise<T> {
  const method = String(options.method || 'GET').toUpperCase()
  const isFormData = options.body instanceof FormData
  const includeCSRF = !['GET', 'HEAD', 'OPTIONS'].includes(method)

  if (includeCSRF) {
    const csrfReady = await ensureCsrfCookie(API_BASE_URL)
    if (!csrfReady) {
      throw new Error('Could not initialize a secure session. Please refresh and try again.')
    }
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
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

function base(groupId: number | string) {
  return `/api/v1/submissions/groups/${groupId}`
}

export function fetchSubmission(groupId: number | string) {
  return requestJson<SubmissionDetail>(`${base(groupId)}/`)
}

export function saveDraft(groupId: number | string, payload: SaveDraftPayload) {
  return requestJson<SubmissionWriteResult>(`${base(groupId)}/`, {
    method: 'PUT',
    body: JSON.stringify(payload)
  })
}

export function submitEntry(groupId: number | string) {
  return requestJson<SubmissionWriteResult>(`${base(groupId)}/submit/`, {
    method: 'POST',
    body: JSON.stringify({})
  })
}

export function uploadSubmissionFile(
  groupId: number | string,
  slot: SubmissionSlot,
  file: File
) {
  const body = new FormData()
  body.append('file', file)
  // No Content-Type header: the browser sets it with the multipart boundary,
  // and overriding it makes the upload unparseable on the server.
  return requestJson<SubmissionWriteResult>(`${base(groupId)}/files/${slot}/`, {
    method: 'POST',
    body
  })
}

export function removeSubmissionFile(groupId: number | string, slot: SubmissionSlot) {
  return requestJson<SubmissionWriteResult>(`${base(groupId)}/files/${slot}/`, {
    method: 'DELETE'
  })
}

export function submissionFileDownloadUrl(groupId: number | string, slot: SubmissionSlot) {
  return `${API_BASE_URL}${base(groupId)}/files/${slot}/download/`
}
