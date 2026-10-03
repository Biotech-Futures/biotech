import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia, type Pinia } from 'pinia'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createRouter, createWebHashHistory } from 'vue-router'
import type { FinalistDetail, FinalistEntry } from '@/utils/finalistAPI'
import { ApiError } from '@/utils/apiError'

const fetchFinalist = vi.fn()
const submitAvailability = vi.fn()
const uploadPresentation = vi.fn()
const submitFinalist = vi.fn()
const reopenFinalist = vi.fn()

vi.mock('@/utils/finalistAPI', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/utils/finalistAPI')>()
  return {
    ...actual,
    fetchFinalist: (...args: unknown[]) => fetchFinalist(...args),
    submitAvailability: (...args: unknown[]) => submitAvailability(...args),
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
  availability_submitted_at: null,
  availability_submitted_by_name: '',
  presentation: null,
  submitted_presentation: null,
  submitted_at: null,
  submitted_by_name: '',
  reopened_at: null,
  stage: 'not_started',
  is_submitted: false,
  is_locked: false,
  updated_at: new Date().toISOString(),
})

const buildDetail = (
  entry: Partial<FinalistEntry> | null = {},
  isOpen = true,
  over: Partial<FinalistDetail> = {}
): FinalistDetail => ({
  group: { id: 1, name: 'BTF1' },
  deadline: { closes_at: new Date(Date.now() + 5 * 86_400_000).toISOString(), is_extended: false, is_open: isOpen },
  times_shown: true,
  sessions: SESSIONS,
  symposium_date: null,
  max_file_size: 25 * 1024 * 1024,
  entry: entry === null ? null : { ...blankEntry(), ...entry },
  ...over,
})

// The team's times, submitted by one of it.
const answered = (ids: number[]): Partial<FinalistEntry> => ({
  available_session_ids: ids,
  availability_submitted_at: '2026-10-05T03:30:00Z',
  availability_submitted_by_name: 'Amy Chen',
})

const lockedEntry = (): Partial<FinalistEntry> => ({
  ...answered([1]),
  presentation: PDF,
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
    routes: [{ path: '/groups/:id/finalist', name: 'group-finalist', component: stub }],
  })
  await router.push('/groups/1/finalist')
  await router.isReady()
  wrapper = mount(FinalistPage, { attachTo: document.body, global: { plugins: [router, pinia] } })
  await flushPromises()
  return wrapper
}

const button = (label: RegExp) => wrapper!.findAll('button').find((b) => label.test(b.text().trim()))
const checkbox = (id: number) => wrapper!.find(`[data-testid="session-${id}"]`)
const submitTimes = () => wrapper!.find('[data-testid="submit-availability"]')
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
})

