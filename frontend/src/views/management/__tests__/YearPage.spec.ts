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
  fetchNewYear,
  fetchRegistrationOpen,
  fetchRelease,
  fetchSubmissionDeadline,
  startNewYear,
  type NewYearState
} from '@/utils/managementAPI'

vi.mock('@/utils/gradingAPI', () => ({
  fetchFinalists: vi.fn()
}))
vi.mock('@/utils/managementAPI', () => ({
  fetchCertificatesRelease: vi.fn(),
  fetchChallengeStart: vi.fn(),
  fetchFinalistEmailDetails: vi.fn(),
  fetchGroupExtensions: vi.fn(),
  fetchNewYear: vi.fn(),
  fetchRegistrationOpen: vi.fn(),
  fetchRelease: vi.fn(),
  fetchSubmissionDeadline: vi.fn(),
  startNewYear: vi.fn()
}))
const certsMock = vi.mocked(fetchCertificatesRelease)
const finalistsMock = vi.mocked(fetchFinalists)
const extensionsMock = vi.mocked(fetchGroupExtensions)
const marksMock = vi.mocked(fetchRelease)
const deadlineMock = vi.mocked(fetchSubmissionDeadline)
const registrationMock = vi.mocked(fetchRegistrationOpen)
const challengeStartMock = vi.mocked(fetchChallengeStart)
const symposiumMock = vi.mocked(fetchFinalistEmailDetails)
const newYearMock = vi.mocked(fetchNewYear)
const startMock = vi.mocked(startNewYear)

const yearState = (over: Partial<NewYearState> = {}): NewYearState => ({
  year: 2026, next_year: 2027, blockers: [], warnings: [], sending: false, started: null, ...over
})

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
  const wrapper = mount(YearPage, { global: { stubs: { teleport: true } } })
  await flushPromises()
  return wrapper
}

const fact = (wrapper: Awaited<ReturnType<typeof mountPage>>, label: string) =>
  wrapper
    .findAll('.year__facts li')
    .find((li) => li.text().includes(label))!

