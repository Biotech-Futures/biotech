import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  buildAdminQuery,
  fetchAdminSummary,
  fetchAdminUsers,
  deleteAdminUser,
  bulkSetUsersActive,
  bulkDeleteUsers,
  fetchAdminGroupList,
  fetchNextGroupName,
  createGroup,
  updateGroup,
  fetchGroupMessages,
  removeGroupMessage,
  removeGroupMember,
  bulkDeleteGroups,
  replaceMentor
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

  it('serializes the status filter as active=true / active=false', async () => {
    const payload = {
      msg: 'Users retrieved successfully',
      data: { items: [], total: 0, page: 1, limit: 25, hasMore: false }
    }
    const fetchMock = vi
      .fn()
      .mockImplementation(() =>
        Promise.resolve(new Response(JSON.stringify(payload), { status: 200 }))
      )
    vi.stubGlobal('fetch', fetchMock)

    await fetchAdminUsers({ active: true })
    await fetchAdminUsers({ active: false })
    await fetchAdminUsers({ active: undefined })

    const urls = fetchMock.mock.calls.map(([url]) => String(url))
    expect(urls[0]).toContain('active=true')
    expect(urls[1]).toContain('active=false')
    expect(urls[2]).not.toContain('active')
  })
})

describe('bulk user actions', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('deleteAdminUser sends optional force body', async () => {
    const fetchMock = vi
      .fn()
      .mockImplementation((url: string) => {
        if (String(url).includes('/services/csrf/')) {
          return Promise.resolve(new Response(JSON.stringify({ csrfToken: 'test-token' }), { status: 200 }))
        }
        return Promise.resolve(
          new Response(JSON.stringify({ msg: 'User deleted successfully', data: null }), { status: 200 })
        )
      })
    vi.stubGlobal('fetch', fetchMock)

    await deleteAdminUser(7, true)

    const [, init] = fetchMock.mock.calls.find(([u]) => String(u).includes('/user/7/')) as [string, RequestInit]
    expect(init!.method).toBe('DELETE')
    expect(JSON.parse(String(init.body))).toEqual({ force: true })
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

describe('fetchAdminGroupList', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('unwraps the group list envelope and passes list params', async () => {
    const payload = {
      msg: 'Groups retrieved successfully',
      data: {
        items: [{ id: 1, name: 'BTF1', members: [], mentor: null, createdAt: '2026-01-01T00:00:00Z', updatedAt: '2026-01-01T00:00:00Z' }],
        total: 1,
        page: 1,
        limit: 25,
        has_more: false
      }
    }
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(payload), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    const result = await fetchAdminGroupList({
      page: 1,
      limit: 25,
      searchGroup: 'Team',
      mentorStatus: 'matched',
      sortBy: 'name',
      sortOrder: 'asc'
    })

    const calledUrl = String(fetchMock.mock.calls[0][0])
    expect(calledUrl).toContain('/api/v1/admin/group/')
    expect(calledUrl).toContain('searchGroup=Team')
    expect(calledUrl).toContain('mentorStatus=matched')
    expect(calledUrl).toContain('sortBy=name')
    expect(calledUrl).toContain('sortOrder=asc')
    expect(result).toEqual(payload.data)
    expect(result.total).toBe(1)
  })
})

describe('fetchNextGroupName', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('requests the preview endpoint and resolves the plain name string', async () => {
    const payload = { msg: 'Next group name retrieved successfully', data: { name: 'BTF41' } }
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(payload), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    const result = await fetchNextGroupName()

    expect(String(fetchMock.mock.calls[0][0])).toContain('/api/v1/admin/group/next-name/')
    expect(result).toBe('BTF41')
  })
})

describe('createGroup', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  const fetchMockFor = (data: unknown) =>
    vi.fn().mockImplementation((url: string) => {
      if (String(url).includes('/services/csrf/')) {
        return Promise.resolve(new Response(JSON.stringify({ csrfToken: 'test-token' }), { status: 200 }))
      }
      return Promise.resolve(
        new Response(JSON.stringify({ msg: 'Group created successfully', data }), { status: 201 })
      )
    })

  it('posts the given name and unwraps the created group', async () => {
    const created = { id: 41, name: 'BTF41', members: [], mentor: null, createdAt: '2026-01-01T00:00:00Z', updatedAt: '2026-01-01T00:00:00Z' }
    const fetchMock = fetchMockFor(created)
    vi.stubGlobal('fetch', fetchMock)

    const result = await createGroup('BTF41')

    const [, init] = fetchMock.mock.calls.find(([u]) => String(u).includes('/api/v1/admin/group/')) as [string, RequestInit]
    expect(init!.method).toBe('POST')
    expect(JSON.parse(String(init.body))).toEqual({ name: 'BTF41' })
    expect(result.data).toEqual(created)
  })

  it('omits the name when called with none, letting the backend auto-name it', async () => {
    const created = { id: 42, name: 'BTF42', members: [], mentor: null, createdAt: '2026-01-01T00:00:00Z', updatedAt: '2026-01-01T00:00:00Z' }
    const fetchMock = fetchMockFor(created)
    vi.stubGlobal('fetch', fetchMock)

    await createGroup()

    const [, init] = fetchMock.mock.calls.find(([u]) => String(u).includes('/api/v1/admin/group/')) as [string, RequestInit]
    const body = JSON.parse(String(init.body))
    expect(body.name).toBeUndefined()
  })
})