describe('availability', () => {
  it('lists every time from the server', async () => {
    await mountPage(buildDetail(null))

    expect(wrapper!.text()).toContain('10:00 – 11:00')
    expect(wrapper!.text()).toContain('13:55 – 15:00')
    expect(wrapper!.find('.status-line').text()).toContain('Not Started')
  })

  it('sends nothing until Submit Availability is pressed', async () => {
    await mountPage(buildDetail(null))
    expect(submitTimes().attributes('disabled')).toBeDefined()

    await checkbox(1).trigger('change')
    await checkbox(3).trigger('change')
    expect(submitAvailability).not.toHaveBeenCalled()
    expect(submitTimes().attributes('disabled')).toBeUndefined()
  })

  it('submits the ticked times for the team and says who did, when', async () => {
    await mountPage(buildDetail(null))
    submitAvailability.mockResolvedValue(result({ ...answered([1, 3]), stage: 'in_progress' }))

    await checkbox(1).trigger('change')
    await checkbox(3).trigger('change')
    await submitTimes().trigger('click')
    await flushPromises()

    expect(submitAvailability).toHaveBeenCalledWith('1', [1, 3])
    const line = wrapper!.find('[data-testid="availability-submitted"]').text()
    // Day first, 24 hour, in the viewer's time.
    expect(line).toMatch(/^Submitted by Amy Chen on 5\/10\/2026 \d{2}:30$/)
    // Nothing new to send until a tick changes.
    expect(submitTimes().attributes('disabled')).toBeDefined()
  })

  it('says when the times could not be submitted', async () => {
    await mountPage(buildDetail(null))
    submitAvailability.mockRejectedValue(new Error('Network down'))

    await checkbox(2).trigger('change')
    await submitTimes().trigger('click')
    await flushPromises()

    expect(wrapper!.find('.submission-message--error').exists()).toBe(true)
    expect(wrapper!.find('[data-testid="availability-submitted"]').exists()).toBe(false)
  })

  it("shows the team's times as ticked, for anyone on it", async () => {
    await mountPage(buildDetail({ ...answered([2]), stage: 'in_progress' }))

    expect((checkbox(2).element as HTMLInputElement).checked).toBe(true)
    expect((checkbox(1).element as HTMLInputElement).checked).toBe(false)
    expect(wrapper!.find('fieldset').attributes('disabled')).toBeUndefined()
    expect(wrapper!.find('[data-testid="availability-submitted"]').text()).toContain('Submitted by Amy Chen on ')
  })

  it('cannot submit no times at all', async () => {
    await mountPage(buildDetail({ ...answered([2]), stage: 'in_progress' }))

    await checkbox(2).trigger('change')

    expect(submitTimes().attributes('disabled')).toBeDefined()
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
  it('needs no availability while the sessions are hidden, and says they come later', async () => {
    submitFinalist.mockResolvedValueOnce(result(lockedEntry()))
    await mountPage(buildDetail({ presentation: PDF, stage: 'in_progress' }, true, { times_shown: false, sessions: [] }))
    expect(wrapper!.find('[data-testid="sessions-not-shown"]').text()).toBe(
      "The sessions will be shown here once they're set."
    )
    expect(wrapper!.find('fieldset.finalist-sessions').exists()).toBe(false)

    await button(/^Submit$/)!.trigger('click')
    await flushPromises()
    expect(submitFinalist).toHaveBeenCalled()
  })

  it('sends the team to availability until its times are submitted', async () => {
    // Ticked, as carried over from before, but never submitted.
    await mountPage(buildDetail({ available_session_ids: [1], presentation: PDF, stage: 'in_progress' }))

    await button(/^Submit$/)!.trigger('click')
    await flushPromises()

    expect(submitFinalist).not.toHaveBeenCalled()
    expect(wrapper!.find('.submission-message').text()).toContain("Submit your team's availability first.")
  })

  it('sends the team to availability when a tick changed since it was submitted', async () => {
    await mountPage(buildDetail({ ...answered([1]), presentation: PDF, stage: 'in_progress' }))

    await checkbox(2).trigger('change')
    await button(/^Submit$/)!.trigger('click')
    await flushPromises()

    expect(submitFinalist).not.toHaveBeenCalled()
    expect(wrapper!.find('.submission-message').text()).toContain("Submit your team's availability first.")
  })

  it('shows what the server says when it still wants the times', async () => {
    await mountPage(buildDetail({ ...answered([1]), presentation: PDF, stage: 'in_progress' }))
    submitFinalist.mockRejectedValue(
      new ApiError({
        error: 'Submit the sessions your team can attend first.',
        code: 'availability_required',
        request_id: 'x',
      })
    )

    await button(/^Submit$/)!.trigger('click')
    await flushPromises()

    expect(submitFinalist).toHaveBeenCalledWith('1')
    expect(wrapper!.find('.submission-message').text()).toContain('Submit the sessions your team can attend first.')
  })

  it('sends the team to the presentation step when nothing is uploaded', async () => {
    await mountPage(buildDetail({ ...answered([1]), stage: 'in_progress' }))

    await button(/^Submit$/)!.trigger('click')
    await flushPromises()

    expect(submitFinalist).not.toHaveBeenCalled()
    expect(wrapper!.find('.submission-message').text()).toContain('A presentation must be uploaded')
  })

  it('submits a complete entry', async () => {
    await mountPage(buildDetail({ ...answered([1]), presentation: PDF, stage: 'in_progress' }))
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
    expect(submitTimes().exists()).toBe(false)
    // Who submitted the times still shows.
    expect(wrapper!.find('[data-testid="availability-submitted"]').exists()).toBe(true)

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

  it('shows the submitted slides rather than an unfinished revision', async () => {
    await mountPage(
      buildDetail(
        {
          ...lockedEntry(),
          presentation: PPTX,
          is_locked: false,
          stage: 'revising',
          reopened_at: new Date().toISOString(),
        },
        false,
      ),
    )

    expect(wrapper!.find('.submission-file').text()).toContain('deck.pdf')
    expect((checkbox(1).element as HTMLInputElement).checked).toBe(true)
  })

  it('reopens when the window regains focus after the deadline is extended', async () => {
    await mountPage(buildDetail(null, false))
    fetchFinalist.mockResolvedValue(buildDetail(null, true))

    window.dispatchEvent(new Event('focus'))
    await flushPromises()

    expect(wrapper!.find('fieldset').attributes('disabled')).toBeUndefined()
  })
})