beforeEach(() => {
  newYearMock.mockReset().mockResolvedValue(yearState())
  startMock.mockReset()
  registrationMock.mockReset().mockResolvedValue({
    open_now: false, opens_at: '2026-03-01T00:00:00Z', closes_at: '2026-06-30T13:59:00Z'
  })
  challengeStartMock.mockReset().mockResolvedValue({
    year: 2026, starts_at: new Date(2026, 6, 27, 23, 59).toISOString(), set_by: 'Ada Admin', updated_at: null
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
  it('shows the year the backend says is in progress, not the deadline year', async () => {
    newYearMock.mockResolvedValue(yearState({ year: 2027, next_year: 2028 }))
    const wrapper = await mountPage()
    expect(wrapper.find('.year__value').text()).toBe('2027')
  })

  it('says when and by whom Start new year began it', async () => {
    const startedAt = '2026-09-03T01:00:00Z'
    newYearMock.mockResolvedValue(yearState({
      started: { year: 2026, started_at: startedAt, started_by: 'Ada Admin', counts: {} }
    }))
    const wrapper = await mountPage()
    expect(wrapper.get('[data-test="year-started"]').text()).toBe(
      `Started ${formatStatementTime(startedAt)} by Ada Admin.`
    )
  })

  it('lists the year in order, registration to certificates', async () => {
    const wrapper = await mountPage()
    expect(wrapper.findAll('.year__fact-label').map((label) => label.text())).toEqual([
      'Registration Start',
      'Registration Close',
      'Challenge Start',
      'Submission Deadline',
      'Last Extension',
      'Marks',
      'Notify Finalists',
      'Symposium Date',
      'Certificates',
    ])
    expect(fact(wrapper, 'Registration Start').text()).toContain(formatStatementTime('2026-03-01T00:00:00Z'))
    expect(fact(wrapper, 'Registration Close').text()).toContain(formatStatementTime('2026-06-30T13:59:00Z'))
    expect(fact(wrapper, 'Challenge Start').text()).toContain('27/07/2026')
    expect(fact(wrapper, 'Symposium Date').text()).toContain('20/11/2026')
  })

  it('says a date is not set until it is', async () => {
    registrationMock.mockResolvedValue({ open_now: true, opens_at: null, closes_at: null })
    challengeStartMock.mockResolvedValue({ year: 2026, starts_at: null, set_by: '', updated_at: null })
    symposiumMock.mockRejectedValue(new Error('down'))
    const wrapper = await mountPage()
    for (const label of ['Registration Start', 'Registration Close', 'Challenge Start', 'Symposium Date'])
      expect(fact(wrapper, label).text()).toContain('not set')
  })

  it('reports the furthest extension as the real end of the window', async () => {
    const wrapper = await mountPage()
    expect(fact(wrapper, 'Last Extension').text()).toContain(formatStatementTime('2026-11-08T00:00:00Z'))
  })

  it('shows each release gate in its own state', async () => {
    const wrapper = await mountPage()
    expect(fact(wrapper, 'Marks').text()).toContain('released')
    expect(fact(wrapper, 'Certificates').text()).toContain('not released')
  })

  it('counts notified finalists, and says so when there are none', async () => {
    const wrapper = await mountPage()
    expect(fact(wrapper, 'Notify Finalists').text()).toContain('1 of 2 notified')

    finalistsMock.mockResolvedValue({ finalists: [] })
    const empty = await mountPage()
    expect(fact(empty, 'Notify Finalists').text()).toContain('no finalists')
  })

  it('keeps rendering when every lookup fails — best effort, never blank', async () => {
    deadlineMock.mockRejectedValue(new Error('down'))
    marksMock.mockRejectedValue(new Error('down'))
    certsMock.mockRejectedValue(new Error('down'))
    extensionsMock.mockRejectedValue(new Error('down'))
    finalistsMock.mockRejectedValue(new Error('down'))
    const wrapper = await mountPage()
    expect(fact(wrapper, 'Submission Deadline').text()).toContain('not set')
    expect(fact(wrapper, 'Last Extension').text()).toContain('none granted')
    expect(fact(wrapper, 'Marks').text()).toContain('not released')
  })

})

describe('Start new year', () => {
  const button = (wrapper: Awaited<ReturnType<typeof mountPage>>) => wrapper.get('[data-test="start-new-year"]')
  // Looked up again each time: the dialog's footer is drawn afresh as it changes.
  const confirmButton = (wrapper: Awaited<ReturnType<typeof mountPage>>) =>
    wrapper.get('.admin-modal--confirm').findAll('button').find((b) => b.text() === 'Start new year')!

  it('stays off while something stops it, and says what', async () => {
    newYearMock.mockResolvedValue(yearState({ blockers: ['2027 can be started from 1 September 2026.'] }))
    const wrapper = await mountPage()
    expect(button(wrapper).attributes('disabled')).toBeDefined()
    expect(wrapper.get('[data-test="year-blockers"]').text()).toContain('from 1 September 2026')
  })

  it('checks again while an email is sending, and comes on once it has finished', async () => {
    vi.useFakeTimers()
    try {
      newYearMock
        .mockResolvedValueOnce(yearState({ sending: true, blockers: ['An email is sending or waiting to send.'] }))
        .mockResolvedValue(yearState())
      const wrapper = await mountPage()
      expect(button(wrapper).attributes('disabled')).toBeDefined()

      await vi.advanceTimersByTimeAsync(15000)
      await flushPromises()

      expect(newYearMock).toHaveBeenCalledTimes(2)
      expect(button(wrapper).attributes('disabled')).toBeUndefined()
      // Nothing sending, so it stops checking.
      await vi.advanceTimersByTimeAsync(15000)
      expect(newYearMock).toHaveBeenCalledTimes(2)
    } finally {
      vi.useRealTimers()
    }
  })

  it('shows what is worth knowing first without stopping it', async () => {
    newYearMock.mockResolvedValue(yearState({ warnings: ["Marks haven't been released."] }))
    const wrapper = await mountPage()
    expect(wrapper.get('[data-test="year-warnings"]').text()).toContain("Marks haven't been released.")
    expect(button(wrapper).attributes('disabled')).toBeUndefined()
  })

  it('starts only once the next year is typed, then says what it changed', async () => {
    startMock.mockResolvedValue(yearState({
      year: 2027,
      next_year: 2028,
      started: {
        year: 2027, started_at: '2026-09-03T01:00:00Z', started_by: 'Ada Admin',
        counts: {
          accounts: 412, groups: 1, tasks: 5, role_tasks: 2, events: 3, announcements: 9, resources: 4,
          extensions: 0, late_links: 2
        }
      }
    }))
    const wrapper = await mountPage()
    await button(wrapper).trigger('click')
    expect(wrapper.get('.admin-modal--confirm').text()).toContain('Start 2027?')
    expect(confirmButton(wrapper).attributes('disabled')).toBeDefined()

    await wrapper.get('#new-year-confirm').setValue('2027')
    expect(confirmButton(wrapper).attributes('disabled')).toBeUndefined()
    await confirmButton(wrapper).trigger('click')
    await flushPromises()

    expect(startMock).toHaveBeenCalledWith('2027')
    expect(wrapper.find('.year__value').text()).toBe('2027')
    const done = wrapper.get('[data-test="year-done"]').text()
    expect(done).toContain('2027 has started.')
    expect(done).toContain('412 accounts deactivated and signed out')
    expect(done).toContain('1 group archived')
    expect(done).toContain('2 role tasks archived')
    expect(done).toContain('0 extensions revoked')
    // The facts are read again for the new year.
    expect(deadlineMock).toHaveBeenCalledTimes(2)
  })

  it('says why when it could not start', async () => {
    startMock.mockRejectedValue(new Error('Submissions are still open.'))
    const wrapper = await mountPage()
    await button(wrapper).trigger('click')
    await wrapper.get('#new-year-confirm').setValue('2027')
    await confirmButton(wrapper).trigger('click')
    await flushPromises()
    expect(wrapper.get('.year__error').text()).toContain('Submissions are still open.')
    expect(wrapper.find('[data-test="year-done"]').exists()).toBe(false)
  })
})