describe('updateGroup', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('PUTs the new name to the given group id', async () => {
    const updated = { id: 1, name: 'Renamed Group', members: [], mentor: null, createdAt: '2026-01-01T00:00:00Z', updatedAt: '2026-01-01T00:00:00Z' }
    const fetchMock = vi.fn().mockImplementation((url: string) => {
      if (String(url).includes('/services/csrf/')) {
        return Promise.resolve(new Response(JSON.stringify({ csrfToken: 'test-token' }), { status: 200 }))
      }
      return Promise.resolve(
        new Response(JSON.stringify({ msg: 'Group updated successfully', data: updated }), { status: 200 })
      )
    })
    vi.stubGlobal('fetch', fetchMock)

    const result = await updateGroup(1, 'Renamed Group')

    const [, init] = fetchMock.mock.calls.find(([u]) => String(u).includes('/group/1/')) as [string, RequestInit]
    expect(init!.method).toBe('PUT')
    expect(JSON.parse(String(init.body))).toEqual({ name: 'Renamed Group' })
    expect(result.data).toEqual(updated)
  })
})

describe('fetchGroupMessages', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('requests the messages endpoint with pagination params and resolves the envelope data', async () => {
    const payload = {
      msg: 'Messages retrieved successfully',
      data: {
        items: [
          {
            id: 'm1',
            group_id: '1',
            sender: { id: '10', name: 'Ada Lovelace', email: 'ada@example.com', role: 'student' },
            message_type: 'text',
            text: 'Hey team, how is everyone?',
            attachments: [],
            gif: null,
            sent_at: '2026-01-05T00:00:00Z',
            edited_at: null
          }
        ],
        total: 1,
        page: 1,
        limit: 50,
        has_more: false
      }
    }
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(payload), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    const result = await fetchGroupMessages(1, { page: 1, limit: 50 })

    const calledUrl = String(fetchMock.mock.calls[0][0])
    expect(calledUrl).toContain('/api/v1/admin/group/1/messages/')
    expect(calledUrl).toContain('page=1')
    expect(calledUrl).toContain('limit=50')
    expect(result).toEqual(payload.data)
  })
})

describe('removeGroupMessage', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('DELETEs the message and resolves the confirmation message', async () => {
    const fetchMock = vi.fn().mockImplementation((url: string) => {
      if (String(url).includes('/services/csrf/')) {
        return Promise.resolve(new Response(JSON.stringify({ csrfToken: 'test-token' }), { status: 200 }))
      }
      return Promise.resolve(
        new Response(
          JSON.stringify({ msg: 'Message removed successfully', data: { id: 'm1', group_id: '1' } }),
          { status: 200 }
        )
      )
    })
    vi.stubGlobal('fetch', fetchMock)

    const result = await removeGroupMessage(1, 'm1')

    const [, init] = fetchMock.mock.calls.find(([u]) => String(u).includes('/group/1/messages/m1/')) as [
      string,
      RequestInit
    ]
    expect(init!.method).toBe('DELETE')
    expect(result).toBe('Message removed successfully')
  })
})

