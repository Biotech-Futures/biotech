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
  /** The marker's comment on the part as a whole; "" when none. */
  overall_comment?: string
  /** On the Results section: the part's marks added up, e.g. "14.5". */
  subtotal?: string
  /** The most they could be, e.g. "20". */
  subtotal_max?: string
}

export async function requestJson<T>(pathOrUrl: string, options: RequestInit = {}): Promise<T> {
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

// Submission file URLs are absolute when storage is Azure (SAS-signed) but
// relative (/media/...) with local dev storage — resolve those against the
// API origin so they don't 404 against the SPA dev server.
export function resolveApiFileUrl(url: string | null): string | null {
  if (!url) return null
  return url.startsWith('http') ? url : `${API_BASE_URL}${url}`
}

// Save a blob through a synthetic <a download> click. Needed because the API
// sits on a different origin than the SPA dev server, so a plain <a href>
// would not carry the session cookie.
export function triggerBlobDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

// GET a binary endpoint with the session cookie and return the blob plus the
// server-suggested filename (from Content-Disposition, if any).
export async function requestBlob(
  pathOrUrl: string,
  options: RequestInit = {}
): Promise<{ blob: Blob; filename: string | null }> {
  const method = String(options.method || 'GET').toUpperCase()
  const includeCSRF = !['GET', 'HEAD', 'OPTIONS'].includes(method)
  const csrfReady = await ensureCsrfCookie(API_BASE_URL)
  if (!csrfReady) throw new Error('Could not initialize a secure session.')
  const url = pathOrUrl.startsWith('http') ? pathOrUrl : `${API_BASE_URL}${pathOrUrl}`
  const response = await fetch(url, {
    credentials: 'include',
    ...options,
    headers: buildSessionHeaders({
      includeCSRF,
      isFormData: options.body instanceof FormData,
      headers: { Accept: '*/*', ...(options.headers || {}) }
    })
  })
  if (!response.ok) throw await apiErrorFromResponse(response)
  const disposition = response.headers.get('content-disposition') || ''
  const match = /filename="?([^";]+)"?/.exec(disposition)
  return { blob: await response.blob(), filename: match?.[1] ?? null }
}

// Fetch a submitted file and save it through a blob link. A plain <a download>
// can't force this: the file URL is cross-origin, where browsers ignore the
// download attribute, and local /media/ serves PDFs inline (the storage layer
// only bakes an attachment disposition into Azure SAS URLs).
export async function downloadSubmissionFile(url: string, fallbackName: string): Promise<void> {
  const { blob, filename } = await requestBlob(url)
  triggerBlobDownload(blob, filename ?? fallbackName)
}

// ---------------------------------------------------------------------------
// Admin marking API — ported from adminweb (src/query/grading.ts + type/
// grading.ts). Decimal fields (mark, max_mark) come down as strings because
// Django's DecimalField serialises that way — convert to Number only at the
// last moment for display / input state.
// ---------------------------------------------------------------------------

export interface SubmissionComponent {
  id: number
  code: string
  name: string
  is_optional: boolean
  accepts_file: boolean
  accepts_text: boolean
  accepts_link: boolean
  order: number
}

export interface SubmissionAnswer {
  prompt: string
  answer: string
}

export interface Submission {
  id: number
  component: number
  file_url: string | null
  /** Attachment-download variant of the submitted file's URL. */
  file_download_url?: string | null
  /** Original filename of the uploaded file, when the component has one. */
  file_name?: string | null
  text: string
  /** SAQ only: per-question blocks; `text` is the same content flattened. */
  answers?: SubmissionAnswer[] | null
  link: string
  submitted_at: string
  is_late: boolean
  /** Marker's overall feedback on the whole submission. */
  overall_comment: string
}

export interface RubricCriterion {
  id: number
  rubric: number
  name: string
  max_mark: string
  order: number
}

export interface Grade {
  id: number
  submission: number
  criterion: number
  mark: string | null
  comment: string
  graded_by: number | null
  /** Display name of the last marker of this criterion. */
  graded_by_name: string | null
  graded_at: string
}

