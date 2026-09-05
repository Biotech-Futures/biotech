import { ApiError, apiErrorFromResponse, normalizeApiErrorBody } from './apiError'
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

/** How far an entry has got, independently of whether the window is open. */
export type SubmissionStage = 'not_started' | 'in_progress' | 'submitted' | 'revising'

/** One requirement the poster did not visibly meet. */
export interface PosterWarning {
  code: string
  passed: boolean
  message: string
}

/**
 * What the format checks found when the poster was uploaded.
 *
 * Only ever warnings: a structural failure is refused at upload.
 */
export interface PosterChecks {
  /** False when the poster carries no readable text, so nothing could be checked. */
  has_text: boolean
  /** True when the file could not be parsed; it was accepted rather than refused. */
  unreadable: boolean
  warnings: PosterWarning[]
}

export interface SubmissionRecord {
  /** The working copy, edited while the entry is in progress. */
  answers: Record<string, string>
  poster: StoredFile | null
  poster_checks: PosterChecks | null
  report: StoredFile | null
  prototype: StoredFile | null
  prototype_url: string
  /** What was actually submitted; unchanged while a revision is in progress. */
  submitted_answers: Record<string, string> | null
  submitted_poster: StoredFile | null
  submitted_poster_checks: PosterChecks | null
  submitted_report: StoredFile | null
  submitted_prototype: StoredFile | null
  submitted_prototype_url: string
  submitted_at: string | null
  submitted_by_name: string
  reopened_at: string | null
  /**
   * How far the entry has got, said independently of the deadline.
   *
   * Whether the window is open is a separate fact; the page pairs the two.
   */
  stage: SubmissionStage
  is_submitted: boolean
  /** Submitted and not reopened — editing is closed. */
  is_locked: boolean
  is_late: boolean
  updated_at: string
}

/** A question the form should render. Defined in the database, not here. */
export interface SubmissionQuestion {
  key: string
  prompt: string
  help_text: string
  is_required: boolean
  /** Word limit, matching the rule the competition publishes. Null = no limit. */
  max_words: number | null
}

export interface SubmissionDetail {
  group: { id: number; name: string }
  deadline: SubmissionDeadline
  questions: SubmissionQuestion[]
  /** Section title and supporting line, editable by admins. */
  instructions: Record<string, { heading: string; body: string }>
  /** Upload ceiling in bytes per slot, set by the server. PDFs are held to a
   *  tighter limit than the prototype. */
  max_file_sizes: Record<SubmissionSlot, number>
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

/** Reopen a submitted entry for revision, leaving the submitted copy in place. */
export function reopenEntry(groupId: number | string) {
  return requestJson<SubmissionWriteResult>(`${base(groupId)}/reopen/`, {
    method: 'POST',
    body: JSON.stringify({})
  })
}

/**
 * Upload one attachment, reporting progress as it goes.
 *
 * XMLHttpRequest rather than fetch: only XHR exposes upload progress, and a
 * large poster on a slow line otherwise looks like a frozen page.
 */
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
  // No Content-Type header is set: the browser adds it along with the
  // multipart boundary, and overriding it makes the upload unparseable.
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
      // Same error shape the fetch-based calls produce, so callers can read
      // `.message` and `.body` without caring which transport was used.
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

/** Inline display, for the poster and report only — the prototype accepts
 *  arbitrary file types and the endpoint refuses to render it. */
export function submissionFilePreviewUrl(groupId: number | string, slot: SubmissionSlot) {
  return `${API_BASE_URL}${base(groupId)}/files/${slot}/preview/`
}

/**
 * Fetch an attachment and return a local object URL for displaying it.
 *
 * `X-Frame-Options: DENY` blocks framing the endpoint, so the bytes are
 * shown from memory. The caller must `releasePreview` or it leaks.
 */
export async function fetchPreviewObjectUrl(
  groupId: number | string,
  slot: SubmissionSlot
): Promise<string> {
  const response = await fetch(submissionFilePreviewUrl(groupId, slot), {
    credentials: 'include',
    // Must stay permissive: the API negotiates content types and has no PDF
    // renderer registered, so asking specifically for application/pdf is
    // refused with 406 before the view ever runs.
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
