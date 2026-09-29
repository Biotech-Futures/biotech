import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia, type Pinia } from 'pinia'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createRouter, createWebHashHistory } from 'vue-router'
import type { FinalistDetail, FinalistEntry } from '@/utils/finalistAPI'
import { ApiError } from '@/utils/apiError'

const fetchFinalist = vi.fn()
const saveAvailability = vi.fn()
const uploadPresentation = vi.fn()
const submitFinalist = vi.fn()
const reopenFinalist = vi.fn()

vi.mock('@/utils/finalistAPI', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/utils/finalistAPI')>()
  return {
    ...actual,
    fetchFinalist: (...args: unknown[]) => fetchFinalist(...args),
    saveAvailability: (...args: unknown[]) => saveAvailability(...args),
    uploadPresentation: (...args: unknown[]) => uploadPresentation(...args),
    submitFinalist: (...args: unknown[]) => submitFinalist(...args),
    reopenFinalist: (...args: unknown[]) => reopenFinalist(...args),
  }
})

// Imported after the mock is registered so the component picks up the stubs.
const FinalistPage = (await import('../FinalistPage.vue')).default

// This year's times, as set on Management > Finalist Presentation.
const SESSIONS = [
  { id: 1, label: '10:00 – 11:00' },
  { id: 2, label: '11:40 – 12:30' },
  { id: 3, label: '13:55 – 15:00' },
]
const PDF = { storage_key: 'f/deck.pdf', name: 'deck.pdf', mime: 'application/pdf', size: 2048 }
const PPTX = { ...PDF, storage_key: 'f/deck.pptx', name: 'deck.pptx' }

const blankEntry = (): FinalistEntry => ({
  available_session_ids: [],
  presentation: null,
  submitted_session_ids: [],
  submitted_presentation: null,
  submitted_at: null,
  submitted_by_name: '',
  reopened_at: null,
  stage: 'not_started',
  is_submitted: false,
  is_locked: false,
  updated_at: new Date().toISOString(),
})

// A student's view unless said otherwise: each student ticks their own times.
const buildDetail = (
  entry: Partial<FinalistEntry> | null = {},
  isOpen = true,
  over: Partial<FinalistDetail> = {}
): FinalistDetail => ({
  group: { id: 1, name: 'BTF1' },
  deadline: { closes_at: new Date(Date.now() + 5 * 86_400_000).toISOString(), is_extended: false, is_open: isOpen },
  sessions: SESSIONS,
  symposium_date: null,
  can_choose_sessions: true,
  max_file_size: 25 * 1024 * 1024,
  entry: entry === null ? null : { ...blankEntry(), ...entry },
  ...over,
})

const lockedEntry = (): Partial<FinalistEntry> => ({
  available_session_ids: [1],
  presentation: PDF,
  submitted_session_ids: [1],
  submitted_presentation: PDF,
  submitted_at: new Date().toISOString(),
  stage: 'submitted',
  is_submitted: true,
  is_locked: true,
})

let pinia: Pinia
let wrapper: VueWrapper | null = null

const mountPage = async (detail: FinalistDetail) => {
  fetchFinalist.mockResolvedValue(detail)
  const stub = { template: '<div />' }
  const router = createRouter({
    history: createWebHashHistory(),
    routes: [{ path: '/groups/:id/submission', name: 'group-submission', component: stub }],
  })
  await router.push('/groups/1/submission')
  await router.isReady()
  wrapper = mount(FinalistPage, { attachTo: document.body, global: { plugins: [router, pinia] } })
  await flushPromises()
  return wrapper
}

const button = (label: RegExp) => wrapper!.findAll('button').find((b) => label.test(b.text().trim()))
const checkbox = (id: number) => wrapper!.find(`[data-testid="session-${id}"]`)
const result = (entry: Partial<FinalistEntry>) => ({
  deadline: buildDetail().deadline,
  entry: { ...blankEntry(), ...entry },
})

beforeEach(() => {
  pinia = createPinia()
  setActivePinia(pinia)
  vi.clearAllMocks()
  vi.stubGlobal('scrollTo', vi.fn())
  Element.prototype.scrollIntoView = vi.fn()
})

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
  vi.unstubAllGlobals()
})

describe('layout', () => {
  it('shows availability and the presentation together on one card', async () => {
    await mountPage(buildDetail(null))

    expect(wrapper!.findAll('section.card')).toHaveLength(1)
    expect(wrapper!.find('[data-testid="finalist-availability"]').isVisible()).toBe(true)
    expect(wrapper!.find('[data-testid="finalist-presentation"]').isVisible()).toBe(true)
  })

  it('places the portal step strip it is given between the status and the card', async () => {
    fetchFinalist.mockResolvedValue(buildDetail(null))
    const router = createRouter({
      history: createWebHashHistory(),
      routes: [{ path: '/groups/:id/submission', name: 'group-submission', component: { template: '<div />' } }],
    })
    await router.push('/groups/1/submission')
    await router.isReady()
    wrapper = mount(FinalistPage, {
      global: { plugins: [router, pinia] },
      slots: { steps: '<nav data-testid="strip" />' },
    })
    await flushPromises()

    const html = wrapper.html()
    expect(html.indexOf('status-line')).toBeLessThan(html.indexOf('data-testid="strip"'))
    expect(html.indexOf('data-testid="strip"')).toBeLessThan(html.indexOf('finalist-availability'))
  })
})

