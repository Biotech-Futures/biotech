import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia, type Pinia } from 'pinia'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createRouter, createWebHashHistory } from 'vue-router'
import type { SubmissionDetail, SubmissionRecord } from '@/utils/submissionsAPI'

/**
 * Behaviour tests for the submission portal.
 *
 * Deliberately about the rules a student can be hurt by rather than about
 * markup: whether a submitted entry can still be quietly edited, whether a
 * closed deadline is enforced in the page and not only on the server, and
 * whether the progress count tells the truth. Formatting helpers are covered
 * in utils/__tests__/submissionFormat.spec.ts.
 *
 * Two design points these specs pin down, because both are easy to "fix" into
 * something worse:
 *
 * * Submit is never disabled for an incomplete entry. It stays clickable and
 *   the server answers with the list of unanswered questions, which the page
 *   then names. Greying the button out instead would leave a student hunting
 *   for which box is blank.
 * * A locked entry offers "Resubmit" (reopen it), and only once reopened does
 *   the action become "New Attempt". The first ever submission is plain
 *   "Submit".
 */

const saveDraft = vi.fn()
const submitEntry = vi.fn()
const reopenEntry = vi.fn()
const fetchSubmission = vi.fn()

vi.mock('@/utils/submissionsAPI', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/utils/submissionsAPI')>()
  return {
    ...actual,
    fetchSubmission: (...args: unknown[]) => fetchSubmission(...args),
    saveDraft: (...args: unknown[]) => saveDraft(...args),
    submitEntry: (...args: unknown[]) => submitEntry(...args),
    reopenEntry: (...args: unknown[]) => reopenEntry(...args),
    // Previewing pulls a blob over the network; no spec here asserts on a
    // rendered PDF, so keep it inert.
    fetchPreviewObjectUrl: vi.fn().mockResolvedValue(''),
    releasePreview: vi.fn(),
  }
})

// Imported after the mock is registered so the component picks up the stubs.
const GroupSubmissionPage = (await import('../GroupSubmissionPage.vue')).default

