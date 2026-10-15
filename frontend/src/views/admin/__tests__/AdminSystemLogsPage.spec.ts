import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'

import AdminSystemLogsPage from '@/views/admin/AdminSystemLogsPage.vue'
import { downloadSystemLogs, fetchSystemLog, fetchSystemLogs, type SystemLogRow } from '@/utils/adminAPI'
import { registerProfileTimeZone } from '@/utils/date'

vi.mock('@/utils/adminAPI', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/utils/adminAPI')>()),
  fetchSystemLogs: vi.fn(),
  fetchSystemLog: vi.fn(),
  downloadSystemLogs: vi.fn()
}))

const listMock = vi.mocked(fetchSystemLogs)
const detailMock = vi.mocked(fetchSystemLog)
const downloadMock = vi.mocked(downloadSystemLogs)

const buildRow = (overrides: Partial<SystemLogRow> = {}): SystemLogRow => ({
  id: 1,
  // 9 Oct 2026, 4:12:01 pm in Sydney (AEDT).
  created_at: '2026-10-09T05:12:01Z',
  level: 40,
  level_name: 'ERROR',
  logger_name: 'apps.services.mailer',
  message: 'auth_email.send_failed kind=login error=SMTPServerDisconnected',
  message_truncated: false,
  has_traceback: true,
  request_id: 'rid-1',
  request_method: 'POST',
  request_path: '/services/send-login-code/',
  status_code: null,
  user: { id: 42, email: 'amy@example.com', name: 'Amy Chen' },
  ...overrides
})

const page = (rows: SystemLogRow[], count = rows.length) => ({ count, next: null, previous: null, results: rows })

let wrapper: VueWrapper | undefined

const mountPage = async () => {
  wrapper = mount(AdminSystemLogsPage, { global: { stubs: { Teleport: true } } })
  await flushPromises()
  return wrapper
}

const lastListCall = () => listMock.mock.calls.at(-1)![0]!

const setField = async (selector: string, value: string) => {
  const field = wrapper!.find(selector)
  await field.setValue(value)
  await field.trigger('change')
  await flushPromises()
}

const button = (text: string) => wrapper!.findAll('button').find((item) => item.text().includes(text))!

beforeEach(() => {
  registerProfileTimeZone(() => 'Australia/Sydney')
  listMock.mockResolvedValue(page([buildRow()]))
})

afterEach(() => {
  wrapper?.unmount()
  wrapper = undefined
  registerProfileTimeZone(() => undefined)
  vi.useRealTimers()
  vi.clearAllMocks()
})

