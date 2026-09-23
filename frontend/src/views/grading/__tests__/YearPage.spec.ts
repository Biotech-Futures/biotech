import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import YearPage from '@/views/grading/YearPage.vue'
import {
  fetchCertificatesRelease,
  fetchFinalists,
  fetchGroupExtensions,
  fetchRelease,
  fetchSubmissionDeadline
} from '@/utils/gradingAPI'

vi.mock('@/utils/gradingAPI', () => ({
  fetchCertificatesRelease: vi.fn(),
  fetchFinalists: vi.fn(),
  fetchGroupExtensions: vi.fn(),
  fetchRelease: vi.fn(),
  fetchSubmissionDeadline: vi.fn()
}))
const certsMock = vi.mocked(fetchCertificatesRelease)
const finalistsMock = vi.mocked(fetchFinalists)
const extensionsMock = vi.mocked(fetchGroupExtensions)
const marksMock = vi.mocked(fetchRelease)
const deadlineMock = vi.mocked(fetchSubmissionDeadline)

const finalist = (notified: boolean) => ({
  group_id: 1,
  group_name: 'BTF-1',
  flagged_at: '2026-09-01T00:00:00Z',
  flagged_by: 'Ada Admin',
  notified,
  notified_at: notified ? '2026-09-02T00:00:00Z' : null,
  notified_by: notified ? 'Ada Admin' : null
})

const extension = (until: string) => ({
  id: 1, group_id: 7, group_name: 'BTF-1', extended_until: until, grace_hours: 0,
  reason: '', granted_at: '', granted_by: null, revoked_at: null, revoked_by: null
})

const mountPage = async () => {
  const wrapper = mount(YearPage)
  await flushPromises()
  return wrapper
}

const fact = (wrapper: Awaited<ReturnType<typeof mountPage>>, label: string) =>
  wrapper
    .findAll('.year__facts li')
    .find((li) => li.text().includes(label))!

beforeEach(() => {
  certsMock.mockReset().mockResolvedValue({ released_at: null, released_by: null })
  marksMock.mockReset().mockResolvedValue({ released_at: '2026-09-20T00:00:00Z', released_by: 'Ada' })
  finalistsMock.mockReset().mockResolvedValue({ finalists: [finalist(true), finalist(false)] })
  extensionsMock.mockReset().mockResolvedValue({
    extensions: [extension('2026-11-01T00:00:00Z'), extension('2026-11-08T00:00:00Z')]
  })
  deadlineMock.mockReset().mockResolvedValue({
    deadline: {
      closes_at: '2026-10-30T13:00:00Z', grace_hours: 6, is_open: true,
      set_by: 'Ada Admin', created_at: ''
    }
  })
})

describe('the year dashboard', () => {
  it('derives the competition year from the deadline, like the backend cohort', async () => {
    const wrapper = await mountPage()
    expect(wrapper.find('.year__value').text()).toBe('2026')
  })

  it('falls back to the calendar year when no deadline exists', async () => {
    deadlineMock.mockResolvedValue({ deadline: null })
    const wrapper = await mountPage()
    expect(wrapper.find('.year__value').text()).toBe(String(new Date().getFullYear()))
    expect(fact(wrapper, 'Submission deadline').text()).toContain('not set')
  })

  it('reports the furthest extension as the real end of the window', async () => {
    const wrapper = await mountPage()
    expect(fact(wrapper, 'Last extension').text()).toContain(
      `${new Date('2026-11-08T00:00:00Z').toLocaleDateString('en-GB')} ${new Date('2026-11-08T00:00:00Z').toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hourCycle: 'h23' })}`
    )
  })

  it('shows each release gate in its own state', async () => {
    const wrapper = await mountPage()
    expect(fact(wrapper, 'Marks').text()).toContain('released')
    expect(fact(wrapper, 'Certificates').text()).toContain('not released')
  })

  it('counts notified finalists, and says so when there are none', async () => {
    const wrapper = await mountPage()
    expect(fact(wrapper, 'Notify finalists').text()).toContain('1 of 2 notified')

    finalistsMock.mockResolvedValue({ finalists: [] })
    const empty = await mountPage()
    expect(fact(empty, 'Notify finalists').text()).toContain('no finalists')
  })

  it('keeps rendering when every lookup fails — best effort, never blank', async () => {
    deadlineMock.mockRejectedValue(new Error('down'))
    marksMock.mockRejectedValue(new Error('down'))
    certsMock.mockRejectedValue(new Error('down'))
    extensionsMock.mockRejectedValue(new Error('down'))
    finalistsMock.mockRejectedValue(new Error('down'))
    const wrapper = await mountPage()
    expect(fact(wrapper, 'Submission deadline').text()).toContain('not set')
    expect(fact(wrapper, 'Last extension').text()).toContain('none granted')
    expect(fact(wrapper, 'Marks').text()).toContain('not released')
  })

  it('the Start new year button stays parked until the backend exists', async () => {
    const wrapper = await mountPage()
    const start = wrapper.findAll('button').find((b) => /Start new year/.test(b.text()))!
    expect(start.attributes('disabled')).toBeDefined()
    expect(wrapper.text()).toContain('still being built')
  })
})
