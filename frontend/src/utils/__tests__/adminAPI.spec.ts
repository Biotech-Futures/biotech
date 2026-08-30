import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  buildAdminQuery,
  fetchAdminSummary,
  fetchAdminUsers,
  bulkSetUsersActive,
  bulkDeleteUsers
} from '@/utils/adminAPI'

describe('buildAdminQuery', () => {
  it('serializes params and skips empties', () => {
    const qs = buildAdminQuery({ page: 2, search: '  ', role: 'admin' })
    expect(qs).toContain('page=2')
    expect(qs).toContain('role=admin')
    expect(qs).not.toContain('search')
  })

  it('joins array values with commas', () => {
    const qs = buildAdminQuery({ role: ['admin', 'mentor'] })
    expect(qs).toBe('?role=admin%2Cmentor')
  })

  it('returns empty string when nothing to serialize', () => {
    expect(buildAdminQuery({ search: '', page: undefined })).toBe('')
  })
})

describe('fetchAdminSummary', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('requests the admin summary endpoint and resolves its JSON', async () => {
    const payload = { active_users: 5, upcoming_events: 3 }
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(payload), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    const result = await fetchAdminSummary()

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/admin/summary/'),
      expect.objectContaining({ credentials: 'include' })
    )
    expect(result).toEqual(payload)
  })

  it('rejects with an ApiError on a failed response', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('boom', { status: 500 })))

    const error = await fetchAdminSummary().catch((e) => e)
    expect(error).toBeInstanceOf(Error)
    expect((error as { message?: string }).message).toBeTruthy()
  })
})

describe('fetchAdminUsers', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('unwraps the custom list envelope and passes limit/sortBy/sortOrder', async () => {
    const payload = {
      msg: 'Users retrieved successfully',
      data: { items: [{ id: 1, firstName: 'Ada' }], total: 1, page: 1, limit: 25, hasMore: false }
    }
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify(payload), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    const result = await fetchAdminUsers({
      page: 1,
      limit: 25,
      search: 'ada',
      role: 'supervisor',
      sortBy: 'name',
      sortOrder: 'asc'
    })

    const calledUrl = String(fetchMock.mock.calls[0][0])
    expect(calledUrl).toContain('/api/v1/admin/user/')
    expect(calledUrl).toContain('limit=25')
    expect(calledUrl).toContain('sortBy=name')
    expect(calledUrl).toContain('sortOrder=asc')
    expect(calledUrl).toContain('role=supervisor')
    expect(result).toEqual(payload.data)
    expect(result.total).toBe(1)
  })
})

describe('bulk user actions', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('bulkSetUsersActive posts the exact status body', async () => {
    const fetchMock = vi
      .fn()
      .mockImplementation((url: string) => {
        if (String(url).includes('/services/csrf/')) {
          return Promise.resolve(new Response(JSON.stringify({ csrfToken: 'test-token' }), { status: 200 }))
        }
        return Promise.resolve(
          new Response(
            JSON.stringify({
              msg: '2 user(s) activated',
              data: { updatedIds: [1, 2], unchangedIds: [], notFoundIds: [], skippedSelf: false }
            }),
            { status: 200 }
          )
        )
      })
    vi.stubGlobal('fetch', fetchMock)

    const result = await bulkSetUsersActive({
      isActive: true,
      userIds: [1, 2]
    })

    const [, init] = fetchMock.mock.calls.find(([u]) => String(u).includes('/bulk-status/')) as [string, RequestInit]
    expect(init!.method).toBe('PATCH')
    expect(JSON.parse(String(init.body))).toEqual({ isActive: true, userIds: [1, 2] })
    expect(result.msg).toContain('activated')
    expect(result.data.updatedIds).toEqual([1, 2])
  })

  it('bulkDeleteUsers sends selectAll filters and expectedCount', async () => {
    const fetchMock = vi
      .fn()
      .mockImplementation((url: string) => {
        if (String(url).includes('/services/csrf/')) {
          return Promise.resolve(new Response(JSON.stringify({ csrfToken: 'test-token' }), { status: 200 }))
        }
        return Promise.resolve(
          new Response(
            JSON.stringify({
              msg: '2 user(s) deleted',
              data: { deletedIds: [1, 2], failedIds: [], notFoundIds: [], skippedSelf: false, skippedAdmins: 0 }
            }),
            { status: 200 }
          )
        )
      })
    vi.stubGlobal('fetch', fetchMock)

    await bulkDeleteUsers({
      userIds: [],
      force: true,
      selectAll: true,
      filters: { search: 'ada', role: 'student' },
      excludeIds: [3],
      expectedCount: 2
    })

    const [, init] = fetchMock.mock.calls.find(([u]) => String(u).includes('/bulk-delete/')) as [string, RequestInit]
    expect(init!.method).toBe('POST')
    const body = JSON.parse(String(init.body))
    expect(body.force).toBe(true)
    expect(body.selectAll).toBe(true)
    expect(body.expectedCount).toBe(2)
    expect(body.filters).toEqual({ search: 'ada', role: 'student' })
    expect(body.excludeIds).toEqual([3])
  })
})