export interface GroupMarkingComponentBlock {
  component: SubmissionComponent
  submission: Submission | null
  rubric_id: number | null
  criteria: RubricCriterion[]
  grades: Grade[]
  /** Who last scored this component (newest scored grade's author). */
  last_grader_name: string | null
}

export interface GroupMarkingPayload {
  /** project_title: the title the team submitted; "" when it gave none. */
  group: { id: number; group_name: string; project_title: string }
  year: number
  components: GroupMarkingComponentBlock[]
}

export interface GradeBulkItem {
  submission: number
  criterion: number
  mark: string | null
  comment: string
  /** The mark and comment the marker started from: the server refuses the
   *  save if another marker has changed them since. */
  expected_mark?: string | null
  expected_comment?: string
}

/** An overall comment edited on the marking page, and the one it started from. */
export interface OverallCommentEdit {
  comment: string
  expected: string
}

// One row per group, whether or not they've submitted. Powers the
// per-component table and the detail view's prev/next navigation.
export interface ComponentRow {
  group_id: number
  group_name: string
  submission_id: number | null
  submitted_at: string | null
  is_late: boolean
  /** How far past the deadline, e.g. "3h 12m"; "" when the amount is unknown;
   *  null for on-time or unsubmitted rows. */
  late_by: string | null
  criteria_graded: number
  /** Sum of scored marks for this component (2-dp string), null when ungraded. */
  marks_total: string | null
  last_grader_name: string | null
  grader_names: string[]
  /** Latest marker per rubric position (1-based); only scored criteria appear. */
  criterion_markers: { n: number; marker: string }[]
}

export interface ComponentListPayload {
  component: SubmissionComponent
  year: number
  criteria_total: number
  rows: ComponentRow[]
}

// GradingJob polling payload — poll until status becomes "done" (then download
// download_url) or "failed" (surface `error`).
export type GradingJobStatus = 'pending' | 'running' | 'done' | 'failed'

export interface GradingJobDetail {
  id: number
  kind: string
  status: GradingJobStatus
  // Django-served proxy URL, resolved once the job is done. The client never
  // sees the underlying storage URL (Azure or local).
  download_url: string | null
  error: string | null
  created_at: string
  finished_at: string | null
}

// Response from bulk-upload (dry-run and commit share the shape; commit adds
// `applied: true` + `written`).
export interface BulkUploadRowEntry {
  row: number
  group_id: number
  criterion_id: number
  submission_id: number
  mark: string | null
  comment: string
  grade_id?: number
  // Updates only: the group's name and the sheet columns whose values differ.
  group_name?: string | null
  columns?: string[]
  old_mark?: string | null
  old_comment?: string
}

export interface BulkUploadError {
  row: number
  message: string
}

export interface BulkUploadSummary {
  creates: number
  updates: number
  unchanged: number
  overall_comments?: number
  // SAQ sheets only: marking key selections parsed from the sheet.
  marking_categories?: number
  errors: number
}

/** Categorised validation report shown on preview. */
export interface BulkUploadChecks {
  missing_headers: string[]
  /** Why the known headers are out of order, e.g. "product_category should
   *  come before r1_mark"; "" when they are in order. */
  header_order?: string
  // The sheet's type column check ("SAQs", "Poster", …).
  expected_type?: string
  /** The only year the sheet's rows may carry: the current challenge year. */
  expected_year?: number
  /** The first wrong year a row carried, or the sheet's year when all are right. */
  found_year?: string | null
  year_ok?: boolean
  found_type?: string | null
  type_ok?: boolean
  bad_group_rows: { row: number; reason: string }[]
  bad_marks: { row: number; column: string; hint: string }[]
}

export interface BulkUploadCategoryEntry {
  row: number
  group_id: number
  group_name?: string | null
  // The category columns this change touches, and those of them that had a
  // stored value (replaced or cleared) rather than being set for the first time.
  columns?: string[]
  overwritten_columns?: string[]
  product_categories: string[]
  product_category_other: string
  solution_category: string
  solution_category_other: string
}

/** A group's overall comment the sheet changes. An empty old_comment means
 *  none was stored (a new record); otherwise it's replaced or cleared. */
