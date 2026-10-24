// Test data and the fake live connection shared by groupSubmissionPage.spec.ts
// and groupSubmissionPage.timers.spec.ts.
import type { SubmissionDetail, SubmissionRecord } from '@/utils/submissionsAPI'

export const QUESTIONS = [
  {
    key: 'solution_purpose',
    prompt: 'What does your solution do?',
    help_text: '',
    is_required: true,
    max_words: 150,
  },
  {
    key: 'inspiration',
    prompt: 'What was the inspiration?',
    help_text: '',
    is_required: true,
    max_words: 150,
  },
]

export const POSTER = { storage_key: 'x/p.pdf', name: 'poster.pdf', mime: 'application/pdf', size: 2048 }
export const ANSWERED = { solution_purpose: 'An answer.', inspiration: 'Another answer.' }

export const TITLE = 'Coral Rescue Kit'
export const CONFIRMED_CHECKLIST = { supervisor_email: true, btf_logo: true, school_logo: true, team_code: true, page_size: true }

const emptyRecord = (): SubmissionRecord => ({
  project_title: '',
  answers: {},
  poster: null,
  poster_checks: null,
  report: null,
  prototype: null,
  prototype_url: '',
  submitted_project_title: '',
  submitted_answers: null,
  submitted_poster: null,
  submitted_poster_checks: null,
  submitted_report: null,
  submitted_prototype: null,
  submitted_prototype_url: '',
  submitted_at: null,
  submitted_by_name: '',
  reopened_at: null,
  stage: 'not_started',
  is_submitted: false,
  is_locked: false,
  is_late: false,
  auto_submitted: false,
  poster_checklist: {},
  updated_at: new Date().toISOString(),
})

export const buildDetail = (
  overrides: { submission?: Partial<SubmissionRecord> | null; isOpen?: boolean } = {},
): SubmissionDetail => ({
  group: { id: 1, name: 'BTF1' },
  deadline: {
    closes_at: new Date(Date.now() + 7 * 86_400_000).toISOString(),
    is_extended: false,
    is_open: overrides.isOpen ?? true,
  },
  questions: QUESTIONS,
  instructions: {
    questions: { heading: 'Short Answer Questions', body: 'Max 150 words each.' },
    poster: { heading: 'Poster', body: 'Upload a PDF.' },
    extras: { heading: 'Additional Materials', body: 'Optional.' },
  },
  max_file_sizes: { poster: 10_485_760, report: 5_242_880, prototype: 26_214_400 },
  submission:
    overrides.submission === null ? null : { ...emptyRecord(), ...(overrides.submission ?? {}) },
})

/** A locked entry: submitted, not reopened. */
export const submittedDetail = () =>
  buildDetail({
    submission: {
      answers: ANSWERED,
      poster: POSTER,
      submitted_answers: ANSWERED,
      submitted_poster: POSTER,
      submitted_at: new Date().toISOString(),
      stage: 'submitted',
      is_submitted: true,
      is_locked: true,
    },
  })

/** Submitted, then reopened: editable again, with the snapshot still standing. */
export const reopenedDetail = () => {
  const now = Date.now()
  return buildDetail({
    submission: {
      answers: ANSWERED,
      poster: POSTER,
      submitted_answers: ANSWERED,
      submitted_poster: POSTER,
      submitted_at: new Date(now - 60_000).toISOString(),
      reopened_at: new Date(now).toISOString(),
      stage: 'revising',
      is_submitted: true,
      is_locked: false,
    },
  })
}

const stub = { template: '<div />' }

export const ROUTES = [
  { path: '/groups/:id/submission', name: 'group-submission', component: stub },
  { path: '/groups/:id', name: 'group-detail', component: stub },
  { path: '/resources/:id', name: 'resource-detail', component: stub },
]

/** Stands in for the live connection, so no test reaches a real server. */
export class FakeSocket {
  static OPEN = 1
  static instances: FakeSocket[] = []
  readyState = 0
  sent: unknown[] = []
  onopen: (() => void) | null = null
  onmessage: ((event: { data: string }) => void) | null = null
  onclose: ((event: { code: number }) => void) | null = null

  constructor(public url: string) {
    FakeSocket.instances.push(this)
  }

  send(data: string) {
    this.sent.push(JSON.parse(data))
  }

  close(code = 1000) {
    this.readyState = 3
    this.onclose?.({ code })
  }
}
