import { ApiError, apiErrorFromResponse, normalizeApiErrorBody } from './apiError'
import { buildSessionHeaders, ensureCsrfCookie } from './csrf'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export type SubmissionSlot = 'poster' | 'report' | 'prototype'

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

export type SubmissionStage = 'not_started' | 'in_progress' | 'submitted' | 'revising'

export interface PosterWarning {
  code: string
  passed: boolean
  message: string
}

/** Warnings from the poster format checks; structural failures are refused at upload instead. */
export interface PosterChecks {
  has_text: boolean
  unreadable: boolean
  warnings: PosterWarning[]
}

export interface SubmissionRecord {
  answers: Record<string, string>
  poster: StoredFile | null
  poster_checks: PosterChecks | null
  report: StoredFile | null
  prototype: StoredFile | null
  prototype_url: string
  /** The submitted copy, unchanged while a revision is in progress. */
  submitted_answers: Record<string, string> | null
  submitted_poster: StoredFile | null
  submitted_poster_checks: PosterChecks | null
  submitted_report: StoredFile | null
  submitted_prototype: StoredFile | null
  submitted_prototype_url: string
  submitted_at: string | null
  submitted_by_name: string
  reopened_at: string | null
  stage: SubmissionStage
  is_submitted: boolean
  is_locked: boolean
  is_late: boolean
  updated_at: string
}

export interface SubmissionQuestion {
  key: string
  prompt: string
  help_text: string
  is_required: boolean
  /** Null means no limit. */
  max_words: number | null
}

export interface SubmissionDetail {
  group: { id: number; name: string }
  deadline: SubmissionDeadline
  questions: SubmissionQuestion[]
  instructions: Record<string, { heading: string; body: string }>
  /** Upload limit in bytes per slot. */
  max_file_sizes: Record<SubmissionSlot, number>
  /** Null until the team first saves something. */
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

export function reopenEntry(groupId: number | string) {
  return requestJson<SubmissionWriteResult>(`${base(groupId)}/reopen/`, {
    method: 'POST',
    body: JSON.stringify({})
  })
}

/** Uses XMLHttpRequest because fetch cannot report upload progress. */
export async function uploadSubmissionFile(
  groupId: number | string,
  slot: SubmissionSlot,
  file: File,
  onProgress?: (percent: number) => void
): Promise<SubmissionWriteResult> {
  const csrfReady = await ensureCsrfCookie(API_BASE_URL)
  if (!csrfReady) {
    throw new Error('Could not initialize a secure session. Please refresh and try again.')
  }

  const body = new FormData()
  body.append('file', file)
  // No Content-Type: the browser must set it to include the multipart boundary.
  const headers = buildSessionHeaders({
    includeCSRF: true,
    isFormData: true,
    headers: { Accept: 'application/json' }
  })

  return new Promise<SubmissionWriteResult>((resolve, reject) => {
    const request = new XMLHttpRequest()
    request.open('POST', `${API_BASE_URL}${base(groupId)}/files/${slot}/`)
    request.withCredentials = true
    headers.forEach((value, key) => {
      if (value) request.setRequestHeader(key, value)
    })

    request.upload.addEventListener('progress', (event) => {
      if (!onProgress || !event.lengthComputable) return
      onProgress(Math.round((event.loaded / event.total) * 100))
    })

    request.addEventListener('load', () => {
      let parsed: unknown = null
      try {
        parsed = request.responseText ? JSON.parse(request.responseText) : null
      } catch {
        parsed = null
      }
      if (request.status >= 200 && request.status < 300) {
        resolve(parsed as SubmissionWriteResult)
        return
      }
      // Same error shape as the fetch-based calls.
      reject(
        new ApiError(
          normalizeApiErrorBody(
            parsed,
            `Upload failed: ${request.status}`,
            request.getResponseHeader('X-Request-ID') || undefined,
            request.status
          ),
          request.status
        )
      )
    })

    request.addEventListener('error', () => reject(new Error('Network error during upload.')))
    request.addEventListener('abort', () => reject(new Error('Upload cancelled.')))
    request.send(body)
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

/** Poster and report only; the endpoint refuses to render the prototype. */
export function submissionFilePreviewUrl(groupId: number | string, slot: SubmissionSlot) {
  return `${API_BASE_URL}${base(groupId)}/files/${slot}/preview/`
}

/** Object URL for an attachment; release it with releasePreview. */
export async function fetchPreviewObjectUrl(
  groupId: number | string,
  slot: SubmissionSlot
): Promise<string> {
  const response = await fetch(submissionFilePreviewUrl(groupId, slot), {
    credentials: 'include',
    // Accept: application/pdf is refused with 406, as the API has no PDF renderer.
    headers: buildSessionHeaders({ headers: { Accept: '*/*' } })
  })

  if (!response.ok) {
    throw await apiErrorFromResponse(response)
  }

  return URL.createObjectURL(await response.blob())
}

export function releasePreview(objectUrl: string | null) {
  if (objectUrl) URL.revokeObjectURL(objectUrl)
}
