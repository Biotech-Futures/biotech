// The Management section's API: the run-the-competition levers (deadlines,
// releases, Document Setup, the finalist, results and Symposium emails, and
// the Finalist Presentation tab). Everything here is under /api/v1/management/.
import { requestBlob, requestJson, triggerBlobDownload, type ComponentBlock } from './gradingAPI'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export interface EmailedCount {
  total: number
  emailed: number
}

/** This year's teams due the email, and how many have it. */
/** People due an email and emailed (at least once), and how many emails
 *  that is: someone on several teams gets one per team. */
export interface PeopleEmailedCount extends EmailedCount {
  times: EmailedCount
}

// ---------------------------------------------------------------------------
// The Results section on a group's page

/** The marks summary's details and total, as its document has them. */
export interface GroupResultsSummary {
  project_title: string
  /** "Project Category", or "Project Categories" for more than one. */
  project_category_heading: string
  project_category: string
  solution_category: string
  /** SAQ and Poster marks together, e.g. "40.5". */
  combined_total: string
  /** The most they could be, e.g. "70". */
  combined_max: string
}

/** A student's or mentor's certificate in the group. */
export interface GroupCertificate {
  user_id: number
  name: string
  kind: 'student' | 'mentor'
  file_name: string
}

export interface GroupResults {
  marks_released: boolean
  certificates_released: boolean
  /** A finalist team's certificates, while certificates exclude finalists. */
  certificates_withheld: boolean
  /** Results are only for a group that made a submission. */
  has_submission: boolean
  year: number
  /** Once marks are released: SAQ and Poster marks and comments. */
  components: ComponentBlock[]
  /** Once marks are released: as the marks summary fills them. */
  summary: GroupResultsSummary | null
  /** The marks summary's download name; "" until marks are released. */
  summary_file_name: string
  /** Once certificates are released: every student's, then mentor's. */
  certificates: GroupCertificate[]
}

// GET /api/v1/management/groups/{id}/results/ — what's out for the group.
export function fetchGroupResults(groupId: number | string): Promise<GroupResults> {
  return requestJson<GroupResults>(`/api/v1/management/groups/${groupId}/results/`)
}

// GET /api/v1/management/groups/{id}/results/summary/ — the marks summary docx.
export async function downloadGroupSummary(groupId: number | string, fallbackName: string): Promise<void> {
  const { blob, filename } = await requestBlob(`/api/v1/management/groups/${groupId}/results/summary/`)
  triggerBlobDownload(blob, filename ?? fallbackName)
}

// GET /api/v1/management/groups/{id}/results/certificate/{userId}/ — one certificate docx.
export async function downloadGroupCertificate(
  groupId: number | string,
  certificate: GroupCertificate
): Promise<void> {
  const { blob, filename } = await requestBlob(
    `/api/v1/management/groups/${groupId}/results/certificate/${certificate.user_id}/`
  )
  triggerBlobDownload(blob, filename ?? certificate.file_name)
}

// ---------------------------------------------------------------------------
// The submission deadline and per-team extensions

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

// GET /api/v1/management/deadline/extensions/ — every granted extension.
export function fetchGroupExtensions(): Promise<{ extensions: GroupExtension[] }> {
  return requestJson<{ extensions: GroupExtension[] }>('/api/v1/management/deadline/extensions/')
}

