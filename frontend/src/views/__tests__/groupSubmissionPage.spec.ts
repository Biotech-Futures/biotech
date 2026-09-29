import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia, type Pinia } from 'pinia'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createRouter, createWebHashHistory } from 'vue-router'
import { ApiError } from '@/utils/apiError'
import type { SubmissionDetail, SubmissionRecord } from '@/utils/submissionsAPI'

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

const ROUTES = [
  { path: '/groups/:id/submission', name: 'group-submission', component: stub },
  { path: '/groups/:id', name: 'group-detail', component: stub },
  { path: '/resources/:id', name: 'resource-detail', component: stub },
]

let pinia: Pinia
let wrapper: VueWrapper | null = null

const mountPage = async (detail: SubmissionDetail) => {
  fetchSubmission.mockResolvedValue(detail)
  const router = createRouter({ history: createWebHashHistory(), routes: ROUTES })
  await router.push('/groups/1/submission')
  await router.isReady()
  // Attached to the document so focus can actually move.
  wrapper = mount(GroupSubmissionPage, {
    attachTo: document.body,
    global: { plugins: [router, pinia] },
  })
  for (let i = 0; i < 4; i += 1) await flushPromises()
  return wrapper
}

const buttons = () => wrapper!.findAll('button')
const buttonNamed = (label: RegExp) => buttons().find((b) => label.test(b.text().trim()))

const goToLastStep = async () => {
  await buttonNamed(/Additional/)!.trigger('click')
  await flushPromises()
}

beforeEach(() => {
  pinia = createPinia()
  setActivePinia(pinia)
  vi.clearAllMocks()
  vi.stubGlobal('confirm', vi.fn().mockReturnValue(true))
  // jsdom has no scrollTo; stubbed to keep test output readable.
  vi.stubGlobal('scrollTo', vi.fn())
})

afterEach(() => {
  // Unmounted so the countdown and auto-save timers cannot hang the run.
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

  it('clears an error banner by itself after four seconds', async () => {
    vi.useFakeTimers()
    try {
      await mountPage(buildDetail({ submission: { answers: {}, poster: POSTER } }))
      await goToLastStep()
      await buttonNamed(/^Submit$/)!.trigger('click')
      await flushPromises()
      expect(wrapper!.find('.submission-message').exists()).toBe(true)

      await vi.advanceTimersByTimeAsync(4000)

      expect(wrapper!.find('.submission-message').exists()).toBe(false)
    } finally {
      vi.useRealTimers()
    }
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
    await wrapper!.find('[data-testid="reopen-confirm"]').trigger('click')
    await flushPromises()

    expect(reopenEntry).toHaveBeenCalledWith('1')
    expect(submitEntry).not.toHaveBeenCalled()
  })

  it('asks before reopening, and says the current submission stands', async () => {
    await mountPage(submittedDetail())

    await wrapper!.find('[data-testid="resubmit"]').trigger('click')
    await flushPromises()

    const dialog = wrapper!.find('[data-testid="reopen-dialog"]')
    expect(dialog.exists()).toBe(true)
    expect(dialog.text()).toContain('stays in place')
    expect(reopenEntry).not.toHaveBeenCalled()
  })

  it('asks in the page rather than through the browser', async () => {
    await mountPage(submittedDetail())

    await wrapper!.find('[data-testid="resubmit"]').trigger('click')
    await flushPromises()

    expect(window.confirm).not.toHaveBeenCalled()
    expect(wrapper!.find('[role="dialog"]').attributes('aria-modal')).toBe('true')
  })

  it('does nothing at all if the question is declined', async () => {
    await mountPage(submittedDetail())

    await wrapper!.find('[data-testid="resubmit"]').trigger('click')
    await flushPromises()
    await wrapper!.find('[data-testid="reopen-cancel"]').trigger('click')
    await flushPromises()

    expect(reopenEntry).not.toHaveBeenCalled()
    expect(wrapper!.find('[data-testid="reopen-dialog"]').exists()).toBe(false)
  })

  it('closes on Escape without reopening', async () => {
    await mountPage(submittedDetail())

    await wrapper!.find('[data-testid="resubmit"]').trigger('click')
    await flushPromises()
    await wrapper!.find('[data-testid="reopen-dialog"]').trigger('keydown.esc')
    await flushPromises()

    expect(wrapper!.find('[data-testid="reopen-dialog"]').exists()).toBe(false)
    expect(reopenEntry).not.toHaveBeenCalled()
  })

  it('reopens only once the dialog is confirmed', async () => {
    await mountPage(submittedDetail())
    reopenEntry.mockResolvedValue({
      deadline: reopenedDetail().deadline,
      submission: reopenedDetail().submission!,
    })

    await wrapper!.find('[data-testid="resubmit"]').trigger('click')
    await flushPromises()
    await wrapper!.find('[data-testid="reopen-confirm"]').trigger('click')
    await flushPromises()

    expect(reopenEntry).toHaveBeenCalledWith('1')
    expect(wrapper!.find('[data-testid="reopen-dialog"]').exists()).toBe(false)
  })
})

