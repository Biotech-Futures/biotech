import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  buildAdminQuery,
  fetchAdminSummary,
  fetchAdminUsers,
  importAdminMentors,
  importAdminStudents,
  fetchAdminTasks,
  createAdminTask,
  updateAdminTask,
  deleteAdminTask,
  fetchTaskRoleRecipients,
  deleteAdminUser,
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

  it('importAdminStudents posts parsed student rows and unwraps the result envelope', async () => {
    const rows = [
      {
        firstName: 'Ada',
        lastName: 'Lovelace',
        email: 'ada.lovelace@example.edu',
        country: 'Australia',
        state: 'NSW',
        schoolName: 'Sydney Girls High School',
        yearLevel: 11,
        interests: ['Genetics', 'Bioinformatics'],
        guardianFirstName: 'Anne',
        guardianLastName: 'Lovelace',
        guardianEmail: 'anne.lovelace@example.com',
        supervisorFirstName: 'Mary',
        supervisorLastName: 'Somerville',
        supervisorEmail: 'm.somerville@example.edu',
        joinpermResponseId: 'R_1a2b3c4d5e6f7g8',
        active: true,
        groupNumber: '1'
      }
    ]
    const payload = {
      msg: 'Bulk import complete: 1 created, 1 skipped, 1 co-registration group created',
      data: {
        created: [{ id: 1, firstName: 'Ada', lastName: 'Lovelace', email: 'ada.lovelace@example.edu' }],
        skipped: [{ email: 'existing@example.edu', reason: 'Email already exists' }],
        coRegistration: {
          groupsCreated: [{ name: 'BTF1', memberCount: 2 }],
          warnings: ['BTF1 has 6 members']
        }
      }
    }
    const fetchMock = vi
      .fn()
      .mockImplementation((url: string) => {
        if (String(url).includes('/services/csrf/')) {
          return Promise.resolve(new Response(JSON.stringify({ csrfToken: 'test-token' }), { status: 200 }))
        }
        return Promise.resolve(
          new Response(JSON.stringify(payload), {
            status: 201,
            headers: { 'Content-Type': 'application/json' }
          })
        )
      })
    vi.stubGlobal('fetch', fetchMock)

    const result = await importAdminStudents(rows)

    const [, init] = fetchMock.mock.calls.find(([u]) => String(u).includes('/user/bulk/')) as [string, RequestInit]
    expect(init!.method).toBe('POST')
    expect(JSON.parse(String(init.body))).toEqual(rows)
    expect(result).toEqual(payload)
    expect(result.data.created).toHaveLength(1)
    expect(result.data.skipped[0]).toEqual({
      email: 'existing@example.edu',
      reason: 'Email already exists'
    })
    expect(result.data.coRegistration?.groupsCreated[0]).toEqual({
      name: 'BTF1',
      memberCount: 2
    })
  })

  it('importAdminMentors posts parsed mentor rows as mentor users and unwraps the result envelope', async () => {
    const rows = [
      {
        firstName: 'Mary',
        lastName: 'Somerville',
        email: 'mary@example.edu',
        country: 'Australia',
        state: 'NSW',
        interests: ['Genetics', 'Bioinformatics'],
        mentorReason: 'I want to support students exploring biotech careers.',
        mentorInstitution: 'University of Sydney',
        mentorBackground: 'postgraduate',
        mentorMaxGroupCount: 2
      }
    ]
    const payload = {
      msg: 'Bulk import complete: 1 created, 1 skipped',
      data: {
        created: [{ id: 1, firstName: 'Mary', lastName: 'Somerville', email: 'mary@example.edu' }],
        skipped: [{ email: 'existing@example.edu', reason: 'Email already exists' }]
      }
    }
    const fetchMock = vi
      .fn()
      .mockImplementation((url: string) => {
        if (String(url).includes('/services/csrf/')) {
          return Promise.resolve(new Response(JSON.stringify({ csrfToken: 'test-token' }), { status: 200 }))
        }
        return Promise.resolve(
          new Response(JSON.stringify(payload), {
            status: 201,
            headers: { 'Content-Type': 'application/json' }
          })
        )
      })
    vi.stubGlobal('fetch', fetchMock)

    const result = await importAdminMentors(rows)

    const [, init] = fetchMock.mock.calls.find(([u]) => String(u).includes('/user/bulk/')) as [string, RequestInit]
    expect(init!.method).toBe('POST')
    expect(JSON.parse(String(init.body))).toEqual([
      {
        firstName: 'Mary',
        lastName: 'Somerville',
        email: 'mary@example.edu',
        role: 'mentor',
        state: 'NSW',
        country: 'Australia',
        interests: ['Genetics', 'Bioinformatics'],
        mentorReason: 'I want to support students exploring biotech careers.',
        mentorInstitution: 'University of Sydney',
        mentorBackground: 'postgraduate',
        mentorMaxGroupCount: 2,
        active: true
      }
    ])
    expect(result).toEqual(payload)
    expect(result.data.created).toHaveLength(1)
    expect(result.data.skipped[0]).toEqual({
      email: 'existing@example.edu',
      reason: 'Email already exists'
    })
  })
})