describe('removeGroupMember', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('DELETEs the membership and resolves the confirmation message', async () => {
    const fetchMock = vi.fn().mockImplementation((url: string) => {
      if (String(url).includes('/services/csrf/')) {
        return Promise.resolve(new Response(JSON.stringify({ csrfToken: 'test-token' }), { status: 200 }))
      }
      return Promise.resolve(
        new Response(JSON.stringify({ msg: 'Member removed successfully', data: null }), { status: 200 })
      )
    })
    vi.stubGlobal('fetch', fetchMock)

    const result = await removeGroupMember(1, 10)

    const [, init] = fetchMock.mock.calls.find(([u]) => String(u).includes('/group/1/members/10/')) as [
      string,
      RequestInit
    ]
    expect(init!.method).toBe('DELETE')
    expect(result).toBe('Member removed successfully')
  })
})

describe('bulkDeleteGroups', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  const fetchMockFor = (data: unknown) =>
    vi.fn().mockImplementation((url: string) => {
      if (String(url).includes('/services/csrf/')) {
        return Promise.resolve(new Response(JSON.stringify({ csrfToken: 'test-token' }), { status: 200 }))
      }
      return Promise.resolve(
        new Response(JSON.stringify({ msg: '2 group(s) deleted', data }), { status: 200 })
      )
    })

  it('posts explicit groupIds and force', async () => {
    const fetchMock = fetchMockFor({ deletedIds: [1, 2], failedIds: [], notFoundIds: [] })
    vi.stubGlobal('fetch', fetchMock)

    const result = await bulkDeleteGroups({ groupIds: [1, 2], force: true })

    const [, init] = fetchMock.mock.calls.find(([u]) => String(u).includes('/group/bulk-delete/')) as [
      string,
      RequestInit
    ]
    expect(init!.method).toBe('POST')
    const body = JSON.parse(String(init.body))
    expect(body).toEqual({ groupIds: [1, 2], force: true })
    expect(result.data?.deletedIds).toEqual([1, 2])
  })

  it('sends selectAll, filters, excludeIds, expectedCount and limit, and resolves remaining', async () => {
    const fetchMock = fetchMockFor({
      deletedIds: [3, 4],
      failedIds: [],
      notFoundIds: [],
      remaining: 36
    })
    vi.stubGlobal('fetch', fetchMock)

    const result = await bulkDeleteGroups({
      selectAll: true,
      filters: { searchGroup: 'BTF', mentorStatus: 'unmatched' },
      excludeIds: [1, 2],
      expectedCount: 40,
      force: false,
      limit: 25
    })

    const [, init] = fetchMock.mock.calls.find(([u]) => String(u).includes('/group/bulk-delete/')) as [
      string,
      RequestInit
    ]
    expect(init!.method).toBe('POST')
    const body = JSON.parse(String(init.body))
    expect(body).toEqual({
      selectAll: true,
      filters: { searchGroup: 'BTF', mentorStatus: 'unmatched' },
      excludeIds: [1, 2],
      expectedCount: 40,
      force: false,
      limit: 25
    })
    expect(result.data?.remaining).toBe(36)
  })
})

describe('replaceMentor', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('posts the membership/group/new-mentor triple and resolves the replaced count', async () => {
    const fetchMock = vi.fn().mockImplementation((url: string) => {
      if (String(url).includes('/services/csrf/')) {
        return Promise.resolve(new Response(JSON.stringify({ csrfToken: 'test-token' }), { status: 200 }))
      }
      return Promise.resolve(
        new Response(JSON.stringify({ msg: 'Mentor replaced successfully', data: { replaced: 1 } }), { status: 200 })
      )
    })
    vi.stubGlobal('fetch', fetchMock)

    const result = await replaceMentor({ membershipId: 100, groupId: 1, newMentorUserId: 23 })

    const [, init] = fetchMock.mock.calls.find(([u]) => String(u).includes('/mentor-match/replace/')) as [
      string,
      RequestInit
    ]
    expect(init!.method).toBe('POST')
    expect(JSON.parse(String(init.body))).toEqual({ membershipId: 100, groupId: 1, newMentorUserId: 23 })
    expect(result.replaced).toBe(1)
  })
})