describe('AdminSystemLogsPage', () => {
  it('renders the rows with local times and a level badge', async () => {
    listMock.mockResolvedValue(
      page([
        buildRow(),
        buildRow({ id: 2, level_name: 'WARNING', message: 'x'.repeat(300), message_truncated: true, has_traceback: false, user: null, request_path: '' })
      ])
    )
    await mountPage()

    const rows = wrapper!.findAll('tbody tr.data-table-row')
    expect(rows).toHaveLength(2)
    const first = rows[0].text()
    expect(first).toContain('09/10/26 16:12:01') // UTC 05:12:01 shown in Sydney
    expect(rows[0].find('.log-level').text()).toBe('ERROR')
    expect(rows[0].find('.log-level').classes()).toContain('log-level--danger')
    expect(first).toContain('apps.services.mailer')
    expect(first).toContain('Amy Chen')
    expect(first).toContain('POST /services/send-login-code/')
    expect(rows[0].find('time').attributes('datetime')).toBe('2026-10-09T05:12:01Z')

    expect(rows[1].find('.log-level').classes()).toContain('log-level--warning')
    expect(rows[1].text()).toContain('…')
    expect(rows[1].text()).toContain('—')
    expect(wrapper!.text()).toContain('Times are shown in Australia/Sydney; exports use UTC.')
  })

  it('asks for the first page with no filters on opening', async () => {
    await mountPage()

    expect(listMock).toHaveBeenCalledOnce()
    const params = lastListCall()
    expect(params.page).toBe(1)
    expect(params.page_size).toBeGreaterThan(0)
    expect([params.from, params.to, params.level, params.source, params.user, params.q, params.request_id]).toEqual(
      Array(7).fill(undefined)
    )
  })

  it('shows Loading while the rows are on their way', async () => {
    let resolve!: (value: ReturnType<typeof page>) => void
    listMock.mockReturnValue(new Promise((done) => (resolve = done)))
    wrapper = mount(AdminSystemLogsPage, { global: { stubs: { Teleport: true } } })
    await flushPromises()

    expect(wrapper.find('.data-table-empty').text()).toBe('Loading...')

    resolve(page([buildRow()]))
    await flushPromises()
    expect(wrapper.find('.data-table-empty').exists()).toBe(false)
    expect(wrapper.findAll('tbody tr.data-table-row')).toHaveLength(1)
  })

  it('says when nothing has been logged, and when nothing matches the filters', async () => {
    listMock.mockResolvedValue(page([]))
    await mountPage()
    expect(wrapper!.find('.data-table-empty').text()).toBe('No logs have been recorded yet.')

    await setField('#log-level-filter', 'ERROR')
    expect(wrapper!.find('.data-table-empty').text()).toBe('No logs match these filters.')
  })

  it('shows the error when the rows cannot be loaded', async () => {
    listMock.mockRejectedValue(new Error('You do not have admin privileges.'))
    await mountPage()

    expect(wrapper!.find('[role="alert"]').text()).toContain('You do not have admin privileges.')
  })

  it('sends each filter, from page 1', async () => {
    await mountPage()

    await setField('#log-level-filter', 'WARNING')
    expect(lastListCall()).toMatchObject({ level: 'WARNING', page: 1 })

    await setField('#log-source-filter', ' apps.services ')
    expect(lastListCall()).toMatchObject({ level: 'WARNING', source: 'apps.services' })

    await setField('#log-user-filter', 'amy@example.com')
    expect(lastListCall()).toMatchObject({ user: 'amy@example.com' })

    await setField('#log-request-filter', 'rid-1')
    expect(lastListCall()).toMatchObject({ request_id: 'rid-1' })
  })

  it('sends a date range across the 4 October daylight-saving change in the admin’s own timezone', async () => {
    await mountPage()

    await setField('#log-from-filter', '2026-10-01')
    await setField('#log-to-filter', '2026-10-15')

    // Sydney is +10:00 on 1 October and +11:00 by 15 October.
    expect(lastListCall()).toMatchObject({
      from: '2026-10-01T00:00:00.000+10:00',
      to: '2026-10-15T23:59:59.999+11:00'
    })
  })

  it('refuses a "From" date after the "To" date without asking the server', async () => {
    await mountPage()
    await setField('#log-to-filter', '2026-10-01')
    const calls = listMock.mock.calls.length

    await setField('#log-from-filter', '2026-10-15')

    expect(listMock.mock.calls.length).toBe(calls)
    expect(wrapper!.find('[role="alert"]').text()).toContain('The "From" date is after the "To" date.')
    expect(button('Export CSV').attributes('disabled')).toBeDefined()
  })

  it('searches messages once typing stops', async () => {
    await mountPage()
    vi.useFakeTimers()

    await wrapper!.find('input[type="search"]').setValue('smtp')
    expect(listMock).toHaveBeenCalledOnce()

    vi.advanceTimersByTime(350)
    await flushPromises()
    expect(lastListCall()).toMatchObject({ q: 'smtp', page: 1 })
  })

  it('clears every filter at once', async () => {
    await mountPage()
    await setField('#log-level-filter', 'ERROR')

    await button('Clear filters').trigger('click')
    await flushPromises()

    expect(lastListCall().level).toBeUndefined()
    expect(wrapper!.find('#log-level-filter').element).toHaveProperty('value', '')
    expect(button('Clear filters')).toBeUndefined()
  })

  it('loads the full message and traceback when a row is expanded', async () => {
    let resolveDetail!: (value: Awaited<ReturnType<typeof fetchSystemLog>>) => void
    detailMock.mockReturnValue(new Promise((done) => (resolveDetail = done)))
    await mountPage()
    expect(detailMock).not.toHaveBeenCalled()

    await wrapper!.find('.data-table-expand-btn').trigger('click')
    await flushPromises()

    expect(detailMock).toHaveBeenCalledWith(1)
    expect(wrapper!.find('.data-table-detail-row').text()).toContain('Loading details...')

    resolveDetail({
      ...buildRow(),
      message: 'the whole message',
      traceback: 'Traceback (most recent call last):\nSMTPServerDisconnected',
      module: 'mailer',
      func_name: '_send_in_pool',
      line_no: 58,
      extra: { kind: 'login' }
    })
    await flushPromises()

    const detail = wrapper!.find('.data-table-detail-row').text()
    expect(detail).toContain('the whole message')
    expect(detail).toContain('SMTPServerDisconnected')
    expect(detail).toContain('apps.services.mailer (mailer._send_in_pool:58)')
    expect(detail).toContain('Amy Chen (amy@example.com)')
    expect(detail).toContain('kind')
  })

  it('offers to try again when the details cannot be loaded', async () => {
    detailMock.mockRejectedValueOnce(new Error('Not found.')).mockResolvedValueOnce({
      ...buildRow(),
      traceback: '',
      module: '',
      func_name: '',
      line_no: null,
      extra: {}
    })
    await mountPage()
    await wrapper!.find('.data-table-expand-btn').trigger('click')
    await flushPromises()
    expect(wrapper!.find('.data-table-detail-row').text()).toContain('Not found.')

    await button('Try again').trigger('click')
    await flushPromises()
    expect(detailMock).toHaveBeenCalledTimes(2)
    expect(wrapper!.find('.data-table-detail-row').text()).toContain('Message')
  })

  it('exports the current filters, showing that it is busy until the file is ready', async () => {
    let finish!: () => void
    downloadMock.mockReturnValue(new Promise<void>((done) => (finish = done)))
    await mountPage()
    await setField('#log-level-filter', 'ERROR')

    await button('Export CSV').trigger('click')
    await flushPromises()

    expect(downloadMock).toHaveBeenCalledWith(expect.objectContaining({ level: 'ERROR' }), 'csv')
    expect(button('Exporting...').attributes('aria-busy')).toBe('true')
    expect(button('Export JSON').attributes('disabled')).toBeDefined()

    finish()
    await flushPromises()
    expect(button('Export CSV').attributes('disabled')).toBeUndefined()
  })

  it('exports JSON and shows an export that failed', async () => {
    downloadMock.mockRejectedValue(new Error('Could not export the system logs.'))
    await mountPage()

    await button('Export JSON').trigger('click')
    await flushPromises()

    expect(downloadMock).toHaveBeenCalledWith(expect.anything(), 'json')
    expect(wrapper!.find('[role="alert"]').text()).toContain('Could not export the system logs.')
  })
})