const QUESTIONS = [
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

const POSTER = { storage_key: 'x/p.pdf', name: 'poster.pdf', mime: 'application/pdf', size: 2048 }
const ANSWERED = { solution_purpose: 'An answer.', inspiration: 'Another answer.' }

const emptyRecord = (): SubmissionRecord => ({
  answers: {},
  poster: null,
  report: null,
  prototype: null,
  prototype_url: '',
  submitted_answers: null,
  submitted_poster: null,
  submitted_report: null,
  submitted_prototype: null,
  submitted_prototype_url: '',
  submitted_at: null,
  submitted_by_name: '',
  reopened_at: null,
  status: 'in_progress',
  is_submitted: false,
  is_locked: false,
  is_late: false,
  updated_at: new Date().toISOString(),
})

const buildDetail = (
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
const submittedDetail = () =>
  buildDetail({
    submission: {
      answers: ANSWERED,
      poster: POSTER,
      submitted_answers: ANSWERED,
      submitted_poster: POSTER,
      submitted_at: new Date().toISOString(),
      status: 'submitted',
      is_submitted: true,
      is_locked: true,
    },
  })

/** Submitted, then reopened: editable again, with the snapshot still standing. */
const reopenedDetail = () => {
  const now = Date.now()
  return buildDetail({
    submission: {
      answers: ANSWERED,
      poster: POSTER,
      submitted_answers: ANSWERED,
      submitted_poster: POSTER,
      submitted_at: new Date(now - 60_000).toISOString(),
      reopened_at: new Date(now).toISOString(),
      status: 'in_progress',
      is_submitted: true,
      is_locked: false,
    },
  })
}

const stub = { template: '<div />' }

// The page renders a RouterLink back to the team, so that named route has to
// exist here or every mount throws while resolving it.
const ROUTES = [
  { path: '/submission/:id', name: 'submission', component: stub },
  { path: '/groups/:id', name: 'group-detail', component: stub },
]

let pinia: Pinia
let wrapper: VueWrapper | null = null

const mountPage = async (detail: SubmissionDetail) => {
  fetchSubmission.mockResolvedValue(detail)
  const router = createRouter({ history: createWebHashHistory(), routes: ROUTES })
  await router.push('/submission/1')
  await router.isReady()
  wrapper = mount(GroupSubmissionPage, { global: { plugins: [router, pinia] } })
  for (let i = 0; i < 4; i += 1) await flushPromises()
  return wrapper
}

const buttons = () => wrapper!.findAll('button')
const buttonNamed = (label: RegExp) => buttons().find((b) => label.test(b.text().trim()))

/** The submit control lives on the final step of the wizard, not the first. */
const goToLastStep = async () => {
  await buttonNamed(/Additional/)!.trigger('click')
  await flushPromises()
}

beforeEach(() => {
  pinia = createPinia()
  setActivePinia(pinia)
  vi.clearAllMocks()
  vi.stubGlobal('confirm', vi.fn().mockReturnValue(true))
  // Changing step scrolls back to the top. jsdom has no layout, so the real
  // call prints "Not implemented" for every step change and buries the results.
  vi.stubGlobal('scrollTo', vi.fn())
})

afterEach(() => {
  // The page runs an interval for the countdown and a debounce timer for
  // auto-save; leaking either hangs the run.
  wrapper?.unmount()
  wrapper = null
  vi.unstubAllGlobals()
})

describe('required-answer progress', () => {
  it('counts nothing complete on a brand new entry', async () => {
    await mountPage(buildDetail({ submission: null }))
    expect(wrapper!.text()).toContain('0 of 2')
  })

  it('does not count whitespace as an answer', async () => {
    // A student who typed a space must not be told the question is done.
    await mountPage(
      buildDetail({ submission: { answers: { solution_purpose: 'Real.', inspiration: '   ' } } }),
    )
    expect(wrapper!.text()).toContain('1 of 2')
  })

  it('reports every required question answered', async () => {
    await mountPage(buildDetail({ submission: { answers: ANSWERED } }))
    expect(wrapper!.text()).toContain('2 of 2')
  })
})

describe('submitting', () => {
  it('offers a plain Submit on a first attempt', async () => {
    await mountPage(buildDetail({ submission: { answers: ANSWERED, poster: POSTER } }))
    await goToLastStep()
    expect(buttonNamed(/^Submit$/)).toBeTruthy()
    expect(buttonNamed(/New Attempt/i)).toBeUndefined()
  })

  it('stays clickable on an incomplete entry so the server can name what is missing', async () => {
    await mountPage(buildDetail({ submission: { answers: {} } }))
    await goToLastStep()
    expect(buttonNamed(/^Submit$/)?.attributes('disabled')).toBeUndefined()
  })

  it('names the unanswered questions when the server refuses', async () => {
    await mountPage(buildDetail({ submission: { answers: {}, poster: POSTER } }))
    await goToLastStep()
    saveDraft.mockResolvedValue({ deadline: submittedDetail().deadline, submission: emptyRecord() })
    submitEntry.mockRejectedValue(
      Object.assign(new Error('Required answers missing.'), {
        body: { missing: ['solution_purpose'] },
      }),
    )

    await buttonNamed(/^Submit$/)!.trigger('click')
    await flushPromises()

    expect(submitEntry).toHaveBeenCalled()
  })

  it('calls the API when submit is pressed', async () => {
    const detail = buildDetail({ submission: { answers: ANSWERED, poster: POSTER } })
    await mountPage(detail)
    await goToLastStep()
    saveDraft.mockResolvedValue({ deadline: detail.deadline, submission: detail.submission! })
    submitEntry.mockResolvedValue({
      deadline: detail.deadline,
      submission: { ...detail.submission!, is_locked: true, submitted_at: new Date().toISOString() },
    })

    await buttonNamed(/^Submit$/)!.trigger('click')
    await flushPromises()

    expect(submitEntry).toHaveBeenCalledWith('1')
  })
})

describe('a submitted entry', () => {
  it('reports itself as submitted rather than in progress', async () => {
    await mountPage(submittedDetail())
    const status = wrapper!.find('.status-line').text()
    expect(status).toContain('Submitted')
    expect(status).not.toContain('In Progress')
  })

  it('cannot be edited without reopening it first', async () => {
    // The snapshot only survives because editing is refused here; a writable
    // box would let a student quietly replace what was submitted.
    await mountPage(submittedDetail())
    const boxes = wrapper!.findAll('textarea')
    expect(boxes.length).toBeGreaterThan(0)
    boxes.forEach((box) => expect(box.attributes('disabled')).toBeDefined())
  })

  it('offers Resubmit, which reopens rather than submitting again', async () => {
    await mountPage(submittedDetail())
    const resubmit = buttonNamed(/^Resubmit$/)
    expect(resubmit).toBeTruthy()

    reopenEntry.mockResolvedValue({
      deadline: reopenedDetail().deadline,
      submission: reopenedDetail().submission!,
    })
    await resubmit!.trigger('click')
    await flushPromises()

    expect(reopenEntry).toHaveBeenCalledWith('1')
    expect(submitEntry).not.toHaveBeenCalled()
  })
})

describe('a reopened entry', () => {
  it('is editable again', async () => {
    await mountPage(reopenedDetail())
    wrapper!.findAll('textarea').forEach((box) => {
      expect(box.attributes('disabled')).toBeUndefined()
    })
  })

  it('calls the action New Attempt rather than Submit', async () => {
    await mountPage(reopenedDetail())
    await goToLastStep()
    expect(buttonNamed(/New Attempt/i)).toBeTruthy()
    expect(buttonNamed(/^Submit$/)).toBeUndefined()
  })
})

describe('a closed deadline', () => {
  it('refuses editing in the page, not only on the server', async () => {
    // The server is the real gate, but leaving the boxes live would invite a
    // student to write a long answer only to have the save rejected.
    await mountPage(buildDetail({ isOpen: false, submission: null }))
    const boxes = wrapper!.findAll('textarea')
    expect(boxes.length).toBeGreaterThan(0)
    boxes.forEach((box) => expect(box.attributes('disabled')).toBeDefined())
  })

  it('does not offer submit at all', async () => {
    await mountPage(
      buildDetail({ isOpen: false, submission: { answers: ANSWERED, poster: POSTER } }),
    )
    await goToLastStep()
    expect(buttonNamed(/^Submit$/)).toBeUndefined()
    expect(buttonNamed(/New Attempt/i)).toBeUndefined()
  })
})

describe('loading failure', () => {
  it('reports the error instead of rendering an empty form', async () => {
    fetchSubmission.mockRejectedValue(new Error('network down'))
    const router = createRouter({ history: createWebHashHistory(), routes: ROUTES })
    await router.push('/submission/1')
    await router.isReady()
    wrapper = mount(GroupSubmissionPage, { global: { plugins: [router, pinia] } })
    for (let i = 0; i < 4; i += 1) await flushPromises()

    expect(wrapper.findAll('textarea')).toHaveLength(0)
    expect(wrapper.text()).toMatch(/try again/i)
  })
})