describe('a reopened entry', () => {
  it('is editable again', async () => {
    await mountPage(reopenedDetail())
    wrapper!.findAll('textarea').forEach((box) => {
      expect(box.attributes('disabled')).toBeUndefined()
    })
  })

  it('still calls the action Submit, not something else', async () => {
    await mountPage(reopenedDetail())
    await goToLastStep()
    expect(buttonNamed(/^Submit$/)).toBeTruthy()
    expect(buttonNamed(/New Attempt/i)).toBeUndefined()
  })
})

describe('a closed deadline', () => {
  it('refuses editing in the page, not only on the server', async () => {
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

    // Models an edit already in progress when the refusal landed.
    saveDraft.mockClear()
    await wrapper!.vm.$forceUpdate()
    await new Promise((resolve) => setTimeout(resolve, 2200))
    await flushPromises()
    expect(saveDraft).not.toHaveBeenCalled()
  })

  it('notices the deadline passing even for a student who is only reading', async () => {
    vi.useFakeTimers()
    try {
      const open = buildDetail({ submission: { answers: ANSWERED } })
      open.deadline.closes_at = new Date(Date.now() + 30_000).toISOString()

      fetchSubmission.mockResolvedValueOnce(open)
      const router = createRouter({ history: createWebHashHistory(), routes: ROUTES })
      await router.push('/groups/1/submission')
      await router.isReady()
      wrapper = mount(GroupSubmissionPage, { global: { plugins: [router, pinia] } })
      await flushPromises()
      expect(fetchSubmission).toHaveBeenCalledTimes(1)

      fetchSubmission.mockResolvedValue({
        ...open,
        deadline: { ...open.deadline, is_open: false }
      })

      // The once-a-minute countdown tick triggers the re-check.
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
    await mountPage(buildDetail({ submission: { answers: ANSWERED, poster: POSTER } }))
    await goToLastStep()
    await wrapper!.findAll('textarea')[0].setValue(overLimit)
    await flushPromises()

    await buttonNamed(/^Submit$/)!.trigger('click')
    await flushPromises()

    expect(submitEntry).not.toHaveBeenCalled()
    // Leaving a step flushes auto-save, so check no save carried the over-limit answer.
    for (const [, payload] of saveDraft.mock.calls) {
      expect(Object.keys(payload.answers)).not.toContain(QUESTIONS[0].key)
    }
  })

  it('names one question, never a list, and leaves the counts out', async () => {
    const detail = buildDetail({ submission: { answers: ANSWERED, poster: POSTER } })
    await mountPage(detail)
    // Leaving a step flushes auto-save, so this spec sets its own resolved value.
    saveDraft.mockResolvedValue({ deadline: detail.deadline, submission: detail.submission! })

    await goToLastStep()
    const boxes = wrapper!.findAll('textarea')
    await boxes[0].setValue(overLimit)
    await boxes[1].setValue(overLimit)
    await flushPromises()

    await buttonNamed(/^Submit$/)!.trigger('click')
    await flushPromises()

    const text = wrapper!.find('.submission-message').text()
    expect(text).toContain(QUESTIONS[0].prompt)
    expect(text).not.toContain(QUESTIONS[1].prompt)
    expect(text).not.toContain('limit')
    expect(text).not.toContain('words')
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

describe('the poster template link', () => {
  const goToPoster = async () => {
    await buttonNamed(/Poster/)!.trigger('click')
    await flushPromises()
  }

  it('reads as one instruction with the section body, not two separate lines', async () => {
    // Every tab's header stays mounted, so only the poster tab carries the template sentence.
    await mountPage(buildDetail({ submission: { answers: ANSWERED } }))
    await goToPoster()

    const intro = wrapper!.get('.submission-template-link').element.closest('p')
    expect(intro?.textContent).toContain('Upload a PDF.')
    expect(intro?.textContent).toContain("Your poster must use the programme's")
  })

  it('marks the template as a link with an icon, not colour alone', async () => {
    await mountPage(buildDetail({ submission: { answers: ANSWERED } }))
    await goToPoster()

    const link = wrapper!.find('.submission-template-link')
    expect(link.attributes('href')).toBe('#/resources/9')
    expect(link.find('i.fa-arrow-up-right-from-square').exists()).toBe(true)
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
    await mountPage(
      warned([{ code: 'team_code', message: 'We could not find your team code (BTF1).' }]),
    )
    await goToPoster()

    const notice = wrapper!.find('.poster-notice').text()
    expect(notice).toContain('submission requirements')
    expect(notice).not.toContain('could not find')
  })

  it('leads with the upload having worked, so it does not read as a refusal', async () => {
    await mountPage(warned([{ code: 'team_code', message: 'Missing team code.' }]))
    await goToPoster()

    expect(wrapper!.find('.poster-notice').text()).toMatch(/^Uploaded\./)
  })

  it('keeps the notice to a single line', async () => {
    await mountPage(warned([{ code: 'team_code', message: 'Missing team code.' }]))
    await goToPoster()

    expect(wrapper!.findAll('.poster-notice p')).toHaveLength(1)
  })

  it('clears the notice by itself after four seconds', async () => {
    vi.useFakeTimers()
    try {
      await mountPage(warned([{ code: 'a_series_size', message: 'Not an A-series size.' }]))
      await goToPoster()
      expect(wrapper!.find('.poster-notice').exists()).toBe(true)

      await vi.advanceTimersByTimeAsync(4000)

      expect(wrapper!.find('.poster-notice').exists()).toBe(false)
    } finally {
      vi.useRealTimers()
    }
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
    // The draft and submitted findings disagree, so the wrong one would show a notice.
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
    await mountPage(buildDetail({ submission: { answers: ANSWERED, poster: POSTER } }))

    expect(buttonNamed(/^Submit$/)).toBeTruthy()
  })

  it('keeps each arrow labelled with where it goes', async () => {
    await mountPage(buildDetail({ submission: { answers: ANSWERED, poster: POSTER } }))

    const forward = buttons().find((b) => b.attributes('aria-label')?.startsWith('Next:'))
    expect(forward?.attributes('aria-label')).toBe('Next: Poster')
  })

  it('disables the back arrow on the first step rather than removing it', async () => {
    await mountPage(buildDetail({ submission: { answers: ANSWERED, poster: POSTER } }))

    const back = buttons().find((b) => b.attributes('aria-label') === 'Previous step')
    expect(back?.attributes('disabled')).toBeDefined()
  })
})

describe('what the status line says', () => {
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
    expect(text).toContain('Submissions are closed')
    expect(text).not.toContain('never submitted')
    expect(text).not.toContain('In Progress')
  })

  it('still says submitted once the window has closed', async () => {
    const detail = submittedDetail()
    detail.deadline.is_open = false
    await mountPage(detail)
    expect(line()).toContain('Submitted')
  })

  it('tells a team who ran out of time mid-revision that the revision did not count', async () => {
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
    await mountPage(buildDetail({}))

    expect(wrapper!.find('.submission-due__date').text()).not.toContain(
      String(new Date().getFullYear()),
    )
  })

  it('names the year when the deadline is in another one', async () => {
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

  it('drops the countdown entirely once the closing time has passed', async () => {
    const detail = buildDetail({})
    detail.deadline.closes_at = new Date(Date.now() - 3_600_000).toISOString()

    await mountPage(detail)

    expect(wrapper!.find('.submission-remaining').exists()).toBe(false)
    expect(wrapper!.find('.submission-due__date').exists()).toBe(true)
  })

  it('marks the countdown as near inside the last day', async () => {
    const detail = buildDetail({})
    detail.deadline.closes_at = new Date(Date.now() + 3 * 3_600_000).toISOString()

    await mountPage(detail)

    expect(wrapper!.find('.submission-remaining').classes()).toContain('is-near')
  })
})

describe('the word counter', () => {
  it('stays hidden until there is something to count', async () => {
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
    await mountPage(buildDetail({ submission: null }))

    await wrapper!.findAll('textarea')[0].setValue('word '.repeat(151))
    await flushPromises()

    const count = wrapper!.find('.submission-count')
    expect(count.exists()).toBe(true)
    expect(count.classes()).toContain('is-over-limit')
  })
})

describe('how the preview loads the document', () => {
  const openPosterTab = async () => {
    await buttonNamed(/Poster/)!.trigger('click')
    await flushPromises()
  }

  it('points the frame at the endpoint rather than fetching the bytes', async () => {
    // fetch() could not read Azure's cross-origin redirect; a frame can.
    await mountPage(buildDetail({ submission: { answers: ANSWERED, poster: POSTER } }))
    await openPosterTab()

    const src = wrapper!.find('.preview-frame').attributes('src') ?? ''
    expect(src).toContain('/files/poster/preview/')
    expect(src).not.toMatch(/^blob:/)
  })

  it('keys the frame to the stored file so a replacement is not served from cache', async () => {
    await mountPage(buildDetail({ submission: { answers: ANSWERED, poster: POSTER } }))
    await openPosterTab()

    const src = wrapper!.find('.preview-frame').attributes('src') ?? ''
    expect(src).toContain(encodeURIComponent(POSTER.storage_key))
  })

  it('shows nothing to preview when no file is attached', async () => {
    await mountPage(buildDetail({ submission: { answers: ANSWERED } }))
    await openPosterTab()

    expect(wrapper!.find('.preview-frame').exists()).toBe(false)
    expect(wrapper!.find('.preview-empty').exists()).toBe(true)
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

  it('keeps the page wrapper, which carries every design token', async () => {
    // Every design token for the section is declared on .content-area.
    await mountPage(buildDetail({ submission: { answers: ANSWERED, poster: POSTER } }))

    expect(wrapper!.find('.content-area').exists()).toBe(true)
  })

  it('carries no masthead, which the group page header already covers', async () => {
    await mountPage(buildDetail({ submission: { answers: ANSWERED } }))

    expect(wrapper!.find('.portal-brand').exists()).toBe(false)
  })

  it('keeps the deadline, which nothing else on the group page states', async () => {
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