export interface BulkUploadOverallCommentEntry {
  row: number
  group_id: number
  group_name?: string | null
  component_id: number
  comment: string
  old_comment: string
}

export interface BulkUploadResponse {
  creates: BulkUploadRowEntry[]
  updates: BulkUploadRowEntry[]
  unchanged: BulkUploadRowEntry[]
  overall_comments?: BulkUploadOverallCommentEntry[]
  // SAQ shape only: marking key changes parsed from the sheet.
  marking_categories?: BulkUploadCategoryEntry[]
  errors: BulkUploadError[]
  checks?: BulkUploadChecks
  summary: BulkUploadSummary
  applied?: boolean
  written?: number
}

export interface FinalistRow {
  group_id: number
  group_name: string
  flagged_at: string
  flagged_by: string | null
  notified: boolean
  notified_at: string | null
  notified_by: string | null
}

export interface FinalistListResponse {
  finalists: FinalistRow[]
}

// GET /api/v1/grading/groups/{id}/ — composite marking payload for one group.
export function fetchGroupMarking(groupId: number, year?: number): Promise<GroupMarkingPayload> {
  const qs = year ? `?year=${year}` : ''
  return requestJson<GroupMarkingPayload>(`/api/v1/grading/groups/${groupId}/${qs}`)
}

// POST /api/v1/grading/grades/bulk/ — upsert many grades in one round trip.
// Which components carry an overall-comment box, and its heading.
const OVERALL_COMMENT_LABELS: Record<string, string> = {
  SAQ: 'Overall SAQs Comment',
  POSTER: 'Overall Poster Comment',
  REPORT: 'Overall Scientific Report Comment',
  PROTOTYPE: 'Overall Prototype Comment'
}

export function overallCommentLabel(code: string): string | null {
  return OVERALL_COMMENT_LABELS[code] ?? null
}

export function saveGradesBulk(
  items: GradeBulkItem[],
  // `component` is the component code the comment belongs to. Required by the
  // server whenever the entry has content for more than one component: a
  // submission id covers the group's whole entry, so the id alone cannot say
  // which component's comment this is.
  overallComments?: { submission: number; component?: string; comment: string; expected_comment?: string }[]
): Promise<Grade[]> {
  return requestJson<Grade[]>('/api/v1/grading/grades/bulk/', {
    method: 'POST',
    body: JSON.stringify(
      overallComments?.length ? { items, overall_comments: overallComments } : { items }
    )
  })
}

// GET /api/v1/grading/components/{code}/ — table payload for the
// per-component marking flow ("sit down and mark all posters").
export function fetchComponentRows(code: string, year?: number): Promise<ComponentListPayload> {
  const qs = year ? `?year=${year}` : ''
  return requestJson<ComponentListPayload>(`/api/v1/grading/components/${encodeURIComponent(code)}/${qs}`)
}

// GET /api/v1/grading/groups/{id}/download/ — sync zip fetch + browser save.
export async function downloadGroupZip(groupId: number, component?: string): Promise<void> {
  const qs = component ? `?component=${encodeURIComponent(component)}` : ''
  const { blob, filename } = await requestBlob(`/api/v1/grading/groups/${groupId}/download/${qs}`)
  triggerBlobDownload(blob, filename ?? `group-${groupId}.zip`)
}

// POST /api/v1/grading/components/{code}/download/ — kicks off a GradingJob,
// returns the job id. Caller polls fetchJobStatus until done/failed.
export async function startComponentDownload(
  code: string,
  format: 'zip' | 'xlsx',
  groupIds?: number[]
): Promise<number> {
  const data = await requestJson<{ job_id: number }>(
    `/api/v1/grading/components/${encodeURIComponent(code)}/download/`,
    { method: 'POST', body: JSON.stringify({ format, group_ids: groupIds ?? null }) }
  )
  return data.job_id
}

// POST /api/v1/grading/download-all/ — async zip of every group's entry
// across all components. Same 202 + job-polling contract as above.
export async function startAllSubmissionsDownload(): Promise<number> {
  const data = await requestJson<{ job_id: number }>('/api/v1/grading/download-all/', {
    method: 'POST',
    body: JSON.stringify({})
  })
  return data.job_id
}

