import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import YearPage from '@/views/management/YearPage.vue'
import { formatStatementTime } from '@/utils/date'
import { fetchFinalists } from '@/utils/gradingAPI'
import {
  fetchCertificatesRelease,
  fetchChallengeStart,
  fetchFinalistEmailDetails,
  fetchGroupExtensions,
  fetchRegistrationOpen,
  fetchRelease,
  fetchSubmissionDeadline
} from '@/utils/managementAPI'

vi.mock('@/utils/gradingAPI', () => ({
  fetchFinalists: vi.fn()
}))
vi.mock('@/utils/managementAPI', async (importOriginal) => ({
  // The real rule the page shares with the upload dialog.
  challengeYear: (await importOriginal<typeof import('@/utils/managementAPI')>()).challengeYear,
  fetchCertificatesRelease: vi.fn(),
  fetchChallengeStart: vi.fn(),
  fetchFinalistEmailDetails: vi.fn(),
  fetchGroupExtensions: vi.fn(),
  fetchRegistrationOpen: vi.fn(),
  fetchRelease: vi.fn(),
  fetchSubmissionDeadline: vi.fn()
}))
const certsMock = vi.mocked(fetchCertificatesRelease)
const finalistsMock = vi.mocked(fetchFinalists)
const extensionsMock = vi.mocked(fetchGroupExtensions)
const marksMock = vi.mocked(fetchRelease)
const deadlineMock = vi.mocked(fetchSubmissionDeadline)
const registrationMock = vi.mocked(fetchRegistrationOpen)
const challengeStartMock = vi.mocked(fetchChallengeStart)
const symposiumMock = vi.mocked(fetchFinalistEmailDetails)

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
  id: 1, group_id: 7, group_name: 'BTF-1', extended_until: until, added: null, grace_hours: 0,
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
  registrationMock.mockReset().mockResolvedValue({
    open_now: false, opens_at: '2026-03-01T00:00:00Z', closes_at: '2026-06-30T13:59:00Z'
  })
  challengeStartMock.mockReset().mockResolvedValue({
    year: 2026, starts_on: '2026-07-27', set_by: 'Ada Admin', updated_at: null
  })
  // Only the Symposium's date is read from the finalist email's details.
  symposiumMock.mockReset().mockResolvedValue({ symposium_date: '2026-11-20' } as never)
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

  it('lists the year in order, registration to certificates', async () => {
    const wrapper = await mountPage()
    expect(wrapper.findAll('.year__fact-label').map((label) => label.text())).toEqual([
      'Registration start',
      'Registration close',
      'Challenge start',
      'Submission deadline',
      'Last extension',
      'Marks',
      'Notify finalists',
      'Symposium date',
      'Certificates',
    ])
    expect(fact(wrapper, 'Registration start').text()).toContain(formatStatementTime('2026-03-01T00:00:00Z'))
    expect(fact(wrapper, 'Registration close').text()).toContain(formatStatementTime('2026-06-30T13:59:00Z'))
    expect(fact(wrapper, 'Challenge start').text()).toContain('27/07/2026')
    expect(fact(wrapper, 'Symposium date').text()).toContain('20/11/2026')
  })

  it('says a date is not set until it is', async () => {
    registrationMock.mockResolvedValue({ open_now: true, opens_at: null, closes_at: null })
    challengeStartMock.mockResolvedValue({ year: 2026, starts_on: null, set_by: '', updated_at: null })
    symposiumMock.mockRejectedValue(new Error('down'))
    const wrapper = await mountPage()
    for (const label of ['Registration start', 'Registration close', 'Challenge start', 'Symposium date'])
      expect(fact(wrapper, label).text()).toContain('not set')
  })

  it('reports the furthest extension as the real end of the window', async () => {
    const wrapper = await mountPage()
    expect(fact(wrapper, 'Last extension').text()).toContain(formatStatementTime('2026-11-08T00:00:00Z'))
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
