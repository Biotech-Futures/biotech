import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { downloadSystemLogs, fetchSystemLog, fetchSystemLogs } from '@/utils/adminAPI'

const json = (payload: unknown, status = 200) =>
  new Response(JSON.stringify(payload), { status, headers: { 'Content-Type': 'application/json' } })

const calledUrl = (fetchMock: ReturnType<typeof vi.fn>) => new URL(String(fetchMock.mock.calls[0][0]))

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('fetchSystemLogs', () => {
  it('sends the filters and paging, skipping empty ones', async () => {
    const fetchMock = vi.fn().mockResolvedValue(json({ count: 0, next: null, previous: null, results: [] }))
    vi.stubGlobal('fetch', fetchMock)

    await fetchSystemLogs({
      page: 2,
      page_size: 15,
      from: '2026-10-01T00:00:00.000+10:00',
      to: '2026-10-15T23:59:59.999+11:00',
      level: 'ERROR',
      source: '',
      q: 'smtp'
    })

    const url = calledUrl(fetchMock)
    expect(url.pathname).toBe('/api/v1/admin/system-logs/')
    expect(Object.fromEntries(url.searchParams)).toEqual({
      page: '2',
      page_size: '15',
      from: '2026-10-01T00:00:00.000+10:00',
      to: '2026-10-15T23:59:59.999+11:00',
      level: 'ERROR',
      q: 'smtp'
    })
  })

  it('encodes the offset plus sign, which the backend needs as %2B', async () => {
    const fetchMock = vi.fn().mockResolvedValue(json({ count: 0, results: [] }))
    vi.stubGlobal('fetch', fetchMock)

    await fetchSystemLogs({ from: '2026-10-15T00:00:00.000+11:00' })

    expect(String(fetchMock.mock.calls[0][0])).toContain('from=2026-10-15T00%3A00%3A00.000%2B11%3A00')
  })
})

describe('fetchSystemLog', () => {
  it('fetches one row in full', async () => {
    const fetchMock = vi.fn().mockResolvedValue(json({ id: 7, traceback: 'Traceback ...' }))
    vi.stubGlobal('fetch', fetchMock)

    const entry = await fetchSystemLog(7)

    expect(calledUrl(fetchMock).pathname).toBe('/api/v1/admin/system-logs/7/')
    expect(entry.traceback).toBe('Traceback ...')
  })
})

describe('downloadSystemLogs', () => {
  let click: ReturnType<typeof vi.spyOn>

  beforeEach(() => {
    window.URL.createObjectURL = vi.fn(() => 'blob:system-logs')
    window.URL.revokeObjectURL = vi.fn()
    click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
  })

  it('downloads the export with the filters and type, named by the server', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response('Time (UTC),Level\n', {
        status: 200,
        headers: { 'Content-Disposition': 'attachment; filename="system-logs-20261015-101500.csv"' }
      })
    )
    vi.stubGlobal('fetch', fetchMock)
    let savedAs = ''
    click.mockImplementation(function (this: HTMLAnchorElement) {
      savedAs = this.download
    })

    await downloadSystemLogs({ level: 'ERROR', from: '2026-10-01T00:00:00.000+10:00' }, 'csv')

    const url = calledUrl(fetchMock)
    expect(url.pathname).toBe('/api/v1/admin/system-logs/export/')
    expect(Object.fromEntries(url.searchParams)).toEqual({
      level: 'ERROR',
      from: '2026-10-01T00:00:00.000+10:00',
      type: 'csv'
    })
    expect(fetchMock.mock.calls[0][1]).toMatchObject({ credentials: 'include' })
    expect(click).toHaveBeenCalledOnce()
    expect(savedAs).toBe('system-logs-20261015-101500.csv')
    expect(window.URL.revokeObjectURL).toHaveBeenCalledWith('blob:system-logs')
  })

  it('names a JSON export .jsonl when the server gives no name', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{}\n', { status: 200 })))
    let savedAs = ''
    click.mockImplementation(function (this: HTMLAnchorElement) {
      savedAs = this.download
    })

    await downloadSystemLogs({}, 'json')

    expect(savedAs).toBe('system-logs.jsonl')
  })

  it('throws the server error and saves nothing when the export fails', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json({ error: 'Use csv or json.' }, 400)))

    await expect(downloadSystemLogs({}, 'csv')).rejects.toThrow()
    expect(click).not.toHaveBeenCalled()
  })
})
