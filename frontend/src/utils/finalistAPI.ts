import { postFileWithProgress, requestJson } from './submissionsAPI'
import type { StoredFile, SubmissionDeadline, SubmissionStage } from './submissionsAPI'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

/** A presentation time, set on Management > Finalist Presentation. */
export interface FinalistSession {
  id: number
  /** e.g. "9:30 – 10:00" */
  label: string
}

export interface FinalistEntry {
  /** The times the team can make, one answer for the whole team. */
  available_session_ids: number[]
  /** When the team's times were last submitted; null until they are. */
  availability_submitted_at: string | null
  /** Who submitted them: anyone on the team, or an admin. */
  availability_submitted_by_name: string
  presentation: StoredFile | null
  submitted_presentation: StoredFile | null
  submitted_at: string | null
  submitted_by_name: string
  reopened_at: string | null
  stage: SubmissionStage
  is_submitted: boolean
  is_locked: boolean
  updated_at: string
}

export interface FinalistDetail {
  group: { id: number; name: string }
  deadline: SubmissionDeadline
  /** Whether Management has shared the times yet; until then none, and
   *  none are needed to submit. */
  times_shown: boolean
  /** This year's presentation times. */
  sessions: FinalistSession[]
  /** The day they're on (set on Notify Finalists); null until it is. */
  symposium_date: string | null
  max_file_size: number
  /** Null until the team first saves something. */
  entry: FinalistEntry | null
}

export interface FinalistWriteResult {
  deadline: SubmissionDeadline
  entry: FinalistEntry
}

function base(groupId: number | string) {
  return `/api/v1/submissions/finalist/groups/${groupId}`
}

export function fetchFinalist(groupId: number | string) {
  return requestJson<FinalistDetail>(`${base(groupId)}/`)
}

export function submitAvailability(groupId: number | string, sessionIds: number[]) {
  return requestJson<FinalistWriteResult>(`${base(groupId)}/`, {
    method: 'PUT',
    body: JSON.stringify({ session_ids: sessionIds })
  })
}

export function uploadPresentation(
  groupId: number | string,
  file: File,
  onProgress?: (percent: number) => void
) {
  return postFileWithProgress<FinalistWriteResult>(`${base(groupId)}/presentation/`, file, onProgress)
}

export function removePresentation(groupId: number | string) {
  return requestJson<FinalistWriteResult>(`${base(groupId)}/presentation/`, { method: 'DELETE' })
}

export function submitFinalist(groupId: number | string) {
  return requestJson<FinalistWriteResult>(`${base(groupId)}/submit/`, {
    method: 'POST',
    body: JSON.stringify({})
  })
}

export function reopenFinalist(groupId: number | string) {
  return requestJson<FinalistWriteResult>(`${base(groupId)}/reopen/`, {
    method: 'POST',
    body: JSON.stringify({})
  })
}

export function presentationDownloadUrl(groupId: number | string) {
  return `${API_BASE_URL}${base(groupId)}/presentation/download/`
}

export function presentationPreviewUrl(groupId: number | string) {
  return `${API_BASE_URL}${base(groupId)}/presentation/preview/`
}