// GET /api/v1/grading/jobs/{id}/ — poll target for async downloads.
export function fetchJobStatus(jobId: number): Promise<GradingJobDetail> {
  return requestJson<GradingJobDetail>(`/api/v1/grading/jobs/${jobId}/`)
}

// Fetch a finished job's file (session-authenticated) and save it.
export async function downloadJobResult(job: GradingJobDetail): Promise<void> {
  if (!job.download_url) throw new Error('Job has no download URL yet.')
  const { blob, filename } = await requestBlob(job.download_url)
  triggerBlobDownload(blob, filename ?? `grading-job-${job.id}`)
}

// POST /api/v1/grading/components/{code}/bulk-upload/ — multipart spreadsheet
// upload. Same call for preview and apply; flip `dryRun` to switch modes. The
// backend re-parses on apply so the committed diff reflects current DB state.
export function bulkUploadMarks(
  code: string,
  file: File,
  dryRun: boolean
): Promise<BulkUploadResponse> {
  const form = new FormData()
  form.append('file', file)
  form.append('dry_run', dryRun ? 'true' : 'false')
  return requestJson<BulkUploadResponse>(
    `/api/v1/grading/components/${encodeURIComponent(code)}/bulk-upload/`,
    { method: 'POST', body: form }
  )
}

// The marking key's header categories for one group (per-group, not per
// component — the same header appears on every marking key sheet).
export interface GroupCategories {
  product_categories: string[]
  product_category_other: string
  solution_category: string
  solution_category_other: string
}

export function fetchGroupCategories(groupId: number): Promise<GroupCategories> {
  return requestJson<GroupCategories>(`/api/v1/grading/groups/${groupId}/categories/`)
}

export function saveGroupCategories(
  groupId: number,
  data: GroupCategories
): Promise<GroupCategories> {
  return requestJson<GroupCategories>(`/api/v1/grading/groups/${groupId}/categories/`, {
    method: 'POST',
    body: JSON.stringify(data)
  })
}

// Ranking table for picking finalists: per-group mark totals by component.
export interface FinalistCandidateRow {
  group_id: number
  group_name: string
  is_late: boolean
  /** How far past the deadline, e.g. "3h 12m"; "" when the amount is unknown;
   *  null for on-time or unsubmitted rows. */
  late_by: string | null
  /** Component code -> summed marks (decimal string), null when ungraded. */
  marks: Record<string, string | null>
  total: string | null
  markers: string[]
  /** Latest marker per rubric criterion, e.g. {label: "SAQ 1", marker: "Ada"}. */
  criterion_markers: { label: string; marker: string }[]
  /** The title the team submitted; "" when it gave none. */
  project_title: string
  /** The categories picked on the marking key; "" when none. */
  project_category: string
  solution_category: string
  is_finalist: boolean
  has_submission: boolean
  /** Components the team submitted that still have unmarked criteria. */
  incomplete: string[]
}

export interface FinalistCandidatesResponse {
  components: { code: string; name: string }[]
  rows: FinalistCandidateRow[]
}

// GET /api/v1/grading/finalists/candidates/ — sorted by total, highest first.
export function fetchFinalistCandidates(): Promise<FinalistCandidatesResponse> {
  return requestJson<FinalistCandidatesResponse>('/api/v1/grading/finalists/candidates/')
}

// GET /api/v1/grading/finalists/ — the current finalist set.
export function fetchFinalists(): Promise<FinalistListResponse> {
  return requestJson<FinalistListResponse>('/api/v1/grading/finalists/')
}

// POST /api/v1/grading/groups/{id}/finalist/ — idempotent upsert. Telling
// the team is Notify Finalists' job.
export function addFinalist(groupId: number): Promise<void> {
  return requestJson<void>(`/api/v1/grading/groups/${groupId}/finalist/`, { method: 'POST' })
}

// DELETE /api/v1/grading/groups/{id}/finalist/ — idempotent removal.
export function removeFinalist(groupId: number): Promise<void> {
  return requestJson<void>(`/api/v1/grading/groups/${groupId}/finalist/`, {
    method: 'DELETE'
  })
}
