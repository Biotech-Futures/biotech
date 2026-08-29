import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia, type Pinia } from 'pinia'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createRouter, createWebHashHistory } from 'vue-router'
import { ApiError } from '@/utils/apiError'
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
 * * Submit is never disabled for an incomplete entry. It stays clickable, and
 *   pressing it says what is missing and moves to the first thing that needs
 *   fixing. Greying the button out instead would leave a student hunting for
 *   which box is blank with nothing to tell them why.
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
  // Attached to the document so focus actually moves: an unattached component
  // can never hold document.activeElement, and sending the student to the
  // question that needs fixing is part of what these specs check.
  wrapper = mount(GroupSubmissionPage, {
    attachTo: document.body,
    global: { plugins: [router, pinia] },
  })
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

  it('refuses an incomplete entry without listing every unanswered question', async () => {
    // The message used to name each blank question, which for a mostly-empty
    // form was a wall of prompts. It now says only what kind of thing is
    // missing; the page navigates to the first one instead of describing it.
    await mountPage(buildDetail({ submission: { answers: {}, poster: POSTER } }))
    await goToLastStep()

    await buttonNamed(/^Submit$/)!.trigger('click')
    await flushPromises()

    // toContain, not toBe: the banner carries a dismiss control of its own.
    const message = wrapper!.find('.submission-message').text()
    expect(message).toContain('Some required questions have not been answered.')
    expect(message).not.toContain(QUESTIONS[0].prompt)
    expect(submitEntry).not.toHaveBeenCalled()
  })

  it('sends the student to the first unanswered question, not merely back a step', async () => {
    await mountPage(
      buildDetail({
        submission: { answers: { solution_purpose: 'Done.' }, poster: POSTER },
      }),
    )
    await goToLastStep()

    await buttonNamed(/^Submit$/)!.trigger('click')
    await flushPromises()

    expect(wrapper!.find('[aria-current="step"]').text()).toContain('Questions')
    // The first question is answered, so the second is the one to land on.
    expect(document.activeElement?.id).toBe(QUESTIONS[1].key)
  })

  it('sends the student to the poster step when only the poster is missing', async () => {
    await mountPage(buildDetail({ submission: { answers: ANSWERED, poster: null } }))
    await goToLastStep()

    await buttonNamed(/^Submit$/)!.trigger('click')
    await flushPromises()

    expect(wrapper!.find('.submission-message').text()).toContain(
      'A poster must be uploaded before the entry can be submitted.',
    )
    expect(wrapper!.find('[aria-current="step"]').text()).toContain('Poster')
    expect(submitEntry).not.toHaveBeenCalled()
  })

  it('reports both when the questions are unanswered and the poster is missing', async () => {
    // Questions come first on the form, so that is where the student is sent —
    // but being told about only one of the two problems would mean a second
    // refusal waiting behind the first.
    await mountPage(buildDetail({ submission: { answers: {}, poster: null } }))
    await goToLastStep()

    await buttonNamed(/^Submit$/)!.trigger('click')
    await flushPromises()

    expect(wrapper!.find('.submission-message').text()).toContain(
      'Some required questions have not been answered, and no poster has been uploaded.',
    )
    expect(wrapper!.find('[aria-current="step"]').text()).toContain('Questions')
    expect(submitEntry).not.toHaveBeenCalled()
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

describe('the deadline passing while the page is open', () => {
  // Both cases below start from an entry that is open and editable — the
  // student has not been told the deadline passed, because as far as the
  // last successful fetch knew, it had not.
  const openDetail = () => buildDetail({ submission: { answers: ANSWERED } })

  it('closes the page when a save is refused as too late, instead of leaving it retrying forever', async () => {
    await mountPage(openDetail())
    saveDraft.mockRejectedValue(
      new ApiError({ error: 'Closed.', code: 'submissions_closed', request_id: 'r1' }, 403),
    )

    // Any edit queues an auto-save; wait out the debounce for it to fire.
    await wrapper!.findAll('textarea')[0].setValue('One more word.')
    await new Promise((resolve) => setTimeout(resolve, 2200))
    await flushPromises()

    // The one failed save is enough to know writes are refused — the page
    // does not wait for a second attempt to say so.
    wrapper!.findAll('textarea').forEach((box) => {
      expect(box.attributes('disabled')).toBeDefined()
    })
    expect(wrapper!.find('.submission-closed').exists()).toBe(true)
    expect(wrapper!.text()).toMatch(/deadline has passed/i)
  })

  it('stops auto-save from repeating the same failed request once closed', async () => {
    await mountPage(openDetail())
    saveDraft.mockRejectedValue(
      new ApiError({ error: 'Closed.', code: 'submissions_closed', request_id: 'r1' }, 403),
    )

    await wrapper!.findAll('textarea')[0].setValue('First edit.')
    await new Promise((resolve) => setTimeout(resolve, 2200))
    await flushPromises()
    expect(saveDraft).toHaveBeenCalledTimes(1)

    // The box is now disabled, so this models the field already having been
    // in the middle of an edit when the refusal landed, not a fresh attempt.
    saveDraft.mockClear()
    await wrapper!.vm.$forceUpdate()
    await new Promise((resolve) => setTimeout(resolve, 2200))
    await flushPromises()
    expect(saveDraft).not.toHaveBeenCalled()
  })

  it('notices the deadline passing even for a student who is only reading', async () => {
    // No save ever fires here — nothing is being typed — so the only way the
    // page can find out is by asking again once the clock reaches closes_at.
    vi.useFakeTimers()
    try {
      const open = buildDetail({ submission: { answers: ANSWERED } })
      open.deadline.closes_at = new Date(Date.now() + 30_000).toISOString()

      // The initial load resolves before the clock is advanced at all, so
      // this mock is consumed once and does not affect the later re-check.
      fetchSubmission.mockResolvedValueOnce(open)
      const router = createRouter({ history: createWebHashHistory(), routes: ROUTES })
      await router.push('/submission/1')
      await router.isReady()
      wrapper = mount(GroupSubmissionPage, { global: { plugins: [router, pinia] } })
      await flushPromises()
      expect(fetchSubmission).toHaveBeenCalledTimes(1)

      // Only now does the server start reporting the deadline as passed — the
      // re-check has to happen after this point to observe it.
      fetchSubmission.mockResolvedValue({
        ...open,
        deadline: { ...open.deadline, is_open: false }
      })

      // The countdown ticks once a minute; that tick is what notices the
      // clock has crossed closes_at and triggers the re-check.
      await vi.advanceTimersByTimeAsync(60_000)
      await flushPromises()

      expect(fetchSubmission).toHaveBeenCalledTimes(2)
      expect(wrapper!.find('.submission-closed').exists()).toBe(true)
      wrapper!.findAll('textarea').forEach((box) => {
        expect(box.attributes('disabled')).toBeDefined()
      })
    } finally {
      vi.useRealTimers()
    }
  })

  it('does not assume closed just because the announced time passed, since a grace period may still be running', async () => {
    // The server is always asked rather than the client deciding on its own:
    // closes_at passing does not mean writes are refused, and the client is
    // never told how long any grace period is.
    vi.useFakeTimers()
    try {
      const open = buildDetail({ submission: { answers: ANSWERED } })
      open.deadline.closes_at = new Date(Date.now() + 30_000).toISOString()
      fetchSubmission.mockResolvedValue(open)

      const router = createRouter({ history: createWebHashHistory(), routes: ROUTES })
      await router.push('/submission/1')
      await router.isReady()
      wrapper = mount(GroupSubmissionPage, { global: { plugins: [router, pinia] } })
      await flushPromises()

      // The re-check finds the server still accepting writes — a grace
      // window — because every call keeps returning the same open mock.
      await vi.advanceTimersByTimeAsync(60_000)
      await flushPromises()

      expect(fetchSubmission).toHaveBeenCalledTimes(2)
      wrapper!.findAll('textarea').forEach((box) => {
        expect(box.attributes('disabled')).toBeUndefined()
      })
    } finally {
      vi.useRealTimers()
    }
  })
})

describe('an answer over its word limit', () => {
  const overLimit = Array(200).fill('word').join(' ')

  it('is left out of the save instead of being sent and refused', async () => {
    await mountPage(buildDetail({ submission: { answers: ANSWERED } }))
    const boxes = wrapper!.findAll('textarea')

    await boxes[0].setValue(overLimit)
    await boxes[1].setValue('Still a valid answer.')
    await new Promise((resolve) => setTimeout(resolve, 2200))
    await flushPromises()

    expect(saveDraft).toHaveBeenCalledTimes(1)
    const sent = saveDraft.mock.calls[0][1].answers
    expect(sent).toEqual({ inspiration: 'Still a valid answer.' })
  })

  it('leaves the status honestly showing unsaved changes rather than saved', async () => {
    // A save can succeed for everything else while this one answer is still
    // only sitting in the browser — the status line must not claim otherwise.
    const detail = buildDetail({ submission: { answers: ANSWERED } })
    await mountPage(detail)
    saveDraft.mockResolvedValue({ deadline: detail.deadline, submission: detail.submission! })

    await wrapper!.findAll('textarea')[0].setValue(overLimit)
    await new Promise((resolve) => setTimeout(resolve, 2200))
    await flushPromises()

    expect(saveDraft).toHaveBeenCalledTimes(1)
    expect(wrapper!.find('.submission-savestate').text()).toMatch(/unsaved/i)
  })

  it('refuses to submit rather than silently sending the last saved version', async () => {
    // changedAnswers() would otherwise send whatever was saved before the
    // student went over the limit — technically valid, but not what is
    // currently in the box, which is worse than refusing outright.
    await mountPage(buildDetail({ submission: { answers: ANSWERED, poster: POSTER } }))
    await goToLastStep()
    await wrapper!.findAll('textarea')[0].setValue(overLimit)
    await flushPromises()

    await buttonNamed(/^Submit$/)!.trigger('click')
    await flushPromises()

    expect(submitEntry).not.toHaveBeenCalled()
    // A save may still happen — moving to the offending question is a tab
    // change, and leaving a tab flushes any pending auto-save. What matters is
    // that no save carried the over-limit answer, in either direction: neither
    // the too-long text nor the older valid version it would have replaced.
    for (const [, payload] of saveDraft.mock.calls) {
      expect(Object.keys(payload.answers)).not.toContain(QUESTIONS[0].key)
    }
  })

  it('names the question by its prompt, not its database key', async () => {
    await mountPage(buildDetail({ submission: { answers: ANSWERED, poster: POSTER } }))
    await goToLastStep()
    await wrapper!.findAll('textarea')[0].setValue(overLimit)
    await flushPromises()

    await buttonNamed(/^Submit$/)!.trigger('click')
    await flushPromises()

    const message = wrapper!.find('.submission-message').text()
    expect(message).toContain(QUESTIONS[0].prompt)
    expect(message).not.toContain(QUESTIONS[0].key)
  })
})
