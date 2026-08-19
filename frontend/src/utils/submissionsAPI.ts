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

/** Slots the browser can display inline. The prototype accepts arbitrary file
 *  types, so it is download-only — see the preview view for the reasoning. */
export const PREVIEWABLE_SLOTS: SubmissionSlot[] = ['poster', 'report']

export function submissionFilePreviewUrl(groupId: number | string, slot: SubmissionSlot) {
  return `${API_BASE_URL}${base(groupId)}/files/${slot}/preview/`
}

/**
 * Fetch an attachment and return a local object URL for displaying it.
 *
 * The backend sets `X-Frame-Options: DENY` across the whole platform, so
 * pointing a frame straight at the preview endpoint is refused by the browser.
 * Fetching the bytes and showing them from memory makes the content part of
 * this page rather than an embedded foreign document, so the framing rule does
 * not apply — and it carries credentials reliably even when the API is served
 * from a different domain than the app.
 *
 * The caller owns the returned URL and must pass it to `releasePreview` when
 * finished, or the browser holds the file in memory for the life of the tab.
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