describe('what the fixes cover', () => {
  it('lets a drag pass through the preview while a file is dragged', async () => {
    await mountPage(buildDetail({ presentation: PDF, stage: 'in_progress' }))
    const root = wrapper!.find('.content-area')

    window.dispatchEvent(Object.assign(new Event('dragenter'), { dataTransfer: { types: ['Files'] } }))
    await flushPromises()
    expect(root.classes()).toContain('is-dragging-file')

    window.dispatchEvent(new Event('drop'))
    await flushPromises()
    expect(root.classes()).not.toContain('is-dragging-file')
  })

  it('says when availability was saved', async () => {
    await mountPage(buildDetail(null))
    saveAvailability.mockResolvedValue(result({ available_session_ids: [2] }))

    await checkbox(2).trigger('change')
    expect(wrapper!.find('[data-testid="finalist-savestate"]').text()).toBe('Unsaved changes')

    await new Promise((resolve) => setTimeout(resolve, 800))
    await flushPromises()
    expect(wrapper!.find('[data-testid="finalist-savestate"]').text()).toMatch(/^Saved /)
  })

  it('says when availability could not be saved', async () => {
    await mountPage(buildDetail(null))
    saveAvailability.mockRejectedValue(new Error('Network down'))

    await checkbox(2).trigger('change')
    await new Promise((resolve) => setTimeout(resolve, 800))
    await flushPromises()

    expect(wrapper!.find('[data-testid="finalist-savestate"]').text()).toBe('Could not save')
  })

  it('still sends a tick made just before leaving the page', async () => {
    await mountPage(buildDetail(null))
    saveAvailability.mockResolvedValue(result({ available_session_ids: [3] }))

    await checkbox(3).trigger('change')
    wrapper!.unmount()
    wrapper = null

    expect(saveAvailability).toHaveBeenCalledWith('1', [3])
  })
})

describe('availability', () => {
  it('lists every time from the server', async () => {
    await mountPage(buildDetail(null))

    expect(wrapper!.text()).toContain('10:00 – 11:00')
    expect(wrapper!.text()).toContain('13:55 – 15:00')
    expect(wrapper!.find('.status-line').text()).toContain('Not Started')
  })

  it('saves the chosen times after a short pause', async () => {
    await mountPage(buildDetail(null))
    saveAvailability.mockResolvedValue(result({ available_session_ids: [1, 3] }))

    await checkbox(1).trigger('change')
    await checkbox(3).trigger('change')
    await new Promise((resolve) => setTimeout(resolve, 800))
    await flushPromises()

    expect(saveAvailability).toHaveBeenCalledTimes(1)
    expect(saveAvailability).toHaveBeenCalledWith('1', [1, 3])
  })

  it('shows the saved choices as ticked', async () => {
    await mountPage(buildDetail({ available_session_ids: [2], stage: 'in_progress' }))

    expect((checkbox(2).element as HTMLInputElement).checked).toBe(true)
    expect((checkbox(1).element as HTMLInputElement).checked).toBe(false)
  })
})

describe('the presentation', () => {
  it('refuses a file that is not a PDF or PowerPoint before uploading', async () => {
    await mountPage(buildDetail(null))
    const input = wrapper!.find('input[type="file"]')
    Object.defineProperty(input.element, 'files', { value: [new File(['x'], 'notes.docx')] })

    await input.trigger('change')
    await flushPromises()

    expect(uploadPresentation).not.toHaveBeenCalled()
    expect(wrapper!.find('.submission-message').text()).toContain('PDF or PowerPoint')
  })

  it('uploads a dropped PowerPoint file', async () => {
    await mountPage(buildDetail(null))
    uploadPresentation.mockResolvedValue(result({ presentation: PPTX, stage: 'in_progress' }))
    const file = new File(['pk'], 'deck.pptx')

    await wrapper!.find('[data-testid="drop-presentation"]').trigger('drop', {
      dataTransfer: { files: [file], types: ['Files'] },
    })
    await flushPromises()

    expect(uploadPresentation).toHaveBeenCalledWith('1', file, expect.any(Function))
  })

  it('previews a PDF in the page', async () => {
    await mountPage(buildDetail({ presentation: PDF, stage: 'in_progress' }))

    expect(wrapper!.find('iframe.preview-frame').exists()).toBe(true)
  })

  it('explains that a PowerPoint file cannot be previewed', async () => {
    await mountPage(buildDetail({ presentation: PPTX, stage: 'in_progress' }))

    expect(wrapper!.find('iframe.preview-frame').exists()).toBe(false)
    expect(wrapper!.text()).toContain("PowerPoint files can't be previewed here")
  })
})

