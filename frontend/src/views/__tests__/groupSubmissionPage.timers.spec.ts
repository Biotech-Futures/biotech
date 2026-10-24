// GroupSubmissionPage's tests that turn on its timers: auto-save, 2s after
// typing stops, and catching up, 2.5s after a teammate saves. The clock is
// fake here, so each test moves it on past the timer at once instead of
// waiting for it.

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia, type Pinia } from 'pinia'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createRouter, createWebHashHistory } from 'vue-router'
import { ApiError } from '@/utils/apiError'
import type { SubmissionDetail } from '@/utils/submissionsAPI'
import * as Y from 'yjs'
import { toBase64 } from '@/composables/useSharedDoc'
import {
  POSTER,
  ANSWERED,
  TITLE,
  CONFIRMED_CHECKLIST,
  buildDetail,
  ROUTES,
  FakeSocket,
} from './groupSubmissionPage.shared'

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
  // Before the page mounts, so every timer it sets runs on the fake clock.
  vi.useFakeTimers()
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
  vi.useRealTimers()
})

describe('submitting', () => {
  it('saves the project title with the draft', async () => {
    const detail = buildDetail({ submission: { answers: ANSWERED } })
    await mountPage(detail)
    saveDraft.mockResolvedValue({ deadline: detail.deadline, submission: detail.submission! })

    await wrapper!.find('#project-title').setValue(TITLE)
    await vi.advanceTimersByTimeAsync(2200)
    await flushPromises()

    expect(saveDraft).toHaveBeenCalledWith('1', expect.objectContaining({ project_title: TITLE }))
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
    await vi.advanceTimersByTimeAsync(2200)
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
    await vi.advanceTimersByTimeAsync(2200)
    await flushPromises()
    expect(saveDraft).toHaveBeenCalledTimes(1)

    // Models an edit already in progress when the refusal landed.
    saveDraft.mockClear()
    await wrapper!.vm.$forceUpdate()
    await vi.advanceTimersByTimeAsync(2200)
    await flushPromises()
    expect(saveDraft).not.toHaveBeenCalled()
  })
})

describe('an answer over its word limit', () => {
  const overLimit = Array(200).fill('word').join(' ')

  it('is left out of the save instead of being sent and refused', async () => {
    await mountPage(buildDetail({ submission: { answers: ANSWERED } }))
    const boxes = wrapper!.findAll('textarea')

    await boxes[0].setValue(overLimit)
    await boxes[1].setValue('Still a valid answer.')
    await vi.advanceTimersByTimeAsync(2200)
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
    await vi.advanceTimersByTimeAsync(2200)
    await flushPromises()

    expect(saveDraft).toHaveBeenCalledTimes(1)
    expect(wrapper!.find('.submission-savestate').text()).toMatch(/unsaved/i)
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

  it('saves only the ticks that changed', async () => {
    const detail = withPoster({ team_code: true })
    await mountPage(detail)
    saveDraft.mockResolvedValue({ deadline: detail.deadline, submission: detail.submission! })
    await goToPoster()

    await wrapper!.find('#checklist-btf_logo').setValue(true)
    await vi.advanceTimersByTimeAsync(2200)
    await flushPromises()

    expect(saveDraft.mock.calls.at(-1)![1].poster_checklist).toEqual({ btf_logo: true })
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

  it('sends typing into the shared document, and never saves answers from the page', async () => {
    await mountPage(coedited())
    await connect()

    await box().setValue('Live text. More.')
    await vi.advanceTimersByTimeAsync(2200)
    await flushPromises()

    expect(sentOfType('doc-update').length).toBeGreaterThan(0)
    expect(saveDraft).not.toHaveBeenCalled()
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

    await vi.advanceTimersByTimeAsync(250)
    ;(box().element as HTMLTextAreaElement).blur()
    await vi.advanceTimersByTimeAsync(250)

    expect(cursors().filter((m) => m.type === 'cursor').at(-1)).toMatchObject({ field: 'inspiration', at: null })
  })
})

describe('the admin view', () => {
  const asAdmin = (detail: SubmissionDetail): SubmissionDetail => ({ ...detail, admin_access: true })

  const draft = (isOpen = false, poster_checklist: Record<string, boolean> = CONFIRMED_CHECKLIST) =>
    asAdmin(
      buildDetail({ isOpen, submission: { project_title: TITLE, answers: ANSWERED, poster: POSTER, poster_checklist, stage: 'in_progress' } })
    )

  const click = async (testId: string) => {
    await wrapper!.find(`[data-testid="${testId}"]`).trigger('click')
    await flushPromises()
  }

  const box = () => wrapper!.find('#inspiration')

  const savedByTeam = (inspiration: string, isOpen = false) =>
    asAdmin(buildDetail({ isOpen, submission: { project_title: TITLE, answers: { ...ANSWERED, inspiration }, poster: POSTER, stage: 'in_progress' } }))

  it('edits without saving anything until Save', async () => {
    await mountPage(draft())
    await click('admin-edit')

    await box().setValue('Fixed by the programme.')
    await vi.advanceTimersByTimeAsync(2200)
    await flushPromises()

    expect(saveDraft).not.toHaveBeenCalled()
    expect(wrapper!.find('[data-testid="admin-bar"]').text()).toContain('Unsaved changes')
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
    await vi.advanceTimersByTimeAsync(2700)
    await flushPromises()

    expect((box().element as HTMLTextAreaElement).value).toBe('Ben’s saved answer.')
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
    await vi.advanceTimersByTimeAsync(2700)
    await flushPromises()

    expect(wrapper!.find('[data-testid="admin-bar"]').text()).toContain('Draft')
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

  it('never saves a teammate’s text as your own', async () => {
    await mountPage(buildDetail({ submission: { answers: ANSWERED } }))
    openSocket()

    fromBen({ type: 'text', field: 'inspiration', text: 'Ben’s draft' })
    await vi.advanceTimersByTimeAsync(2200)
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
    await vi.advanceTimersByTimeAsync(2200)
    await flushPromises()

    expect(saveDraft).toHaveBeenCalledTimes(1)
    expect(saveDraft.mock.calls[0]![1].answers).toEqual({ solution_purpose: 'My change' })
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
    await vi.advanceTimersByTimeAsync(2700)
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
    await vi.advanceTimersByTimeAsync(2700)
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
  it('only sends the title when it was changed here', async () => {
    const detail = buildDetail({ submission: { project_title: TITLE, answers: ANSWERED } })
    await mountPage(detail)
    saveDraft.mockResolvedValue({ deadline: detail.deadline, submission: detail.submission! })

    await wrapper!.find('#inspiration').setValue('An edit')
    await vi.advanceTimersByTimeAsync(2200)
    await flushPromises()
    expect(saveDraft.mock.calls[0]![1]).not.toHaveProperty('project_title')

    await wrapper!.find('#project-title').setValue('A new title')
    await vi.advanceTimersByTimeAsync(2200)
    await flushPromises()
    expect(saveDraft.mock.calls[1]![1]).toHaveProperty('project_title', 'A new title')
  })
})

describe('the prototype link', () => {
  const linkInput = () => wrapper!.find('#prototype-url')

  const linkNote = () => wrapper!.find('#prototype-url-note')

  const waitForAutosave = async () => {
    await vi.advanceTimersByTimeAsync(2200)
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
})
