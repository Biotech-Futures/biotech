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
  /** Certificates gate only: finalist teams are held out of the release. */
  exclude_finalists?: boolean
  /** True while any team can still submit — releasing is refused until closed. */
  submissions_open?: boolean
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
async function requestBlob(
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

// Fetch bytes for the summary/certificate docx and trigger a browser download.
// Rendered server-side via docxtpl (see backend/apps/grading/services/docx.py).
async function downloadDocx(path: string, filename: string) {
  const { blob } = await requestBlob(path)
  triggerBlobDownload(blob, filename)
}

export function downloadMySummary(groupName: string) {
  return downloadDocx('/api/v1/grading/me/summary/', `marks-summary-${groupName}.docx`)
}

export function downloadMyCertificate(groupName: string) {
  return downloadDocx('/api/v1/grading/me/certificate/', `certificate-${groupName}.docx`)
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
  description: string
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
  group: { id: number; group_name: string }
  year: number
  components: GroupMarkingComponentBlock[]
}

export interface GradeBulkItem {
  submission: number
  criterion: number
  mark: string | null
  comment: string
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
  /** Students on the team with an address to be emailed at. */
  students: number
}

export interface FinalistListResponse {
  finalists: FinalistRow[]
}

export interface GradingSettingsDetail {
  director_1_name: string
  director_1_position: string
  director_1_signature: string | null
  director_2_name: string
  director_2_position: string
  director_2_signature: string | null
  marks_summary_template: string | null
  certificate_template: string | null
  mentor_certificate_template: string | null
  component_weights: Record<string, number>
}

/** The docx templates set up on Document Setup. */
export type TemplateKind = 'marks-summary' | 'certificate' | 'mentor-certificate'

/** The name Download Current Template saves each template under. */
export const TEMPLATE_DOWNLOAD_NAMES: Record<TemplateKind, string> = {
  'marks-summary': 'BTF_Marks_Summary_Template.docx',
  certificate: 'BTF_Student_Certificate_Template.docx',
  'mentor-certificate': 'BTF_Mentor_Certificate_Template.docx'
}

// GET /api/v1/grading/certificates-release/ — the certificates gate, separate
// from marks so certificates can go out on a different day.
export function fetchCertificatesRelease(): Promise<ReleaseStatus> {
  return requestJson<ReleaseStatus>('/api/v1/grading/certificates-release/')
}

// POST /api/v1/grading/certificates-release/ — flip certificates on/off.
export function toggleCertificatesRelease(release: boolean): Promise<ReleaseStatus> {
  return requestJson<ReleaseStatus>('/api/v1/grading/certificates-release/', {
    method: 'POST',
    body: JSON.stringify({ release })
  })
}

// POST — change only the finalist exclusion; the release stamp stays put.
export function setCertificatesFinalistExclusion(exclude: boolean): Promise<ReleaseStatus> {
  return requestJson<ReleaseStatus>('/api/v1/grading/certificates-release/', {
    method: 'POST',
    body: JSON.stringify({ exclude_finalists: exclude })
  })
}

// Per-team extra time on top of the global deadline.
export interface GroupExtension {
  /** Row id — group_id is no longer unique since revoked rows are kept. */
  id: number
  group_id: number
  group_name: string
  extended_until: string
  /** Time past the normal deadline, grace aside, e.g. "1d 18h"; null
   *  without a deadline or once the deadline has moved past it. */
  added: string | null
  /** Quiet extra hours the server accepts past the granted time. */
  grace_hours: number
  reason: string
  granted_at: string
  granted_by: string | null
  /** Soft revoke: set when an admin revoked this extension; row stays listed. */
  revoked_at: string | null
  revoked_by: string | null
}

// GET /api/v1/grading/deadline/extensions/ — every granted extension.
export function fetchGroupExtensions(): Promise<{ extensions: GroupExtension[] }> {
  return requestJson<{ extensions: GroupExtension[] }>('/api/v1/grading/deadline/extensions/')
}

// POST — grant or update one team's extension (one per team).
export function saveGroupExtension(
  groupId: number,
  extendedUntil: string,
  graceHours: number,
  reason: string
): Promise<{ extension: GroupExtension }> {
  return requestJson<{ extension: GroupExtension }>('/api/v1/grading/deadline/extensions/', {
    method: 'POST',
    body: JSON.stringify({
      group_id: groupId,
      extended_until: extendedUntil,
      grace_hours: graceHours,
      reason
    })
  })
}

// DELETE — revoke a team's extension (idempotent).
export function removeGroupExtension(groupId: number): Promise<void> {
  return requestJson<void>(`/api/v1/grading/deadline/extensions/${groupId}/`, {
    method: 'DELETE'
  })
}

// The active submission deadline; null means submissions are closed until set.
export interface SubmissionDeadline {
  closes_at: string
  /** Quiet extra hours the server accepts past the announced time. */
  grace_hours: number
  is_open: boolean
  /** Display name of the admin who set it; null for script-created rows. */
  set_by: string | null
  created_at: string
}

// GET /api/v1/grading/deadline/ — the deadline currently in force.
export function fetchSubmissionDeadline(): Promise<{ deadline: SubmissionDeadline | null }> {
  return requestJson<{ deadline: SubmissionDeadline | null }>('/api/v1/grading/deadline/')
}

/** The current challenge year, as the backend's current_cohort works it out:
 *  the deadline's year, or the calendar year while no deadline exists. */
export const challengeYear = (deadline: SubmissionDeadline | null) =>
  deadline ? new Date(deadline.closes_at).getFullYear() : new Date().getFullYear()

// POST /api/v1/grading/deadline/ — set a new deadline (newest active row wins).
export function saveSubmissionDeadline(
  closesAt: string,
  graceHours: number
): Promise<{ deadline: SubmissionDeadline | null }> {
  return requestJson<{ deadline: SubmissionDeadline | null }>('/api/v1/grading/deadline/', {
    method: 'POST',
    body: JSON.stringify({ closes_at: closesAt, grace_hours: graceHours })
  })
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
  overallComments?: { submission: number; component?: string; comment: string }[]
): Promise<Grade[]> {
  return requestJson<Grade[]>('/api/v1/grading/grades/bulk/', {
    method: 'POST',
    body: JSON.stringify(
      overallComments?.length ? { items, overall_comments: overallComments } : { items }
    )
  })
}

// PATCH /api/v1/grading/grades/{id}/ — inline edit for a single grade.
export function updateGrade(
  gradeId: number,
  patch: { mark?: string | null; comment?: string }
): Promise<Grade> {
  return requestJson<Grade>(`/api/v1/grading/grades/${gradeId}/`, {
    method: 'PATCH',
    body: JSON.stringify(patch)
  })
}

// GET /api/v1/grading/components/{code}/ — table payload for the
// per-component marking flow ("sit down and mark all posters").
export function fetchComponentRows(code: string, year?: number): Promise<ComponentListPayload> {
  const qs = year ? `?year=${year}` : ''
  return requestJson<ComponentListPayload>(`/api/v1/grading/components/${encodeURIComponent(code)}/${qs}`)
}

// Which placeholders the active docx template actually contains.
export interface TemplateScan {
  uploaded: boolean
  /** Placeholders present that the renderer knows how to fill. */
  present: string[]
  /** Placeholders present that would be left blank — usually typos. */
  unknown: string[]
}

// GET /api/v1/grading/settings/template-scan/{kind}/
export function fetchTemplateScan(kind: TemplateKind): Promise<TemplateScan> {
  return requestJson<TemplateScan>(`/api/v1/grading/settings/template-scan/${kind}/`)
}

// POST /api/v1/grading/settings/template-scan/{kind}/ — scan a picked file
// WITHOUT saving it, so the page can preview a selection before Save
// replaces the stored template. A file the renderer can't open 400s.
export function scanTemplateCandidate(
  kind: TemplateKind,
  file: File
): Promise<TemplateScan> {
  const fd = new FormData()
  fd.append('file', file)
  return requestJson<TemplateScan>(`/api/v1/grading/settings/template-scan/${kind}/`, {
    method: 'POST',
    body: fd
  })
}

// GET /api/v1/grading/settings/test-people/{kind}/ — who a template can be
// tested with: this year's students, or mentors for the mentor certificate.
export function fetchTemplateTestPeople(
  kind: TemplateKind
): Promise<{ options: TestEmailRecipient[] }> {
  return requestJson<{ options: TestEmailRecipient[] }>(
    `/api/v1/grading/settings/test-people/${kind}/`
  )
}

// GET /api/v1/grading/settings/test-render/{kind}/ — render the active docx
// template with synthetic data and save it, so admins can check placeholders.
// With `person` (from fetchTemplateTestPeople), that person's real document.
export async function downloadTemplateTestRender(
  kind: TemplateKind,
  person?: string
): Promise<void> {
  const qs = person ? `?person=${encodeURIComponent(person)}` : ''
  const { blob, filename } = await requestBlob(`/api/v1/grading/settings/test-render/${kind}/${qs}`)
  triggerBlobDownload(blob, filename ?? `test-${kind}.docx`)
}

// GET /api/v1/grading/settings/template/{kind}/ — the saved template file,
// always under the same name.
export async function downloadSavedTemplate(
  kind: TemplateKind
): Promise<void> {
  const { blob, filename } = await requestBlob(`/api/v1/grading/settings/template/${kind}/`)
  triggerBlobDownload(blob, filename ?? TEMPLATE_DOWNLOAD_NAMES[kind])
}

// POST /api/v1/grading/settings/test-render/{kind}/ — render a picked file
// with synthetic data while the saved template stays active. With `person`,
// that person's real details.
export async function downloadCandidateTestRender(
  kind: TemplateKind,
  file: File,
  person?: string
): Promise<void> {
  const fd = new FormData()
  fd.append('file', file)
  if (person) fd.append('person', person)
  const { blob, filename } = await requestBlob(
    `/api/v1/grading/settings/test-render/${kind}/`,
    { method: 'POST', body: fd }
  )
  triggerBlobDownload(blob, filename ?? `test-${kind}.docx`)
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

// GET /api/v1/grading/release/ — current release status (admin view).
export function fetchRelease(): Promise<ReleaseStatus> {
  return requestJson<ReleaseStatus>('/api/v1/grading/release/')
}

// POST /api/v1/grading/release/ — flip release on (or off with release=false).
export function toggleRelease(release: boolean): Promise<ReleaseStatus> {
  return requestJson<ReleaseStatus>('/api/v1/grading/release/', {
    method: 'POST',
    body: JSON.stringify({ release })
  })
}

// GET /api/v1/grading/settings/ — director names and positions + template metadata.
export function fetchGradingSettings(): Promise<GradingSettingsDetail> {
  return requestJson<GradingSettingsDetail>('/api/v1/grading/settings/')
}

// PATCH /api/v1/grading/settings/ — JSON for text-only edits, FormData when
// any file (signature / docx template) is being uploaded.
export function updateGradingSettings(
  patch:
    | Partial<
        Pick<
          GradingSettingsDetail,
          | 'director_1_name'
          | 'director_1_position'
          | 'director_2_name'
          | 'director_2_position'
          | 'component_weights'
        >
      >
    | FormData
): Promise<GradingSettingsDetail> {
  const isForm = patch instanceof FormData
  return requestJson<GradingSettingsDetail>('/api/v1/grading/settings/', {
    method: 'PATCH',
    body: isForm ? patch : JSON.stringify(patch)
  })
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
  /** No project title is kept yet, so this is always "". */
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

// POST /api/v1/grading/finalists/notify/ — email finalist teams not yet
// notified. Pass groupIds to restrict the send to those teams; omitted means
// all. Safe to repeat: already-notified flags are skipped server-side.
export function notifyFinalists(groupIds?: number[]): Promise<{ sent: number; pending: number }> {
  return requestJson<{ sent: number; pending: number }>('/api/v1/grading/finalists/notify/', {
    method: 'POST',
    body: JSON.stringify(groupIds?.length ? { group_ids: groupIds } : {})
  })
}

/** What the finalist email tells teams about the Symposium (dates as YYYY-MM-DD). */
export interface FinalistEmailFields {
  symposium_date: string | null
  confirm_by: string | null
  slides_due: string | null
  registration_url: string
}

export interface FinalistEmailDetails extends FinalistEmailFields {
  /** Every detail is set, so the email can go out. */
  complete: boolean
  /** Sydney's today (YYYY-MM-DD): the earliest any of the dates may be. */
  today: string
  /** Saved date fields already before today, which block sending. */
  dates_in_past: string[]
}

// GET /api/v1/grading/finalists/email/ — the finalist email's dates and link.
export function fetchFinalistEmailDetails(): Promise<FinalistEmailDetails> {
  return requestJson<FinalistEmailDetails>('/api/v1/grading/finalists/email/')
}

// PATCH /api/v1/grading/finalists/email/ — save them.
export function updateFinalistEmailDetails(
  fields: Partial<FinalistEmailFields>
): Promise<FinalistEmailDetails> {
  return requestJson<FinalistEmailDetails>('/api/v1/grading/finalists/email/', {
    method: 'PATCH',
    body: JSON.stringify(fields)
  })
}

export interface FinalistEmailPreview {
  subject: string
  /** The team the preview is addressed to. */
  group_name: string
  html: string
}

// POST /api/v1/grading/finalists/email/preview/ — the email as a finalist
// would get it, for the given (possibly unsaved) details. Sends nothing.
// `recipient` is a person picked in Send Test Email: their team's email.
export function previewFinalistEmail(
  fields: Partial<FinalistEmailFields>,
  recipient = ''
): Promise<FinalistEmailPreview> {
  return requestJson<FinalistEmailPreview>('/api/v1/grading/finalists/email/preview/', {
    method: 'POST',
    body: JSON.stringify({ ...fields, ...(recipient ? { recipient } : {}) })
  })
}

// ---------------------------------------------------------------------------
// Results emails (Release Results tab)

export interface ResultsEmailFields {
  survey_url: string
  survey_closes: string | null
}

export interface EmailedCount {
  total: number
  emailed: number
}

export interface ResultsEmailDetails extends ResultsEmailFields {
  /** Both survey details are set. */
  complete: boolean
  /** Sydney's today (YYYY-MM-DD): the earliest the close date may be. */
  today: string
  /** The saved close date is already before today, which blocks sending. */
  closes_in_past: boolean
  year: number
  marks_released: boolean
  certificates_released: boolean
  /** Whether each email is switched on in System Emails. */
  emails_on: Record<ResultsAudience, boolean>
  /** Whether the Document Setup templates each email's files need are uploaded. */
  templates_ready: Record<ResultsAudience, boolean>
  /** Groups due the group email, which goes to their students and mentors. */
  groups: EmailedCount
  supervisors: EmailedCount
}

export type ResultsAudience = 'groups' | 'supervisors'

export interface ResultsEmailBatch {
  /** People emailed in this batch. */
  emailed: number
  /** Groups or supervisors not emailed in full. */
  failed: number
  /** The last group or supervisor tried; pass it back for the next batch. */
  cursor: number
  /** Everyone due has been tried in this run. */
  done: boolean
  groups: EmailedCount
  supervisors: EmailedCount
}

export interface ResultsEmailPreview {
  subject: string
  /** The team or supervisor the preview is addressed to. */
  to: string
  html: string
  /** The names of the files the email carries. */
  attachments: string[]
}

// GET /api/v1/grading/results-email/ — survey details, releases and counts.
export function fetchResultsEmailDetails(): Promise<ResultsEmailDetails> {
  return requestJson<ResultsEmailDetails>('/api/v1/grading/results-email/')
}

// PATCH /api/v1/grading/results-email/ — save the survey details.
export function updateResultsEmailDetails(
  fields: Partial<ResultsEmailFields>
): Promise<ResultsEmailDetails> {
  return requestJson<ResultsEmailDetails>('/api/v1/grading/results-email/', {
    method: 'PATCH',
    body: JSON.stringify(fields)
  })
}

// POST /api/v1/grading/results-email/preview/ — one email as it would go out,
// for the given (possibly unsaved) details. Sends nothing. `recipient` is a
// person picked in Send Test Email: their email and files.
export function previewResultsEmail(
  audience: ResultsAudience,
  fields: Partial<ResultsEmailFields>,
  recipient = ''
): Promise<ResultsEmailPreview> {
  return requestJson<ResultsEmailPreview>('/api/v1/grading/results-email/preview/', {
    method: 'POST',
    body: JSON.stringify({ audience, ...fields, ...(recipient ? { recipient } : {}) })
  })
}

// GET /api/v1/grading/results-email/sample-sheet/ — the marks spreadsheet the
// supervisor email carries, filled with made-up groups.
export async function downloadResultsSampleSheet(): Promise<void> {
  const { blob, filename } = await requestBlob('/api/v1/grading/results-email/sample-sheet/')
  triggerBlobDownload(blob, filename ?? 'BTF_Student_Marks_Sample.xlsx')
}

// GET /api/v1/grading/results-email/supervisor-sheet/{id}/ — the real marks
// spreadsheet that supervisor's email would carry, to check before sending.
export async function downloadSupervisorMarksSheet(supervisorId: string): Promise<void> {
  const { blob, filename } = await requestBlob(`/api/v1/grading/results-email/supervisor-sheet/${supervisorId}/`)
  triggerBlobDownload(blob, filename ?? 'BTF_Student_Marks.xlsx')
}

// POST /api/v1/grading/results-email/send/ — email the next few groups, or
// supervisors; call again with the returned cursor until done.
export function sendResultsEmailBatch(
  audience: ResultsAudience,
  cursor: number | null
): Promise<ResultsEmailBatch> {
  return requestJson<ResultsEmailBatch>('/api/v1/grading/results-email/send/', {
    method: 'POST',
    body: JSON.stringify({ audience, cursor })
  })
}

// GET /api/v1/grading/finalists/ — the current finalist set.
export function fetchFinalists(): Promise<FinalistListResponse> {
  return requestJson<FinalistListResponse>('/api/v1/grading/finalists/')
}

/** The Symposium emails on the Email Nonfinalist tab: to teams that submitted
 *  but weren't picked, and to teams that didn't submit. */
export type SymposiumEmail = 'nonfinalists' | 'nonsubmissions'

/** This year's teams due the email, and how many have it. */
export interface SymposiumEmailStatus {
  teams: EmailedCount
  /** Their students with an address; mentors and supervisors get it too. */
  students: EmailedCount
  /** Why sending is refused (details missing on Notify Finalists, switched
   *  off), or "" when it may go ahead. */
  blocked: string
}

export interface SymposiumEmailPreview {
  subject: string
  /** The team the preview is addressed to. */
  to: string
  html: string
}

export interface SymposiumEmailBatch {
  /** People emailed in this batch. */
  emailed: number
  /** Teams in this batch not emailed in full; left for the next press. */
  failed: number
  cursor: number
  done: boolean
  teams: EmailedCount
  students: EmailedCount
}

// GET /api/v1/grading/{nonfinalists|nonsubmissions}/ — who the email is for.
export function fetchSymposiumEmail(email: SymposiumEmail): Promise<SymposiumEmailStatus> {
  return requestJson<SymposiumEmailStatus>(`/api/v1/grading/${email}/`)
}

// POST /api/v1/grading/{email}/preview/ — the email as `recipient`'s team (a
// person picked in Send Test Email) would get it, else the first team due.
// Nothing is sent.
export function previewSymposiumEmail(
  email: SymposiumEmail,
  recipient = ''
): Promise<SymposiumEmailPreview> {
  return requestJson<SymposiumEmailPreview>(`/api/v1/grading/${email}/preview/`, {
    method: 'POST',
    body: JSON.stringify(recipient ? { recipient } : {})
  })
}

// POST /api/v1/grading/{email}/send/ — email the next few teams; call again
// with the returned cursor until done.
export function sendSymposiumEmailBatch(
  email: SymposiumEmail,
  cursor: number | null
): Promise<SymposiumEmailBatch> {
  return requestJson<SymposiumEmailBatch>(`/api/v1/grading/${email}/send/`, {
    method: 'POST',
    body: JSON.stringify({ cursor })
  })
}

/** The emails that have Send Test Email beside their preview. */
export type TestEmailKind = SymposiumEmail | 'finalist' | 'results-groups' | 'results-supervisors'

/** Someone the email can be tested as, e.g. "(BTF07) Amy Chen". */
export interface TestEmailRecipient {
  value: string
  label: string
}

// GET /api/v1/grading/test-email/{kind}/ — everyone the email can go to.
export function fetchTestEmailRecipients(kind: TestEmailKind): Promise<{ recipients: TestEmailRecipient[] }> {
  return requestJson<{ recipients: TestEmailRecipient[] }>(`/api/v1/grading/test-email/${kind}/`)
}

// POST /api/v1/grading/test-email/{kind}/ — send the email, exactly as
// `recipient` would get it, to `to`. `fields` are the page's unsaved details,
// as its preview uses them. Nothing is recorded as sent.
export function sendTestEmail(
  kind: TestEmailKind,
  recipient: string,
  to: string,
  fields: object = {}
): Promise<{ sent_to: string }> {
  return requestJson<{ sent_to: string }>(`/api/v1/grading/test-email/${kind}/`, {
    method: 'POST',
    body: JSON.stringify({ ...fields, recipient, to })
  })
}

// POST /api/v1/grading/groups/{id}/finalist/ — idempotent upsert; optionally
// fires the notification email (once the email details are set).
export function addFinalist(groupId: number, notify = false): Promise<void> {
  return requestJson<void>(`/api/v1/grading/groups/${groupId}/finalist/`, {
    method: 'POST',
    body: JSON.stringify({ notify })
  })
}

// DELETE /api/v1/grading/groups/{id}/finalist/ — idempotent removal.
export function removeFinalist(groupId: number): Promise<void> {
  return requestJson<void>(`/api/v1/grading/groups/${groupId}/finalist/`, {
    method: 'DELETE'
  })
}