describe('admin task actions', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  const task = {
    id: 7,
    name: 'Submit reflection',
    description: 'Write a short update',
    due_date: '2026-09-15T00:00:00+00:00',
    status: 'todo',
    completed: false,
    parent: null,
    task_type: 'individual',
    group: null,
    assigned_user: 12,
    created_by: { id: 1, name: 'Admin User' },
    creator_role: 'global_admin',
    deleted_at: null,
    created_at: '2026-09-01T00:00:00+00:00',
    updated_at: '2026-09-01T00:00:00+00:00'
  }

  const mockTaskFetch = (payload: unknown, status = 200) =>
    vi.fn().mockImplementation((url: string) => {
      if (String(url).includes('/services/csrf/')) {
        return Promise.resolve(new Response(JSON.stringify({ csrfToken: 'test-token' }), { status: 200 }))
      }
      return Promise.resolve(
        new Response(status === 204 ? null : JSON.stringify(payload), {
          status,
          headers: { 'Content-Type': 'application/json' }
        })
      )
    })

  it('fetchAdminTasks unwraps the list envelope and passes pagination, filter, and sort params', async () => {
    const payload = {
      msg: 'Tasks retrieved successfully',
      data: { items: [task], total: 1, page: 2, limit: 25, has_more: false }
    }
    const fetchMock = mockTaskFetch(payload)
    vi.stubGlobal('fetch', fetchMock)

    const result = await fetchAdminTasks({
      page: 2,
      limit: 25,
      task_type: 'individual',
      sortBy: 'due',
      sortOrder: 'asc'
    })

    const calledUrl = String(fetchMock.mock.calls[0][0])
    expect(calledUrl).toContain('/api/v1/admin/task/')
    const params = new URL(calledUrl).searchParams
    expect(params.get('page')).toBe('2')
    expect(params.get('limit')).toBe('25')
    expect(params.get('task_type')).toBe('individual')
    expect(params.get('sortBy')).toBe('due')
    expect(params.get('sortOrder')).toBe('asc')
    expect(result).toEqual(payload.data)
  })

  it('createAdminTask posts the task payload and returns the response envelope', async () => {
    const payload = { msg: 'Task created successfully', data: task }
    const fetchMock = mockTaskFetch(payload, 201)
    vi.stubGlobal('fetch', fetchMock)

    const body = {
      name: 'Submit reflection',
      description: 'Write a short update',
      due_date: '2026-09-15T00:00:00Z',
      status: 'todo' as const,
      parent: null,
      task_type: 'individual' as const,
      group: null,
      assigned_user: 12,
      assigned_role: null
    }
    const result = await createAdminTask(body)

    const [, init] = fetchMock.mock.calls.find(([url]) => String(url).includes('/task/')) as [string, RequestInit]
    expect(init.method).toBe('POST')
    expect(JSON.parse(String(init.body))).toEqual(body)
    expect(result).toEqual(payload)
  })

  it('createAdminTask returns the role fan-out envelope', async () => {
    const payload = {
      msg: "Created 3 tasks for every user with the 'mentor' role",
      data: { created_count: 3, assigned_role: 'mentor' }
    }
    const fetchMock = mockTaskFetch(payload, 201)
    vi.stubGlobal('fetch', fetchMock)

    const result = await createAdminTask({
      name: 'Mentor training',
      task_type: 'individual',
      assigned_user: null,
      assigned_role: 'mentor'
    })

    const [, init] = fetchMock.mock.calls.find(([url]) => String(url).includes('/task/')) as [string, RequestInit]
    expect(init.method).toBe('POST')
    expect(JSON.parse(String(init.body))).toEqual({
      name: 'Mentor training',
      task_type: 'individual',
      assigned_user: null,
      assigned_role: 'mentor'
    })
    expect(result).toEqual(payload)
  })

  it('updateAdminTask patches the task payload and returns the response envelope', async () => {
    const payload = { msg: 'Task updated successfully', data: { ...task, status: 'done', completed: true } }
    const fetchMock = mockTaskFetch(payload)
    vi.stubGlobal('fetch', fetchMock)

    const body = {
      name: 'Updated task',
      description: 'Updated detail',
      due_date: null,
      status: 'done' as const,
      parent: null
    }
    const result = await updateAdminTask(7, body)

    const [, init] = fetchMock.mock.calls.find(([url]) => String(url).includes('/task/7/')) as [string, RequestInit]
    expect(init.method).toBe('PATCH')
    expect(JSON.parse(String(init.body))).toEqual(body)
    expect(result).toEqual(payload)
  })

  it('deleteAdminTask sends DELETE to the task detail endpoint and handles the 204 response', async () => {
    const fetchMock = mockTaskFetch(null, 204)
    vi.stubGlobal('fetch', fetchMock)

    const result = await deleteAdminTask(7)

    const [, init] = fetchMock.mock.calls.find(([url]) => String(url).includes('/task/7/')) as [string, RequestInit]
    expect(init.method).toBe('DELETE')
    expect(result).toBeUndefined()
  })

  it('fetchTaskRoleRecipients passes the role query and returns the response envelope', async () => {
    const payload = {
      msg: 'Recipient count retrieved successfully',
      data: { role: 'mentor', count: 3 }
    }
    const fetchMock = mockTaskFetch(payload)
    vi.stubGlobal('fetch', fetchMock)

    const result = await fetchTaskRoleRecipients('mentor')

    const calledUrl = String(fetchMock.mock.calls[0][0])
    expect(calledUrl).toContain('/api/v1/admin/task/role-recipients/')
    expect(new URL(calledUrl).searchParams.get('role')).toBe('mentor')
    expect(result).toEqual(payload)
  })
})