describe('submitting', () => {
  it('sends a student to availability when they have chosen no times', async () => {
    await mountPage(buildDetail({ presentation: PDF, stage: 'in_progress' }))

    await button(/^Submit$/)!.trigger('click')
    await flushPromises()

    expect(submitFinalist).not.toHaveBeenCalled()
    expect(wrapper!.find('.submission-message').text()).toContain('Choose at least one session you can attend')
  })

  it("leaves a mentor's submit to the server, which says when no student has chosen times", async () => {
    await mountPage(buildDetail({ presentation: PDF, stage: 'in_progress' }, true, { can_choose_sessions: false }))
    submitFinalist.mockRejectedValue(
      new ApiError({
        error: 'At least one student needs to choose the sessions they can attend first.',
        code: 'availability_required',
        request_id: 'x',
      })
    )

    await button(/^Submit$/)!.trigger('click')
    await flushPromises()

    expect(submitFinalist).toHaveBeenCalledWith('1')
    expect(wrapper!.find('.submission-message').text()).toContain('At least one student needs to choose')
  })

  it('sends the team to the presentation step when nothing is uploaded', async () => {
    await mountPage(buildDetail({ available_session_ids: [1], stage: 'in_progress' }))

    await button(/^Submit$/)!.trigger('click')
    await flushPromises()

    expect(submitFinalist).not.toHaveBeenCalled()
    expect(wrapper!.find('.submission-message').text()).toContain('A presentation must be uploaded')
  })

  it('submits a complete entry', async () => {
    await mountPage(buildDetail({ available_session_ids: [1], presentation: PDF, stage: 'in_progress' }))
    submitFinalist.mockResolvedValue(result(lockedEntry()))

    await button(/^Submit$/)!.trigger('click')
    await flushPromises()

    expect(submitFinalist).toHaveBeenCalledWith('1')
    expect(wrapper!.find('.status-line').text()).toContain('Submitted')
  })

  it('locks a submitted entry until it is reopened in the page', async () => {
    await mountPage(buildDetail(lockedEntry()))
    reopenFinalist.mockResolvedValue(result({ ...lockedEntry(), is_locked: false, stage: 'revising' }))

    expect(wrapper!.find('fieldset').attributes('disabled')).toBeDefined()
    expect(button(/^Submit$/)).toBeUndefined()

    await wrapper!.find('[data-testid="finalist-resubmit"]').trigger('click')
    await flushPromises()
    await button(/^Reopen$/)!.trigger('click')
    await flushPromises()

    expect(reopenFinalist).toHaveBeenCalledWith('1')
    expect(wrapper!.find('fieldset').attributes('disabled')).toBeUndefined()
  })
})

describe('times', () => {
  it("lists this year's times and the Symposium day", async () => {
    await mountPage(buildDetail(null, true, { symposium_date: '2026-10-23' }))

    const labels = wrapper!.findAll('.finalist-session').map((l) => l.text())
    expect(labels).toEqual(['10:00 – 11:00', '11:40 – 12:30', '13:55 – 15:00'])
    expect(wrapper!.text()).toContain('The sessions are on Friday 23 October 2026.')
  })

  it('shows the times to a mentor without letting them tick for the students', async () => {
    await mountPage(buildDetail(null, true, { can_choose_sessions: false }))

    expect(wrapper!.find('fieldset').attributes('disabled')).toBeDefined()
    expect(wrapper!.find('[data-testid="students-choose"]').text()).toBe('Each student chooses their own sessions.')
  })

  it('says when no times have been set up yet', async () => {
    await mountPage(buildDetail(null, true, { sessions: [] }))

    expect(wrapper!.text()).toContain('No sessions have been set up yet.')
  })
})

describe('after the deadline', () => {
  it('freezes the page and shuts an empty preview', async () => {
    await mountPage(buildDetail(null, false))

    expect(wrapper!.find('fieldset').attributes('disabled')).toBeDefined()
    expect(button(/^Submit$/)).toBeUndefined()
    expect(wrapper!.find('[data-testid="toggle-finalist-preview"]').attributes('disabled')).toBeDefined()
    expect(wrapper!.find('.status-line').text()).toContain('Not Submitted')
  })

  it('shows what was submitted rather than an unfinished revision', async () => {
    await mountPage(
      buildDetail(
        {
          ...lockedEntry(),
          available_session_ids: [3],
          presentation: PPTX,
          is_locked: false,
          stage: 'revising',
          reopened_at: new Date().toISOString(),
        },
        false,
      ),
    )

    expect((checkbox(1).element as HTMLInputElement).checked).toBe(true)
    expect((checkbox(3).element as HTMLInputElement).checked).toBe(false)
  })

  it('reopens when the window regains focus after the deadline is extended', async () => {
    await mountPage(buildDetail(null, false))
    fetchFinalist.mockResolvedValue(buildDetail(null, true))

    window.dispatchEvent(new Event('focus'))
    await flushPromises()

    expect(wrapper!.find('fieldset').attributes('disabled')).toBeUndefined()
  })
})
