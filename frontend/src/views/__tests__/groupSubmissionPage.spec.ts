import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia, type Pinia } from 'pinia'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createRouter, createWebHashHistory } from 'vue-router'
import { ApiError } from '@/utils/apiError'
import type { SubmissionDetail, SubmissionRecord } from '@/utils/submissionsAPI'
import * as Y from 'yjs'
import { toBase64 } from '@/composables/useSharedDoc'

const saveDraft = vi.fn()
const submitEntry = vi.fn()
const reopenEntry = vi.fn()
const fetchSubmission = vi.fn()
const uploadSubmissionFile = vi.fn()

vi.mock('@/utils/submissionsAPI', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/utils/submissionsAPI')>()
  return {
    ...actual,
    fetchSubmission: (...args: unknown[]) => fetchSubmission(...args),
    saveDraft: (...args: unknown[]) => saveDraft(...args),
    submitEntry: (...args: unknown[]) => submitEntry(...args),
    reopenEntry: (...args: unknown[]) => reopenEntry(...args),
    uploadSubmissionFile: (...args: unknown[]) => uploadSubmissionFile(...args),
  }
})

const fetchFinalist = vi.fn()
vi.mock('@/utils/finalistAPI', () => ({
  fetchFinalist: (...args: unknown[]) => fetchFinalist(...args),
}))

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

const TITLE = 'Coral Rescue Kit'
const CONFIRMED_CHECKLIST = { supervisor_email: true, btf_logo: true, school_logo: true, team_code: true, page_size: true }

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

/** Stands in for the live connection, so no test reaches a real server. */
class FakeSocket {
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

beforeEach(() => {
  FakeSocket.instances = []
  vi.stubGlobal('WebSocket', FakeSocket)
  pinia = createPinia()
  setActivePinia(pinia)
  vi.clearAllMocks()
  fetchFinalist.mockRejectedValue(Object.assign(new Error('Not a finalist'), { status: 403 }))
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
    expect(wrapper!.text()).toContain('0 of 3')
  })

  it('does not count whitespace as an answer', async () => {
    await mountPage(
      buildDetail({ submission: { answers: { solution_purpose: 'Real.', inspiration: '   ' } } }),
    )
    expect(wrapper!.text()).toContain('1 of 3')
  })

  it('reports every required question answered', async () => {
    await mountPage(buildDetail({ submission: { project_title: TITLE, answers: ANSWERED } }))
    expect(wrapper!.text()).toContain('3 of 3')
  })

