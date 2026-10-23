import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '@/utils/apiError'
import { ensureCsrfCookie } from '@/utils/csrf'
import {
  addSupervisedGroupMembers,
  createAllWaitingGroups,
  createSupervisedGroup,
  deleteSupervisedGroup,
  fetchAvailableMentors,
  fetchInterestCatalog,
  fetchSupervisedGroups,
  personName,
  removeSupervisedGroupMembers,
  renameSupervisedGroup,
  saveSupervisedGroupOrder,
  updateSupervisedGroup,
} from '@/utils/supervisedGroups'

// The CSRF layer is mocked so writes need no /services/csrf/ round-trip.
vi.mock('@/utils/csrf', () => ({
  ensureCsrfCookie: vi.fn(async () => true),
  buildSessionHeaders: ({ includeCSRF, headers }: { includeCSRF?: boolean; headers?: Record<string, string> }) => ({
    ...(headers || {}),
    ...(includeCSRF ? { 'X-CSRFToken': 'csrf-test' } : {}),
  }),
}))
const csrfMock = vi.mocked(ensureCsrfCookie)

const fetchMock = vi.fn()

const jsonResponse = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })

const lastCall = () => {
  const call = fetchMock.mock.calls.at(-1)!
  return {
    url: String(call[0]),
    init: (call[1] ?? {}) as RequestInit,
    body: call[1]?.body ? JSON.parse(String(call[1].body)) : undefined,
  }
}

const group = { id: 7, group_name: 'BTF07', members: [], interests: ['Space'] }

beforeEach(() => {
  fetchMock.mockReset()
  csrfMock.mockClear()
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('personName', () => {
  it('uses the name, then the email, then a dash', () => {
    expect(personName({ first_name: 'Ava', last_name: 'Nguyen' })).toBe('Ava Nguyen')
    expect(personName({ first_name: ' ', email: 'ava@example.com' })).toBe('ava@example.com')
    expect(personName({})).toBe('—')
  })
})

describe('reads', () => {
  it('lists the groups, giving each its interests even when the reply has none', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse([group, { ...group, id: 8, interests: null }]))
    const groups = await fetchSupervisedGroups()
    expect(groups.map((g) => g.interests)).toEqual([['Space'], []])
    const { url, init } = lastCall()
    expect(url).toMatch(/\/api\/v1\/users\/supervised-groups\/$/)
    expect(init.method).toBe('GET')
    // A read needs no CSRF token, so the cookie isn't fetched for it.
    expect((init.headers as Record<string, string>)['X-CSRFToken']).toBeUndefined()
    expect(csrfMock).not.toHaveBeenCalled()
  })

  it('reads the interest catalogue and the mentors free to join', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ interests: ['Space', 'Water'] }))
    expect(await fetchInterestCatalog()).toEqual(['Space', 'Water'])
    expect(lastCall().url).toContain('/api/v1/users/supervised-groups/interests/')

    const mentors = [{ id: 3, first_name: 'Mo', last_name: 'Lee', email: 'mo@example.com' }]
    fetchMock.mockResolvedValueOnce(jsonResponse(mentors))
    expect(await fetchAvailableMentors()).toEqual(mentors)
    expect(lastCall().url).toContain('/api/v1/users/supervised-groups/mentors/')
  })
})

describe('writes', () => {
  it('creates a group with its interests, sending the CSRF token', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(group))
    expect(await createSupervisedGroup(['Space'])).toEqual(group)
    const { init, body } = lastCall()
    expect(init.method).toBe('POST')
    expect((init.headers as Record<string, string>)['X-CSRFToken']).toBe('csrf-test')
    expect(csrfMock).toHaveBeenCalled()
    expect(body).toEqual({ interests: ['Space'] })
  })

  it('creates a group with no interests by default', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(group))
    await createSupervisedGroup()
    expect(lastCall().body).toEqual({ interests: [] })
  })

  it('updates and renames a group', async () => {
    fetchMock.mockImplementation(async () => jsonResponse(group))
    await updateSupervisedGroup(7, { interests: ['Water'] })
    expect(lastCall()).toMatchObject({ body: { interests: ['Water'] } })
    expect(lastCall().init.method).toBe('PATCH')
    expect(lastCall().url).toContain('/api/v1/users/supervised-groups/7/')

    await renameSupervisedGroup(7, 'Team Rocket')
    expect(lastCall().body).toEqual({ group_name: 'Team Rocket' })
  })

  it('adds students by default, or mentors, and removes members', async () => {
    fetchMock.mockImplementation(async () => jsonResponse(group))
    await addSupervisedGroupMembers(7, [1, 2])
    expect(lastCall().body).toEqual({ user_ids: [1, 2], role: 'student' })
    expect(lastCall().url).toContain('/api/v1/users/supervised-groups/7/members/')

    await addSupervisedGroupMembers(7, [3], 'mentor')
    expect(lastCall().body).toEqual({ user_ids: [3], role: 'mentor' })

    await removeSupervisedGroupMembers(7, [2])
    expect(lastCall().init.method).toBe('DELETE')
    expect(lastCall().body).toEqual({ user_ids: [2] })
  })

  it('saves the order, creates the waiting groups and deletes a group', async () => {
    fetchMock.mockResolvedValueOnce(new Response(null, { status: 204 }))
    await saveSupervisedGroupOrder([8, 7])
    expect(lastCall().init.method).toBe('PUT')
    expect(lastCall().body).toEqual({ group_ids: [8, 7] })
    expect(lastCall().url).toContain('/api/v1/users/supervised-groups/order/')

    fetchMock.mockResolvedValueOnce(jsonResponse([group]))
    expect(await createAllWaitingGroups('members')).toEqual([group])
    expect(lastCall().body).toEqual({ registered_by: 'members' })
    expect(lastCall().url).toContain('/api/v1/users/supervised-groups/place/')

    fetchMock.mockResolvedValueOnce(new Response(null, { status: 204 }))
    await deleteSupervisedGroup(7)
    expect(lastCall().init.method).toBe('DELETE')
    expect(lastCall().url).toContain('/api/v1/users/supervised-groups/7/')
  })

  it('throws the API error whenever the server refuses', async () => {
    fetchMock.mockImplementation(async () => jsonResponse({ detail: 'Not yours.' }, 403))
    await expect(fetchSupervisedGroups()).rejects.toBeInstanceOf(ApiError)
    await expect(createSupervisedGroup()).rejects.toBeInstanceOf(ApiError)
    await expect(updateSupervisedGroup(7, {})).rejects.toBeInstanceOf(ApiError)
    await expect(fetchInterestCatalog()).rejects.toBeInstanceOf(ApiError)
    await expect(addSupervisedGroupMembers(7, [1])).rejects.toBeInstanceOf(ApiError)
    await expect(removeSupervisedGroupMembers(7, [1])).rejects.toBeInstanceOf(ApiError)
    await expect(saveSupervisedGroupOrder([7])).rejects.toBeInstanceOf(ApiError)
    await expect(createAllWaitingGroups('supervisor')).rejects.toBeInstanceOf(ApiError)
    await expect(deleteSupervisedGroup(7)).rejects.toBeInstanceOf(ApiError)
    await expect(fetchAvailableMentors()).rejects.toBeInstanceOf(ApiError)
  })
})