// POST — grant or update one team's extension (one per team).
export function saveGroupExtension(
  groupId: number,
  extendedUntil: string,
  graceHours: number,
  reason: string
): Promise<{ extension: GroupExtension }> {
  return requestJson<{ extension: GroupExtension }>('/api/v1/management/deadline/extensions/', {
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
  return requestJson<void>(`/api/v1/management/deadline/extensions/${groupId}/`, {
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

// GET /api/v1/management/deadline/ — the deadline currently in force.
export function fetchSubmissionDeadline(): Promise<{ deadline: SubmissionDeadline | null }> {
  return requestJson<{ deadline: SubmissionDeadline | null }>('/api/v1/management/deadline/')
}

/** The current challenge year, as the backend's current_cohort works it out:
 *  the deadline's year, or the calendar year while no deadline exists. */
export const challengeYear = (deadline: SubmissionDeadline | null) =>
  deadline ? new Date(deadline.closes_at).getFullYear() : new Date().getFullYear()

// POST /api/v1/management/deadline/ — set a new deadline (newest active row wins).
export function saveSubmissionDeadline(
  closesAt: string,
  graceHours: number
): Promise<{ deadline: SubmissionDeadline | null }> {
  return requestJson<{ deadline: SubmissionDeadline | null }>('/api/v1/management/deadline/', {
    method: 'POST',
    body: JSON.stringify({ closes_at: closesAt, grace_hours: graceHours })
  })
}

// ---------------------------------------------------------------------------
// Releasing marks and certificates

// GET /api/v1/management/release/ — surfaces released_at so the UI can decide
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

// GET /api/v1/management/certificates-release/ — the certificates gate, separate
// from marks so certificates can go out on a different day.
export function fetchCertificatesRelease(): Promise<ReleaseStatus> {
  return requestJson<ReleaseStatus>('/api/v1/management/certificates-release/')
}

// POST /api/v1/management/certificates-release/ — flip certificates on/off.
export function toggleCertificatesRelease(release: boolean): Promise<ReleaseStatus> {
  return requestJson<ReleaseStatus>('/api/v1/management/certificates-release/', {
    method: 'POST',
    body: JSON.stringify({ release })
  })
}

// POST — change only the finalist exclusion; the release stamp stays put.
export function setCertificatesFinalistExclusion(exclude: boolean): Promise<ReleaseStatus> {
  return requestJson<ReleaseStatus>('/api/v1/management/certificates-release/', {
    method: 'POST',
    body: JSON.stringify({ exclude_finalists: exclude })
  })
}

// GET /api/v1/management/release/ — current release status (admin view).
export function fetchRelease(): Promise<ReleaseStatus> {
  return requestJson<ReleaseStatus>('/api/v1/management/release/')
}

// POST /api/v1/management/release/ — flip release on (or off with release=false).
export function toggleRelease(release: boolean): Promise<ReleaseStatus> {
  return requestJson<ReleaseStatus>('/api/v1/management/release/', {
    method: 'POST',
    body: JSON.stringify({ release })
  })
}

// ---------------------------------------------------------------------------
// Document Setup: director details and the docx templates

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

// GET /api/v1/management/settings/ — director names and positions + template metadata.
export function fetchGradingSettings(): Promise<GradingSettingsDetail> {
  return requestJson<GradingSettingsDetail>('/api/v1/management/settings/')
}

// PATCH /api/v1/management/settings/ — JSON for text-only edits, FormData when
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
  return requestJson<GradingSettingsDetail>('/api/v1/management/settings/', {
    method: 'PATCH',
    body: isForm ? patch : JSON.stringify(patch)
  })
}

// Which placeholders the active docx template actually contains.
export interface TemplateScan {
  uploaded: boolean
  /** Placeholders present that the renderer knows how to fill. */
  present: string[]
  /** Placeholders present that would be left blank — usually typos. */
  unknown: string[]
}

// GET /api/v1/management/settings/template-scan/{kind}/
export function fetchTemplateScan(kind: TemplateKind): Promise<TemplateScan> {
  return requestJson<TemplateScan>(`/api/v1/management/settings/template-scan/${kind}/`)
}

// POST /api/v1/management/settings/template-scan/{kind}/ — scan a picked file
// WITHOUT saving it, so the page can preview a selection before Save
// replaces the stored template. A file the renderer can't open 400s.
export function scanTemplateCandidate(
  kind: TemplateKind,
  file: File
): Promise<TemplateScan> {
  const fd = new FormData()
  fd.append('file', file)
  return requestJson<TemplateScan>(`/api/v1/management/settings/template-scan/${kind}/`, {
    method: 'POST',
    body: fd
  })
}

// GET /api/v1/management/settings/test-people/{kind}/ — who a template can be
// tested with: this year's students, or mentors for the mentor certificate.
export function fetchTemplateTestPeople(
  kind: TemplateKind
): Promise<{ options: TestEmailRecipient[] }> {
  return requestJson<{ options: TestEmailRecipient[] }>(
    `/api/v1/management/settings/test-people/${kind}/`
  )
}

// GET /api/v1/management/settings/test-render/{kind}/ — render the active docx
// template with synthetic data and save it, so admins can check placeholders.
// With `person` (from fetchTemplateTestPeople), that person's real document.
export async function downloadTemplateTestRender(
  kind: TemplateKind,
  person?: string
): Promise<void> {
  const qs = person ? `?person=${encodeURIComponent(person)}` : ''
  const { blob, filename } = await requestBlob(`/api/v1/management/settings/test-render/${kind}/${qs}`)
  triggerBlobDownload(blob, filename ?? `test-${kind}.docx`)
}

// GET /api/v1/management/settings/template/{kind}/ — the saved template file,
// always under the same name.
export async function downloadSavedTemplate(
  kind: TemplateKind
): Promise<void> {
  const { blob, filename } = await requestBlob(`/api/v1/management/settings/template/${kind}/`)
  triggerBlobDownload(blob, filename ?? TEMPLATE_DOWNLOAD_NAMES[kind])
}

// POST /api/v1/management/settings/test-render/{kind}/ — render a picked file
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
    `/api/v1/management/settings/test-render/${kind}/`,
    { method: 'POST', body: fd }
  )
  triggerBlobDownload(blob, filename ?? `test-${kind}.docx`)
}

// ---------------------------------------------------------------------------
// Bulk email runs, and the finalist email on Notify Finalists

// POST /api/v1/management/finalists/notify/ — email finalist teams not yet
// notified. Pass groupIds to restrict the send to those teams; omitted means
// all. Safe to repeat: already-notified flags are skipped server-side.
/** A bulk email's run on the server: the one going now, or the last. */
export interface EmailRun {
  /** People due the email when it started, and emailed so far. */
  due: number
  emailed: number
  /** Teams or supervisors not emailed in full; the next run tries them again. */
  failed: number
  /** Why it stopped short, e.g. the mail server couldn't be reached, or "". */
  error: string
  /** Who it couldn't reach, e.g. "(BTF07) Amy Chen", and why, e.g.
   *  "address refused" ("" for a run from before reasons were kept). */
  missed: { who: string; reason: string }[]
  started_at: string
  finished_at: string | null
}

export interface EmailRunState {
  /** A run is sending the email now. */
  sending: boolean
  /** The address emails go out from, where undeliverable ones come back to. */
  sent_from?: string
  run: EmailRun | null
}

/** The run started, and finalist teams still to notify. */
export interface FinalistNotifyResult extends EmailRunState {
  pending: number
}

// Starts a run on the server that emails them, so the page can be closed.
// Or pass which: 'new' for the teams no send has tried yet, 'missed' for
// only the people earlier sends missed.
export function notifyFinalists(
  groupIds?: number[],
  which?: FinalistSendWhich
): Promise<FinalistNotifyResult> {
  return requestJson<FinalistNotifyResult>('/api/v1/management/finalists/notify/', {
    method: 'POST',
    body: JSON.stringify(which ? { which } : groupIds?.length ? { group_ids: groupIds } : {})
  })
}

/** A send limited to the teams no send has tried yet, or to the people
 *  earlier sends missed. */
export type FinalistSendWhich = 'new' | 'missed'

/** What the finalist email tells teams about the Symposium (dates as YYYY-MM-DD). */
export interface FinalistEmailFields {
  symposium_date: string | null
  confirm_by: string | null
  slides_due: string | null
  registration_url: string
}

export interface FinalistEmailDetails extends FinalistEmailFields, EmailRunState {
  /** Every detail is set, so the email can go out. */
  complete: boolean
  /** Sydney's today (YYYY-MM-DD): the earliest any of the dates may be. */
  today: string
  /** Saved date fields already before today, which block sending. */
  dates_in_past: string[]
  /** Why sending waits for submissions (and extensions) to close, or "". */
  submissions_open: string
  /** Everyone the finalist email goes to, by role; a notified team's
   *  members count as emailed. */
  counts: Record<'students' | 'mentors' | 'supervisors', PeopleEmailedCount>
  /** The teams, and people on them, each limited send would email. */
  waiting: Record<FinalistSendWhich, { teams: number; people: number }>
}

// GET /api/v1/management/finalists/email/ — the finalist email's dates and link.
export function fetchFinalistEmailDetails(): Promise<FinalistEmailDetails> {
  return requestJson<FinalistEmailDetails>('/api/v1/management/finalists/email/')
}

// PATCH /api/v1/management/finalists/email/ — save them.
export function updateFinalistEmailDetails(
  fields: Partial<FinalistEmailFields>
): Promise<FinalistEmailDetails> {
  return requestJson<FinalistEmailDetails>('/api/v1/management/finalists/email/', {
    method: 'PATCH',
    body: JSON.stringify(fields)
  })
}

// ---------------------------------------------------------------------------
// Finalist Presentation tab: the times finalists can present at the Symposium

/** One time on the Symposium day, as "HH:MM" (24 hour). */
export interface PresentationSlot {
  id: number
  starts_at: string
  ends_at: string
}

export interface PresentationSlots {
  year: number
  /** The day they're on, set on Notify Finalists; null until it is. */
  symposium_date: string | null
  /** Earliest first. */
  slots: PresentationSlot[]
}

export type PresentationSlotFields = Pick<PresentationSlot, 'starts_at' | 'ends_at'>

const PRESENTATION_SLOTS = '/api/v1/management/finalists/presentation-slots/'

// GET — this year's times. Every change below answers with the whole list.
export function fetchPresentationSlots(): Promise<PresentationSlots> {
  return requestJson<PresentationSlots>(PRESENTATION_SLOTS)
}

// POST — add a time.
export function addPresentationSlot(fields: PresentationSlotFields): Promise<PresentationSlots> {
  return requestJson<PresentationSlots>(PRESENTATION_SLOTS, {
    method: 'POST',
    body: JSON.stringify(fields)
  })
}

// PATCH {id}/ — change a time.
export function updatePresentationSlot(
  id: number,
  fields: Partial<PresentationSlotFields>
): Promise<PresentationSlots> {
  return requestJson<PresentationSlots>(`${PRESENTATION_SLOTS}${id}/`, {
    method: 'PATCH',
    body: JSON.stringify(fields)
  })
}

// DELETE {id}/ — remove a time.
export function deletePresentationSlot(id: number): Promise<PresentationSlots> {
  return requestJson<PresentationSlots>(`${PRESENTATION_SLOTS}${id}/`, { method: 'DELETE' })
}

/** A finalist team and its answer: the times the whole team can make. */
export interface PresentationResponseTeam {
  group_id: number
  group_name: string
  /** The time the team has been given; null until it is. */
  allocated_slot_id: number | null
  /** The times the team can make; empty until it answers. */
  slot_ids: number[]
  /** When it submitted them, and who; null until it has. */
  answered_at: string | null
  answered_by: string | null
}

// PUT /api/v1/management/finalists/presentation-allocation/{group_id}/ — give a
// finalist team a time, or take it away with null.
export function allocatePresentationSlot(
  groupId: number,
  slotId: number | null
): Promise<{ group_id: number; slot_id: number | null }> {
  return requestJson<{ group_id: number; slot_id: number | null }>(
    `/api/v1/management/finalists/presentation-allocation/${groupId}/`,
    { method: 'PUT', body: JSON.stringify({ slot_id: slotId }) }
  )
}

/** A finalist team's presentation slides, once handed in. */
export interface PresentationSlidesTeam {
  group_id: number
  group_name: string
  submitted: boolean
  file_name: string
  /** Who handed them in; null when not yet, or their account is gone. */
  submitted_by: string | null
  submitted_at: string | null
}

export interface PresentationSlides {
  /** Set on Notify Finalists; null until it is. */
  slides_due: string | null
  teams: PresentationSlidesTeam[]
}

// GET /api/v1/management/finalists/presentation-slides/ — this year's finalist
// teams and the slides each has handed in, the latest first; teams still to
// hand theirs in follow, by number.
export function fetchPresentationSlides(): Promise<PresentationSlides> {
  return requestJson<PresentationSlides>('/api/v1/management/finalists/presentation-slides/')
}

// GET /api/v1/management/finalists/presentation-slides/{group_id}/file/ — a
// team's slides, for a link: a PDF opens in the browser, anything else downloads.
export function presentationSlidesUrl(groupId: number): string {
  return `${API_BASE_URL}/api/v1/management/finalists/presentation-slides/${groupId}/file/`
}

// GET /api/v1/management/finalists/presentation-responses/ — this year's
// finalist teams by number, each student in them, and what they answered.
export function fetchPresentationResponses(): Promise<{ teams: PresentationResponseTeam[] }> {
  return requestJson<{ teams: PresentationResponseTeam[] }>(
    '/api/v1/management/finalists/presentation-responses/'
  )
}

export interface FinalistEmailPreview {
  subject: string
  /** The team the preview is addressed to. */
  group_name: string
  html: string
}

// POST /api/v1/management/finalists/email/preview/ — the email as a finalist
// would get it, for the given (possibly unsaved) details. Sends nothing.
// `recipient` is a person picked in Send Test Email: their team's email.
export function previewFinalistEmail(
  fields: Partial<FinalistEmailFields>,
  recipient = ''
): Promise<FinalistEmailPreview> {
  return requestJson<FinalistEmailPreview>('/api/v1/management/finalists/email/preview/', {
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
  /** Why sending waits for submissions (and extensions) to close, or "". */
  submissions_open: string
  /** Each email's run: whether it's sending now, and its progress. */
  runs: Record<ResultsAudience, EmailRunState>
  /** Groups due the group email, which goes to their students and mentors. */
  groups: EmailedCount
  supervisors: EmailedCount
}

export type ResultsAudience = 'groups' | 'supervisors'

export interface ResultsEmailPreview {
  subject: string
  /** The team or supervisor the preview is addressed to. */
  to: string
  html: string
  /** The names of the files the email carries. */
  attachments: string[]
}

// GET /api/v1/management/results-email/ — survey details, releases and counts.
export function fetchResultsEmailDetails(): Promise<ResultsEmailDetails> {
  return requestJson<ResultsEmailDetails>('/api/v1/management/results-email/')
}

// PATCH /api/v1/management/results-email/ — save the survey details.
export function updateResultsEmailDetails(
  fields: Partial<ResultsEmailFields>
): Promise<ResultsEmailDetails> {
  return requestJson<ResultsEmailDetails>('/api/v1/management/results-email/', {
    method: 'PATCH',
    body: JSON.stringify(fields)
  })
}

// POST /api/v1/management/results-email/preview/ — one email as it would go out,
// for the given (possibly unsaved) details. Sends nothing. `recipient` is a
// person picked in Send Test Email: their email and files.
export function previewResultsEmail(
  audience: ResultsAudience,
  fields: Partial<ResultsEmailFields>,
  recipient = ''
): Promise<ResultsEmailPreview> {
  return requestJson<ResultsEmailPreview>('/api/v1/management/results-email/preview/', {
    method: 'POST',
    body: JSON.stringify({ audience, ...fields, ...(recipient ? { recipient } : {}) })
  })
}

// GET /api/v1/management/results-email/sample-sheet/ — the marks spreadsheet the
// supervisor email carries, filled with made-up groups.
export async function downloadResultsSampleSheet(): Promise<void> {
  const { blob, filename } = await requestBlob('/api/v1/management/results-email/sample-sheet/')
  triggerBlobDownload(blob, filename ?? 'BTF_Student_Marks_Sample.xlsx')
}

// GET /api/v1/management/results-email/supervisor-sheet/{id}/ — the real marks
// spreadsheet that supervisor's email would carry, to check before sending.
export async function downloadSupervisorMarksSheet(supervisorId: string): Promise<void> {
  const { blob, filename } = await requestBlob(`/api/v1/management/results-email/supervisor-sheet/${supervisorId}/`)
  triggerBlobDownload(blob, filename ?? 'BTF_Student_Marks.xlsx')
}

// POST /api/v1/management/results-email/send/ — email the next few groups, or
// supervisors; call again with the returned cursor until done.
// POST /api/v1/management/results-email/send/ — start a run on the server that
// emails ``audience``, so the page can be closed; the details, with its progress.
export function startResultsEmail(audience: ResultsAudience): Promise<ResultsEmailDetails> {
  return requestJson<ResultsEmailDetails>('/api/v1/management/results-email/send/', {
    method: 'POST',
    body: JSON.stringify({ audience })
  })
}

// ---------------------------------------------------------------------------
// The Symposium emails and Send Test Email

/** The Symposium emails on the Email Nonfinalist tab: to teams that submitted
 *  but weren't picked, and to teams that didn't submit. */
export type SymposiumEmail = 'nonfinalists' | 'nonsubmissions'

export interface SymposiumEmailStatus extends EmailRunState {
  teams: EmailedCount
  /** Their members with an address, by role; each gets the email. */
  students: PeopleEmailedCount
  mentors: PeopleEmailedCount
  supervisors: PeopleEmailedCount
  /** Why sending is refused (details missing on Notify Finalists, switched
   *  off, submissions still open), or "" when it may go ahead. */
  blocked: string
}

export interface SymposiumEmailPreview {
  subject: string
  /** The team the preview is addressed to. */
  to: string
  html: string
}

// GET /api/v1/management/{nonfinalists|nonsubmissions}/ — who the email is for.
export function fetchSymposiumEmail(email: SymposiumEmail): Promise<SymposiumEmailStatus> {
  return requestJson<SymposiumEmailStatus>(`/api/v1/management/${email}/`)
}

// POST /api/v1/management/{email}/preview/ — the email as `recipient`'s team (a
// person picked in Send Test Email) would get it, else the first team due.
// Nothing is sent.
export function previewSymposiumEmail(
  email: SymposiumEmail,
  recipient = ''
): Promise<SymposiumEmailPreview> {
  return requestJson<SymposiumEmailPreview>(`/api/v1/management/${email}/preview/`, {
    method: 'POST',
    body: JSON.stringify(recipient ? { recipient } : {})
  })
}

// POST /api/v1/management/{email}/send/ — email the next few teams; call again
// with the returned cursor until done.
// POST /api/v1/management/{nonfinalists|nonsubmissions}/send/ — start a run on
// the server that emails every team due it, so the page can be closed.
export function startSymposiumEmail(email: SymposiumEmail): Promise<SymposiumEmailStatus> {
  return requestJson<SymposiumEmailStatus>(`/api/v1/management/${email}/send/`, {
    method: 'POST',
    body: JSON.stringify({})
  })
}

/** The emails that have Send Test Email beside their preview. */
export type TestEmailKind = SymposiumEmail | 'finalist' | 'results-groups' | 'results-supervisors'

/** Someone the email can be tested as, e.g. "(BTF07) Amy Chen". */
export interface TestEmailRecipient {
  value: string
  label: string
}

// GET /api/v1/management/test-email/{kind}/ — everyone the email can go to.
export function fetchTestEmailRecipients(kind: TestEmailKind): Promise<{ recipients: TestEmailRecipient[] }> {
  return requestJson<{ recipients: TestEmailRecipient[] }>(`/api/v1/management/test-email/${kind}/`)
}

// POST /api/v1/management/test-email/{kind}/ — send the email, exactly as
// `recipient` would get it, to `to`. `fields` are the page's unsaved details,
// as its preview uses them. Nothing is recorded as sent.
export function sendTestEmail(
  kind: TestEmailKind,
  recipient: string,
  to: string,
  fields: object = {}
): Promise<{ sent_to: string; sent_from?: string }> {
  return requestJson<{ sent_to: string; sent_from?: string }>(`/api/v1/management/test-email/${kind}/`, {
    method: 'POST',
    body: JSON.stringify({ ...fields, recipient, to })
  })
}
