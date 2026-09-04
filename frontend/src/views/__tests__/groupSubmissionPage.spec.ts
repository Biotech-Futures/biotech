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
  poster_checks: null,
  report: null,
  prototype: null,
  prototype_url: '',
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
      stage: 'submitted',
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
      stage: 'revising',
      is_submitted: true,
      is_locked: false,
    },
  })
}

const stub = { template: '<div />' }

// The portal is a section of the group page and reads the team from the route,
// so it is mounted on the route it really lives at.
const ROUTES = [
  { path: '/groups/:id/submission', name: 'group-submission', component: stub },
  { path: '/groups/:id', name: 'group-detail', component: stub },
]

let pinia: Pinia
let wrapper: VueWrapper | null = null

const mountPage = async (detail: SubmissionDetail) => {
  fetchSubmission.mockResolvedValue(detail)
  const router = createRouter({ history: createWebHashHistory(), routes: ROUTES })
  await router.push('/groups/1/submission')
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
    await router.push('/groups/1/submission')
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
    expect(wrapper!.find('.status-line').text()).toContain('Submissions are closed')
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
      await router.push('/groups/1/submission')
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
      expect(wrapper!.find('.status-line').text()).toContain('Submissions are closed')
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
      await router.push('/groups/1/submission')
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

describe('what the format checks found about the poster', () => {
  const warned = (warnings: { code: string; message: string }[]) =>
    buildDetail({
      submission: {
        answers: ANSWERED,
        poster: POSTER,
        poster_checks: {
          has_text: true,
          unreadable: false,
          warnings: warnings.map((w) => ({ ...w, passed: false })),
        },
      },
    })

  const goToPoster = async () => {
    await buttonNamed(/Poster/)!.trigger('click')
    await flushPromises()
  }

  it('points at the requirements rather than naming what it could not find', async () => {
    // These checks read text, which is evidence rather than proof: a team code
    // set inside an image is invisible to them. Asserting "your team code is
    // missing" would be confidently wrong for a poster that is perfectly
    // correct, so the notice stays general.
    await mountPage(
      warned([{ code: 'team_code', message: 'We could not find your team code (BTF1).' }]),
    )
    await goToPoster()

    const notice = wrapper!.find('.poster-notice').text()
    expect(notice).toContain('submission requirements')
    expect(notice).not.toContain('could not find')
  })

  it('makes clear the entry can still be submitted', async () => {
    // The distinction the whole soft half rests on: this is advice, and a
    // student who reads it as a blocked submission will go looking for a
    // problem that is not there.
    await mountPage(warned([{ code: 'team_code', message: 'Missing team code.' }]))
    await goToPoster()

    expect(wrapper!.find('.poster-notice').text()).toContain('submit without changing anything')
  })

  it('does not warn at all when the poster passed every check', async () => {
    await mountPage(
      buildDetail({
        submission: {
          answers: ANSWERED,
          poster: POSTER,
          poster_checks: { has_text: true, unreadable: false, warnings: [] },
        },
      }),
    )
    await goToPoster()

    expect(wrapper!.find('.poster-notice').exists()).toBe(false)
  })

  it('says nothing about a poster that carried no readable text', async () => {
    // A poster flattened to an image cannot be checked. Silence is right here:
    // there is no finding to report, and inventing one would be wrong.
    await mountPage(
      buildDetail({
        submission: {
          answers: ANSWERED,
          poster: POSTER,
          poster_checks: { has_text: false, unreadable: false, warnings: [] },
        },
      }),
    )
    await goToPoster()

    expect(wrapper!.find('.poster-notice').exists()).toBe(false)
  })

  it('reports on the submitted poster once the entry is locked', async () => {
    // A locked entry shows what was submitted, and its findings have to follow
    // the same rule or the notice would describe a different file. Set up so
    // the two disagree: the draft was flagged, the submitted copy was clean,
    // so a notice appearing at all would mean the wrong one was read.
    const detail = submittedDetail()
    detail.submission!.poster_checks = {
      has_text: true,
      unreadable: false,
      warnings: [{ code: 'team_code', message: 'Draft finding.', passed: false }],
    }
    detail.submission!.submitted_poster_checks = {
      has_text: true,
      unreadable: false,
      warnings: [],
    }
    await mountPage(detail)
    await goToPoster()

    expect(wrapper!.find('.poster-notice').exists()).toBe(false)
  })
})

describe('moving between steps', () => {
  it('offers Submit from the first step, not only the last', async () => {
    // The reason the arrows replaced a labelled Next: a team who has finished
    // should not have to walk to the end of the wizard to find the button.
    await mountPage(buildDetail({ submission: { answers: ANSWERED, poster: POSTER } }))

    expect(buttonNamed(/^Submit$/)).toBeTruthy()
  })

  it('keeps each arrow labelled with where it goes', async () => {
    // An icon-only control still has to say what it does for anyone using a
    // screen reader, so the destination moves to the accessible name.
    await mountPage(buildDetail({ submission: { answers: ANSWERED, poster: POSTER } }))

    const forward = buttons().find((b) => b.attributes('aria-label')?.startsWith('Next:'))
    expect(forward?.attributes('aria-label')).toBe('Next: Poster')
  })

  it('disables the back arrow on the first step rather than removing it', async () => {
    // Hiding it would make the row reflow as the student moves through.
    await mountPage(buildDetail({ submission: { answers: ANSWERED, poster: POSTER } }))

    const back = buttons().find((b) => b.attributes('aria-label') === 'Previous step')
    expect(back?.attributes('disabled')).toBeDefined()
  })
})

describe('what the status line says', () => {
  // Stage and window are independent, so all eight pairings are stated here.
  // The three that used to be wrong are the closed ones that are not
  // "submitted" — each previously read "In Progress" after the deadline.
  const line = () => wrapper!.find('.status-line').text()

  const at = (stage: SubmissionRecord['stage'], isOpen: boolean, extra = {}) =>
    buildDetail({
      isOpen,
      submission: { stage, ...extra },
    })

  it('invites a team that has not started while the window is open', async () => {
    await mountPage(at('not_started', true))
    expect(line()).toContain('Not Started')
  })

  it('says a started entry is in progress while the window is open', async () => {
    await mountPage(at('in_progress', true, { answers: ANSWERED }))
    expect(line()).toContain('In Progress')
  })

  it('says submitted while the window is open', async () => {
    await mountPage(submittedDetail())
    expect(line()).toContain('Submitted')
  })

  it('reassures a team mid-revision that their entry still stands', async () => {
    await mountPage(reopenedDetail())
    const text = line()
    expect(text).toContain('In Progress')
    expect(text).toContain('still stands')
  })

  it('tells a team that never started that nothing went in', async () => {
    await mountPage(at('not_started', false))
    const text = line()
    expect(text).toContain('Not Submitted')
    expect(text).toContain('Submissions are closed')
    expect(text).not.toContain('In Progress')
  })

  it('tells a team with an unsubmitted draft that it never went in', async () => {
    await mountPage(at('in_progress', false, { answers: ANSWERED }))
    const text = line()
    expect(text).toContain('Not Submitted')
    expect(text).toContain('never submitted')
    expect(text).not.toContain('In Progress')
  })

  it('still says submitted once the window has closed', async () => {
    const detail = submittedDetail()
    detail.deadline.is_open = false
    await mountPage(detail)
    expect(line()).toContain('Submitted')
  })

  it('tells a team who ran out of time mid-revision that the revision did not count', async () => {
    // The case that mattered most: they have a valid entry on record, and the
    // version they were editing is not it.
    const detail = reopenedDetail()
    detail.deadline.is_open = false
    await mountPage(detail)

    const text = line()
    expect(text).toContain('Submitted')
    expect(text).toContain('unfinished revision was not submitted')
    expect(text).not.toContain('In Progress')
  })
})

describe('which copy of the entry is shown', () => {
  const SUBMITTED_ANSWERS = { solution_purpose: 'SUBMITTED.', inspiration: 'SUBMITTED.' }
  const DRAFT_ANSWERS = { solution_purpose: 'DRAFT.', inspiration: 'DRAFT.' }
  const SUBMITTED_POSTER = { ...POSTER, name: 'submitted.pdf' }
  const DRAFT_POSTER = { ...POSTER, name: 'draft.pdf' }

  const midRevision = (isOpen: boolean) => {
    const now = Date.now()
    return buildDetail({
      isOpen,
      submission: {
        stage: 'revising',
        answers: DRAFT_ANSWERS,
        poster: DRAFT_POSTER,
        submitted_answers: SUBMITTED_ANSWERS,
        submitted_poster: SUBMITTED_POSTER,
        submitted_at: new Date(now - 60_000).toISOString(),
        reopened_at: new Date(now).toISOString(),
        is_submitted: true,
        is_locked: false,
      },
    })
  }

  it('shows the draft while a revision is still possible', async () => {
    await mountPage(midRevision(true))
    expect(wrapper!.findAll('textarea')[0].element.value).toBe('DRAFT.')
  })

  it('shows what was submitted once the window has closed', async () => {
    // Otherwise the team reads a draft nobody will ever mark, and believes it
    // is their entry.
    await mountPage(midRevision(false))
    expect(wrapper!.findAll('textarea')[0].element.value).toBe('SUBMITTED.')
  })

  it('shows the submitted poster once the window has closed', async () => {
    await mountPage(midRevision(false))
    await buttonNamed(/Poster/)!.trigger('click')
    await flushPromises()

    expect(wrapper!.find('.submission-file').text()).toContain('submitted.pdf')
  })
})

describe('how the status line is worded', () => {
  it('does not repeat the deadline date the header already shows', async () => {
    await mountPage(buildDetail({ isOpen: false, submission: { stage: 'not_started' } }))

    const text = wrapper!.find('.status-line').text()
    expect(text).toContain('Submissions are closed.')
    expect(text).not.toMatch(/deadline passed on/i)
  })

  it('ends the headline with a full stop when a detail follows it', async () => {
    await mountPage(submittedDetail())

    expect(wrapper!.find('.status-line__state').text()).toBe('Submitted.')
  })

  it('says the window is shut in the status line, not a separate banner', async () => {
    // The banner said the same thing twice, one line below the status it
    // duplicated.
    await mountPage(buildDetail({ isOpen: false, submission: { stage: 'not_started' } }))

    expect(wrapper!.find('.submission-closed').exists()).toBe(false)
    expect(wrapper!.find('.status-line').text()).toContain('Submissions are closed')
  })

  it('leaves the headline unpunctuated when it stands alone', async () => {
    await mountPage(buildDetail({ submission: { stage: 'in_progress', answers: ANSWERED } }))

    expect(wrapper!.find('.status-line__state').text()).toBe('In Progress')
  })
})

describe('how the deadline reads', () => {
  it('leaves the year out when the deadline falls this year', async () => {
    // Four characters of noise in a line that was already crowded.
    await mountPage(buildDetail({}))

    expect(wrapper!.find('.submission-due__date').text()).not.toContain(
      String(new Date().getFullYear()),
    )
  })

  it('names the year when the deadline is in another one', async () => {
    // The shortening must never make a deadline read as this year when it is
    // not — the saving is not worth an ambiguous closing date.
    const nextYear = new Date()
    nextYear.setFullYear(nextYear.getFullYear() + 1)
    const detail = buildDetail({})
    detail.deadline.closes_at = nextYear.toISOString()

    await mountPage(detail)

    expect(wrapper!.find('.submission-due__date').text()).toContain(
      String(nextYear.getFullYear()),
    )
  })

  it('shows the countdown while the window is open', async () => {
    await mountPage(buildDetail({}))

    expect(wrapper!.find('.submission-remaining').exists()).toBe(true)
  })

  it('marks the countdown as near inside the last day', async () => {
    // The chip changes colour rather than shape, so nothing on the row moves
    // underneath a student who is mid-sentence.
    const detail = buildDetail({})
    detail.deadline.closes_at = new Date(Date.now() + 3 * 3_600_000).toISOString()

    await mountPage(detail)

    expect(wrapper!.find('.submission-remaining').classes()).toContain('is-near')
  })
})

describe('the word counter', () => {
  it('stays hidden until there is something to count', async () => {
    // Six "0 / 150 words" lines on an untouched form read as six things already
    // wrong. The limit is stated in the section instructions, so nothing is lost
    // by waiting.
    await mountPage(buildDetail({ submission: null }))

    expect(wrapper!.findAll('.submission-count')).toHaveLength(0)
  })

  it('appears once a question is answered, for that question only', async () => {
    await mountPage(buildDetail({ submission: null }))

    await wrapper!.findAll('textarea')[0].setValue('Two words')
    await flushPromises()

    const counts = wrapper!.findAll('.submission-count')
    expect(counts).toHaveLength(1)
    expect(counts[0].text()).toContain('2 / 150 words')
  })

  it('treats whitespace as nothing, the same as the progress count does', async () => {
    await mountPage(buildDetail({ submission: null }))

    await wrapper!.findAll('textarea')[0].setValue('   ')
    await flushPromises()

    expect(wrapper!.findAll('.submission-count')).toHaveLength(0)
  })

  it('still shows a count that is over the limit', async () => {
    // The counter turning itself off must never hide the one state that
    // actually blocks a submission.
    await mountPage(buildDetail({ submission: null }))

    await wrapper!.findAll('textarea')[0].setValue('word '.repeat(151))
    await flushPromises()

    const count = wrapper!.find('.submission-count')
    expect(count.exists()).toBe(true)
    expect(count.classes()).toContain('is-over-limit')
  })
})

describe('collapsing a preview', () => {
  const openPosterTab = async () => {
    await buttonNamed(/Poster/)!.trigger('click')
    await flushPromises()
  }

  it('starts open, so an uploaded poster is visible without asking', async () => {
    await mountPage(buildDetail({ submission: { answers: ANSWERED, poster: POSTER } }))
    await openPosterTab()

    const toggle = wrapper!.find('[data-testid="toggle-poster-preview"]')
    expect(toggle.attributes('aria-expanded')).toBe('true')
    expect(wrapper!.find('.preview-panel').classes()).not.toContain('is-collapsed')
  })

  it('folds away when the heading is pressed', async () => {
    await mountPage(buildDetail({ submission: { answers: ANSWERED, poster: POSTER } }))
    await openPosterTab()

    await wrapper!.find('[data-testid="toggle-poster-preview"]').trigger('click')
    await flushPromises()

    expect(wrapper!.find('[data-testid="toggle-poster-preview"]').attributes('aria-expanded')).toBe(
      'false',
    )
    expect(wrapper!.find('.preview-panel').classes()).toContain('is-collapsed')
  })

  it('hides the document rather than unloading it', async () => {
    // Tearing the iframe down would make every re-open refetch the file.
    await mountPage(buildDetail({ submission: { answers: ANSWERED, poster: POSTER } }))
    await openPosterTab()

    await wrapper!.find('[data-testid="toggle-poster-preview"]').trigger('click')
    await flushPromises()

    const body = wrapper!.find('#poster-preview-body')
    expect(body.exists()).toBe(true)
    expect((body.element as HTMLElement).style.display).toBe('none')
  })

  it('opens again on a second press', async () => {
    await mountPage(buildDetail({ submission: { answers: ANSWERED, poster: POSTER } }))
    await openPosterTab()

    const toggle = () => wrapper!.find('[data-testid="toggle-poster-preview"]')
    await toggle().trigger('click')
    await toggle().trigger('click')
    await flushPromises()

    expect(toggle().attributes('aria-expanded')).toBe('true')
  })
})

describe('as a section of the group page', () => {
  // There is one mount. The portal used to render as a page of its own as well,
  // behind an `embedded` prop that varied its chrome; that mount is gone, and
  // these specs pin what the single remaining one owes the page around it.

  it('keeps the page wrapper, which carries every design token', async () => {
    // This spec once asserted the opposite, and that assertion held a real bug
    // in place. Every token here — panel background, border, shadow, field
    // colours, the spacing scale — is declared on .content-area. Dropping the
    // class left about a hundred declarations pointing at undefined properties,
    // so panels rendered with no background, no border and no spacing, and the
    // page came out as text and buttons floating in white space.
    await mountPage(buildDetail({ submission: { answers: ANSWERED, poster: POSTER } }))

    expect(wrapper!.find('.content-area').exists()).toBe(true)
  })

  it('carries no masthead, which the group page header already covers', async () => {
    // It also echoed the Qualtrics form's header, which is the thing the client
    // reacted to.
    await mountPage(buildDetail({ submission: { answers: ANSWERED } }))

    expect(wrapper!.find('.portal-brand').exists()).toBe(false)
  })

  it('keeps the deadline, which nothing else on the group page states', async () => {
    // The deadline shares a strip with the masthead that was removed, so it is
    // easy to lose the closing date by accident while tidying that strip up.
    await mountPage(buildDetail({ submission: { answers: ANSWERED } }))

    expect(wrapper!.find('.submission-due').exists()).toBe(true)
  })

  it('carries no back link, which pointed at the page it now lives on', async () => {
    await mountPage(buildDetail({ submission: { answers: ANSWERED } }))

    expect(wrapper!.find('.submission-back').exists()).toBe(false)
  })

  it('keeps everything that matters', async () => {
    await mountPage(buildDetail({ submission: { answers: ANSWERED, poster: POSTER } }))

    expect(wrapper!.findAll('textarea')).toHaveLength(QUESTIONS.length)
    expect(wrapper!.find('.submission-due').exists()).toBe(true)
    expect(wrapper!.find('.status-line').exists()).toBe(true)
    expect(wrapper!.find('.submission-steps').exists()).toBe(true)
    expect(buttonNamed(/^Submit$/)).toBeTruthy()
  })
})