  it('counts a blank project title as outstanding', async () => {
    await mountPage(buildDetail({ submission: { project_title: '   ', answers: ANSWERED } }))
    expect(wrapper!.text()).toContain('2 of 3')
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
        submission: { project_title: TITLE, answers: { solution_purpose: 'Done.' }, poster: POSTER },
      }),
    )
    await goToLastStep()

    await buttonNamed(/^Submit$/)!.trigger('click')
    await flushPromises()

    expect(wrapper!.find('[aria-current="step"]').text()).toContain('Questions')
    expect(document.activeElement?.id).toBe(QUESTIONS[1].key)
  })

  it('sends the student to the poster step when only the poster is missing', async () => {
    await mountPage(
      buildDetail({ submission: { project_title: TITLE, answers: ANSWERED, poster: null } }),
    )
    await goToLastStep()

    await buttonNamed(/^Submit$/)!.trigger('click')
    await flushPromises()

    expect(wrapper!.find('.submission-message').text()).toContain(
      'Please upload your poster before submitting.',
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

  it('sends the student to the project title when only the title is missing', async () => {
    await mountPage(buildDetail({ submission: { answers: ANSWERED, poster: POSTER } }))
    await goToLastStep()

    await buttonNamed(/^Submit$/)!.trigger('click')
    await flushPromises()

    expect(wrapper!.find('.submission-message').text()).toContain(
      'A project title is required before the entry can be submitted.',
    )
    expect(wrapper!.find('[aria-current="step"]').text()).toContain('Questions')
    expect(document.activeElement?.id).toBe('project-title')
    expect(submitEntry).not.toHaveBeenCalled()
  })

  it('names the title and the poster when both are missing', async () => {
    await mountPage(buildDetail({ submission: { answers: ANSWERED, poster: null } }))
    await goToLastStep()

    await buttonNamed(/^Submit$/)!.trigger('click')
    await flushPromises()

    expect(wrapper!.find('.submission-message').text()).toContain(
      'A project title is required, and no poster has been uploaded.',
    )
  })

  it('saves the project title with the draft', async () => {
    const detail = buildDetail({ submission: { answers: ANSWERED } })
    await mountPage(detail)
    saveDraft.mockResolvedValue({ deadline: detail.deadline, submission: detail.submission! })

    await wrapper!.find('#project-title').setValue(TITLE)
    await new Promise((resolve) => setTimeout(resolve, 2200))
    await flushPromises()

    expect(saveDraft).toHaveBeenCalledWith('1', expect.objectContaining({ project_title: TITLE }))
  })

  it('caps the project title at 150 characters', async () => {
    await mountPage(buildDetail({ submission: { answers: ANSWERED } }))

    expect(wrapper!.find('#project-title').attributes('maxlength')).toBe('150')
  })

  it('calls the API when submit is pressed', async () => {
    const detail = buildDetail({
      submission: { project_title: TITLE, answers: ANSWERED, poster: POSTER, poster_checklist: CONFIRMED_CHECKLIST },
    })
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
    expect(wrapper!.find('#project-title').attributes('disabled')).toBeDefined()
  })

  it('does not offer submit or uploads at all', async () => {
    await mountPage(
      buildDetail({ isOpen: false, submission: { answers: ANSWERED, poster: POSTER } }),
    )
    await goToLastStep()
    expect(buttonNamed(/^Submit$/)).toBeUndefined()
    expect(buttonNamed(/^(Upload|Replace|Remove)$/)).toBeUndefined()
  })

  it('shuts the preview of a file that was never uploaded', async () => {
    await mountPage(buildDetail({ isOpen: false, submission: { answers: ANSWERED } }))
    await buttonNamed(/Poster/)!.trigger('click')
    await flushPromises()

    const toggle = wrapper!.find('[data-testid="toggle-poster-preview"]')
    expect(toggle.attributes('disabled')).toBeDefined()
    expect(toggle.attributes('aria-expanded')).toBe('false')
    expect(wrapper!.find('#poster-preview-body').isVisible()).toBe(false)

    await toggle.trigger('click')
    expect(wrapper!.find('#poster-preview-body').isVisible()).toBe(false)
  })

  it('keeps the preview of an uploaded file available once closed', async () => {
    const detail = submittedDetail()
    detail.deadline.is_open = false
    await mountPage(detail)
    await buttonNamed(/Poster/)!.trigger('click')
    await flushPromises()

    const toggle = wrapper!.find('[data-testid="toggle-poster-preview"]')
    expect(toggle.attributes('disabled')).toBeUndefined()
    expect(wrapper!.find('#poster-preview-body').isVisible()).toBe(true)
  })

  it('leaves an empty preview open while uploads are still possible', async () => {
    await mountPage(buildDetail({ submission: { answers: ANSWERED } }))
    await buttonNamed(/Poster/)!.trigger('click')
    await flushPromises()

    expect(wrapper!.find('[data-testid="toggle-poster-preview"]').attributes('disabled')).toBeUndefined()
  })

  it('hides an empty prototype link once it can no longer be edited', async () => {
    await mountPage(buildDetail({ isOpen: false, submission: { answers: ANSWERED } }))

    expect(wrapper!.find('#prototype-url').exists()).toBe(false)
  })

  it('still shows a prototype link that was given', async () => {
    const detail = submittedDetail()
    detail.deadline.is_open = false
    detail.submission!.submitted_prototype_url = 'https://example.com/demo'
    await mountPage(detail)

    const link = wrapper!.find('#prototype-url')
    expect((link.element as HTMLInputElement).value).toBe('https://example.com/demo')
    expect(link.attributes('disabled')).toBeDefined()
  })

  it('keeps the empty link box while the entry is editable', async () => {
    await mountPage(buildDetail({ submission: { answers: ANSWERED } }))

    expect(wrapper!.find('#prototype-url').exists()).toBe(true)
  })




  it('brings the form back when an extension reopens the entry', async () => {
    await mountPage(buildDetail({ isOpen: false, submission: null }))
    expect(wrapper!.find('textarea').attributes('disabled')).toBeDefined()

    fetchSubmission.mockResolvedValue(buildDetail({ isOpen: true, submission: null }))
    window.dispatchEvent(new Event('focus'))
    await flushPromises()

    expect(wrapper!.find('textarea').attributes('disabled')).toBeUndefined()
    expect(buttonNamed(/^Submit$/)).toBeTruthy()
  })
})

describe('a deadline changed while the page is open', () => {
  it('reopens a closed page when the window regains focus', async () => {
    await mountPage(buildDetail({ isOpen: false, submission: null }))
    expect(wrapper!.find('textarea').attributes('disabled')).toBeDefined()

    fetchSubmission.mockResolvedValue(buildDetail({ isOpen: true, submission: null }))
    window.dispatchEvent(new Event('focus'))
    await flushPromises()

    expect(wrapper!.find('textarea').attributes('disabled')).toBeUndefined()
    expect(wrapper!.find('.status-line').text()).not.toContain('Submissions are closed')
  })

  it('keeps unsaved typing when the deadline moves while open', async () => {
    await mountPage(buildDetail({ submission: { answers: ANSWERED } }))
    await wrapper!.findAll('textarea')[0].setValue('Typed but not saved yet.')

    const moved = buildDetail({ submission: { answers: { solution_purpose: 'Server copy.' } } })
    moved.deadline.closes_at = new Date(Date.now() + 9 * 86_400_000).toISOString()
    fetchSubmission.mockResolvedValue(moved)
    window.dispatchEvent(new Event('focus'))
    await flushPromises()

    expect((wrapper!.findAll('textarea')[0].element as HTMLTextAreaElement).value).toBe(
      'Typed but not saved yet.',
    )
  })

  it('checks again when the Submission tab is opened', async () => {
    fetchSubmission.mockResolvedValue(buildDetail({ isOpen: false, submission: null }))
    const router = createRouter({ history: createWebHashHistory(), routes: ROUTES })
    await router.push('/groups/1/submission')
    await router.isReady()
    wrapper = mount(GroupSubmissionPage, { global: { plugins: [router, pinia] } })
    await flushPromises()

    fetchSubmission.mockResolvedValue(buildDetail({ isOpen: true, submission: null }))
    await router.push('/groups/1')
    await router.push('/groups/1/submission')
    await flushPromises()

    expect(fetchSubmission).toHaveBeenCalledTimes(2)
    expect(wrapper!.find('textarea').attributes('disabled')).toBeUndefined()
  })
})

describe('dropping a file onto a slot', () => {
  const pdf = (bytes = 2048) =>
    new File([new Uint8Array(bytes)], 'poster.pdf', { type: 'application/pdf' })
  const drop = (slot: string, file: File) =>
    wrapper!.find(`[data-testid="drop-${slot}"]`).trigger('drop', {
      dataTransfer: { files: [file], types: ['Files'] },
    })

  it('uploads a dropped poster through the same path as the file picker', async () => {
    const detail = buildDetail({ submission: { answers: ANSWERED } })
    await mountPage(detail)
    uploadSubmissionFile.mockResolvedValue({ deadline: detail.deadline, submission: detail.submission })
    const file = pdf()

    await drop('poster', file)
    await flushPromises()

    expect(uploadSubmissionFile).toHaveBeenCalledWith('1', 'poster', file, expect.any(Function))
  })

  it('accepts drops on the report and prototype slots too', async () => {
    const detail = buildDetail({ submission: { answers: ANSWERED } })
    await mountPage(detail)
    uploadSubmissionFile.mockResolvedValue({ deadline: detail.deadline, submission: detail.submission })

    await drop('report', pdf())
    await flushPromises()
    await drop('prototype', new File(['zip'], 'model.zip'))
    await flushPromises()

    expect(uploadSubmissionFile.mock.calls.map((call) => call[1])).toEqual(['report', 'prototype'])
  })

  it('refuses an oversized dropped file before uploading it', async () => {
    await mountPage(buildDetail({ submission: { answers: ANSWERED } }))

    await drop('poster', pdf(11_000_000))
    await flushPromises()

    expect(uploadSubmissionFile).not.toHaveBeenCalled()
    expect(wrapper!.find('.submission-message').text()).toContain('over the')
  })

  it('ignores a drop once submissions are closed', async () => {
    await mountPage(buildDetail({ isOpen: false, submission: { answers: ANSWERED } }))

    await drop('poster', pdf())
    await flushPromises()

    expect(uploadSubmissionFile).not.toHaveBeenCalled()
  })

  it('ignores a drop on a locked entry', async () => {
    await mountPage(submittedDetail())

    await drop('poster', pdf())
    await flushPromises()

    expect(uploadSubmissionFile).not.toHaveBeenCalled()
  })

  it('still uploads a file chosen with the picker', async () => {
    const detail = buildDetail({ submission: { answers: ANSWERED } })
    await mountPage(detail)
    uploadSubmissionFile.mockResolvedValue({ deadline: detail.deadline, submission: detail.submission })
    const file = pdf()
    const input = wrapper!.find('[data-testid="drop-poster"] input[type="file"]')
    Object.defineProperty(input.element, 'files', { value: [file] })

    await input.trigger('change')
    await flushPromises()

    expect(uploadSubmissionFile).toHaveBeenCalledWith('1', 'poster', file, expect.any(Function))
  })

  it('uploads a file dropped onto the preview panel', async () => {
    const detail = buildDetail({ submission: { answers: ANSWERED } })
    await mountPage(detail)
    uploadSubmissionFile.mockResolvedValue({ deadline: detail.deadline, submission: detail.submission })

    for (const slot of ['poster', 'report']) {
      await wrapper!
        .find(`[data-testid="drop-${slot}"] .preview-panel`)
        .trigger('drop', { dataTransfer: { files: [pdf()], types: ['Files'] } })
      await flushPromises()
    }

    expect(uploadSubmissionFile.mock.calls.map((call) => call[1])).toEqual(['poster', 'report'])
  })

  it('lets drags pass through the preview frame while a file is dragged', async () => {
    await mountPage(buildDetail({ submission: { answers: ANSWERED } }))
    const root = wrapper!.find('.content-area')

    window.dispatchEvent(Object.assign(new Event('dragenter'), { dataTransfer: { types: ['Files'] } }))
    await flushPromises()
    expect(root.classes()).toContain('is-dragging-file')

    window.dispatchEvent(new Event('drop'))
    await flushPromises()
    expect(root.classes()).not.toContain('is-dragging-file')
  })

  it('highlights the slot while a file is dragged over it', async () => {
    await mountPage(buildDetail({ submission: { answers: ANSWERED } }))
    const slot = wrapper!.find('[data-testid="drop-poster"]')

    await slot.trigger('dragover', { dataTransfer: { types: ['Files'], dropEffect: 'none' } })
    expect(slot.classes()).toContain('is-drop-target')

    await slot.trigger('dragleave', { relatedTarget: null })
    expect(slot.classes()).not.toContain('is-drop-target')
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

describe('the poster checklist', () => {
  const withPoster = (checklist: Record<string, boolean>, warnings: { code: string; message: string }[] = []) =>
    buildDetail({
      submission: {
        project_title: TITLE,
        answers: ANSWERED,
        poster: POSTER,
        poster_checklist: checklist,
        poster_checks: { has_text: true, unreadable: false, warnings: warnings.map((w) => ({ ...w, passed: false })) },
      },
    })
  const goToPoster = async () => {
    await buttonNamed(/Poster/)!.trigger('click')
    await flushPromises()
  }
  const box = (key: string) => wrapper!.find(`#checklist-${key}`).element as HTMLInputElement

  it('arrives with detected items ticked once a poster is attached', async () => {
    await mountPage(withPoster({ team_code: true, page_size: true }))
    await goToPoster()

    expect(box('team_code').checked).toBe(true)
    expect(box('btf_logo').checked).toBe(false)
    expect(wrapper!.find('[data-testid="poster-checklist"]').text()).toContain('2 of 5 confirmed')
  })

  it('is shown but cannot be ticked before a poster is attached', async () => {
    await mountPage(buildDetail({ submission: { answers: ANSWERED } }))
    await goToPoster()

    expect(wrapper!.findAll('[data-testid="poster-checklist"] input')).toHaveLength(5)
    expect(box('btf_logo').disabled).toBe(true)
  })

  it('saves only the ticks that changed', async () => {
    const detail = withPoster({ team_code: true })
    await mountPage(detail)
    saveDraft.mockResolvedValue({ deadline: detail.deadline, submission: detail.submission! })
    await goToPoster()

    await wrapper!.find('#checklist-btf_logo').setValue(true)
    await new Promise((resolve) => setTimeout(resolve, 2200))
    await flushPromises()

    expect(saveDraft.mock.calls.at(-1)![1].poster_checklist).toEqual({ btf_logo: true })
  })

  it('takes the whole platform to the top when an upload is refused', async () => {
    await mountPage(buildDetail({ submission: { answers: ANSWERED } }))
    uploadSubmissionFile.mockRejectedValue(new Error('Your poster must be in portrait orientation.'))
    await goToPoster()
    const scroller = wrapper!.element.parentElement!
    Object.defineProperty(scroller, 'scrollTop', { configurable: true, value: 400 })
    scroller.scrollTo = vi.fn()
    const windowScroll = vi.spyOn(window, 'scrollTo').mockImplementation(() => {})

    await wrapper!.find('[data-testid="drop-poster"]').trigger('drop', {
      dataTransfer: { files: [new File(['%PDF'], 'poster.pdf', { type: 'application/pdf' })], types: ['Files'] },
    })
    await flushPromises()

    expect(wrapper!.find('.submission-message').text()).toContain('portrait orientation')
    expect(scroller.scrollTo).toHaveBeenCalledWith({ top: 0, behavior: 'smooth' })
    expect(windowScroll).toHaveBeenCalledWith({ top: 0, behavior: 'smooth' })
    windowScroll.mockRestore()
  })

  it('holds Submit until every item is ticked', async () => {
    await mountPage(withPoster({ ...CONFIRMED_CHECKLIST, btf_logo: false }))
    await goToLastStep()

    await buttonNamed(/^Submit$/)!.trigger('click')
    await flushPromises()

    expect(wrapper!.find('.submission-message').text()).toContain(
      'Please tick every item in the poster checklist before submitting.'
    )
    expect(document.activeElement?.id).toBe('checklist-btf_logo')
    expect(submitEntry).not.toHaveBeenCalled()
  })
})

describe('co-editing', () => {
  const LIVE = { title: TITLE, 'answer:inspiration': 'Live text.', 'answer:solution_purpose': ANSWERED.solution_purpose }
  const coedited = (isOpen = true): SubmissionDetail => ({
    ...buildDetail({
      isOpen,
      submission: { project_title: TITLE, answers: ANSWERED, poster: POSTER, poster_checklist: CONFIRMED_CHECKLIST, stage: 'in_progress' },
    }),
    coediting: true,
  })
  const socket = () => FakeSocket.instances[FakeSocket.instances.length - 1]!
  const sentOfType = (type: string) => (socket().sent as Array<{ type: string; id?: number }>).filter((m) => m.type === type)
  const receive = (message: object) => socket().onmessage?.({ data: JSON.stringify(message) })
  const box = () => wrapper!.find('#inspiration')

  /** Plays the server: the page connects and receives the live document. */
  async function connect(editable = true, texts: Record<string, string> = LIVE) {
    const truth = new Y.Doc()
    Object.entries(texts).forEach(([name, value]) => truth.getText(name).insert(0, value))
    socket().readyState = FakeSocket.OPEN
    socket().onopen?.()
    receive({ type: 'hello', user: { id: 1, name: 'Me' } })
    receive({
      type: 'doc-state',
      update: toBase64(Y.encodeStateAsUpdate(truth)),
      vector: toBase64(Y.encodeStateVector(truth)),
      full: false,
      editable,
    })
    await flushPromises()
    return truth
  }

  it('keeps the boxes read-only until the live answers arrive', async () => {
    await mountPage(coedited())
    expect(box().attributes('disabled')).toBeDefined()
    expect(wrapper!.find('[data-testid="coedit-note"]').text()).toContain('Connecting')

    await connect()

    expect(box().attributes('disabled')).toBeUndefined()
    expect(wrapper!.find('[data-testid="coedit-note"]').exists()).toBe(false)
  })

  it('shows the live answers, which are newer than the saved copy', async () => {
    await mountPage(coedited())
    await connect()

    expect((box().element as HTMLTextAreaElement).value).toBe('Live text.')
  })

  it('sends typing into the shared document, and never saves answers from the page', async () => {
    await mountPage(coedited())
    await connect()

    await box().setValue('Live text. More.')
    await new Promise((resolve) => setTimeout(resolve, 2200))
    await flushPromises()

    expect(sentOfType('doc-update').length).toBeGreaterThan(0)
    expect(saveDraft).not.toHaveBeenCalled()
  })

  it("types a teammate's text out in a box this person is not in", async () => {
    const frames: FrameRequestCallback[] = []
    let now = 0
    const realFrame = window.requestAnimationFrame
    window.requestAnimationFrame = (callback: FrameRequestCallback) => frames.push(callback)
    const clock = vi.spyOn(performance, 'now').mockImplementation(() => now)
    try {
      await mountPage(coedited())
      const truth = await connect()
      const before = Y.encodeStateVector(truth)
      truth.getText('answer:inspiration').insert(10, ' From Ben.')

      receive({ type: 'doc-update', update: toBase64(Y.encodeStateAsUpdate(truth, before)) })
      await flushPromises()
      expect((box().element as HTMLTextAreaElement).value).toBe('Live text.')
      while (frames.length) {
        now += 16
        frames.splice(0).forEach((callback) => callback(now))
      }
      await flushPromises()

      expect((box().element as HTMLTextAreaElement).value).toBe('Live text. From Ben.')
    } finally {
      window.requestAnimationFrame = realFrame
      clock.mockRestore()
    }
  })

  it("shows a teammate's typing at once in the box this person is in", async () => {
    await mountPage(coedited())
    const truth = await connect()
    ;(box().element as HTMLTextAreaElement).focus()
    const before = Y.encodeStateVector(truth)
    truth.getText('answer:inspiration').insert(10, ' From Ben.')

    receive({ type: 'doc-update', update: toBase64(Y.encodeStateAsUpdate(truth, before)) })
    await flushPromises()

    expect((box().element as HTMLTextAreaElement).value).toBe('Live text. From Ben.')
  })

  it("shares where this person's cursor is, and clears it on leaving the box", async () => {
    await mountPage(coedited())
    await connect()
    const cursors = () => socket().sent as Array<{ type: string; field?: string; at?: string | null; typed?: boolean }>

    ;(box().element as HTMLTextAreaElement).focus()
    await flushPromises()
    const shared = cursors().filter((m) => m.type === 'cursor')
    expect(shared).toHaveLength(1)
    expect(shared[0]).toMatchObject({ field: 'inspiration', typed: false })
    expect(typeof shared[0]!.at).toBe('string')

    await new Promise((resolve) => setTimeout(resolve, 250))
    ;(box().element as HTMLTextAreaElement).blur()
    await new Promise((resolve) => setTimeout(resolve, 250))

    expect(cursors().filter((m) => m.type === 'cursor').at(-1)).toMatchObject({ field: 'inspiration', at: null })
  })

  it('never locks a box while a teammate types in it', async () => {
    await mountPage(coedited())
    await connect()

    receive({ type: 'typing', user: { id: 9, name: 'Ben' }, field: 'inspiration', typing: true })
    await flushPromises()

    expect(box().attributes('disabled')).toBeUndefined()
    expect(wrapper!.text()).toContain('Ben is typing')
  })

  it('says so when the server will not take edits', async () => {
    await mountPage(coedited())
    await connect(false)

    expect(box().attributes('disabled')).toBeDefined()
    expect(wrapper!.find('[data-testid="coedit-note"]').text()).toContain("can't be edited right now")
  })

  it('saves the live answers before submitting', async () => {
    const detail = coedited()
    await mountPage(detail)
    await connect()
    submitEntry.mockResolvedValue({ deadline: detail.deadline, submission: submittedDetail().submission! })
    await goToLastStep()

    await buttonNamed(/^Submit$/)!.trigger('click')
    await flushPromises()
    const flush = sentOfType('doc-flush')[0]!
    expect(submitEntry).not.toHaveBeenCalled()
    receive({ type: 'doc-flushed', id: flush.id, ok: true })
    await flushPromises()

    expect(submitEntry).toHaveBeenCalled()
  })

  it('leaves a box alone while a word is being composed, whatever else changes on the page', async () => {
    await mountPage(coedited())
    await connect()
    const element = box().element as HTMLTextAreaElement

    await box().trigger('compositionstart')
    element.value = 'Live text.日本'
    receive({ type: 'typing', user: { id: 9, name: 'Ben' }, field: 'inspiration', typing: true })
    await flushPromises()

    expect(element.value).toBe('Live text.日本')
  })

  describe('without the live connection', () => {
    const note = () => wrapper!.find('[data-testid="coedit-note"]')

    /** The page opens but the live connection never gets through, and ten seconds pass. */
    async function blocked(detail = coedited()) {
      vi.useFakeTimers()
      saveDraft.mockResolvedValue({ deadline: detail.deadline, submission: detail.submission! })
      await mountPage(detail)
      expect(box().attributes('disabled')).toBeDefined()
      vi.advanceTimersByTime(10_000)
      await flushPromises()
      return detail
    }

    afterEach(() => {
      vi.useRealTimers()
    })

    it('lets the student type after ten seconds, saving as without co-editing', async () => {
      await blocked()

      expect(box().attributes('disabled')).toBeUndefined()
      expect(note().text()).toContain("Live editing isn't available on this connection.")
      await box().setValue('Typed offline.')
      vi.advanceTimersByTime(2000)
      await flushPromises()

      expect(saveDraft).toHaveBeenCalledWith(
        '1',
        expect.objectContaining({ answers: { inspiration: 'Typed offline.' }, live_unavailable: true })
      )
    })

    it('saves an answer over its word limit as typed, as live editing does', async () => {
      await blocked()
      const long = Array.from({ length: 151 }, () => 'word').join(' ')

      await box().setValue(long)
      vi.advanceTimersByTime(2000)
      await flushPromises()

      expect(saveDraft).toHaveBeenCalledWith('1', expect.objectContaining({ answers: { inspiration: long }, live_unavailable: true }))
    })

    it("brings in the team's saved changes every ten seconds, leaving the box being edited alone", async () => {
      const detail = await blocked()
      fetchSubmission.mockResolvedValue({
        ...detail,
        submission: {
          ...detail.submission!,
          answers: { ...detail.submission!.answers, inspiration: 'From Ben.', solution_purpose: 'Theirs.' }
        }
      })
      vi.advanceTimersByTime(9_000)
      // Typed a moment before the refresh, so not yet saved.
      await wrapper!.find('#solution_purpose').setValue('Mine, not saved yet.')

      vi.advanceTimersByTime(1_000)
      await flushPromises()

      expect((box().element as HTMLTextAreaElement).value).toBe('From Ben.')
      expect((wrapper!.find('#solution_purpose').element as HTMLTextAreaElement).value).toBe('Mine, not saved yet.')
    })

    it('saves what was typed, then goes back to live editing once the connection is made', async () => {
      await blocked()
      await box().setValue('Typed offline.')

      await connect()
      await flushPromises()

      // The returning shared copy never replaces what is on screen before it is saved.
      expect((box().element as HTMLTextAreaElement).value).toBe('Typed offline.')

      expect(saveDraft).toHaveBeenCalledWith(
        '1',
        expect.objectContaining({ answers: { inspiration: 'Typed offline.' }, live_unavailable: true })
      )
      expect(socket().sent.at(-1)).toMatchObject({ type: 'doc-sync' })
      expect(note().exists() && note().text()).not.toContain("Live editing isn't available")
    })

    it('submits without offering the last saved answers, since its typing is saved directly', async () => {
      const detail = await blocked()
      submitEntry.mockResolvedValue({ deadline: detail.deadline, submission: submittedDetail().submission! })
      await goToLastStep()

      await buttonNamed(/^Submit$/)!.trigger('click')
      await flushPromises()

      expect(wrapper!.find('[data-testid="confirm-dialog"]').exists()).toBe(false)
      expect(submitEntry).toHaveBeenCalled()
    })

    it('never switches an admin, who saves privately anyway', async () => {
      await blocked({ ...coedited(), admin_access: true })

      expect(note().exists() && note().text()).not.toContain("Live editing isn't available")
    })
  })

  async function submitWithFailedSave() {
    const flush = sentOfType('doc-flush')[0]!
    receive({ type: 'doc-flushed', id: flush.id, ok: false })
    await flushPromises()
  }

  it('offers to submit the last saved answers when the live ones could not be saved', async () => {
    const detail = coedited()
    await mountPage(detail)
    await connect()
    submitEntry.mockResolvedValue({ deadline: detail.deadline, submission: submittedDetail().submission! })
    await goToLastStep()

    await buttonNamed(/^Submit$/)!.trigger('click')
    await flushPromises()
    await submitWithFailedSave()
    expect(wrapper!.find('[data-testid="confirm-dialog"]').text()).toContain('Submit without your latest typing?')
    expect(submitEntry).not.toHaveBeenCalled()
    await wrapper!.find('[data-testid="confirm-dialog-confirm"]').trigger('click')
    await flushPromises()

    expect(submitEntry).toHaveBeenCalled()
  })

  it('submits nothing when the offer is declined', async () => {
    await mountPage(coedited())
    await connect()
    await goToLastStep()

    await buttonNamed(/^Submit$/)!.trigger('click')
    await flushPromises()
    await submitWithFailedSave()
    await wrapper!.find('[data-testid="confirm-dialog-cancel"]').trigger('click')
    await flushPromises()

    expect(submitEntry).not.toHaveBeenCalled()
  })

  it('makes the same offer before the live answers have even arrived', async () => {
    const detail = coedited()
    await mountPage(detail)
    submitEntry.mockResolvedValue({ deadline: detail.deadline, submission: submittedDetail().submission! })
    await goToLastStep()

    await buttonNamed(/^Submit$/)!.trigger('click')
    await flushPromises()

    expect(sentOfType('doc-flush')).toHaveLength(0)
    expect(wrapper!.find('[data-testid="confirm-dialog"]').text()).toContain('Submit your answers as last saved?')
  })

  it('leaves an admin editing privately, saving through the page as before', async () => {
    const detail = { ...coedited(false), admin_access: true }
    await mountPage(detail)
    saveDraft.mockResolvedValue({ deadline: detail.deadline, submission: detail.submission! })
    await wrapper!.find('[data-testid="admin-edit"]').trigger('click')
    await flushPromises()

    await box().setValue('Fixed by the programme.')
    await wrapper!.find('[data-testid="admin-save"]').trigger('click')
    await flushPromises()

    expect(saveDraft.mock.calls.at(-1)![1].answers).toEqual({ inspiration: 'Fixed by the programme.' })
    expect(sentOfType('doc-update')).toHaveLength(0)
  })
})

describe('the admin view', () => {
  const asAdmin = (detail: SubmissionDetail): SubmissionDetail => ({ ...detail, admin_access: true })
  const draft = (isOpen = false, poster_checklist: Record<string, boolean> = CONFIRMED_CHECKLIST) =>
    asAdmin(
      buildDetail({ isOpen, submission: { project_title: TITLE, answers: ANSWERED, poster: POSTER, poster_checklist, stage: 'in_progress' } })
    )
  const submitted = (isOpen = false) => {
    const detail = submittedDetail()
    detail.deadline.is_open = isOpen
    detail.submission!.project_title = TITLE
    detail.submission!.submitted_project_title = TITLE
    detail.submission!.poster_checklist = CONFIRMED_CHECKLIST
    return asAdmin(detail)
  }
  const click = async (testId: string) => {
    await wrapper!.find(`[data-testid="${testId}"]`).trigger('click')
    await flushPromises()
  }
  const box = () => wrapper!.find('#inspiration')
  const result = (detail: SubmissionDetail) => ({ deadline: detail.deadline, submission: detail.submission! })

  it('opens read-only in every state, with its own bar instead of the team status', async () => {
    await mountPage(draft(true))

    expect(box().attributes('disabled')).toBeDefined()
    const bar = wrapper!.find('[data-testid="admin-bar"]').text()
    expect(bar).toContain('BTF1')
    expect(bar).toContain('Draft, not submitted')
    expect(bar).toContain('Can edit until')
    expect(wrapper!.find('.status-line').exists()).toBe(false)
    expect(buttonNamed(/^Submit$/)).toBeUndefined()
  })

  it('edits without saving anything until Save', async () => {
    await mountPage(draft())
    await click('admin-edit')

    await box().setValue('Fixed by the programme.')
    await new Promise((resolve) => setTimeout(resolve, 2200))
    await flushPromises()

    expect(saveDraft).not.toHaveBeenCalled()
    expect(wrapper!.find('[data-testid="admin-bar"]').text()).toContain('Unsaved changes')
  })

  it("saves to the team's draft on Save, then goes back to read-only", async () => {
    const detail = draft()
    await mountPage(detail)
    saveDraft.mockResolvedValue(result(detail))
    await click('admin-edit')
    await box().setValue('Fixed by the programme.')

    await click('admin-save')

    expect(saveDraft.mock.calls.at(-1)![1].answers).toEqual({ inspiration: 'Fixed by the programme.' })
    expect(wrapper!.find('.submission-message').text()).toContain("Saved to BTF1's draft.")
    expect(box().attributes('disabled')).toBeDefined()
  })

  it('asks before reopening a submitted entry while the round is open', async () => {
    const detail = submitted(true)
    await mountPage(detail)
    reopenEntry.mockResolvedValue(result(reopenedDetail()))
    saveDraft.mockResolvedValue(result(reopenedDetail()))
    await click('admin-edit')
    await box().setValue('Fixed by the programme.')

    await click('admin-save')
    expect(wrapper!.find('[data-testid="confirm-dialog"]').text()).toContain('Reopen for the team?')
    await click('confirm-dialog-confirm')

    expect(reopenEntry).toHaveBeenCalled()
    expect(saveDraft).toHaveBeenCalled()
  })

  it('submits a submitted entry for the team after the deadline without reopening it', async () => {
    const detail = submitted()
    await mountPage(detail)
    saveDraft.mockResolvedValue(result(detail))
    submitEntry.mockResolvedValue(result(detail))
    await click('admin-edit')
    await box().setValue('Fixed by the programme.')

    await click('admin-submit')
    expect(wrapper!.find('[data-testid="confirm-dialog"]').text()).toContain('This becomes their latest submission')
    await click('confirm-dialog-confirm')

    expect(submitEntry).toHaveBeenCalled()
    expect(reopenEntry).not.toHaveBeenCalled()
    expect(wrapper!.find('.submission-message').text()).toContain('Submitted for BTF1.')
  })

  it('needs every checklist item ticked to submit, without the template checks', async () => {
    await mountPage(draft(false, { ...CONFIRMED_CHECKLIST, btf_logo: false }))
    await click('admin-edit')

    await click('admin-submit')

    expect(wrapper!.find('.submission-message').text()).toContain('Please tick every item in the poster checklist')
    expect(submitEntry).not.toHaveBeenCalled()
  })

  it('starts the checklist afresh for a new poster, and sends every tick with it', async () => {
    const detail = draft()
    await mountPage(detail)
    uploadSubmissionFile.mockResolvedValue(result(detail))
    saveDraft.mockResolvedValue(result(detail))
    submitEntry.mockResolvedValue(result(submitted()))
    await click('admin-edit')
    await buttonNamed(/Poster/)!.trigger('click')
    await flushPromises()
    await wrapper!.find('[data-testid="drop-poster"]').trigger('drop', {
      dataTransfer: { files: [new File(['%PDF'], 'fixed.pdf', { type: 'application/pdf' })], types: ['Files'] },
    })
    await flushPromises()
    expect((wrapper!.find('#checklist-team_code').element as HTMLInputElement).checked).toBe(false)

    for (const key of Object.keys(CONFIRMED_CHECKLIST)) await wrapper!.find(`#checklist-${key}`).setValue(true)
    await click('admin-submit')
    await click('confirm-dialog-confirm')

    expect(saveDraft.mock.calls.at(-1)![1].poster_checklist).toEqual(CONFIRMED_CHECKLIST)
    expect(submitEntry).toHaveBeenCalled()
  })

  it('holds an uploaded file until Save', async () => {
    const detail = draft()
    await mountPage(detail)
    uploadSubmissionFile.mockResolvedValue(result(detail))
    saveDraft.mockResolvedValue(result(detail))
    await click('admin-edit')
    await buttonNamed(/Poster/)!.trigger('click')
    await flushPromises()

    await wrapper!.find('[data-testid="drop-poster"]').trigger('drop', {
      dataTransfer: { files: [new File(['%PDF'], 'fixed.pdf', { type: 'application/pdf' })], types: ['Files'] },
    })
    await flushPromises()
    expect(uploadSubmissionFile).not.toHaveBeenCalled()
    expect(wrapper!.text()).toContain('not saved yet')

    await click('admin-save')

    expect(uploadSubmissionFile).toHaveBeenCalledWith('1', 'poster', expect.any(File), expect.any(Function))
  })

  it('discards changes after asking', async () => {
    await mountPage(draft())
    await click('admin-edit')
    await box().setValue('Not wanted.')

    await click('admin-discard')
    await click('confirm-dialog-confirm')

    expect((box().element as HTMLTextAreaElement).value).toBe(ANSWERED.inspiration)
    expect(box().attributes('disabled')).toBeDefined()
  })

  it('warns before overwriting an answer the team changed meanwhile', async () => {
    await mountPage(draft())
    await click('admin-edit')
    await box().setValue('Fixed by the programme.')
    fetchSubmission.mockResolvedValue(
      asAdmin(buildDetail({ submission: { project_title: TITLE, answers: { ...ANSWERED, inspiration: 'The team’s edit' }, poster: POSTER } }))
    )

    await click('admin-save')

    expect(wrapper!.find('[data-testid="confirm-dialog"]').text()).toContain('Overwrite a conflicting change?')
    await click('confirm-dialog-cancel')
    expect(saveDraft).not.toHaveBeenCalled()
  })

  const savedByTeam = (inspiration: string, isOpen = false) =>
    asAdmin(buildDetail({ isOpen, submission: { project_title: TITLE, answers: { ...ANSWERED, inspiration }, poster: POSTER, stage: 'in_progress' } }))

  it("starts editing from the team's latest saved answers", async () => {
    await mountPage(draft())
    fetchSubmission.mockResolvedValue(savedByTeam('Saved by the team since.'))

    await click('admin-edit')

    expect((box().element as HTMLTextAreaElement).value).toBe('Saved by the team since.')
  })

  it("shows the team's latest saved answers on leaving edit mode", async () => {
    await mountPage(draft())
    await click('admin-edit')
    fetchSubmission.mockResolvedValue(savedByTeam('Saved by the team while you edited.'))

    await click('admin-done')

    expect((box().element as HTMLTextAreaElement).value).toBe('Saved by the team while you edited.')
  })

  it('catches up on what the team saved while viewing', async () => {
    await mountPage(draft(true))
    const socket = FakeSocket.instances[FakeSocket.instances.length - 1]!
    socket.readyState = FakeSocket.OPEN
    socket.onopen?.()
    const fromBen = (message: object) =>
      socket.onmessage?.({ data: JSON.stringify({ user: { id: 9, name: 'Ben' }, ...message }) })
    fetchSubmission.mockResolvedValue(savedByTeam('Ben’s saved answer.', true))

    fromBen({ type: 'typing', field: 'inspiration', typing: true })
    fromBen({ type: 'typing', field: 'inspiration', typing: false })
    await new Promise((resolve) => setTimeout(resolve, 2700))
    await flushPromises()

    expect((box().element as HTMLTextAreaElement).value).toBe('Ben’s saved answer.')
  })

  it('asks to reopen if the team submitted while you were editing, in an open round', async () => {
    await mountPage(draft(true))
    await click('admin-edit')
    await box().setValue('Fixed by the programme.')
    fetchSubmission.mockResolvedValue(submitted(true))

    await click('admin-save')

    expect(wrapper!.find('[data-testid="confirm-dialog"]').text()).toContain('Reopen for the team?')
    await click('confirm-dialog-cancel')
    expect(saveDraft).not.toHaveBeenCalled()
  })

  it('keeps changes off a submission the team made while you were editing, after the deadline', async () => {
    await mountPage(draft())
    await click('admin-edit')
    await box().setValue('Fixed by the programme.')
    const teamSubmitted = submitted()
    fetchSubmission.mockResolvedValue(teamSubmitted)
    saveDraft.mockResolvedValue(result(teamSubmitted))

    await click('admin-save')

    expect(reopenEntry).not.toHaveBeenCalled()
    expect(wrapper!.find('.submission-message').text()).toContain('BTF1 still sees their submission until you submit.')
  })

  it('shows a link the team just added while viewing', async () => {
    await mountPage(draft(true))
    const socket = FakeSocket.instances[FakeSocket.instances.length - 1]!
    socket.readyState = FakeSocket.OPEN
    socket.onopen?.()
    fetchSubmission.mockResolvedValue(
      asAdmin(buildDetail({ isOpen: true, submission: { project_title: TITLE, answers: ANSWERED, poster: POSTER, prototype_url: 'https://example.com/demo', stage: 'in_progress' } }))
    )

    socket.onmessage?.({ data: JSON.stringify({ type: 'changed', item: 'link', user: { id: 9, name: 'Ben' } }) })
    await flushPromises()

    expect((wrapper!.find('#prototype-url').element as HTMLInputElement).value).toBe('https://example.com/demo')
  })

  it('treats a poster the team replaced meanwhile as a conflict', async () => {
    await mountPage(draft())
    await click('admin-edit')
    await buttonNamed(/Poster/)!.trigger('click')
    await flushPromises()
    await wrapper!.find('[data-testid="drop-poster"]').trigger('drop', {
      dataTransfer: { files: [new File(['%PDF'], 'fixed.pdf', { type: 'application/pdf' })], types: ['Files'] },
    })
    await flushPromises()
    const replaced = { ...POSTER, storage_key: 'x/team-new.pdf' }
    fetchSubmission.mockResolvedValue(
      asAdmin(buildDetail({ submission: { project_title: TITLE, answers: ANSWERED, poster: replaced, stage: 'in_progress' } }))
    )

    await click('admin-save')

    expect(wrapper!.find('[data-testid="confirm-dialog"]').text()).toContain('Overwrite a conflicting change?')
    await click('confirm-dialog-cancel')
    expect(uploadSubmissionFile).not.toHaveBeenCalled()
  })

  it('says when a submitted entry has saved changes not yet submitted', async () => {
    const detail = submitted()
    detail.submission!.answers = { ...ANSWERED, inspiration: 'Saved by an admin, not submitted.' }

    await mountPage(detail)

    expect(wrapper!.find('[data-testid="admin-bar"]').text()).toContain('saved changes not yet submitted')
  })

  it('keeps the bar current while viewing, as the team saves', async () => {
    await mountPage(asAdmin(buildDetail({ isOpen: true, submission: null })))
    const socket = FakeSocket.instances[FakeSocket.instances.length - 1]!
    socket.readyState = FakeSocket.OPEN
    socket.onopen?.()
    fetchSubmission.mockResolvedValue(savedByTeam('A first answer.', true))

    const fromBen = (message: object) =>
      socket.onmessage?.({ data: JSON.stringify({ user: { id: 9, name: 'Ben' }, ...message }) })

    // An ordinary save sends no signal of its own; the catch-up follows Ben stopping typing.
    fromBen({ type: 'typing', field: 'inspiration', typing: true })
    fromBen({ type: 'typing', field: 'inspiration', typing: false })
    await new Promise((resolve) => setTimeout(resolve, 2700))
    await flushPromises()

    expect(wrapper!.find('[data-testid="admin-bar"]').text()).toContain('Draft, not submitted')
  })

  it("saves a fix to one answer while the team's other answer is over its limit", async () => {
    const overLimit = 'word '.repeat(151).trim()
    const detail = asAdmin(
      buildDetail({ submission: { project_title: TITLE, answers: { ...ANSWERED, solution_purpose: overLimit }, poster: POSTER, stage: 'in_progress' } })
    )
    await mountPage(detail)
    saveDraft.mockResolvedValue(result(detail))
    await click('admin-edit')

    await box().setValue('Fixed by the programme.')
    await click('admin-save')

    expect(saveDraft.mock.calls.at(-1)![1].answers).toEqual({ inspiration: 'Fixed by the programme.' })
  })

  it("still stops a save when the admin's own change is over the limit", async () => {
    await mountPage(draft())
    await click('admin-edit')

    await box().setValue('word '.repeat(151).trim())
    await click('admin-save')

    expect(saveDraft).not.toHaveBeenCalled()
    expect(wrapper!.find('.submission-message').text()).toContain('Answer too long')
  })

  it('asks before leaving for another team with unsaved changes', async () => {
    await mountPage(draft())
    await click('admin-edit')
    await box().setValue('Unsaved.')
    const confirm = vi.fn().mockReturnValue(false)
    vi.stubGlobal('confirm', confirm)

    await wrapper!.vm.$router.push('/groups/2/submission')

    expect(confirm).toHaveBeenCalled()
    expect(wrapper!.vm.$route.params.id).toBe('1')
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
    expect(text).toContain('Submissions are closed. Your unfinished revision')
    expect(text).not.toContain('..')
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

  it('shows the submitted project title once the window has closed', async () => {
    const detail = midRevision(false)
    detail.submission!.project_title = 'Draft title'
    detail.submission!.submitted_project_title = 'Submitted title'
    await mountPage(detail)

    expect((wrapper!.find('#project-title').element as HTMLInputElement).value).toBe('Submitted title')
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

describe('the Finalist step', () => {
  // The finalist round has a section of its own on the group page.
  it('is not a step of the entry, even for a finalist group', async () => {
    fetchFinalist.mockResolvedValue({})
    await mountPage(buildDetail({ submission: { answers: ANSWERED } }))

    const labels = wrapper!.findAll('.submission-step__label').map((label) => label.text())
    expect(labels).toEqual(['Questions', 'Poster', 'Additional materials'])
    expect(buttonNamed(/Finalist/)).toBeUndefined()
  })
})


describe('live typing', () => {
  const socket = () => FakeSocket.instances[FakeSocket.instances.length - 1]!
  const openSocket = () => {
    socket().readyState = FakeSocket.OPEN
    socket().onopen?.()
    socket().onmessage?.({ data: JSON.stringify({ type: 'hello', user: { id: 1, name: 'Me' } }) })
  }
  const teammateTyping = (field: string) =>
    socket().onmessage?.({
      data: JSON.stringify({ type: 'typing', user: { id: 9, name: 'Ben' }, field, typing: true }),
    })

  it('joins the team’s room while the questions are open for editing', async () => {
    await mountPage(buildDetail({ submission: { answers: ANSWERED } }))

    expect(socket().url).toContain('/ws/live/submission/1/')
  })

  it('holds no connection once the round has closed', async () => {
    await mountPage(buildDetail({ isOpen: false, submission: { answers: ANSWERED } }))

    expect(FakeSocket.instances.every((s) => s.readyState === 3)).toBe(true)
  })

  it('stays connected to a submitted entry, so a reopen elsewhere arrives', async () => {
    await mountPage(submittedDetail())

    expect(socket().readyState).not.toBe(3)
  })

  it('tells teammates which question is being typed in', async () => {
    await mountPage(buildDetail({ submission: { answers: ANSWERED } }))
    openSocket()

    await wrapper!.find('#inspiration').setValue('A new thought')

    expect(socket().sent).toContainEqual({ type: 'typing', field: 'inspiration', typing: true })
  })

  it('shows a teammate typing under that question only', async () => {
    await mountPage(buildDetail({ submission: { answers: ANSWERED } }))
    openSocket()

    teammateTyping('inspiration')
    await flushPromises()

    const field = wrapper!.find('#inspiration').element.closest('.submission-field')!
    expect(field.textContent).toContain('Ben is typing…')
    expect(wrapper!.findAll('.typing-indicator')).toHaveLength(1)
  })

  it('shows a teammate typing the project title', async () => {
    await mountPage(buildDetail({ submission: { answers: ANSWERED } }))
    openSocket()

    teammateTyping('project-title')
    await flushPromises()

    const field = wrapper!.find('#project-title').element.closest('.submission-field')!
    expect(field.textContent).toContain('Ben is typing…')
  })
})

describe('live text', () => {
  const socket = () => FakeSocket.instances[FakeSocket.instances.length - 1]!
  const openSocket = () => {
    socket().readyState = FakeSocket.OPEN
    socket().onopen?.()
    socket().onmessage?.({ data: JSON.stringify({ type: 'hello', user: { id: 1, name: 'Me' } }) })
  }
  const fromBen = (message: object) =>
    socket().onmessage?.({ data: JSON.stringify({ user: { id: 9, name: 'Ben' }, ...message }) })

  it('shares what you type with teammates', async () => {
    await mountPage(buildDetail({ submission: { answers: ANSWERED } }))
    openSocket()

    await wrapper!.find('#inspiration').setValue('A new thought')

    expect(socket().sent).toContainEqual({ type: 'text', field: 'inspiration', text: 'A new thought', caret: 13 })
  })

  it('shows a teammate’s text as they type and locks that box only', async () => {
    await mountPage(buildDetail({ submission: { answers: ANSWERED } }))
    openSocket()

    fromBen({ type: 'typing', field: 'inspiration', typing: true })
    fromBen({ type: 'text', field: 'inspiration', text: 'Ben’s draft' })
    await flushPromises()

    const box = wrapper!.find('#inspiration')
    expect((box.element as HTMLTextAreaElement).value).toBe('Ben’s draft')
    expect(box.attributes('disabled')).toBeDefined()
    expect(wrapper!.find('#solution_purpose').attributes('disabled')).toBeUndefined()

    fromBen({ type: 'typing', field: 'inspiration', typing: false })
    await flushPromises()
    expect(wrapper!.find('#inspiration').attributes('disabled')).toBeUndefined()
  })

  it('never saves a teammate’s text as your own', async () => {
    await mountPage(buildDetail({ submission: { answers: ANSWERED } }))
    openSocket()

    fromBen({ type: 'text', field: 'inspiration', text: 'Ben’s draft' })
    await new Promise((resolve) => setTimeout(resolve, 2200))
    await flushPromises()

    expect(saveDraft).not.toHaveBeenCalled()
  })

  it('keeps your own unsaved edits elsewhere when a teammate’s text arrives', async () => {
    const detail = buildDetail({ submission: { answers: ANSWERED } })
    await mountPage(detail)
    saveDraft.mockResolvedValue({ deadline: detail.deadline, submission: detail.submission! })
    openSocket()

    await wrapper!.find('#solution_purpose').setValue('My change')
    fromBen({ type: 'text', field: 'inspiration', text: 'Ben’s draft' })
    await new Promise((resolve) => setTimeout(resolve, 2200))
    await flushPromises()

    expect(saveDraft).toHaveBeenCalledTimes(1)
    expect(saveDraft.mock.calls[0]![1].answers).toEqual({ solution_purpose: 'My change' })
  })

  it('shows a teammate typing the project title', async () => {
    await mountPage(buildDetail({ submission: { answers: ANSWERED } }))
    openSocket()

    fromBen({ type: 'text', field: 'project-title', text: 'Coral Rescue' })
    await flushPromises()

    expect((wrapper!.find('#project-title').element as HTMLInputElement).value).toBe('Coral Rescue')
  })
})

describe('bringing boxes back in line after live text', () => {
  const socket = () => FakeSocket.instances[FakeSocket.instances.length - 1]!
  const fromBen = (message: object) =>
    socket().onmessage?.({ data: JSON.stringify({ user: { id: 9, name: 'Ben' }, ...message }) })
  const savedByBen = (inspiration: string) =>
    buildDetail({ submission: { answers: { ...ANSWERED, inspiration } } })

  async function benFinishes(saved: string) {
    socket().readyState = FakeSocket.OPEN
    socket().onopen?.()
    fromBen({ type: 'text', field: 'inspiration', text: 'Ben’s draf' })
    fetchSubmission.mockResolvedValue(savedByBen(saved))
    fromBen({ type: 'typing', field: 'inspiration', typing: false })
    await new Promise((resolve) => setTimeout(resolve, 2700))
    await flushPromises()
  }

  it('shows what was actually saved once a teammate’s box unlocks', async () => {
    await mountPage(buildDetail({ submission: { answers: ANSWERED } }))

    await benFinishes('Ben’s draft, finished')

    expect((wrapper!.find('#inspiration').element as HTMLTextAreaElement).value).toBe('Ben’s draft, finished')
    expect(saveDraft).not.toHaveBeenCalled()
  })

  it('leaves a box you are editing alone', async () => {
    const detail = buildDetail({ submission: { answers: ANSWERED } })
    await mountPage(detail)
    saveDraft.mockReturnValue(new Promise(() => undefined))

    await wrapper!.find('#solution_purpose').setValue('My unsaved change')
    await benFinishes('Ben’s draft, finished')

    expect((wrapper!.find('#solution_purpose').element as HTMLTextAreaElement).value).toBe('My unsaved change')
    expect((wrapper!.find('#inspiration').element as HTMLTextAreaElement).value).toBe('Ben’s draft, finished')
  })

  it('catches up on coming back to the tab, so an old answer is never edited over', async () => {
    await mountPage(buildDetail({ submission: { answers: ANSWERED } }))
    socket().readyState = FakeSocket.OPEN
    socket().onopen?.()
    const visibility = vi.spyOn(document, 'visibilityState', 'get')
    visibility.mockReturnValue('hidden')
    document.dispatchEvent(new Event('visibilitychange'))
    await flushPromises()
    fetchSubmission.mockResolvedValue(savedByBen('Ben wrote this while you were away'))

    visibility.mockReturnValue('visible')
    document.dispatchEvent(new Event('visibilitychange'))
    await flushPromises()
    socket().readyState = FakeSocket.OPEN
    socket().onopen?.()
    await flushPromises()
    visibility.mockRestore()

    expect((wrapper!.find('#inspiration').element as HTMLTextAreaElement).value).toBe(
      'Ben wrote this while you were away'
    )
  })

  it('fetches again when your own save lands while a refresh is loading', async () => {
    const detail = buildDetail({ submission: { answers: ANSWERED } })
    await mountPage(detail)
    socket().readyState = FakeSocket.OPEN
    socket().onopen?.()
    let finishSave: (value: unknown) => void = () => undefined
    saveDraft.mockReturnValueOnce(new Promise((resolve) => (finishSave = resolve)))
    let finishRefresh: (value: unknown) => void = () => undefined
    fetchSubmission.mockReturnValueOnce(new Promise((resolve) => (finishRefresh = resolve)))

    await wrapper!.find('#solution_purpose').setValue('My latest answer')
    fromBen({ type: 'typing', field: 'inspiration', typing: true })
    fromBen({ type: 'typing', field: 'inspiration', typing: false })
    // The autosave goes out at 2 s and the refresh at 2.5 s; both are still loading.
    await new Promise((resolve) => setTimeout(resolve, 2700))
    const mine = { ...ANSWERED, solution_purpose: 'My latest answer', inspiration: 'Ben’s answer' }
    fetchSubmission.mockResolvedValue(buildDetail({ submission: { answers: mine } }))
    finishSave({ deadline: detail.deadline, submission: buildDetail({ submission: { answers: mine } }).submission })
    await flushPromises()
    // The refresh began before the save landed, so it holds the old answer.
    finishRefresh(savedByBen('Ben’s answer'))
    await flushPromises()

    expect((wrapper!.find('#solution_purpose').element as HTMLTextAreaElement).value).toBe('My latest answer')
    expect((wrapper!.find('#inspiration').element as HTMLTextAreaElement).value).toBe('Ben’s answer')
  })
})

describe('live panel and title', () => {
  const socket = () => FakeSocket.instances[FakeSocket.instances.length - 1]!
  const openSocket = () => {
    socket().readyState = FakeSocket.OPEN
    socket().onopen?.()
    socket().onmessage?.({ data: JSON.stringify({ type: 'hello', user: { id: 1, name: 'Me' } }) })
  }
  const fromBen = (message: object) =>
    socket().onmessage?.({ data: JSON.stringify({ user: { id: 9, name: 'Ben' }, ...message }) })

  it('swaps a locked box for the live panel with the cursor', async () => {
    await mountPage(buildDetail({ submission: { answers: ANSWERED } }))
    openSocket()

    fromBen({ type: 'text', field: 'inspiration', text: 'Ben’s draft', caret: 5 })
    await flushPromises()

    const field = wrapper!.find('#inspiration').element.closest('.submission-field')!
    expect(field.querySelector('[data-testid="live-text"]')).not.toBeNull()
    expect(field.querySelector('.live-text__caret')).not.toBeNull()
    expect(wrapper!.find('#inspiration').isVisible()).toBe(false)
  })

  it('only sends the title when it was changed here', async () => {
    const detail = buildDetail({ submission: { project_title: TITLE, answers: ANSWERED } })
    await mountPage(detail)
    saveDraft.mockResolvedValue({ deadline: detail.deadline, submission: detail.submission! })

    await wrapper!.find('#inspiration').setValue('An edit')
    await new Promise((resolve) => setTimeout(resolve, 2200))
    await flushPromises()
    expect(saveDraft.mock.calls[0]![1]).not.toHaveProperty('project_title')

    await wrapper!.find('#project-title').setValue('A new title')
    await new Promise((resolve) => setTimeout(resolve, 2200))
    await flushPromises()
    expect(saveDraft.mock.calls[1]![1]).toHaveProperty('project_title', 'A new title')
  })
})

describe('changes made elsewhere', () => {
  const socket = () => FakeSocket.instances[FakeSocket.instances.length - 1]!
  const openSocket = () => {
    socket().readyState = FakeSocket.OPEN
    socket().onopen?.()
    socket().onmessage?.({ data: JSON.stringify({ type: 'hello', user: { id: 1, name: 'Me' } }) })
  }
  const changed = (item: string) =>
    socket().onmessage?.({ data: JSON.stringify({ type: 'changed', item, user: { id: 9, name: 'Matt' } }) })

  it('shows at once when a teammate submits', async () => {
    await mountPage(buildDetail({ submission: { project_title: TITLE, answers: ANSWERED, poster: POSTER } }))
    openSocket()
    fetchSubmission.mockResolvedValue(submittedDetail())

    changed('submitted')
    await flushPromises()

    expect(wrapper!.find('#inspiration').attributes('disabled')).toBeDefined()
    expect(wrapper!.find('.submission-message').exists()).toBe(false)
  })

  it('opens up at once when a teammate reopens the entry', async () => {
    await mountPage(submittedDetail())
    openSocket()
    fetchSubmission.mockResolvedValue(reopenedDetail())

    changed('reopened')
    await flushPromises()

    expect(wrapper!.find('#inspiration').attributes('disabled')).toBeUndefined()
    expect(wrapper!.find('.submission-message').exists()).toBe(false)
  })

  it('picks up a teammate’s new prototype link', async () => {
    await mountPage(buildDetail({ submission: { answers: ANSWERED } }))
    openSocket()
    fetchSubmission.mockResolvedValue(buildDetail({ submission: { answers: ANSWERED, prototype_url: 'https://example.com/demo' } }))

    changed('draft')
    await flushPromises()

    expect((wrapper!.find('#prototype-url').element as HTMLInputElement).value).toBe('https://example.com/demo')
  })

  it('picks up checklist ticks an admin saved', async () => {
    await mountPage(buildDetail({ submission: { answers: ANSWERED, poster: POSTER } }))
    openSocket()
    fetchSubmission.mockResolvedValue(
      buildDetail({ submission: { answers: ANSWERED, poster: POSTER, poster_checklist: { btf_logo: true } } })
    )

    changed('draft')
    await flushPromises()

    expect((wrapper!.find('#checklist-btf_logo').element as HTMLInputElement).checked).toBe(true)
  })

  it('picks up a teammate’s new poster without touching what you are typing', async () => {
    await mountPage(buildDetail({ submission: { answers: ANSWERED } }))
    openSocket()
    await wrapper!.find('#inspiration').setValue('Half typed')
    const withPoster = buildDetail({ submission: { answers: ANSWERED, poster: POSTER } })
    fetchSubmission.mockResolvedValue(withPoster)
    // Leaving the step saves the typing; the server's reply already includes the poster.
    saveDraft.mockResolvedValue({ deadline: withPoster.deadline, submission: withPoster.submission! })

    changed('files')
    await flushPromises()

    expect((wrapper!.find('#inspiration').element as HTMLTextAreaElement).value).toBe('Half typed')
    await buttonNamed(/Poster/)!.trigger('click')
    await flushPromises()
    expect(wrapper!.text()).toContain('poster.pdf')
  })

  it("takes a teammate's checklist ticks, keeping one ticked here and not yet saved", async () => {
    const poster = (checklist: Record<string, boolean>) =>
      buildDetail({ submission: { answers: ANSWERED, poster: POSTER, poster_checklist: checklist } })
    await mountPage(poster({}))
    openSocket()
    await buttonNamed(/Poster/)!.trigger('click')
    await flushPromises()
    await wrapper!.find('#checklist-school_logo').setValue(true)
    fetchSubmission.mockResolvedValue(poster({ btf_logo: true }))

    changed('checklist')
    await flushPromises()

    const box = (key: string) => wrapper!.find(`#checklist-${key}`).element as HTMLInputElement
    expect(box('btf_logo').checked).toBe(true)
    expect(box('school_logo').checked).toBe(true)
  })
})

describe('the prototype link', () => {
  const linkInput = () => wrapper!.find('#prototype-url')
  const linkNote = () => wrapper!.find('#prototype-url-note')
  const waitForAutosave = async () => {
    await new Promise((resolve) => setTimeout(resolve, 2200))
    await flushPromises()
  }

  const mountEditable = async () => {
    const detail = buildDetail({
      submission: { project_title: TITLE, answers: ANSWERED, poster: POSTER, poster_checklist: CONFIRMED_CHECKLIST },
    })
    await mountPage(detail)
    saveDraft.mockResolvedValue({ deadline: detail.deadline, submission: detail.submission! })
    await goToLastStep()
  }

  it('adds https:// to a link given without it, and saves that', async () => {
    await mountEditable()

    await linkInput().setValue('www.figma.com/file/abc')
    await linkInput().trigger('blur')
    await waitForAutosave()

    expect((linkInput().element as HTMLInputElement).value).toBe('https://www.figma.com/file/abc')
    expect(linkNote().exists()).toBe(false)
    expect(saveDraft).toHaveBeenLastCalledWith(
      '1',
      expect.objectContaining({ prototype_url: 'https://www.figma.com/file/abc' }),
    )
  })

  it('does not flag a link while it is still being typed', async () => {
    await mountEditable()

    await linkInput().setValue('fig')

    expect(linkNote().exists()).toBe(false)
  })

  it('flags text that is not a link and keeps saving the rest without it', async () => {
    await mountEditable()

    await linkInput().setValue('on our drive')
    await linkInput().trigger('blur')
    await waitForAutosave()

    expect(linkNote().text()).toContain("doesn't look like a web link")
    expect(linkInput().attributes('aria-invalid')).toBe('true')
    const sent = saveDraft.mock.calls.at(-1)![1]
    expect(sent).not.toHaveProperty('prototype_url')
    expect(sent).toHaveProperty('answers')
  })

  it('flags a link over 500 characters', async () => {
    await mountEditable()

    await linkInput().setValue(`https://example.com/${'a'.repeat(490)}`)
    await linkInput().trigger('blur')

    expect(linkNote().text()).toContain('longer than 500 characters')
  })

  it('only sends the link when it was changed here', async () => {
    const detail = buildDetail({
      submission: { project_title: TITLE, answers: ANSWERED, prototype_url: 'https://example.com/demo' },
    })
    await mountPage(detail)
    saveDraft.mockResolvedValue({ deadline: detail.deadline, submission: detail.submission! })

    await wrapper!.find('#inspiration').setValue('An edit')
    await waitForAutosave()

    expect(saveDraft.mock.calls[0]![1]).not.toHaveProperty('prototype_url')
  })

  it('stops a submit until the link is fixed or cleared', async () => {
    await mountEditable()

    await linkInput().setValue('on our drive')
    await buttonNamed(/^Submit$/)!.trigger('click')
    await flushPromises()

    expect(wrapper!.find('.submission-message').text()).toContain(
      'The prototype link needs fixing before the entry can be submitted.',
    )
    expect(document.activeElement?.id).toBe('prototype-url')
    expect(linkNote().exists()).toBe(true)
    expect(submitEntry).not.toHaveBeenCalled()
  })
})

describe('stretching an answer box', () => {
  it('gives each question a grip on its bottom border that sets the box height', async () => {
    await mountPage(buildDetail({ submission: { answers: ANSWERED } }))
    const field = () => wrapper!.find('#inspiration').element.closest('.submission-field')!
    const handle = wrapper!.findAll('[data-testid="stretch-handle"]')[1]!

    await handle.trigger('keydown', { key: 'ArrowDown' })

    expect(wrapper!.findAll('[data-testid="stretch-handle"]')).toHaveLength(2)
    expect((field().querySelector('textarea') as HTMLTextAreaElement).style.height).toMatch(/px$/)
  })
})

describe('automated submission', () => {
  it('says the entry was submitted automatically, and when', async () => {
    const detail = submittedDetail()
    detail.deadline.is_open = false
    detail.submission!.auto_submitted = true
    detail.submission!.submitted_by_name = ''
    await mountPage(detail)

    const line = wrapper!.find('.status-line').text()
    expect(line).toContain('Submitted')
    expect(line).toMatch(/Automated Submission on \S/)
    expect(line).not.toContain('By ')
  })

  it('names the person for an ordinary submission', async () => {
    const detail = submittedDetail()
    detail.submission!.submitted_by_name = 'Laura Bennett'
    await mountPage(detail)

    expect(wrapper!.find('.status-line').text()).toContain('By Laura Bennett on')
  })
})

describe('answer box size', () => {
  it('opens each answer box at seven lines', async () => {
    await mountPage(buildDetail({ submission: { answers: ANSWERED } }))

    expect(wrapper!.find('#inspiration').attributes('rows')).toBe('7')
  })
})
